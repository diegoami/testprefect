"""
Advanced: Docker Compose Microservices ML Platform
===================================================

Real-world example of a complete ML platform with:
- API Gateway
- Model Training Service
- Model Serving Service  
- Feature Store
- Monitoring & Metrics
- Message Queue (RabbitMQ)
- Time-series DB (InfluxDB)

Architecture:
  API Gateway → Training Service → Feature Store
              → Serving Service  → Models
              → Monitoring       → Metrics DB
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, List
import docker


@task
def generate_production_compose():
    """Generate production-grade docker-compose.yml"""
    logger = get_run_logger()
    
    compose_content = """version: '3.8'

services:
  # ====================
  # Infrastructure Services
  # ====================
  
  # PostgreSQL - Main database
  postgres:
    image: postgres:15-alpine
    container_name: ml-postgres
    environment:
      POSTGRES_USER: mluser
      POSTGRES_PASSWORD: mlpassword
      POSTGRES_DB: mlplatform
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks:
      - ml-network
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U mluser"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis - Caching & Session
  redis:
    image: redis:7-alpine
    container_name: ml-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - ml-network
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  # RabbitMQ - Message Queue
  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: ml-rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: admin
    ports:
      - "5672:5672"   # AMQP
      - "15672:15672" # Management UI
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
    networks:
      - ml-network
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 5
    restart: unless-stopped

  # InfluxDB - Time-series metrics
  influxdb:
    image: influxdb:2-alpine
    container_name: ml-influxdb
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: adminpassword
      DOCKER_INFLUXDB_INIT_ORG: ml-org
      DOCKER_INFLUXDB_INIT_BUCKET: metrics
      DOCKER_INFLUXDB_INIT_ADMIN_TOKEN: my-super-secret-token
    ports:
      - "8086:8086"
    volumes:
      - influxdb-data:/var/lib/influxdb2
    networks:
      - ml-network
    restart: unless-stopped

  # MinIO - S3-compatible object storage
  minio:
    image: minio/minio:latest
    container_name: ml-minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"   # API
      - "9001:9001"   # Console
    volumes:
      - minio-data:/data
    networks:
      - ml-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    restart: unless-stopped

  # ====================
  # ML Platform Services
  # ====================

  # Feature Store Service
  feature-store:
    image: python:3.11-slim
    container_name: ml-feature-store
    working_dir: /app
    volumes:
      - ./services/feature-store:/app
      - feature-data:/data
    environment:
      DATABASE_URL: postgresql://mluser:mlpassword@postgres:5432/mlplatform
      REDIS_URL: redis://redis:6379
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    networks:
      - ml-network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: |
      bash -c "pip install psycopg2-binary redis minio && python -m http.server 8001"
    restart: unless-stopped

  # Training Service (with GPU support option)
  training-service:
    image: tensorflow/tensorflow:latest
    # For GPU: image: tensorflow/tensorflow:latest-gpu
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: 1
    #           capabilities: [gpu]
    container_name: ml-training-service
    working_dir: /app
    volumes:
      - ./services/training:/app
      - model-data:/models
      - training-data:/data
    environment:
      DATABASE_URL: postgresql://mluser:mlpassword@postgres:5432/mlplatform
      RABBITMQ_URL: amqp://admin:admin@rabbitmq:5672
      MINIO_ENDPOINT: minio:9000
      FEATURE_STORE_URL: http://feature-store:8001
      INFLUXDB_URL: http://influxdb:8086
      INFLUXDB_TOKEN: my-super-secret-token
    networks:
      - ml-network
    depends_on:
      - postgres
      - rabbitmq
      - feature-store
    command: tail -f /dev/null
    restart: unless-stopped

  # Model Serving Service
  serving-service:
    image: tensorflow/serving:latest
    container_name: ml-serving-service
    ports:
      - "8501:8501"  # REST API
      - "8500:8500"  # gRPC
    volumes:
      - model-data:/models
    environment:
      MODEL_NAME: default_model
      MODEL_BASE_PATH: /models
    networks:
      - ml-network
    depends_on:
      - training-service
    restart: unless-stopped

  # API Gateway
  api-gateway:
    image: python:3.11-slim
    container_name: ml-api-gateway
    working_dir: /app
    ports:
      - "8080:8080"
    volumes:
      - ./services/gateway:/app
    environment:
      DATABASE_URL: postgresql://mluser:mlpassword@postgres:5432/mlplatform
      REDIS_URL: redis://redis:6379
      TRAINING_SERVICE_URL: http://training-service:8000
      SERVING_SERVICE_URL: http://serving-service:8501
      FEATURE_STORE_URL: http://feature-store:8001
    networks:
      - ml-network
    depends_on:
      - postgres
      - redis
      - training-service
      - serving-service
    command: |
      bash -c "pip install fastapi uvicorn && python -m uvicorn app:app --host 0.0.0.0 --port 8080"
    restart: unless-stopped

  # Monitoring Service
  monitoring:
    image: python:3.11-slim
    container_name: ml-monitoring
    working_dir: /app
    volumes:
      - ./services/monitoring:/app
    environment:
      INFLUXDB_URL: http://influxdb:8086
      INFLUXDB_TOKEN: my-super-secret-token
      INFLUXDB_ORG: ml-org
      INFLUXDB_BUCKET: metrics
      RABBITMQ_URL: amqp://admin:admin@rabbitmq:5672
    networks:
      - ml-network
    depends_on:
      - influxdb
      - rabbitmq
    command: tail -f /dev/null
    restart: unless-stopped

  # Grafana - Metrics visualization
  grafana:
    image: grafana/grafana:latest
    container_name: ml-grafana
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_INSTALL_PLUGINS: grafana-influxdb-datasource
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - ml-network
    depends_on:
      - influxdb
    restart: unless-stopped

