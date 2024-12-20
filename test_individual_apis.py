import requests
# r = requests.post('http://127.0.0.1:5001/pod', json={"job": "stress-ng --io 2 --timeout 4m", "name": 'test', 'node':'node1'},timeout=2.50)
# r = requests.post('http://127.0.0.1:5001/pod', json={"job": "stress-ng --io 2 --timeout 4m", "name": 'test', 'node':'node2'},timeout=2.50)
# r = requests.post('http://127.0.0.1:5001/pod', json={'node': 'node0', 'job': 'stress-ng -- cpu 1 --io 2 --vm 2 --timeout 137s', 'name': 'pod-f3a64600'},timeout=2.50)

# {'node': 'node0', 'job': 'stress-ng -- cpu 1 --io 2 --vm 2 --vm-bytes 2G --timeout 137s'}
# r = requests.post('http://127.0.0.1:5001/pod-num',json={"node":'node0'})
# r = requests.get('http://127.0.0.1:5001/cpu')
# r = requests.get('http://127.0.0.1:5001/delete-pods')
# r = requests.post('http://127.0.0.1:5001/delete-node',json={'node':'node1'})
r = requests.post('http://127.0.0.1:5001/start-node',json={'node':'node1'})
# r = requests.get('http://127.0.0.1:5001/nodes')
print(r.content)
print(r.status_code)