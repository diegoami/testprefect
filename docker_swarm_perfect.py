"""
Docker Swarm + Prefect: Distributed ML Pipeline
================================================

Docker Swarm provides:
- Multi-node orchestration
- Service replication and scaling
- Load balancing
- Rolling updates
- Secret management
- Overlay networks

Perfect for scaling from single-host to multi-host deployments.

Use cases:
1. Scale ML training across multiple nodes
2. High-availability model serving
3. Distributed data processing
4. Production deployments without Kubernetes complexity
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import docker
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional


# ====================
# SWARM MANAGEMENT
# ====================

@task
def init_swarm():
    """Initialize Docker Swarm"""
    logger = get_run_logger()
    
    try:
        # Check if swarm is already initialized
        client = docker.from_env()
        client.swarm.attrs
        logger.info("Swarm already initialized")
        return {"status": "already_initialized"}
    except docker.errors.APIError:
        # Initialize swarm
        logger.info("Initializing Docker Swarm...")
        result = subprocess.run(
            ["docker", "swarm", "init"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Swarm initialized successfully")
            logger.info(result.stdout)
            return {"status": "initialized", "output": result.stdout}
        else:
            logger.error(f"Failed to initialize swarm: {result.stderr}")
            raise Exception(result.stderr)


@task
def leave_swarm(force: bool = True):
    """Leave Docker Swarm"""
    logger = get_run_logger()
    
    cmd = ["docker", "swarm", "leave"]
    if force:
        cmd.append("--force")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info("Left swarm successfully")
        return {"status": "left"}
    else:
        logger.warning(f"Could not leave swarm: {result.stderr}")
        return {"status": "not_in_swarm"}


@task
def get_swarm_nodes():
    """Get list of swarm nodes"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["docker", "node", "ls", "--format", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        nodes = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        logger.info(f"Found {len(nodes)} nodes in swarm")
        return nodes
    else:
        logger.error("Failed to get nodes")
        return []


# ====================
# STACK FILE GENERATION
# ====================

@task
def generate_stack_file():
    """Generate docker-stack.yml for swarm deployment"""
    logger = get_run_logger()
    
    stack_content = """version: '3.8'

services:
  # PostgreSQL - replicated for HA
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: mluser
      POSTGRES_PASSWORD: mlpassword
      POSTGRES_DB: mlpipeline
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - ml-network
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  # Redis - for caching and session management
  redis:
    image: redis:7-alpine
    networks:
      - ml-network
    deploy:
      replicas: 1
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  # Data Processor - scalable worker service
  data-processor:
    image: python:3.11-slim
    command: tail -f /dev/null
    volumes:
      - data-volume:/data
    environment:
      DATABASE_URL: postgresql://mluser:mlpassword@postgres:5432/mlpipeline
      REDIS_URL: redis://redis:6379
    networks:
      - ml-network
    deploy:
      replicas: 3  # Scale to 3 instances
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '1.0'
          memory: 2G

  # ML Training Service - can scale based on load
  training-service:
    image: tensorflow/tensorflow:latest
    command: tail -f /dev/null
    volumes:
      - data-volume:/data:ro
      - model-volume:/models
    environment:
      DATABASE_URL: postgresql://mluser:mlpassword@postgres:5432/mlpipeline
    networks:
      - ml-network
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 30s
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G

  # Model Serving API - load balanced
  serving-api:
    image: python:3.11-slim
    command: |
      sh -c "pip install fastapi uvicorn && 
             python -c 'from fastapi import FastAPI; app = FastAPI(); @app.get(\"/\"); def read_root(): return {\"status\": \"running\"}; import uvicorn; uvicorn.run(app, host=\"0.0.0.0\", port=8000)'"
    volumes:
      - model-volume:/models:ro
    networks:
      - ml-network
    deploy:
      replicas: 3  # Load balanced across 3 instances
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first  # Rolling update
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '0.5'
          memory: 1G

  # Visualizer - see swarm services (optional)
  visualizer:
    image: dockersamples/visualizer:latest
    ports:
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - ml-network
    deploy:
      placement:
        constraints:
          - node.role == manager
      restart_policy:
        condition: on-failure

networks:
  ml-network:
    driver: overlay
    attachable: true

volumes:
  postgres-data:
  data-volume:
  model-volume:
"""
    
    stack_dir = Path("swarm-stack")
    stack_dir.mkdir(exist_ok=True)
    
    stack_file = stack_dir / "docker-stack.yml"
    stack_file.write_text(stack_content)
    
    logger.info(f"Generated stack file: {stack_file}")
    return str(stack_file)


# ====================
# STACK DEPLOYMENT
# ====================

