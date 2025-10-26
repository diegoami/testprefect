"""
Docker Compose + Prefect: Multi-Container ML Pipeline
======================================================

This example demonstrates using Docker Compose to orchestrate:
- Multiple service containers (database, cache, preprocessing, training)
- Prefect flows that coordinate these services
- Persistent volumes for data and models
- Networks for inter-service communication

Use cases:
1. Microservices-based ML pipeline
2. Multi-stage data processing with different dependencies
3. Services that need to communicate (e.g., training service + monitoring service)
4. Development/staging environments with all dependencies
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import docker
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
import requests


# ====================
# CONFIGURATION
# ====================

class ComposeConfig:
    """Configuration for Docker Compose pipeline"""
    
    # Paths
    COMPOSE_FILE = "docker-compose.yml"
    COMPOSE_DIR = Path.cwd() / "compose-pipeline"
    
    # Service names (from docker-compose.yml)
    POSTGRES_SERVICE = "postgres"
    REDIS_SERVICE = "redis"
    PREPROCESSOR_SERVICE = "preprocessor"
    TRAINER_SERVICE = "trainer"
    API_SERVICE = "api"
    
    # Network
    NETWORK_NAME = "ml-pipeline-network"
    
    # Volumes
    DATA_VOLUME = "pipeline-data"
    MODELS_VOLUME = "pipeline-models"
    POSTGRES_VOLUME = "pipeline-postgres"


# ====================
# DOCKER COMPOSE MANAGEMENT
# ====================

@task
def create_compose_directory():
    """Create directory structure for Docker Compose project"""
    logger = get_run_logger()
    
    compose_dir = ComposeConfig.COMPOSE_DIR
    compose_dir.mkdir(exist_ok=True)
    
    # Create subdirectories
    (compose_dir / "services").mkdir(exist_ok=True)
    (compose_dir / "services" / "preprocessor").mkdir(exist_ok=True)
    (compose_dir / "services" / "trainer").mkdir(exist_ok=True)
    (compose_dir / "services" / "api").mkdir(exist_ok=True)
    
    logger.info(f"Created compose directory: {compose_dir}")
    return str(compose_dir)


@task
def generate_compose_file():
    """Generate docker-compose.yml file"""
    logger = get_run_logger()
    
    compose_content = """version: '3.8'

services:
  # PostgreSQL database for storing metadata
  postgres:
    image: postgres:15-alpine
    container_name: ml-postgres
    environment:
      POSTGRES_USER: mluser
      POSTGRES_PASSWORD: mlpassword
      POSTGRES_DB: mlpipeline
    ports:
      - "5432:5432"
    volumes:
      - pipeline-postgres:/var/lib/postgresql/data
    networks:
      - ml-pipeline-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mluser"]
      interval: 5s
      timeout: 5s
      retries: 5

  # Redis for caching and job queue
  redis:
    image: redis:7-alpine
    container_name: ml-redis
    ports:
      - "6379:6379"
    networks:
      - ml-pipeline-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # Data preprocessing service
  preprocessor:
    image: python:3.11-slim
    container_name: ml-preprocessor
    working_dir: /app
    volumes:
      - pipeline-data:/data
      - ./services/preprocessor:/app
    environment:
      - DATABASE_URL=postgresql://mluser:mlpassword@postgres:5432/mlpipeline
      - REDIS_URL=redis://redis:6379
    networks:
      - ml-pipeline-network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: tail -f /dev/null  # Keep container running

  # Model training service
  trainer:
    image: tensorflow/tensorflow:latest
    container_name: ml-trainer
    working_dir: /app
    volumes:
      - pipeline-data:/data:ro
      - pipeline-models:/models
      - ./services/trainer:/app
    environment:
      - DATABASE_URL=postgresql://mluser:mlpassword@postgres:5432/mlpipeline
      - REDIS_URL=redis://redis:6379
    networks:
      - ml-pipeline-network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: tail -f /dev/null  # Keep container running

  # Model serving API
  api:
    image: python:3.11-slim
    container_name: ml-api
    working_dir: /app
    ports:
      - "8000:8000"
    volumes:
      - pipeline-models:/models:ro
      - ./services/api:/app
    environment:
      - DATABASE_URL=postgresql://mluser:mlpassword@postgres:5432/mlpipeline
      - MODEL_PATH=/models
    networks:
      - ml-pipeline-network
    depends_on:
      - postgres
      - redis
    command: tail -f /dev/null  # Keep container running

networks:
  ml-pipeline-network:
    name: ml-pipeline-network
    driver: bridge