networks:
  ml-network:
    name: ml-platform-network
    driver: bridge

volumes:
  postgres-data:
  redis-data:
  rabbitmq-data:
  influxdb-data:
  minio-data:
  feature-data:
  model-data:
  training-data:
  grafana-data:
"""
    
    # Create compose directory
    compose_dir = Path("compose-ml-platform")
    compose_dir.mkdir(exist_ok=True)
    
    # Write compose file
    compose_file = compose_dir / "docker-compose.yml"
    compose_file.write_text(compose_content)
    
    logger.info(f"Generated production compose file: {compose_file}")
    return str(compose_file)


@task
def generate_service_code():
    """Generate code for each microservice"""
    logger = get_run_logger()
    
    base_dir = Path("compose-ml-platform/services")
    base_dir.mkdir(exist_ok=True, parents=True)
    
    # Feature Store Service
    feature_store_code = '''
"""Feature Store Service"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class FeatureStoreHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/features":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            features = {
                "feature_groups": ["user_features", "item_features"],
                "status": "ready"
            }
            self.wfile.write(json.dumps(features).encode())
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8001), FeatureStoreHandler)
    print("Feature Store running on port 8001")
    server.serve_forever()
'''
    
    # Training Service
    training_service_code = '''
"""Training Service"""
import json
import time
from pathlib import Path

def train_model(config):
    """Train ML model"""
    print(f"Starting training with config: {config}")
    
    # Simulate training
    for epoch in range(5):
        print(f"Epoch {epoch + 1}/5")
        time.sleep(1)
    
    model_id = f"model_{int(time.time())}"
    model_path = f"/models/{model_id}"
    
    # Save model metadata
    Path(model_path).mkdir(exist_ok=True)
    metadata = {
        "model_id": model_id,
        "accuracy": 0.95,
        "trained_at": time.time()
    }
    
    with open(f"{model_path}/metadata.json", "w") as f:
        json.dump(metadata, f)
    
    print(f"Model trained: {model_id}")
    return model_id

if __name__ == "__main__":
    config = {"learning_rate": 0.001, "epochs": 5}
    train_model(config)
'''
    
    # API Gateway
    gateway_code = '''
"""API Gateway"""
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ML Platform API")

class TrainingRequest(BaseModel):
    dataset: str
    config: dict

class PredictionRequest(BaseModel):
    features: list

