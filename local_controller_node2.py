import time
import threading
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from kubernetes import client, config
import logging
import json
from datetime import datetime
import subprocess
import requests

# Load Kubernetes configuration
# config.load_kube_config()

# Initialize FastAPI app
app = FastAPI()

# Initialize logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

#controller values
pid_kp = -1.7
pid_ki = 1.8
pid_kd= 1.3

# Threshold and PID settings
sample_rate = 5  # The closed loop system will sleep for this much of X seconds
reference_input = 0.8  # CPU usage, from 0 to 100
job_sleep_time = 15  # read a job every X seconds
job_file_name = "job_list.txt"
cpu_res_file_name = "cpu.txt"
max_pod_res_file_name = "maxpod.txt"
job_list = []
node_name = "node2"
cur_pod_id = 0
max_pod_upperbound = 7
job_delay = 15  # number of seconds that we believe a the CPU is changed after a job is started, i.e., we need to wait at least that time before we start the closed loop function
read_jobs = False  # if read a job from a file and render the jobs
# global variables
last_pod_start_time = None
last_pod_finish_time = None
max_pod = (
    1  # control input. Share variable, set by the closed loop, read by job assignment
)
CPU_data = []
max_pod_data = []
controller_running = False

#apis
cpu_api = "http://128.110.217.103:5001/cpu"
pod_num_api = "http://128.110.217.103:5001/pod-num"
create_pod_api = "http://128.110.217.103:5001/pod"


# Helper Functions


def read_file_to_list(file_path):
    """read a file, return a list of strings(each line)
    """
    try:
        with open(file_path, 'r') as file:
            lines = file.readlines()
        # Strip newline characters from each line
        lines = [line.strip() for line in lines]
        return lines, None
    except FileNotFoundError:
        return [], "The file was not found."
    except Exception as e:
        return [], e
    
def get_cpu():
    """get the current CPU usage"""
    try:
        response = requests.get(cpu_api)
        if response.status_code == 200:
            cpu_data = response.json()
            return cpu_data[node_name] / 100, None
        else:
            return None, f"Error: {response.status_code}"
    except Exception as e:
        return None, e


def get_pod_num():
    global last_pod_finish_time
    try:
        payload = {"node": node_name}
        response = requests.post(pod_num_api, json=payload)
        if response.status_code == 200:
            res = response.json()
            if len(res["deleted_pods"]) != 0:
                last_pod_finish_time = datetime.now()
            return res["pod_num"], res["deleted_pods"], None
        else:
            return None, None, f"Error: {response.status_code}"
    except Exception as e:
        return None, None, e

def run_job(job_des):
    """create a new pod with the job description"""
    try:
        global cur_pod_id
        payload = {"job": job_des, "name": cur_pod_id, "node": node_name}
        cur_pod_id += 1
        response = requests.post(create_pod_api, json=payload)
        if response.status_code == 200:
            res = response.json()
            return res["success"], res["msg"]
        else:
            return False, f"Error: {response.status_code}"
    except Exception as e:
        return None, e
    