volumes:
  pipeline-data:
    name: pipeline-data
  pipeline-models:
    name: pipeline-models
  pipeline-postgres:
    name: pipeline-postgres
"""
    
    compose_file = ComposeConfig.COMPOSE_DIR / "docker-compose.yml"
    compose_file.write_text(compose_content)
    
    logger.info(f"Generated compose file: {compose_file}")
    return str(compose_file)


@task
def generate_service_scripts():
    """Generate Python scripts for each service"""
    logger = get_run_logger()
    
    # Preprocessor service script
    preprocessor_script = '''
import json
import time
import sys
from pathlib import Path

def preprocess_data(input_file, output_file):
    """Preprocess raw data"""
    print(f"Preprocessing {input_file}...")
    
    # Load data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Simulate preprocessing
    processed = {
        'processed_at': time.time(),
        'samples': data.get('samples', []),
        'preprocessing': 'completed'
    }
    
    # Save processed data
    with open(output_file, 'w') as f:
        json.dump(processed, f, indent=2)
    
    print(f"Preprocessing complete: {output_file}")
    return output_file

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else "/data/raw_data.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "/data/processed_data.json"
    preprocess_data(input_file, output_file)
'''
    
    # Trainer service script
    trainer_script = '''
import json
import time
import sys
from pathlib import Path

def train_model(data_file, model_file):
    """Train ML model"""
    print(f"Training model with {data_file}...")
    
    # Load processed data
    with open(data_file, 'r') as f:
        data = json.load(f)
    
    # Simulate training
    model = {
        'model_id': str(int(time.time())),
        'trained_at': time.time(),
        'training_samples': len(data.get('samples', [])),
        'accuracy': 0.95,
        'model_type': 'classifier'
    }
    
    # Save model
    with open(model_file, 'w') as f:
        json.dump(model, f, indent=2)
    
    print(f"Model trained: {model_file}")
    print(f"Accuracy: {model['accuracy']}")
    return model_file

if __name__ == "__main__":
    data_file = sys.argv[1] if len(sys.argv) > 1 else "/data/processed_data.json"
    model_file = sys.argv[2] if len(sys.argv) > 2 else "/models/model.json"
    train_model(data_file, model_file)
'''
    
    # API service script
    api_script = '''
import json
from pathlib import Path

def serve_model(model_path="/models/model.json"):
    """Serve model predictions"""
    print(f"Loading model from {model_path}...")
    
    if Path(model_path).exists():
        with open(model_path, 'r') as f:
            model = json.load(f)
        print(f"Model loaded: {model.get('model_id')}")
        print(f"Accuracy: {model.get('accuracy')}")
        return model
    else:
        print("No model found")
        return None

if __name__ == "__main__":
    serve_model()
'''
    
    # Write scripts
    scripts = {
        'services/preprocessor/preprocess.py': preprocessor_script,
        'services/trainer/train.py': trainer_script,
        'services/api/serve.py': api_script,
    }
    
    for path, content in scripts.items():
        file_path = ComposeConfig.COMPOSE_DIR / path
        file_path.write_text(content)
        logger.info(f"Created service script: {file_path}")
    
    return list(scripts.keys())


@task
def compose_up(detach: bool = True):
    """Start Docker Compose services"""
    logger = get_run_logger()
    
    compose_dir = ComposeConfig.COMPOSE_DIR
    
    cmd = ["docker-compose", "up"]
    if detach:
        cmd.append("-d")
    
    logger.info("Starting Docker Compose services...")
    result = subprocess.run(
        cmd,
        cwd=compose_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Services started successfully")
        logger.info(result.stdout)
    else:
        logger.error(f"Failed to start services: {result.stderr}")
        raise Exception(result.stderr)
    
    return {"status": "started", "services": ["postgres", "redis", "preprocessor", "trainer", "api"]}


@task
def compose_down(remove_volumes: bool = False):
    """Stop Docker Compose services"""
    logger = get_run_logger()
    
    compose_dir = ComposeConfig.COMPOSE_DIR
    
    cmd = ["docker-compose", "down"]
    if remove_volumes:
        cmd.append("-v")
    
    logger.info("Stopping Docker Compose services...")
    result = subprocess.run(
        cmd,
        cwd=compose_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Services stopped successfully")
    else:
        logger.error(f"Failed to stop services: {result.stderr}")
    
    return {"status": "stopped"}


@task
def wait_for_services(timeout: int = 30):
    """Wait for all services to be healthy"""
    logger = get_run_logger()
    client = docker.from_env()
    
    services = ["ml-postgres", "ml-redis"]
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        all_healthy = True
        
        for service_name in services:
            try:
                container = client.containers.get(service_name)
                health = container.attrs.get('State', {}).get('Health', {}).get('Status')
                
                if health != 'healthy':
                    all_healthy = False
                    logger.info(f"Waiting for {service_name} (status: {health})...")
                    break
            except docker.errors.NotFound:
                all_healthy = False
                logger.info(f"Waiting for {service_name} to start...")
                break
        
        if all_healthy:
            logger.info("All services are healthy!")
            return True
        
        time.sleep(2)
    
    raise TimeoutError(f"Services did not become healthy within {timeout} seconds")


@task
def get_service_status():
    """Get status of all compose services"""
    logger = get_run_logger()
    client = docker.from_env()
    
    services = ["ml-postgres", "ml-redis", "ml-preprocessor", "ml-trainer", "ml-api"]
    status = {}
    
    for service_name in services:
        try:
            container = client.containers.get(service_name)
            status[service_name] = {
                "status": container.status,
                "health": container.attrs.get('State', {}).get('Health', {}).get('Status', 'N/A')
            }
        except docker.errors.NotFound:
            status[service_name] = {"status": "not_found"}
    
    logger.info(f"Service status: {json.dumps(status, indent=2)}")
    return status


# ====================
# PIPELINE TASKS USING COMPOSE SERVICES
# ====================

@task
def execute_in_service(service_name: str, command: List[str]):
    """Execute command in a running compose service"""
    logger = get_run_logger()
    client = docker.from_env()
    
    try:
        container = client.containers.get(service_name)
        
        logger.info(f"Executing in {service_name}: {' '.join(command)}")
        
        exit_code, output = container.exec_run(command)
        output_text = output.decode('utf-8')
        
        logger.info(f"Output:\n{output_text}")
        
        return {
            "service": service_name,
            "exit_code": exit_code,
            "output": output_text
        }
    except docker.errors.NotFound:
        logger.error(f"Service {service_name} not found")
        raise


@task
def generate_sample_data():
    """Generate sample data in the data volume"""
    logger = get_run_logger()
    
    sample_data = {
        "dataset": "sample_training_data",
        "samples": [
            {"features": [0.1, 0.2, 0.3], "label": 1},
            {"features": [0.4, 0.5, 0.6], "label": 0},
            {"features": [0.7, 0.8, 0.9], "label": 1},
        ] * 100  # 300 samples
    }
    
    # Write data using preprocessor service
    result = execute_in_service(
        "ml-preprocessor",
        ["python", "-c", f"import json; json.dump({json.dumps(sample_data)}, open('/data/raw_data.json', 'w'))"]
    )
    
    logger.info("Sample data generated")
    return result


@task
def run_preprocessing():
    """Run preprocessing in the preprocessor service"""
    logger = get_run_logger()
    
    result = execute_in_service(
        "ml-preprocessor",
        ["python", "/app/preprocess.py", "/data/raw_data.json", "/data/processed_data.json"]
    )
    
    return result


@task
def run_training():
    """Run model training in the trainer service"""
    logger = get_run_logger()
    
    result = execute_in_service(
        "ml-trainer",
        ["python", "/app/train.py", "/data/processed_data.json", "/models/model.json"]
    )
    
    return result


@task
def deploy_model():
    """Deploy model to API service"""
    logger = get_run_logger()
    
    result = execute_in_service(
        "ml-api",
        ["python", "/app/serve.py"]
    )
    
    return result


# ====================
# MAIN PIPELINE FLOWS
# ====================

@flow(name="Docker Compose Setup")
def setup_compose_environment():
    """Set up Docker Compose environment"""
    
    print("=" * 70)
    print("SETTING UP DOCKER COMPOSE ENVIRONMENT")
    print("=" * 70)
    
    # Create directory structure
    compose_dir = create_compose_directory()
    
    # Generate compose file and service scripts
    compose_file = generate_compose_file()
    scripts = generate_service_scripts()
    
    print("\nGenerated files:")
    print(f"  - Compose file: {compose_file}")
    print(f"  - Service scripts: {len(scripts)}")
    
    return {
        "compose_dir": compose_dir,
        "compose_file": compose_file,
        "scripts": scripts
    }


@flow(name="Docker Compose ML Pipeline")
def compose_ml_pipeline():
    """Complete ML pipeline using Docker Compose services"""
    
    print("\n" + "=" * 70)
    print("DOCKER COMPOSE ML PIPELINE")
    print("=" * 70)
    
    # Start services
    print("\n[STEP 1: Starting services]")
    compose_up()
    
    # Wait for services to be ready
    print("\n[STEP 2: Waiting for services]")
    wait_for_services()
    
    # Check status
    print("\n[STEP 3: Service status]")
    status = get_service_status()
    
    # Generate sample data
    print("\n[STEP 4: Generating sample data]")
    generate_sample_data()
    
    # Run preprocessing
    print("\n[STEP 5: Running preprocessing]")
    preprocess_result = run_preprocessing()
    
    # Run training
    print("\n[STEP 6: Running training]")
    training_result = run_training()
    
    # Deploy model
    print("\n[STEP 7: Deploying model]")
    deploy_result = deploy_model()
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    
    return {
        "status": "completed",
        "services": status,
        "results": {
            "preprocessing": preprocess_result,
            "training": training_result,
            "deployment": deploy_result
        }
    }


@flow(name="Docker Compose Cleanup")
def cleanup_compose():
    """Clean up Docker Compose environment"""
    
    print("\n" + "=" * 70)
    print("CLEANING UP DOCKER COMPOSE")
    print("=" * 70)
    
    result = compose_down(remove_volumes=True)
    
    print("Cleanup complete")
    return result


# ====================
# ADVANCED: MULTI-STAGE PIPELINE
# ====================

@flow(name="Advanced Multi-Stage Pipeline")
def advanced_compose_pipeline():
    """
    Advanced pipeline with multiple stages and service coordination
    """
    
    print("\n" + "=" * 70)
    print("ADVANCED MULTI-STAGE PIPELINE")
    print("=" * 70)
    
    # Start services
    compose_up()
    wait_for_services()
    
    # Stage 1: Data ingestion (parallel)
    print("\n[STAGE 1: Data Ingestion]")
    data_sources = ["source_a", "source_b", "source_c"]
    ingestion_futures = []
    
    for source in data_sources:
        future = generate_sample_data.submit()
        ingestion_futures.append(future)
    
    # Wait for all ingestion to complete
    ingestion_results = [f.result() for f in ingestion_futures]
    
    # Stage 2: Preprocessing (sequential)
    print("\n[STAGE 2: Preprocessing]")
    preprocess_result = run_preprocessing()
    
    # Stage 3: Training (with monitoring)
    print("\n[STAGE 3: Training with Monitoring]")
    training_result = run_training()
    
    # Stage 4: Validation
    print("\n[STAGE 4: Model Validation]")
    validation_result = execute_in_service(
        "ml-trainer",
        ["python", "-c", "print('Model validation: PASSED')"]
    )
    
    # Stage 5: Deployment
    print("\n[STAGE 5: Deployment]")
    deploy_result = deploy_model()
    
    print("\n" + "=" * 70)
    print("ADVANCED PIPELINE COMPLETE")
    print("=" * 70)
    
    return {
        "status": "completed",
        "stages": {
            "ingestion": len(ingestion_results),
            "preprocessing": "completed",
            "training": "completed",
            "validation": "passed",
            "deployment": "completed"
        }
    }


# ====================
# UTILITY FLOWS
# ====================

@flow(name="View Compose Logs")
def view_compose_logs(service: Optional[str] = None):
    """View logs from Docker Compose services"""
    logger = get_run_logger()
    
    compose_dir = ComposeConfig.COMPOSE_DIR
    
    cmd = ["docker-compose", "logs"]
    if service:
        cmd.append(service)
    
    result = subprocess.run(
        cmd,
        cwd=compose_dir,
        capture_output=True,
        text=True
    )
    
    logger.info(f"Logs:\n{result.stdout}")
    return result.stdout


# ====================
# MAIN
# ====================

if __name__ == "__main__":
    print("Docker Compose + Prefect Examples")
    print("=" * 70)
    print("Choose an option:")
    print("1. Setup Compose Environment")
    print("2. Run Complete ML Pipeline")
    print("3. Run Advanced Multi-Stage Pipeline")
    print("4. Cleanup")
    print("=" * 70)
    
    # Example 1: Setup
    print("\n[Running: Setup Compose Environment]")
    setup_result = setup_compose_environment()
    print(json.dumps(setup_result, indent=2))
    
    # Example 2: Run pipeline
    print("\n[Running: Complete ML Pipeline]")
    pipeline_result = compose_ml_pipeline()
    print(json.dumps(pipeline_result, indent=2))
    
    # Optional: Cleanup
    # cleanup_compose()