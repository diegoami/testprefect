# Docker Compose + Prefect: Complete Guide

## Overview

Docker Compose is perfect for orchestrating multi-container applications with Prefect. This guide covers two approaches:

1. **Basic ML Pipeline** - Simple multi-stage pipeline with volumes
2. **Production Platform** - Complete microservices architecture

---

## 📦 Files Provided

### 1. [docker_compose_prefect.py](computer:///mnt/user-data/outputs/docker_compose_prefect.py)
**Basic Docker Compose + Prefect Pipeline**

**What it includes:**
- PostgreSQL database
- Redis cache
- Data preprocessing service
- Model training service
- Model serving API
- Prefect orchestration

**Best for:**
- Learning Docker Compose with Prefect
- Simple ML pipelines
- Development environments

### 2. [docker_compose_advanced.py](computer:///mnt/user-data/outputs/docker_compose_advanced.py)
**Production-Grade ML Platform**

**What it includes:**
- **Infrastructure:** PostgreSQL, Redis, RabbitMQ, InfluxDB, MinIO
- **ML Services:** Feature Store, Training Service, Serving Service
- **Platform:** API Gateway, Monitoring, Grafana dashboard
- **Volumes:** Persistent data, models, metrics

**Best for:**
- Production deployments
- Microservices architecture
- Teams with multiple services

---

## 🚀 Quick Start

### Option 1: Basic Pipeline

```bash
# 1. Download the file
cd ~/projects/github/testprefect

# 2. Run the setup
python docker_compose_prefect.py

# This will:
# - Create compose-pipeline/ directory
# - Generate docker-compose.yml
# - Create service scripts
# - Start all services
# - Run the ML pipeline
```

### Option 2: Production Platform

```bash
# 1. Download the file
cd ~/projects/github/testprefect

# 2. Run the setup
python docker_compose_advanced.py

# This creates a full platform with 11 services!
```

---

## 📋 What Docker Compose Does

### Advantages Over Single Containers

**Before (Individual Containers):**
```bash
docker run postgres...
docker run redis...
docker run my-app...
# Hard to manage, no automatic networking
```

**After (Docker Compose):**
```yaml
services:
  postgres:
    image: postgres:15
  redis:
    image: redis:7
  my-app:
    depends_on: [postgres, redis]
# All services start together, networked automatically
```

### Key Benefits

1. **One Command to Rule Them All**
   ```bash
   docker-compose up    # Start everything
   docker-compose down  # Stop everything
   ```

2. **Automatic Networking**
   - Services can reach each other by name
   - `postgres:5432` works automatically

3. **Dependency Management**
   - Services start in correct order
   - Wait for health checks

4. **Volume Persistence**
   - Data survives restarts
   - Shared across services

5. **Environment Configuration**
   - Central configuration
   - Environment-specific settings

---

## 🏗️ Architecture Patterns

### Pattern 1: ETL Pipeline

```
┌─────────────┐
│   Source    │
│  Database   │
└──────┬──────┘
       │
       ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Extract    │───▶│  Transform  │───▶│    Load     │
│  Service    │    │   Service   │    │  Service    │
└─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Prefect   │
                    │ Orchestrator│
                    └─────────────┘
```

### Pattern 2: Microservices ML Platform

```
                    ┌──────────────┐
                    │ API Gateway  │
                    └───────┬──────┘
                            │
           ┌────────────────┼────────────────┐
           │                │                │
           ▼                ▼                ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Feature  │   │ Training  │   │  Serving  │
    │   Store   │   │  Service  │   │  Service  │
    └─────┬─────┘   └─────┬─────┘   └─────┬─────┘
          │               │               │
          └───────────────┼───────────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
              ▼                       ▼
       ┌──────────┐           ┌──────────┐
       │PostgreSQL│           │  MinIO   │
       │   (DB)   │           │(Storage) │
       └──────────┘           └──────────┘
```

---

## 🎯 Example Use Cases

### Use Case 1: ML Training Pipeline