@app.get("/")
def root():
    return {"service": "ML Platform API Gateway", "status": "running"}

@app.post("/train")
def train(request: TrainingRequest):
    return {
        "status": "training_started",
        "dataset": request.dataset,
        "job_id": "job_12345"
    }

@app.post("/predict")
def predict(request: PredictionRequest):
    return {
        "prediction": 0.85,
        "confidence": 0.92
    }

@app.get("/models")
def list_models():
    return {
        "models": [
            {"id": "model_1", "status": "active"},
            {"id": "model_2", "status": "training"}
        ]
    }
'''
    
    # Monitoring Service
    monitoring_code = '''
"""Monitoring Service"""
import time
import random
import json

def collect_metrics():
    """Collect and report metrics"""
    while True:
        metrics = {
            "timestamp": time.time(),
            "training_jobs": random.randint(0, 10),
            "active_models": random.randint(5, 15),
            "predictions_per_sec": random.randint(100, 1000),
            "cpu_usage": random.uniform(20, 80),
            "memory_usage": random.uniform(30, 70)
        }
        
        print(f"Metrics: {json.dumps(metrics)}")
        time.sleep(10)

if __name__ == "__main__":
    print("Monitoring service started")
    collect_metrics()
'''
    
    # Write service files
    services = {
        "feature-store/app.py": feature_store_code,
        "training/train.py": training_service_code,
        "gateway/app.py": gateway_code,
        "monitoring/monitor.py": monitoring_code,
    }
    
    for path, code in services.items():
        file_path = base_dir / path
        file_path.parent.mkdir(exist_ok=True, parents=True)
        file_path.write_text(code)
        logger.info(f"Generated service: {file_path}")
    
    return list(services.keys())


@task
def start_platform(detach: bool = True):
    """Start the entire ML platform"""
    logger = get_run_logger()
    
    compose_dir = Path("compose-ml-platform")
    
    logger.info("Starting ML Platform services...")
    cmd = ["docker-compose", "up", "-d"] if detach else ["docker-compose", "up"]
    
    result = subprocess.run(
        cmd,
        cwd=compose_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Platform started successfully")
        logger.info(result.stdout)
    else:
        logger.error(f"Failed to start platform: {result.stderr}")
        raise Exception(result.stderr)
    
    return {"status": "started"}


@task
def wait_for_platform(timeout: int = 120):
    """Wait for platform services to be ready"""
    logger = get_run_logger()
    client = docker.from_env()
    
    critical_services = ["ml-postgres", "ml-redis", "ml-rabbitmq"]
    start_time = time.time()
    
    logger.info("Waiting for critical services...")
    
    while time.time() - start_time < timeout:
        all_ready = True
        
        for service in critical_services:
            try:
                container = client.containers.get(service)
                if container.status != "running":
                    all_ready = False
                    logger.info(f"Waiting for {service}...")
                    break
                
                # Check health if available
                health = container.attrs.get('State', {}).get('Health', {}).get('Status')
                if health and health != 'healthy':
                    all_ready = False
                    logger.info(f"{service} not healthy yet: {health}")
                    break
                    
            except docker.errors.NotFound:
                all_ready = False
                logger.info(f"Service {service} not found")
                break
        
        if all_ready:
            logger.info("All critical services are ready!")
            return True
        
        time.sleep(5)
    
    raise TimeoutError(f"Platform did not start within {timeout} seconds")


@task
def get_platform_status():
    """Get status of all platform services"""
    logger = get_run_logger()
    client = docker.from_env()
    
    services = [
        "ml-postgres", "ml-redis", "ml-rabbitmq", "ml-influxdb",
        "ml-minio", "ml-feature-store", "ml-training-service",
        "ml-serving-service", "ml-api-gateway", "ml-monitoring", "ml-grafana"
    ]
    
    status = {}
    for service in services:
        try:
            container = client.containers.get(service)
            status[service] = {
                "status": container.status,
                "health": container.attrs.get('State', {}).get('Health', {}).get('Status', 'N/A'),
                "ports": container.attrs.get('NetworkSettings', {}).get('Ports', {})
            }
        except docker.errors.NotFound:
            status[service] = {"status": "not_found"}
    
    logger.info(f"Platform status:\n{json.dumps(status, indent=2)}")
    return status


@task
def test_api_gateway():
    """Test the API Gateway"""
    logger = get_run_logger()
    
    import requests
    
    try:
        response = requests.get("http://localhost:8080/", timeout=5)
        logger.info(f"API Gateway response: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to connect to API Gateway: {e}")
        return {"error": str(e)}


@task
def stop_platform(remove_volumes: bool = False):
    """Stop the ML platform"""
    logger = get_run_logger()
    
    compose_dir = Path("compose-ml-platform")
    
    cmd = ["docker-compose", "down"]
    if remove_volumes:
        cmd.append("-v")
    
    logger.info("Stopping ML Platform...")
    result = subprocess.run(
        cmd,
        cwd=compose_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Platform stopped successfully")
    else:
        logger.error(f"Failed to stop platform: {result.stderr}")
    
    return {"status": "stopped"}


# ====================
# FLOWS
# ====================

@flow(name="Setup ML Platform")
def setup_ml_platform():
    """Setup complete ML platform with microservices"""
    
    print("=" * 70)
    print("SETTING UP ML PLATFORM")
    print("=" * 70)
    
    # Generate compose file
    print("\n[1/2] Generating docker-compose.yml...")
    compose_file = generate_production_compose()
    
    # Generate service code
    print("\n[2/2] Generating service code...")
    services = generate_service_code()
    
    print(f"\nSetup complete!")
    print(f"Compose file: {compose_file}")
    print(f"Services: {len(services)}")
    print("\nTo start the platform, run: docker-compose up -d")
    
    return {
        "compose_file": compose_file,
        "services": services
    }


@flow(name="Start ML Platform")
def start_ml_platform():
    """Start the complete ML platform"""
    
    print("=" * 70)
    print("STARTING ML PLATFORM")
    print("=" * 70)
    
    # Start services
    print("\n[1/3] Starting services...")
    start_platform()
    
    # Wait for readiness
    print("\n[2/3] Waiting for services...")
    wait_for_platform()
    
    # Check status
    print("\n[3/3] Checking status...")
    status = get_platform_status()
    
    print("\n" + "=" * 70)
    print("ML PLATFORM RUNNING")
    print("=" * 70)
    print("\nAccess points:")
    print("  - API Gateway:    http://localhost:8080")
    print("  - Grafana:        http://localhost:3000 (admin/admin)")
    print("  - RabbitMQ UI:    http://localhost:15672 (admin/admin)")
    print("  - MinIO Console:  http://localhost:9001 (minioadmin/minioadmin)")
    print("=" * 70)
    
    return status


@flow(name="ML Platform Health Check")
def platform_health_check():
    """Check health of all platform components"""
    
    print("=" * 70)
    print("PLATFORM HEALTH CHECK")
    print("=" * 70)
    
    status = get_platform_status()
    
    # Test API
    print("\nTesting API Gateway...")
    api_status = test_api_gateway()
    
    # Summary
    total = len(status)
    running = sum(1 for s in status.values() if s.get('status') == 'running')
    
    print(f"\nStatus: {running}/{total} services running")
    
    return {
        "services": status,
        "api": api_status,
        "health": "healthy" if running == total else "degraded"
    }


# ====================
# MAIN
# ====================

if __name__ == "__main__":
    print("ML Platform with Docker Compose")
    print("=" * 70)
    print("\nThis will create a production-grade ML platform with:")
    print("  - PostgreSQL, Redis, RabbitMQ, InfluxDB, MinIO")
    print("  - Feature Store, Training Service, Serving Service")
    print("  - API Gateway, Monitoring, Grafana")
    print("=" * 70)
    
    # Setup
    setup_result = setup_ml_platform()
    print(f"\nSetup result: {json.dumps(setup_result, indent=2)}")
    
    # Start (comment out if you want to start manually)
    # start_result = start_ml_platform()
    # print(f"\nPlatform started: {json.dumps(start_result, indent=2)}")