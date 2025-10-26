# Docker + Prefect: Complete Guide

## 📦 Files Overview

### 1. **DOCKER_PREFECT_GUIDE.md** - Comprehensive Guide
[View Guide](computer:///mnt/user-data/outputs/DOCKER_PREFECT_GUIDE.md)

Complete comparison of all approaches for running Docker containers with Prefect:
- Docker Volumes (Named Volumes)
- Bind Mounts (Host Filesystem)
- Prefect Infrastructure Blocks
- Docker Compose
- Cloud Object Storage (S3/GCS)

**Includes:**
- Decision matrix for choosing the right approach
- Pros/cons of each method
- Security considerations
- Performance tips
- Troubleshooting guide

### 2. **docker_prefect_examples.py** - Low-Level Docker API Examples
[View Code](computer:///mnt/user-data/outputs/docker_prefect_examples.py)

Direct Docker SDK examples showing raw container management:

**Examples included:**
- ✅ Docker Volume Pipeline (persistent storage between containers)
- ✅ Bind Mount Pipeline (share data with host)
- ✅ Python Container Pipeline (run Python code in containers)
- ✅ Parallel Container Pipeline (distribute work across containers)
- ✅ Cleanup Utilities (volume management)

**Use when:** You need fine-grained control over Docker containers and want to understand the underlying mechanics.

### 3. **docker_infrastructure_examples.py** - Prefect Infrastructure Blocks
[View Code](computer:///mnt/user-data/outputs/docker_infrastructure_examples.py)

**⭐ RECOMMENDED FOR PRODUCTION**

Uses Prefect's native infrastructure blocks for declarative container configuration:

**Examples included:**
- ✅ Containerized ETL Flow (tasks automatically run in containers)
- ✅ Custom Docker Image Configuration
- ✅ Docker Compose Integration
- ✅ Deployment instructions and templates

**Includes:**
- Infrastructure block setup
- Deployment configuration
- Example Dockerfile
- Docker-compose.yml template
- Complete deployment guide

**Use when:** Deploying to production with Prefect Server/Cloud.

### 4. **ml_pipeline_docker.py** - Real-World ML Pipeline
[View Code](computer:///mnt/user-data/outputs/ml_pipeline_docker.py)

Complete end-to-end ML training pipeline demonstrating:

**Pipeline Stages:**
1. 📥 **Data Extraction** - Pull data from sources
2. 🧹 **Data Preprocessing** - Clean and split data
3. 🔧 **Feature Engineering** - Create features
4. 🎯 **Model Training** - Train ML model in isolated container
5. 📊 **Model Evaluation** - Validate on test set

**Features:**
- Three separate volumes (data, models, artifacts)
- Container isolation per stage
- Model versioning with IDs
- Training metrics tracking
- Volume cleanup utilities

**Use when:** Building ML/data science pipelines with containerized training.

---

## 🚀 Quick Start

### Option 1: Low-Level Docker API (Learning/Development)

```python
from docker_prefect_examples import docker_volume_pipeline

# Run a pipeline using Docker volumes
result = docker_volume_pipeline()
```

### Option 2: Prefect Infrastructure Blocks (Production)

```bash
# 1. Create infrastructure block
python -c "from docker_infrastructure_examples import create_docker_infrastructure_block; create_docker_infrastructure_block()"

# 2. Build deployment
prefect deployment build docker_infrastructure_examples.py:containerized_etl_flow \
  --name "docker-etl" \
  --infrastructure my-docker-container \
  --apply

# 3. Start worker
prefect worker start --pool default-agent-pool

# 4. Run deployment
prefect deployment run 'containerized-etl-flow/docker-etl'
```

### Option 3: ML Pipeline

```python
from ml_pipeline_docker import ml_training_pipeline

# Run complete ML training pipeline
result = ml_training_pipeline(
    data_source="production_db",
    model_name="classifier_v2"
)
```

---

## 📊 Comparison: Which Approach to Use?

| Scenario | Recommended Approach | File |
|----------|---------------------|------|
| **Learning Docker + Prefect** | Low-level Docker API | `docker_prefect_examples.py` |
| **Production Deployment** | Infrastructure Blocks | `docker_infrastructure_examples.py` |
| **ML/AI Pipelines** | ML Pipeline Example | `ml_pipeline_docker.py` |
| **Multi-container Services** | Docker Compose | `docker_infrastructure_examples.py` |
| **Development/Debugging** | Bind Mounts | `docker_prefect_examples.py` |
| **Cloud-native** | Object Storage (S3/GCS) | See guide |

---

## 🎯 Common Use Cases

### Use Case 1: Data Processing Pipeline
**Challenge:** Process large datasets in stages with intermediate storage

**Solution:** Docker Volumes Pipeline
```python
# From docker_prefect_examples.py
docker_volume_pipeline()
```

**Why:** Best performance for I/O operations, data persists between stages

---

### Use Case 2: ML Model Training
**Challenge:** Train models with specific dependencies in isolation

**Solution:** ML Pipeline with Volumes
```python
# From ml_pipeline_docker.py
ml_training_pipeline(model_name="my_model")
```

**Why:** 
- Isolate training environment
- Track artifacts and models separately
- Version control for models

---

### Use Case 3: Production ETL Deployment
**Challenge:** Deploy reliable ETL pipeline to production

**Solution:** Prefect Infrastructure Blocks
```python
# From docker_infrastructure_examples.py
# Use infrastructure blocks with deployment
```

**Why:**
- Declarative configuration
- Environment parity (dev/staging/prod)
- Managed by Prefect
- Automatic retries and monitoring

---

### Use Case 4: Parallel Data Processing
**Challenge:** Process data partitions in parallel

**Solution:** Parallel Container Pipeline
```python
# From docker_prefect_examples.py
parallel_container_pipeline()
```

**Why:**
- Distribute work across containers
- Scale horizontally
- Aggregate results efficiently

---

## 🔧 Prerequisites

### Required Software
```bash
# Docker
docker --version  # Should be 20.10+

# Docker Compose (optional)
docker-compose --version

# Python packages
pip install prefect docker boto3  # boto3 only for cloud storage examples
```

### Docker Setup
```bash
# Start Docker daemon
sudo systemctl start docker

# Test Docker
docker run hello-world

# Create default volumes (optional)
docker volume create prefect-data-volume
docker volume create prefect-model-volume
```

---

## 📝 Best Practices

### 1. Volume Management
```python
# Always clean up volumes when done
@flow
def with_cleanup():
    try:
        # Your pipeline
        result = my_pipeline()
    finally:
        # Cleanup
        cleanup_pipeline_volumes()
```

### 2. Error Handling
```python
@task(retries=3, retry_delay_seconds=5)
def resilient_task():
    # Task with automatic retries
    pass
```

### 3. Resource Limits
```python
# When creating containers, set limits
container = client.containers.run(
    image="...",
    mem_limit="2g",      # 2GB RAM
    cpu_period=100000,
    cpu_quota=50000,     # 50% of one CPU
)
```

### 4. Security
```python
# Use read-only mounts when possible
volumes={
    volume_name: {'bind': '/data', 'mode': 'ro'}  # Read-only
}

# Don't mount sensitive directories
# ❌ Bad: volumes={'/': {'bind': '/host'}}
# ✅ Good: volumes={'/app/data': {'bind': '/data'}}
```

---

## 🐛 Troubleshooting

### Issue: "Volume not found"
```bash
# List all volumes
docker volume ls

# Inspect specific volume
docker volume inspect volume_name

# Create volume manually
docker volume create my-volume
```

### Issue: "Permission denied" on bind mounts
```bash
# Fix permissions (Linux)
sudo chown -R $USER:$USER /path/to/mount

# Or run container with user flag
docker run --user $(id -u):$(id -g) ...
```

### Issue: "Container failed to start"
```bash
# Check Docker logs
docker logs container_id

# Inspect container
docker inspect container_id

# Check image exists
docker images | grep image_name
```

### Issue: Volume cleanup fails
```bash
# Force remove volume
docker volume rm -f volume_name

# Remove all unused volumes
docker volume prune -f
```

---

## 📚 Additional Resources

### Official Documentation
- [Prefect Docs](https://docs.prefect.io)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [Docker Volumes](https://docs.docker.com/storage/volumes/)

### Tutorials
1. Start with `DOCKER_PREFECT_GUIDE.md` for concepts
2. Try `docker_prefect_examples.py` for hands-on learning
3. Read `docker_infrastructure_examples.py` for production patterns
4. Study `ml_pipeline_docker.py` for real-world application

### Community
- [Prefect Slack](https://prefect.io/slack)
- [Prefect Discourse](https://discourse.prefect.io)

---

## 🎓 Learning Path

### Beginner
1. Read `DOCKER_PREFECT_GUIDE.md` (Approach 1 & 2)
2. Run basic examples from `docker_prefect_examples.py`
3. Understand volumes vs. bind mounts

### Intermediate
1. Study `docker_infrastructure_examples.py`
2. Create your first infrastructure block
3. Deploy a simple flow with containers
4. Experiment with parallel execution

### Advanced
1. Study `ml_pipeline_docker.py`
2. Implement multi-stage pipelines
3. Add cloud storage integration
4. Set up production deployments with Prefect Cloud

---

## ⚡ Performance Tips

1. **Use local volumes for I/O intensive tasks**
   - Better performance than bind mounts
   - Managed by Docker

2. **Minimize container startup time**
   - Pre-pull images: `docker pull image_name`
   - Use smaller base images: `alpine` vs `ubuntu`

3. **Cache intermediate results**
   - Use Prefect task caching
   - Store in volumes between runs

4. **Parallel processing**
   - Use `.submit()` for parallel task execution
   - Distribute work across multiple containers

5. **Network optimization**
   - Use `network_mode="host"` for local services
   - Consider Docker networks for container communication

---

## 🚀 Next Steps

After reviewing these examples:

1. **Choose your approach** based on your use case
2. **Start with simple examples** to understand concepts
3. **Build a prototype** pipeline for your specific needs
4. **Add error handling** and monitoring
5. **Deploy to production** using infrastructure blocks
6. **Scale horizontally** by adding more workers

---

## 💡 Tips for Your Use Case

Based on your request for "intermediate data to volumes":

### For ETL Pipelines:
- Use `docker_volume_pipeline()` from `docker_prefect_examples.py`
- Each stage writes to volume, next stage reads from it
- Data persists between container runs

### For ML Pipelines:
- Use `ml_pipeline_docker.py` as template
- Separate volumes for data, models, artifacts
- Easy to version and track model artifacts

### For Production:
- Use infrastructure blocks from `docker_infrastructure_examples.py`
- Declarative configuration
- Easy deployment and scaling

---

**Need help? Check `DOCKER_PREFECT_GUIDE.md` for detailed comparisons and troubleshooting!**