**docker-compose.yml:**
```yaml
services:
  postgres:
    image: postgres:15
    volumes:
      - db-data:/var/lib/postgresql/data
  
  preprocessing:
    image: python:3.11
    volumes:
      - pipeline-data:/data
    depends_on:
      - postgres
  
  training:
    image: tensorflow/tensorflow:latest
    volumes:
      - pipeline-data:/data
      - models:/models
    depends_on:
      - preprocessing
```

**Prefect Flow:**
```python
@flow
def ml_pipeline():
    # Services are already running via compose
    preprocess_result = run_in_service("preprocessing", "preprocess.py")
    train_result = run_in_service("training", "train.py")
    return train_result
```

### Use Case 2: Data Processing Pipeline

**Services:**
- **Ingestion:** Fetch data from APIs
- **Validation:** Check data quality
- **Transformation:** Clean and transform
- **Loading:** Store in database

**Prefect orchestrates:** When to run each service, handle failures, retry logic

### Use Case 3: Real-time Inference

**Services:**
- **API Gateway:** Receive requests
- **Feature Service:** Fetch features
- **Model Service:** Run predictions
- **Cache (Redis):** Store results

**Prefect monitors:** Service health, performance metrics, alerts

---

## 🔧 Common Patterns

### Pattern: Execute Command in Service

```python
@task
def run_in_service(service_name: str, script: str):
    """Execute script inside a running compose service"""
    client = docker.from_env()
    container = client.containers.get(service_name)
    
    exit_code, output = container.exec_run(
        ["python", script]
    )
    
    return output.decode('utf-8')
```

### Pattern: Wait for Service Health

```python
@task
def wait_for_service(service_name: str, timeout: int = 60):
    """Wait for service to be healthy"""
    client = docker.from_env()
    start = time.time()
    
    while time.time() - start < timeout:
        try:
            container = client.containers.get(service_name)
            health = container.attrs['State']['Health']['Status']
            
            if health == 'healthy':
                return True
        except:
            pass
        
        time.sleep(2)
    
    raise TimeoutError(f"{service_name} not healthy")
```

### Pattern: Service-to-Service Communication

```python
@task
def trigger_training_via_api():
    """Trigger training through API Gateway"""
    import requests
    
    response = requests.post(
        "http://localhost:8080/train",
        json={"dataset": "production_data"}
    )
    
    return response.json()
```

---

## 📊 Monitoring & Observability

### Built-in Services

**InfluxDB + Grafana:**
```python
@task
def log_metrics(metrics: dict):
    """Log metrics to InfluxDB"""
    from influxdb_client import InfluxDBClient
    
    client = InfluxDBClient(
        url="http://localhost:8086",
        token="my-token",
        org="ml-org"
    )
    
    write_api = client.write_api()
    write_api.write(
        bucket="metrics",
        record=metrics
    )
```

**View in Grafana:**
- Navigate to `http://localhost:3000`
- Login: admin/admin
- Create dashboards from InfluxDB data

### RabbitMQ for Async Tasks

```python
@task
def queue_training_job(job_config: dict):
    """Queue training job for async processing"""
    import pika
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters('localhost')
    )
    channel = connection.channel()
    channel.queue_declare(queue='training_jobs')
    
    channel.basic_publish(
        exchange='',
        routing_key='training_jobs',
        body=json.dumps(job_config)
    )
    
    connection.close()
```

---

## 🛠️ Development Workflow

### 1. Local Development

```bash
# Start services
docker-compose up -d

# Develop your code
vim services/training/train.py

# Test immediately (hot reload)
docker-compose restart training

# View logs
docker-compose logs -f training
```

### 2. Testing

```python
@flow
def integration_test():
    """Test all services together"""
    
    # Start services
    compose_up()
    
    # Run tests
    test_feature_store()
    test_training_service()
    test_api_gateway()
    
    # Cleanup
    compose_down()
```

### 3. Staging Deployment

```bash
# Use environment-specific compose file
docker-compose -f docker-compose.staging.yml up -d

# Run prefect flows against staging
python run_staging_pipeline.py
```

---

