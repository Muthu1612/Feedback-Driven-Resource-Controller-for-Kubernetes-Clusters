import subprocess
import time
import json


sampling_rate = 1

def get_node_capacity(node_name):
    # Command to get node capacity
    command = ['kubectl', 'get', 'node', node_name, '-o', 'json']
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        node_info = json.loads(result.stdout)
        cpu_capacity_str = node_info['status']['capacity']['cpu']
        if cpu_capacity_str.endswith("m"):
            cpu_capacity_nanocores = int(cpu_capacity_str[:-1]) * 1e6
        else:
            cpu_capacity_nanocores = int(cpu_capacity_str) * 1e9
        return cpu_capacity_nanocores
    else:
        print(f"Error getting node capacity: {result.stderr}")
        return None

def get_metrics():
    command = ['kubectl', 'get', '--raw', '/apis/metrics.k8s.io/v1beta1/nodes']
    
    result = subprocess.run(command, capture_output=True, text=True)
    
    if result.returncode == 0:
        metrics = json.loads(result.stdout)

        for node in metrics.get('items', []):
            node_name = node['metadata']['name']
            cpu_usage_str = node['usage']['cpu']
            
            if cpu_usage_str.endswith("n"):
                cpu_usage_nanocores = int(cpu_usage_str.rstrip('n'))
            else:
                cpu_usage_nanocores = int(cpu_usage_str.rstrip('m')) * 1e6

            cpu_capacity_nanocores = get_node_capacity(node_name)

            if cpu_capacity_nanocores:
                cpu_usage_percentage = (cpu_usage_nanocores / cpu_capacity_nanocores) * 100
                print(f"Node : {node_name}, cpu: {cpu_usage_percentage:.2f}")
            else:
                print(f"Could not calculate CPU usage for node: {node_name}")
    else:
        print(f"Error getting metrics: {result.stderr}")

while True:
    get_metrics()
    time.sleep(sampling_rate)
