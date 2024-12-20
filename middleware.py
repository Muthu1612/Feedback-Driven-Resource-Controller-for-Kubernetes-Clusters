from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from kubernetes import client, config
import re
import subprocess
import json
import logging
import datetime

# Loading Kube config
config.load_kube_config()

# Initializations
app = FastAPI()

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def get_node_capacity(node_name: str):
    command = ["kubectl", "get", "node", node_name, "-o", "json"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        node_info = json.loads(result.stdout)
        cpu_capacity_cores = int(node_info["status"]["capacity"]["cpu"])
        logging.info(f"CPU capacity for node {node_name} : {cpu_capacity_cores}")
        return cpu_capacity_cores * 1e9
    else:
        logging.error(f"Failed to retrieve node capacity for {node_name}: {result.stderr}")
        return None

def parse_input(input_str: str):
    args = re.findall(r"--([a-zA-Z-]+)\s+([^\s]+)", input_str)
    args = {arg[0]: arg[1] for arg in args}
    logging.debug(f"Parsed input arguments: {args}")
    return args


def start_new_pod(args: dict, pod_name: str, node_name: str):
    unique_suffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    new_pod_name = f"stress-ng-pod-{unique_suffix}-{pod_name}"
    stress_values = ["stress-ng"]

    if "cpu" in args:
        stress_values.extend(["--cpu", args["cpu"]])
    if "io" in args:
        stress_values.extend(["--io", args["io"]])
    if "vm" in args:
        stress_values.extend(["--vm", args["vm"], "--vm-bytes", args.get("vm-bytes", "1G")])
    stress_values.append("--timeout")
    stress_values.append(args["timeout"])

    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": new_pod_name},
        "spec": {
            "nodeName": node_name,
            "tolerations": [
                {
                    "key": "node-role.kubernetes.io/control-plane",
                    "operator": "Exists",
                    "effect": "NoSchedule",
                }
            ],
            "containers": [
                {
                    "name": "stress-ng-container",
                    "image": "polinux/stress-ng:latest",
                    "args": stress_values,
                }
            ],
            "restartPolicy": "Never",
        },
    }

    api_instance = client.CoreV1Api()
    try:
        api_response = api_instance.create_namespaced_pod(namespace="default", body=pod_manifest)
        logging.info(f"Pod {new_pod_name} successfully created with status: {api_response.status}")
        return {"success": True, "msg": f"Pod {new_pod_name} created."}
    except client.ApiException as e:
        logging.error(f"Error while creating pod {new_pod_name}: {e}")
        return {"success": False, "msg": str(e)}


@app.get("/cpu")
async def get_cpu():
    usage = {}
    api = client.CustomObjectsApi()
    k8s_nodes = api.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
    for stats in k8s_nodes["items"]:
        node_name = stats["metadata"]["name"]
        cpu_usage_nanoseconds = int(stats["usage"]["cpu"].rstrip("n"))
        cpu_capacity_nanocores = get_node_capacity(node_name)
        if cpu_capacity_nanocores:
            usage[node_name] = (cpu_usage_nanoseconds / cpu_capacity_nanocores) * 100
    return usage


@app.post("/pod")
async def handle_post(request: Request):
    data = await request.json()
    job_desc = data.get("job")
    pod_name = data.get("name")
    node_name = data.get("node")
    args = parse_input(job_desc)
    response = start_new_pod(args, pod_name, node_name)
    return JSONResponse(content=response)


@app.get("/nodes")
async def get_nodes():
    api_instance = client.CoreV1Api()
    try:
        nodes_all = api_instance.list_node()
        nodes_list = [node.metadata.name for node in nodes_all.items]
        logging.info(f"Retrieved nodes: {nodes_list}")
        return {"success": True, "nodes": nodes_list}
    except Exception as e:
        logging.error(f"Error retrieving nodes: {e}")
        raise HTTPException(status_code=500, detail="Error while retrieving nodes.")


@app.post("/pod-num")
async def get_pod_num(request: Request):
    data = await request.json()
    node_name = data.get("node")
    api_instance = client.CoreV1Api()

    try:
        # Delete completed/failed pods
        deleted_pods = delete_pods()
        # Count pods on the node
        field_selector = f"spec.nodeName={node_name}"
        pod_list = api_instance.list_namespaced_pod(namespace="default", field_selector=field_selector)
        pod_count = len(pod_list.items)
        logging.info(f"Total pods on node {node_name}: {pod_count}")
        return {"pod_num": pod_count, "deleted_pods": deleted_pods}
    except Exception as e:
        logging.error(f"Error in get_pod_num: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/delete-node")
async def delete_node(request: Request):
    data = await request.json()
    node_name = data.get("node")
    api_instance = client.CoreV1Api()

    try:
        # Evict pods before deleting the node
        evict_pods(node_name, api_instance)

        # Delete the node
        api_instance.delete_node(node_name)
        logging.info(f"Deleted node: {node_name}")
        return {"success": True, "msg": f"Node {node_name} deleted."}
    except Exception as e:
        logging.error(f"Error deleting node {node_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/start-node")
async def start_node(request: Request):
    data = await request.json()
    node_name = data.get("node")
    api_instance = client.CoreV1Api()
    metadata = client.V1ObjectMeta(name=node_name)
    node_spec = client.V1NodeSpec()
    node = client.V1Node(metadata=metadata, spec=node_spec)

    try:
        # Create the node
        if node_name!="node0":
            api_instance.create_node(node)
            logging.info(f"Started node: {node_name}")
            return {"success": True, "msg": f"Node {node_name} started."}
        else:
            return {"success": True, "msg": f"Node {node_name} is master node."}
    except Exception as e:
        logging.error(f"Error starting node {node_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/delete-pods")
def delete_pods():
    """
    Deletes completed or failed pods in the "default" namespace.
    """
    api_instance = client.CoreV1Api()
    try:
        pod_list = api_instance.list_namespaced_pod("default")
        deleted_pod_names = []
        for pod in pod_list.items:
            if pod.status.phase in ["Succeeded", "Failed"]:
                api_instance.delete_namespaced_pod(pod.metadata.name, "default")
                deleted_pod_names.append(pod.metadata.name)
        logging.info(f"Deleted pods: {deleted_pod_names}")
        return {"success": True, "deleted_pods": deleted_pod_names}
    except Exception as e:
        logging.error(f"Error deleting pods: {e}")
        raise HTTPException(status_code=500, detail=str(e))



def evict_pods(node_name: str, api_instance):
    pods = api_instance.list_namespaced_pod("default")
    pods_on_node = [pod for pod in pods.items if pod.spec.node_name == node_name]

    for pod in pods_on_node:
        try:
            api_instance.delete_namespaced_pod(name=pod.metadata.name, namespace=pod.metadata.namespace)
            logging.info(f"Evicted pod {pod.metadata.name} from node {node_name}")
        except Exception as e:
            logging.error(f"Error evicting pod {pod.metadata.name}: {e}")


# Main entry point to run the application
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
