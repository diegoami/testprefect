# Docker + Prefect Cheat Sheet

## 🚀 Quick Commands

### Volume Operations
```bash
# Create volume
docker volume create my-volume

# List volumes
docker volume ls

# Inspect volume
docker volume inspect my-volume

# Remove volume
docker volume rm my-volume

# Remove all unused volumes
docker volume prune -f
```

### Running Containers with Volumes
```python
import docker

client = docker.from_env()

# With named volume
container = client.containers.run(
    'python:3.11-slim',
    command='python script.py',
    volumes={'my-volume': {'bind': '/data', 'mode': 'rw'}},
    detach=True,
    remove=True
)

# With bind mount
container = client.containers.run(
    'python:3.11-slim',
    command='python script.py',
    volumes={'/host/path': {'bind': '/container/path', 'mode': 'rw'}},
    detach=True,
    remove=True
)
```

## 📋 Common Patterns

### Pattern 1: Multi-Stage Pipeline with Volumes
```python
from prefect import flow, task
import docker

@task
def stage1():
    client = docker.from_env()
    client.containers.run(
        'alpine',
        'sh -c "echo data > /data/stage1.txt"',
        volumes={'pipeline-vol': {'bind': '/data', 'mode': 'rw'}},
        remove=True
    )

@task
def stage2():
    client = docker.from_env()
    client.containers.run(
        'alpine',
        'sh -c "cat /data/stage1.txt > /data/stage2.txt"',
        volumes={'pipeline-vol': {'bind': '/data', 'mode': 'rw'}},
        remove=True
    )

@flow
def pipeline():
    stage1()
    stage2()
```

### Pattern 2: Parallel Processing
```python
@task
def process_partition(partition_id, data):
    client = docker.from_env()
    client.containers.run(
        'python:3.11',
        f'python -c "process({data})"',
        volumes={'results': {'bind': '/results', 'mode': 'rw'}},
        remove=True
    )

@flow
def parallel_pipeline():
    partitions = [1, 2, 3, 4]
    futures = [process_partition.submit(i, data) for i, data in enumerate(partitions)]
    results = [f.result() for f in futures]
```

### Pattern 3: With Cleanup
```python
@flow
def safe_pipeline():
    try:
        # Create volume
        client = docker.from_env()
        volume = client.volumes.create('temp-vol')
        
        # Run pipeline
        my_pipeline()
        
    finally:
        # Cleanup
        volume.remove(force=True)
```

## 🎯 Decision Tree

```
Need to run containerized tasks?
│
├─ YES → Need data to persist between containers?
│        │
│        ├─ YES → Use Docker Volumes
│        │        - Best performance
│        │        - Production-ready
│        │
│        └─ NO → Use temporary containers
│                 - Auto-remove after execution
│
└─ NO → Use regular Prefect tasks
         - No containerization needed
```

## 📊 Volume vs Bind Mount

| Feature | Docker Volume | Bind Mount |
|---------|--------------|------------|
| **Performance** | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Good |
| **Portability** | ⭐⭐⭐⭐ Good | ⭐⭐ Limited |
| **Dev/Debug** | ⭐⭐ Limited | ⭐⭐⭐⭐⭐ Excellent |
| **Production** | ⭐⭐⭐⭐⭐ Recommended | ⭐⭐ Not recommended |
| **Location** | Docker managed | Host filesystem |
| **Inspection** | Via containers | Direct file access |

## 🔑 Key Prefect + Docker Patterns

### Task with Retry in Container
```python
@task(retries=3, retry_delay_seconds=5)
def resilient_container_task():
    client = docker.from_env()
    # Container operation
```

### Conditional Container Execution
```python
@flow
def conditional_flow():
    if needs_processing():
        run_in_container()
    else:
        run_locally()
```

### Container with Custom Image
```python
@task
def custom_image_task():
    client = docker.from_env()
    client.containers.run(
        'my-custom-image:v1.0',
        environment={'CONFIG': 'value'},
        volumes={'data': {'bind': '/data', 'mode': 'rw'}}
    )
```

## 🛠️ Infrastructure Block Setup