@task
def deploy_stack(stack_name: str = "ml-pipeline"):
    """Deploy stack to swarm"""
    logger = get_run_logger()
    
    stack_file = Path("swarm-stack/docker-stack.yml")
    
    if not stack_file.exists():
        raise FileNotFoundError(f"Stack file not found: {stack_file}")
    
    logger.info(f"Deploying stack: {stack_name}")
    
    result = subprocess.run(
        ["docker", "stack", "deploy", "-c", str(stack_file), stack_name],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(f"Stack deployed successfully")
        logger.info(result.stdout)
        return {"status": "deployed", "stack": stack_name}
    else:
        logger.error(f"Failed to deploy stack: {result.stderr}")
        raise Exception(result.stderr)


@task
def remove_stack(stack_name: str = "ml-pipeline"):
    """Remove stack from swarm"""
    logger = get_run_logger()
    
    logger.info(f"Removing stack: {stack_name}")
    
    result = subprocess.run(
        ["docker", "stack", "rm", stack_name],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Stack removed successfully")
        return {"status": "removed"}
    else:
        logger.error(f"Failed to remove stack: {result.stderr}")
        return {"status": "error", "message": result.stderr}


@task
def get_stack_services(stack_name: str = "ml-pipeline"):
    """Get services in a stack"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["docker", "stack", "services", stack_name, "--format", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        services = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        logger.info(f"Found {len(services)} services in stack")
        return services
    else:
        return []


@task
def scale_service(service_name: str, replicas: int):
    """Scale a service in the swarm"""
    logger = get_run_logger()
    
    logger.info(f"Scaling {service_name} to {replicas} replicas")
    
    result = subprocess.run(
        ["docker", "service", "scale", f"{service_name}={replicas}"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(f"Service scaled successfully")
        return {"status": "scaled", "service": service_name, "replicas": replicas}
    else:
        logger.error(f"Failed to scale service: {result.stderr}")
        raise Exception(result.stderr)


@task
def update_service(service_name: str, image: Optional[str] = None, env_add: Optional[Dict] = None):
    """Update a service with new image or environment"""
    logger = get_run_logger()
    
    cmd = ["docker", "service", "update"]
    
    if image:
        cmd.extend(["--image", image])
    
    if env_add:
        for key, value in env_add.items():
            cmd.extend(["--env-add", f"{key}={value}"])
    
    cmd.append(service_name)
    
    logger.info(f"Updating service: {service_name}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        logger.info("Service updated successfully")
        return {"status": "updated"}
    else:
        logger.error(f"Failed to update service: {result.stderr}")
        raise Exception(result.stderr)


# ====================
# SERVICE EXECUTION
# ====================

@task
def execute_in_swarm_service(service_name: str, command: List[str]):
    """Execute command in a swarm service task"""
    logger = get_run_logger()
    
    # Get task ID for service
    result = subprocess.run(
        ["docker", "service", "ps", service_name, "-q", "--filter", "desired-state=running"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0 or not result.stdout.strip():
        raise Exception(f"No running tasks found for service {service_name}")
    
    task_id = result.stdout.strip().split('\n')[0]
    
    # Get container ID from task
    result = subprocess.run(
        ["docker", "inspect", task_id, "--format", "{{.Status.ContainerStatus.ContainerID}}"],
        capture_output=True,
        text=True
    )
    
    container_id = result.stdout.strip()
    
    # Execute command in container
    logger.info(f"Executing in {service_name} (container: {container_id[:12]})")
    
    result = subprocess.run(
        ["docker", "exec", container_id] + command,
        capture_output=True,
        text=True
    )
    
    logger.info(f"Output:\n{result.stdout}")
    
    return {
        "service": service_name,
        "container": container_id[:12],
        "exit_code": result.returncode,
        "output": result.stdout
    }


# ====================
# MONITORING
# ====================

@task
def get_service_logs(service_name: str, tail: int = 100):
    """Get logs from a service"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["docker", "service", "logs", service_name, "--tail", str(tail)],
        capture_output=True,
        text=True
    )
    
    logger.info(f"Logs for {service_name}:\n{result.stdout}")
    return result.stdout


@task
def wait_for_stack_ready(stack_name: str = "ml-pipeline", timeout: int = 300):
    """Wait for all services in stack to be ready"""
    logger = get_run_logger()
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        services = get_stack_services(stack_name)
        
        if not services:
            logger.info("Waiting for services to appear...")
            time.sleep(5)
            continue
        
        all_ready = True
        for service in services:
            replicas = service.get('Replicas', '0/0')
            current, desired = map(int, replicas.split('/'))
            
            if current < desired:
                all_ready = False
                logger.info(f"Waiting for {service['Name']}: {replicas}")
                break
        
        if all_ready:
            logger.info("All services are ready!")
            return True
        
        time.sleep(5)
    
    raise TimeoutError(f"Services did not become ready within {timeout} seconds")


# ====================
# MAIN FLOWS
# ====================

@flow(name="Setup Docker Swarm")
def setup_swarm():
    """Initialize Docker Swarm and create stack file"""
    
    print("=" * 70)
    print("SETTING UP DOCKER SWARM")
    print("=" * 70)
    
    # Initialize swarm
    print("\n[1/2] Initializing swarm...")
    swarm_result = init_swarm()
    
    # Generate stack file
    print("\n[2/2] Generating stack file...")
    stack_file = generate_stack_file()
    
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print(f"\nStack file: {stack_file}")
    print(f"Swarm status: {swarm_result['status']}")
    print("\nNext: Run deploy_swarm_stack() to deploy services")
    
    return {
        "swarm": swarm_result,
        "stack_file": stack_file
    }


@flow(name="Deploy Swarm Stack")
def deploy_swarm_stack(stack_name: str = "ml-pipeline"):
    """Deploy complete ML pipeline to swarm"""
    
    print("=" * 70)
    print("DEPLOYING TO DOCKER SWARM")
    print("=" * 70)
    
    # Deploy stack
    print("\n[1/3] Deploying stack...")
    deploy_result = deploy_stack(stack_name)
    
    # Wait for services
    print("\n[2/3] Waiting for services...")
    wait_for_stack_ready(stack_name)
    
    # Check status
    print("\n[3/3] Checking services...")
    services = get_stack_services(stack_name)
    
    print("\n" + "=" * 70)
    print("DEPLOYMENT COMPLETE")
    print("=" * 70)
    print(f"\nStack: {stack_name}")
    print(f"Services: {len(services)}")
    
    for service in services:
        print(f"  - {service['Name']}: {service['Replicas']}")
    
    print("\nVisualizer: http://localhost:8080")
    print("=" * 70)
    
    return {
        "stack": stack_name,
        "services": services
    }


@flow(name="Scale Swarm Services")
def scale_swarm_services(stack_name: str = "ml-pipeline"):
    """Scale services based on load"""
    
    print("=" * 70)
    print("SCALING SWARM SERVICES")
    print("=" * 70)
    
    # Scale data processors to 5
    print("\n[1/3] Scaling data-processor to 5 replicas...")
    scale_service(f"{stack_name}_data-processor", 5)
    
    # Scale training service to 3
    print("\n[2/3] Scaling training-service to 3 replicas...")
    scale_service(f"{stack_name}_training-service", 3)
    
    # Scale API to 5 for high availability
    print("\n[3/3] Scaling serving-api to 5 replicas...")
    scale_service(f"{stack_name}_serving-api", 5)
    
    # Check new status
    time.sleep(10)  # Wait for scaling
    services = get_stack_services(stack_name)
    
    print("\n" + "=" * 70)
    print("SCALING COMPLETE")
    print("=" * 70)
    
    for service in services:
        print(f"  - {service['Name']}: {service['Replicas']}")
    
    return services


@flow(name="Swarm ML Pipeline")
def swarm_ml_pipeline(stack_name: str = "ml-pipeline"):
    """Run ML pipeline using swarm services"""
    
    print("=" * 70)
    print("SWARM ML PIPELINE")
    print("=" * 70)
    
    # Stage 1: Data processing (distributed across workers)
    print("\n[STAGE 1: Data Processing]")
    result1 = execute_in_swarm_service(
        f"{stack_name}_data-processor",
        ["python", "-c", "print('Processing data in swarm worker...')"]
    )
    
    # Stage 2: Model training (parallel across nodes)
    print("\n[STAGE 2: Model Training]")
    result2 = execute_in_swarm_service(
        f"{stack_name}_training-service",
        ["python", "-c", "print('Training model in swarm...')"]
    )
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    
    return {
        "processing": result1,
        "training": result2
    }


@flow(name="Cleanup Swarm")
def cleanup_swarm(stack_name: str = "ml-pipeline"):
    """Remove stack and leave swarm"""
    
    print("=" * 70)
    print("CLEANING UP SWARM")
    print("=" * 70)
    
    # Remove stack
    print("\n[1/2] Removing stack...")
    remove_stack(stack_name)
    
    time.sleep(5)
    
    # Leave swarm
    print("\n[2/2] Leaving swarm...")
    leave_swarm()
    
    print("\nCleanup complete")
    
    return {"status": "cleaned"}


# ====================
# MAIN
# ====================

if __name__ == "__main__":
    print("Docker Swarm + Prefect Examples")
    print("=" * 70)
    print("\nDocker Swarm provides:")
    print("  - Multi-node orchestration")
    print("  - Service replication")
    print("  - Load balancing")
    print("  - Rolling updates")
    print("  - High availability")
    print("=" * 70)
    
    # Setup
    print("\n[Running: Setup Swarm]")
    setup_result = setup_swarm()
    print(json.dumps(setup_result, indent=2))
    
    # Deploy
    print("\n[Running: Deploy Stack]")
    deploy_result = deploy_swarm_stack()
    print(json.dumps(deploy_result, indent=2, default=str))
    
    # Optional: Scale services
    scale_result = scale_swarm_services()
    
    # Optional: Run pipeline
    pipeline_result = swarm_ml_pipeline()
    
    # Optional: Cleanup
    cleanup_swarm()