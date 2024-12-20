# Feedback-Driven-Resource-Controller-for-Kubernetes-Clusters
Developed an adaptive feedback-based controller for Kubernetes clusters to optimize resource utilization and manage dynamic workloads. Implemented local and global controllers using techniques like PID control to maintain desired CPU utilization across nodes and pods.

# Kubernetes Stress Testing Workflow

This document provides a comprehensive guide to set up and run Kubernetes stress testing using job generation, middleware, local controllers, and a global controller.

---

## Prerequisites

- Python 3 installed
- Kubernetes cluster configured with `kubectl` and `kubeadm`
- Fluent Bit installed for logging (optional but recommended)

---

## Complete Workflow

```
# Step 1: Generate Job List
# The first step is to create a job list for stress testing using job_generation.py.

python3 job_generation.py <io_min> <io_max> <vm_min> <vm_max> <vm_bytes_min> <vm_bytes_max> <timeout_min> <timeout_max> <num_of_jobs>

# Example:
python3 job_generation.py 0 5 0 5 0 4 10 30 30

# Output:
# The generated jobs will be appended to job_list.txt.

# Step 2: Start the Middleware
# Middleware is responsible for handling node scaling and stress testing in the cluster.

python3 middleware_api.py

# API Access:
# The middleware API will run on:
# http://127.0.0.1:5001
# http://128.110.217.103>:5001

# Verification:
# Confirm the middleware is live using the following command:
curl http://127.0.0.1:5001

# Step 3: Start Local Controllers
# Local controllers manage pod creation and job scheduling on individual nodes.

# Configuration:
# Edit local_controller.py to configure settings such as:
# - Sample rate
# - Reference input
# - Job file location
# - API endpoints for middleware integration

# Command:
# Run the local controller on each node:
python3 local_controller_node<node_name>.py

# Note:
# To enable job queue reading, set read_jobs = True in local_controller.py.

# Step 4: Start the Global Controller
# The global controller orchestrates node scaling and cluster-wide job scheduling.

# Configuration:
# Edit global_controller.py to configure:
# - Middleware API endpoints
# - Node list
# - Scaling thresholds
# - Job assignment settings

# Command:
python3 global_controller.py

# Requirements:
# Ensure the job_list.txt file exists in the working directory.