```python
from prefect.infrastructure import DockerContainer

# Create block
docker_block = DockerContainer(
    image="prefecthq/prefect:2-python3.11",
    volumes=["/data:/data:rw"],
    network_mode="bridge",
    auto_remove=True,
    env={"ENV": "prod"}
)

# Save block
docker_block.save("my-docker-block", overwrite=True)
```

## 🎨 Container Options Reference

```python
container = client.containers.run(
    image='python:3.11',
    command='python script.py',
    
    # Volumes
    volumes={
        'vol-name': {'bind': '/path', 'mode': 'rw'},  # Named volume
        '/host': {'bind': '/container', 'mode': 'ro'}  # Bind mount (read-only)
    },
    
    # Networking
    network_mode='bridge',  # or 'host', 'none'
    ports={'8000/tcp': 8000},
    
    # Resources
    mem_limit='2g',
    cpu_period=100000,
    cpu_quota=50000,
    
    # Behavior
    detach=True,        # Run in background
    remove=True,        # Auto-remove after exit
    auto_remove=True,   # Same as remove
    
    # Environment
    environment={
        'KEY': 'value',
        'DEBUG': 'true'
    },
    
    # Working directory
    working_dir='/app',
    
    # User
    user='1000:1000'
)
```

## 🔍 Debugging Tips

### View Container Logs
```python
container = client.containers.run(..., detach=True)
print(container.logs().decode('utf-8'))
```

### Check Volume Contents
```bash
docker run --rm -v my-volume:/data alpine ls -la /data
```

### Interactive Container
```bash
docker run -it --rm -v my-volume:/data python:3.11 bash
```

### Inspect Running Container
```python
container_info = container.attrs
print(container_info['State'])
print(container_info['Mounts'])
```

## ⚠️ Common Pitfalls

### ❌ DON'T: Hardcode paths
```python
volumes={'/home/user/data': {'bind': '/data'}}  # BAD
```

### ✅ DO: Use Path or environment variables
```python
from pathlib import Path
data_path = Path.home() / 'data'
volumes={str(data_path): {'bind': '/data'}}  # GOOD
```

### ❌ DON'T: Forget cleanup
```python
volume = client.volumes.create('temp')
# ... pipeline ...
# Volume left behind!
```

### ✅ DO: Always cleanup
```python
try:
    volume = client.volumes.create('temp')
    # ... pipeline ...
finally:
    volume.remove(force=True)
```

### ❌ DON'T: Mount root or system dirs
```python
volumes={'/': {'bind': '/host'}}  # DANGEROUS
```

### ✅ DO: Mount specific directories
```python
volumes={'/home/user/project': {'bind': '/app'}}  # SAFE
```

## 📦 Quick Start Templates

### Template 1: Simple ETL
```python
from prefect import flow, task
import docker

client = docker.from_env()
VOLUME = 'etl-data'

@task
def extract():
    client.containers.run(
        'alpine', 
        'sh -c "echo data > /data/raw.txt"',
        volumes={VOLUME: {'bind': '/data', 'mode': 'rw'}},
        remove=True
    )

@task
def transform():
    client.containers.run(
        'alpine',
        'sh -c "cat /data/raw.txt | tr a-z A-Z > /data/processed.txt"',
        volumes={VOLUME: {'bind': '/data', 'mode': 'rw'}},
        remove=True
    )

@flow
def etl():
    extract()
    transform()
```

### Template 2: ML Pipeline
```python
@flow
def ml_pipeline():
    # Data volume
    client.volumes.create('ml-data')
    # Model volume  
    client.volumes.create('ml-models')
    
    extract_data()
    preprocess_data()
    train_model()
    evaluate_model()
```

### Template 3: With Prefect Infrastructure
```python
from prefect import flow
from prefect.infrastructure import DockerContainer

@flow
def production_flow():
    # Tasks run in containers automatically
    extract()
    transform()
    load()

# Deploy with:
# prefect deployment build flow.py:production_flow \
#   --infrastructure my-docker-block
```

## 🎓 Learning Resources

1. **Start here**: `DOCKER_README.md`
2. **Basic examples**: `docker_prefect_examples.py`
3. **Production patterns**: `docker_infrastructure_examples.py`
4. **Real-world**: `ml_pipeline_docker.py`
5. **Full guide**: `DOCKER_PREFECT_GUIDE.md`