## 🚦 Best Practices

### 1. Health Checks

Always define health checks:
```yaml
services:
  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### 2. Restart Policies

```yaml
services:
  api:
    restart: unless-stopped  # Auto-restart on failure
```

### 3. Resource Limits

```yaml
services:
  training:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
```

### 4. Network Isolation

```yaml
networks:
  frontend:  # Public-facing services
  backend:   # Internal services only
```

### 5. Secrets Management

```yaml
services:
  api:
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

---

## 🔄 Common Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v

# View logs
docker-compose logs -f [service_name]

# Restart service
docker-compose restart [service_name]

# Scale service
docker-compose up -d --scale worker=3

# Execute command in service
docker-compose exec [service_name] bash

# Rebuild service
docker-compose build [service_name]

# View status
docker-compose ps
```

---

## 📚 Complete Examples

### Example 1: Run Basic Pipeline

```bash
# Download and run
cd ~/projects/github/testprefect
python docker_compose_prefect.py

# Services will start:
# - PostgreSQL (port 5432)
# - Redis (port 6379)
# - Preprocessor service
# - Trainer service
# - API service

# Pipeline will execute:
# 1. Generate sample data
# 2. Preprocess in container
# 3. Train model in container
# 4. Deploy to API
```

### Example 2: Production Platform

```bash
# Download and setup
cd ~/projects/github/testprefect
python docker_compose_advanced.py

# This creates 11 services:
# - PostgreSQL, Redis, RabbitMQ
# - InfluxDB, MinIO, Grafana
# - Feature Store, Training, Serving
# - API Gateway, Monitoring

# Access dashboards:
# - Grafana: http://localhost:3000
# - RabbitMQ: http://localhost:15672
# - MinIO: http://localhost:9001
# - API: http://localhost:8080
```

---

## 🆚 When to Use What

### Use Docker Compose When:
- ✅ Multi-service applications
- ✅ Development environments
- ✅ Testing with dependencies
- ✅ Small-to-medium deployments
- ✅ Single-host deployments

### Use Kubernetes When:
- ✅ Large-scale production
- ✅ Multi-host clusters
- ✅ Auto-scaling needed
- ✅ Complex routing
- ✅ Advanced orchestration

### Use Single Containers When:
- ✅ One-off tasks
- ✅ Simple scripts
- ✅ No dependencies
- ✅ Testing individual components

---

## 🎓 Learning Path

1. **Start Here:** [docker_compose_prefect.py](computer:///mnt/user-data/outputs/docker_compose_prefect.py)
   - Learn basic compose
   - Simple ML pipeline
   - Service communication

2. **Then Try:** [docker_compose_advanced.py](computer:///mnt/user-data/outputs/docker_compose_advanced.py)
   - Production patterns
   - Microservices
   - Monitoring & metrics

3. **Next Steps:**
   - Add your own services
   - Implement CI/CD
   - Deploy to cloud

---

## 🐛 Troubleshooting

### Service won't start
```bash
# Check logs
docker-compose logs [service_name]

# Check if port is in use
netstat -tulpn | grep [port]

# Restart service
docker-compose restart [service_name]
```

### Can't connect between services
```bash
# Check network
docker-compose exec [service] ping [other_service]

# Verify service is running
docker-compose ps

# Check compose file network config
```

### Volume issues
```bash
# Reset volumes (WARNING: deletes data)
docker-compose down -v

# Inspect volume
docker volume inspect [volume_name]

# Manual cleanup
docker volume prune
```

---

## 🎉 Summary

Docker Compose + Prefect is powerful for:

1. **Multi-service ML pipelines**
2. **Microservices orchestration**
3. **Development environments**
4. **Integration testing**
5. **Small-to-medium production deployments**

**Key advantages:**
- Simple YAML configuration
- One command to start everything
- Automatic service networking
- Easy local development
- Production-ready patterns

**Get started:**
1. Download the example files
2. Run `python docker_compose_prefect.py`
3. Experiment with the patterns
4. Build your own pipeline!

Happy composing! 🐳🎼