def get_node_capacity(node_name):
    """Returns the CPU capacity of the node in nanocores."""
    command = ["kubectl", "get", "node", node_name, "-o", "json"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        node_info = json.loads(result.stdout)
        cpu_capacity_cores = int(node_info["status"]["capacity"]["cpu"])
        return cpu_capacity_cores * 1e9
    else:
        logging.error(f"Error getting node capacity: {result.stderr}")
        return None


# PID Controller Class


class PIDController:
    def __init__(self, kp, ki, kd):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.prev_e = 0
        self.integral = 0

    def compute(self, actual_value):
            # Force more aggressive scaling when below target
            if actual_value < 0.75:
                err = 0.80 - actual_value
            elif actual_value > 0.85:
                err = 0.85 - actual_value
            else:
                err = reference_input - actual_value
                
            # Reduced anti-windup threshold
            if abs(self.integral) > 2.0:
                self.integral = 0
                
            self.integral += sample_rate * err
            derivative = (err - self.prev_e) / sample_rate
            u = self.kp * err + self.ki * self.integral + self.kd * derivative
            self.prev_e = err
            return max(1, min(round(u), max_pod_upperbound))


# Monitoring and Job Handling


def closed_loop(controller):
    global max_pod, reference_input, CPU_data, max_pod_data, sample_rate, last_pod_start_time, job_delay, last_pod_finish_time, controller_running
    logging.info("start close loop")
    pod_num = 0
    while True:
        if not controller_running:
            # if the controller is stopped, sleep and continue
            logging.info("controller stopped, waiting")
            time.sleep(sample_rate)
            continue

        # get CPU usage
        cur_cpu, msg = get_cpu()
        if msg != None:
            # error getting the cpu
            logging.critical(f"error getting the CPU: {msg}")
            if len(CPU_data) != 0:
                logging.critical(f"using last CPU {CPU_data[-1]}")
                cur_cpu = CPU_data[-1]
            else:
                logging.critical(f"set CPU to be 0")
                cur_cpu = 0

        logging.info(f"current CPU: {cur_cpu}")
        CPU_data.append(cur_cpu)

        # if maxpod != podnum, it means that the system is unstable, the close loop won't execute
        pod_num, _, msg = get_pod_num()
        if msg is not None:
            logging.critical(f"error when getting pod number, {msg}")
            logging.critical(f"using previous pod number, {pod_num}")
        time_since_last_job_created = (
            (datetime.now() - last_pod_start_time).total_seconds()
            if last_pod_start_time is not None
            else float("inf")
        )
        time_since_last_job_deleted = (
            (datetime.now() - last_pod_finish_time).total_seconds()
            if last_pod_finish_time is not None
            else float("inf")
        )
        if (pod_num > max_pod and cur_cpu > reference_input) or (
            pod_num < max_pod and cur_cpu < reference_input
        ):
            # pod_num hasn't achieve the max_pod with the right dirrection(pod could increase while CPU needs to increase), so wait until the changes actually happens
            logging.info(
                f"max_pod {max_pod} != pod_num {pod_num}, skipping closed loop"
            )
        elif time_since_last_job_created < job_delay and cur_cpu < reference_input:
            # pod just created, so it has the potenrial to increase the cpu to the reference input, wait for a while to let the stress tests started
            logging.info(
                f"last job started {time_since_last_job_created}s ago, skipping closed loop, max_pod {max_pod}"
            )
        elif time_since_last_job_deleted < job_delay and cur_cpu > reference_input:
            logging.info(
                f"last job finished {time_since_last_job_deleted}s ago, skipping closed loop, max_pod {max_pod}"
            )
        else:
            # compute the close loop and undate the max_pod only if the maxpod == pod_num, otherwise, the system is not stable yet
            e = reference_input - cur_cpu
            u = controller.compute(e)
            logging.info(f"closed loop: e: {e}, u: {u}")
            new_max_pod = round(u)
            if new_max_pod < 1:
                new_max_pod = 1
            if new_max_pod >= max_pod_upperbound:
                new_max_pod = max_pod_upperbound
                logging.info(f"maxpod hitting upper bound {max_pod_upperbound}")
            if new_max_pod > max_pod:
                logging.info(f"scaling up, max_pod {max_pod} -> {new_max_pod}")
            elif new_max_pod < max_pod:
                logging.info(f"scaling down, max_pod {max_pod} -> {new_max_pod}")
            else:
                logging.info(f"max_pod remains {max_pod}")
            max_pod = new_max_pod

        max_pod_data.append(max_pod)
        time.sleep(sample_rate)


def render_jobs():
    global job_list, last_pod_start_time
    while job_list:
        job = job_list[0]

        # check if cur_pod_num < max_pod
        cur_pod_num, deleted_pods, msg = get_pod_num()
        if msg != None:
            logging.critical(f"get job num error: {msg}")
            logging.critical("abondon job rendering, will try to render this job later")
        if cur_pod_num >= max_pod:
            logging.info(
                f"current pod num: {cur_pod_num}, max pod num: {max_pod}, job not scheduled"
            )
        else:
            logging.info(
                f"current pod num: {cur_pod_num}, scheduling job {cur_pod_id}: {job}"
            )
            ok, msg = run_job(job)
            if not ok:
                logging.error(
                    f"error when trying to run job: {msg}, will try to run this job again"
                )
            else:
                last_pod_start_time = datetime.now()
                job_list = job_list[1:]
                logging.info(
                    f"job {cur_pod_id} scheduled, remaining jobs: {len(job_list)}"
                )

        time.sleep(job_sleep_time)
    logging.info("job finished")
    exit(0)


def save_list_to_file(list_data, file_name):
    """Writes each element of a list to a file, placing one element per line."""
    try:
        with open(file_name, "w") as file:
            for item in list_data:
                file.write(f"{item}\n")
        return None
    except Exception as e:
        logging.error(f"error occurred when save data to {file_name}, error: {e}")
        return f"An unexpected error occurred: {e}"


def save_cpu_max_pod():
    while True:
        if not controller_running:
            # if the controller is stopped, sleep and continue
            logging.info("controller stopped, waiting")
            time.sleep(sample_rate)
            continue
        if len(CPU_data) > 0:
            logging.info(f"saving CPU {CPU_data[-1]} and max_pod {max_pod_data[-1]}")
        save_list_to_file(CPU_data, cpu_res_file_name)
        save_list_to_file(max_pod_data, max_pod_res_file_name)
        time.sleep(sample_rate)


# Endpoints

@app.get("/start")
async def start_controller():
    """Start the controller."""
    global controller_running
    try:
        controller_running = True
        return {"success": True, "msg": ""}
    except Exception as e:
        logging.error(f"Error starting the local controller: {e}")
        return {"success": False, "msg": str(e)}


@app.get("/stop")
async def stop_controller():
    """Stop the controller."""
    global controller_running
    try:
        controller_running = False
        return {"success": True, "msg": ""}
    except Exception as e:
        logging.error(f"Error stopping the local controller: {e}")
        return {"success": False, "msg": str(e)}


@app.get("/pod-num")
async def get_nodes():
    """Return the current pod number."""
    try:
        res, _, msg = get_pod_num()
        if res is None:
            return {"success": False, "msg": msg, "pod-num": 0}
        else:
            return {"success": True, "msg": "", "pod-num": res}
    except Exception as e:
        logging.error(f"Error in get_nodes: {e}")
        return {"success": False, "msg": str(e), "pod-num": 0}


@app.get("/maxpod")
async def get_maxpod():
    """Return the current maxpod number."""
    try:
        return {"success": True, "msg": "", "maxpod": max_pod}
    except Exception as e:
        logging.error(f"Error in get_maxpod: {e}")
        return {"success": False, "msg": str(e), "maxpod": 0}


@app.post("/job")
async def handle_post(request: Request):
    """Add a new job."""
    global job_list, last_pod_start_time
    try:
        # Parse JSON payload
        data = await request.json()
        job_description = data.get("job")

        logging.info(f"Received a new job request: {job_description}")
        cur_pod_num, _, msg = get_pod_num()
        if cur_pod_num >= max_pod:
            logging.info(f"Maximum pod limit reached: current pods ({cur_pod_num}) >= max pods ({max_pod}). Unable to assign a new job.")
            return {
                "success": False,
                "msg": f"Current pods ({cur_pod_num}) >= max pods ({max_pod}). Unable to assign a new job.",
            }

        # Render the job
        logging.info(f"Current pod count: {cur_pod_num}. Scheduling job: {job_description}")
        ok, msg = run_job(job_description)
        if not ok:
            logging.error(f"Failed to schedule the job. Error: {msg}")
            return {"success": False, "msg": f"Failed to start new job. Error: {msg}"}

        last_pod_start_time = datetime.now()
        logging.info("Job successfully scheduled.")
        return {"success": True, "msg": ""}
    except Exception as e:
        logging.error(f"An error occurred in handle_post: {e}")
        return {"success": False, "msg": str(e)}



@app.post("/reference-input")
async def handle_post_json(request: Request):
    """Set the reference input."""
    global reference_input
    try:
        data = await request.json()
        value = int(data.get("value"))
        if 0 <= value <= 100:
            logging.info(f"Reference input updated to: {value}")
            reference_input = value
            return {"success": True, "msg": ""}
        else:
            logging.warning(f"Invalid reference input: {value}. It must be between 0 and 100.")
            return {"success": False, "msg": "Reference input must be between 0 and 100."}
    except Exception as e:
        logging.error(f"An error occurred while setting the reference input: {e}")
        return {"success": False, "msg": str(e)}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set the logging level for 'urllib3.connectionpool' to WARNING or higher
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    # Log the configurations
    logging.debug(f"Configured Sample Rate: {sample_rate} seconds")
    logging.debug(f"Initial Reference Input (CPU Usage Target): {reference_input * 100}%")
    logging.debug(f"Job Sleep Time: {job_sleep_time} seconds")
    logging.debug(f"Job File Name: {job_file_name}")
    logging.debug(f"CPU API Endpoint: {cpu_api}")
    logging.debug(f"Pod Number API Endpoint: {pod_num_api}")
    logging.debug(f"Pod Creation API Endpoint: {create_pod_api}")
    logging.debug(f"Maximum Number of Pods Allowed: {max_pod}")

    # Start a thread to monitor CPU usage and manage pod scaling
    controller = PIDController(pid_kp, pid_ki, pid_kd)
    closed_loop_thread = threading.Thread(target=closed_loop, args=(controller,))
    closed_loop_thread.daemon = True
    closed_loop_thread.start()

    # Load job list and start job rendering, if required
    if read_jobs:
        job_list, error = read_file_to_list(job_file_name)
        logging.info(f"Attempting to load job list from file: {job_file_name}")
        if error:
            logging.critical(f"Failed to retrieve job list: {error}")
            logging.critical("Application shutting down due to job list error.")
            exit(0)

        # Allow the closed-loop controller to stabilize before job rendering
        time.sleep(5)
        logging.info("Successfully loaded job list. Starting job rendering...")
        job_render_thread = threading.Thread(target=render_jobs)
        job_render_thread.daemon = True
        job_render_thread.start()
    else:
        job_list = []
        logging.info("Job list is empty. No jobs to render.")

    # Start thread to save CPU and max pod data periodically
    save_res_thread = threading.Thread(target=save_cpu_max_pod)
    save_res_thread.daemon = True
    save_res_thread.start()

    # Start the FastAPI server
    logging.info("Starting server on host 0.0.0.0, port 5004...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5004)

