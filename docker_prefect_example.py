"""
Fixed: Docker + Prefect Examples
=================================

This fixes the issue where containers were being removed before logs could be retrieved.
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import docker
from pathlib import Path
import json
import time
from typing import Optional, List


# ====================
# APPROACH 1: DOCKER VOLUMES
# ====================

@task
def create_docker_volume(volume_name: str):
    """Create a Docker volume for persistent storage"""
    logger = get_run_logger()
    client = docker.from_env()
    
    try:
        # Check if volume exists
        volume = client.volumes.get(volume_name)
        logger.info(f"Volume '{volume_name}' already exists")
    except docker.errors.NotFound:
        # Create new volume
        volume = client.volumes.create(name=volume_name)
        logger.info(f"Created volume '{volume_name}'")
    
    return volume.name


@task(retries=2)
def run_container_with_volume(
    image: str,
    command: str,
    volume_name: str,
    container_path: str = "/data"
):
    """
    Run a container with a named volume attached.
    
    FIX: Get logs BEFORE removing container, or don't use remove=True
    """
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Running container: {image}")
    logger.info(f"Volume: {volume_name} -> {container_path}")
    
    # Run container with volume - DON'T auto-remove yet
    container = client.containers.run(
        image=image,
        command=command,
        volumes={volume_name: {'bind': container_path, 'mode': 'rw'}},
        detach=True,
        remove=False  # FIXED: Don't auto-remove so we can get logs
    )
    
    # Wait for completion
    result = container.wait()
    
    # Get logs while container still exists
    logs = container.logs().decode('utf-8')
    
    # Now remove the container
    container.remove()
    
    logger.info(f"Container exit code: {result['StatusCode']}")
    logger.info(f"Container logs:\n{logs}")
    
    return {
        "status_code": result['StatusCode'],
        "logs": logs,
        "volume": volume_name
    }


@flow
def docker_volume_pipeline():
    """
    Pipeline demonstrating Docker volumes for data persistence.
    
    Use case: Process data in stages, each stage in a separate container,
    with data persisting between containers.
    """
    volume_name = "prefect-data-volume"
    
    # Create volume
    create_docker_volume(volume_name)
    
    # Stage 1: Generate data
    result1 = run_container_with_volume(
        image="alpine:latest",
        command="sh -c 'echo \"Stage 1 data\" > /data/stage1.txt && cat /data/stage1.txt'",
        volume_name=volume_name
    )
    
    # Stage 2: Process data (reads from same volume)
    result2 = run_container_with_volume(
        image="alpine:latest",
        command="sh -c 'cat /data/stage1.txt && echo \"Stage 2 processed\" > /data/stage2.txt'",
        volume_name=volume_name
    )
    
    # Stage 3: Aggregate results
    result3 = run_container_with_volume(
        image="alpine:latest",
        command="sh -c 'ls -la /data/ && cat /data/*.txt'",
        volume_name=volume_name
    )
    
    return {
        "volume": volume_name,
        "stages": [result1, result2, result3]
    }


# ====================
# APPROACH 2: BIND MOUNTS
# ====================

@task
def prepare_workspace(workspace_path: str):
    """Prepare a local workspace directory"""
    logger = get_run_logger()
    path = Path(workspace_path)
    path.mkdir(parents=True, exist_ok=True)
    
    # Create initial data file
    input_file = path / "input.json"
    input_file.write_text(json.dumps({
        "dataset": "sales_data",
        "records": 1000,
        "timestamp": time.time()
    }, indent=2))
    
    logger.info(f"Workspace prepared at: {workspace_path}")
    return str(path.absolute())


@task
def run_container_with_bind_mount(
    image: str,
    command: str,
    host_path: str,
    container_path: str = "/workspace"
):
    """Run container with bind mount to share data with host"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Binding {host_path} to {container_path}")
    
    container = client.containers.run(
        image=image,
        command=command,
        volumes={host_path: {'bind': container_path, 'mode': 'rw'}},
        working_dir=container_path,
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()
    
    logger.info(f"Container completed with code: {result['StatusCode']}")
    
    return {
        "status_code": result['StatusCode'],
        "logs": logs,
        "host_path": host_path
    }


@task
def verify_output(workspace_path: str, expected_file: str):
    """Verify that container created expected output"""
    logger = get_run_logger()
    output_path = Path(workspace_path) / expected_file
    
    if output_path.exists():
        content = output_path.read_text()
        logger.info(f"Output file found: {expected_file}")
        logger.info(f"Content:\n{content}")
        return True
    else:
        logger.error(f"Output file not found: {expected_file}")
        return False


@flow
def bind_mount_pipeline(workspace: str = "/tmp/prefect-workspace"):
    """
    Pipeline using bind mounts to share data between host and containers.
    
    Use case: Process files on the host filesystem, allowing inspection
    of intermediate results without entering containers.
    """
    
    # Prepare workspace
    workspace_path = prepare_workspace(workspace)
    
    # Stage 1: Read and process input
    run_container_with_bind_mount(
        image="python:3.11-slim",
        command="sh -c 'cat input.json && echo \"{\\\"processed\\\": true}\" > stage1_output.json'",
        host_path=workspace_path
    )
    
    verify_output(workspace_path, "stage1_output.json")
    
    # Stage 2: Further processing
    run_container_with_bind_mount(
        image="python:3.11-slim",
        command="python -c 'import json; data = json.load(open(\"stage1_output.json\")); data[\"stage2\"] = \"complete\"; json.dump(data, open(\"final_output.json\", \"w\"))'",
        host_path=workspace_path
    )
    
    verify_output(workspace_path, "final_output.json")
    
    return {"workspace": workspace_path}


# ====================
# APPROACH 3: PYTHON PROCESSING IN CONTAINERS
# ====================

@task
def run_python_in_container(
    python_code: str,
    volume_name: str,
    requirements: list = None
):
    """Run Python code in a container with data volume"""
    logger = get_run_logger()
    client = docker.from_env()
    
    # Create requirements installation command if needed
    pip_install = ""
    if requirements:
        pip_install = f"pip install {' '.join(requirements)} && "
    
    # Full command - escape quotes properly
    python_code_escaped = python_code.replace('"', '\\"')
    full_command = f"sh -c '{pip_install}python -c \"{python_code_escaped}\"'"
    
    logger.info("Running Python code in container")
    
    container = client.containers.run(
        image="python:3.11-slim",
        command=full_command,
        volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()
    
    logger.info(f"Python execution logs:\n{logs}")
    
    return {
        "status_code": result['StatusCode'],
        "logs": logs
    }


@flow
def python_container_pipeline():
    """
    Pipeline running Python code in containers with shared data volume.
    
    Use case: Run different Python processing steps in isolated environments
    while sharing data through volumes.
    """
    volume_name = "python-data-volume"
    
    # Create volume
    create_docker_volume(volume_name)
    
    # Step 1: Generate data
    run_python_in_container(
        python_code="""
import json
data = {'values': [1, 2, 3, 4, 5], 'timestamp': 'now'}
with open('/data/raw_data.json', 'w') as f:
    json.dump(data, f)
print('Data generated')
""",
        volume_name=volume_name,
        requirements=[]
    )
    
    # Step 2: Process data
    run_python_in_container(
        python_code="""
import json
with open('/data/raw_data.json', 'r') as f:
    data = json.load(f)
processed = {'sum': sum(data['values']), 'count': len(data['values'])}
with open('/data/processed_data.json', 'w') as f:
    json.dump(processed, f)
print(f'Processed: {processed}')
""",
        volume_name=volume_name,
        requirements=[]
    )
    
    # Step 3: Generate report
    run_python_in_container(
        python_code="""
import json
with open('/data/processed_data.json', 'r') as f:
    data = json.load(f)
report = f"Report: Sum={data['sum']}, Count={data['count']}, Avg={data['sum']/data['count']}"
with open('/data/report.txt', 'w') as f:
    f.write(report)
print(report)
""",
        volume_name=volume_name,
        requirements=[]
    )
    
    return {"volume": volume_name}


# ====================
# APPROACH 4: PARALLEL CONTAINER EXECUTION
# ====================

@task
def process_partition(partition_id: int, volume_name: str, data: list):
    """Process a data partition in a separate container"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Processing partition {partition_id}")
    
    # Prepare Python code for this partition
    python_code = f"""
import json
data = {data}
result = {{'partition_id': {partition_id}, 'sum': sum(data), 'count': len(data)}}
with open(f'/data/partition_{partition_id}.json', 'w') as f:
    json.dump(result, f)
print(f'Partition {partition_id}: {{result}}')
"""
    
    python_code_escaped = python_code.replace('"', '\\"').replace("'", "\\'")
    
    container = client.containers.run(
        image="python:3.11-slim",
        command=f'python -c "{python_code}"',
        volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()
    
    return {
        "partition_id": partition_id,
        "status_code": result['StatusCode'],
        "logs": logs
    }


@task
def aggregate_partition_results(volume_name: str, num_partitions: int):
    """Aggregate results from all partition containers"""
    logger = get_run_logger()
    client = docker.from_env()
    
    python_code = f"""
import json
import glob

results = []
for file in glob.glob('/data/partition_*.json'):
    with open(file, 'r') as f:
        results.append(json.load(f))

total = {{'total_sum': sum(r['sum'] for r in results), 'total_count': sum(r['count'] for r in results)}}
with open('/data/aggregated.json', 'w') as f:
    json.dump(total, f)
print(f'Aggregated: {{total}}')
"""
    
    python_code_escaped = python_code.replace('"', '\\"')
    
    container = client.containers.run(
        image="python:3.11-slim",
        command=f'python -c "{python_code}"',
        volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()
    
    logger.info(f"Aggregation result:\n{logs}")
    
    return logs


@flow
def parallel_container_pipeline():
    """
    Run multiple containers in parallel, each processing a data partition.
    
    Use case: Distribute data processing across multiple containers,
    with results aggregated at the end.
    """
    volume_name = "parallel-processing-volume"
    
    # Create volume
    create_docker_volume(volume_name)
    
    # Partition data
    full_data = list(range(1, 101))  # Numbers 1-100
    partitions = [
        full_data[0:25],
        full_data[25:50],
        full_data[50:75],
        full_data[75:100]
    ]
    
    # Process partitions in parallel
    partition_futures = [
        process_partition.submit(i, volume_name, partition)
        for i, partition in enumerate(partitions)
    ]
    
    # Wait for all partitions to complete
    partition_results = [future.result() for future in partition_futures]
    
    # Aggregate results
    final_result = aggregate_partition_results(volume_name, len(partitions))
    
    return {
        "volume": volume_name,
        "partitions_processed": len(partitions),
        "results": partition_results,
        "final": final_result
    }


# ====================
# CLEANUP UTILITIES
# ====================

@task
def cleanup_volume(volume_name: str, force: bool = False):
    """Remove a Docker volume"""
    logger = get_run_logger()
    client = docker.from_env()
    
    try:
        volume = client.volumes.get(volume_name)
        volume.remove(force=force)
        logger.info(f"Removed volume: {volume_name}")
        return True
    except docker.errors.NotFound:
        logger.warning(f"Volume not found: {volume_name}")
        return False
    except docker.errors.APIError as e:
        logger.error(f"Failed to remove volume: {e}")
        return False


@task
def list_volumes():
    """List all Docker volumes"""
    logger = get_run_logger()
    client = docker.from_env()
    
    volumes = client.volumes.list()
    logger.info(f"Found {len(volumes)} volumes")
    
    for vol in volumes:
        logger.info(f"  - {vol.name}")
    
    return [vol.name for vol in volumes]


@flow
def cleanup_flow(volume_names: Optional[List[str]] = None):
    """Cleanup Docker volumes created by Prefect workflows"""
    
    if volume_names is None:
        # List and cleanup Prefect-related volumes
        all_volumes = list_volumes()
        volume_names = [v for v in all_volumes if 'prefect' in v.lower() or 'python' in v.lower() or 'parallel' in v.lower()]
    
    for volume_name in volume_names:
        cleanup_volume(volume_name, force=True)
    
    return {"cleaned_volumes": volume_names}


# ====================
# EXAMPLE USAGE
# ====================

if __name__ == "__main__":
    print("=" * 70)
    print("Docker + Prefect Examples (FIXED)")
    print("=" * 70)
    
    print("\n" + "=" * 70)
    print("Choose an example to run:")
    print("=" * 70)
    print("1. Docker Volume Pipeline")
    print("2. Bind Mount Pipeline")
    print("3. Python Container Pipeline")
    print("4. Parallel Container Pipeline")
    print("5. Cleanup Volumes")
    print("=" * 70)
    
    # Run Example 1 by default
    print("\nRunning Example 1: Docker Volume Pipeline\n")
    result = docker_volume_pipeline()
    print(json.dumps(result, indent=2))
    
    # Uncomment other examples as needed:
    
    # Example 2: Bind mounts
    # result = bind_mount_pipeline()
    # print(json.dumps(result, indent=2))
    
    # Example 3: Python in containers
    # result = python_container_pipeline()
    # print(json.dumps(result, indent=2))
    
    # Example 4: Parallel processing
    # result = parallel_container_pipeline()
    # print(json.dumps(result, indent=2))
    
    # Example 5: Cleanup
    result = cleanup_flow()
    print(json.dumps(result, indent=2))