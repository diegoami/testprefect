# Docker + Prefect: Complete Guide to Data Persistence

## Overview

When running Prefect workflows with Docker containers, you have several options for persisting and sharing data between containers. This guide compares all approaches.

## Comparison Table

| Approach | Use Case | Pros | Cons | Complexity |
|----------|----------|------|------|------------|
| **Docker Volumes** | Production pipelines with persistent data | - Data survives container deletion<br>- Best performance<br>- Docker manages storage | - Less portable<br>- Harder to inspect data | Medium |
| **Bind Mounts** | Development, debugging | - Easy access from host<br>- Simple to inspect<br>- Full file system access | - Path dependencies<br>- Permission issues | Low |
| **Prefect Infrastructure Blocks** | Production deployments | - Native Prefect integration<br>- Declarative config<br>- Versioned | - Requires setup<br>- Learning curve | Medium |
| **Docker Compose** | Complex multi-container workflows | - Define entire stack<br>- Service dependencies<br>- Reproducible | - Extra config file<br>- Overhead | Medium-High |
| **Shared Network Storage** | Distributed systems | - Multi-host support<br>- Highly scalable | - Network overhead<br>- Complex setup | High |
| **Object Storage (S3/GCS)** | Cloud-native pipelines | - Unlimited scale<br>- Built-in versioning<br>- Cloud integration | - API latency<br>- Costs | Medium |

---

## Approach 1: Docker Volumes (Named Volumes)

### When to Use
- Production pipelines with intermediate data
- Data that needs to persist between workflow runs
- When you want Docker to manage the storage location

### Example
```python
from prefect import flow, task
import docker

@task
def create_volume():
    client = docker.from_env()
    volume = client.volumes.create(name='pipeline-data')
    return volume.name

@task
def process_in_container(volume_name: str):
    client = docker.from_env()
    container = client.containers.run(
        'python:3.11-slim',
        'python -c "import json; json.dump({\"result\": 42}, open(\"/data/output.json\", \"w\"))"',
        volumes={volume_name: {'bind': '/data', 'mode': 'rw'}},
        detach=True,
        remove=True
    )
    container.wait()
    return container.logs()

@flow
def volume_pipeline():
    vol = create_volume()
    result = process_in_container(vol)
    return result
```

### Pros
- Best I/O performance
- Data persists independently of containers
- Docker manages the storage location
- Works across multiple containers

### Cons
- Data location is abstracted (harder to find)
- Requires cleanup (volumes persist after deletion)
- Less portable across environments

### Best Practices
- Use consistent naming conventions
- Implement cleanup tasks
- Document volume purposes
- Use labels for tracking

---

## Approach 2: Bind Mounts (Host Filesystem)

### When to Use
- Development and testing
- Need to inspect/debug intermediate files
- Want direct access to outputs
- Local file processing

### Example
```python
from prefect import flow, task
from pathlib import Path
import docker

@task
def prepare_workspace(path: str = "/tmp/workflow"):
    workspace = Path(path)
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Create input file
    (workspace / "input.txt").write_text("Hello from host")
    return str(workspace.absolute())

@task
def process_with_bind_mount(host_path: str):
    client = docker.from_env()
    container = client.containers.run(
        'alpine:latest',
        'sh -c "cat /workspace/input.txt && echo \"Processed\" > /workspace/output.txt"',
        volumes={host_path: {'bind': '/workspace', 'mode': 'rw'}},
        detach=True,
        remove=True
    )
    container.wait()
    
    # Can immediately read output on host
    output = Path(host_path) / "output.txt"
    return output.read_text()

@flow
def bind_mount_pipeline():
    workspace = prepare_workspace()
    result = process_with_bind_mount(workspace)
    return result
```

### Pros
- Easy to inspect files during development
- Direct access from host
- No cleanup needed
- Simple to understand

### Cons
- Path must exist on host
- Potential permission issues
- Not portable across systems
- Security considerations in production

### Best Practices
- Use relative paths from project root
- Set appropriate permissions
- Clean up temporary files
- Don't use for production secrets

---

## Approach 3: Prefect Infrastructure Blocks (Recommended for Production)

### When to Use
- Production deployments
- Need declarative configuration
- Want infrastructure-as-code
- Running on Prefect Cloud/Server

### Example
```python
from prefect import flow, task
from prefect.infrastructure import DockerContainer

# Create infrastructure block (run once)
docker_block = DockerContainer(
    image="prefecthq/prefect:2-python3.11",
    volumes=[
        "/opt/prefect/data:/data:rw",
        "/var/log/prefect:/logs:rw"
    ],
    env={"DATA_PATH": "/data"},
    auto_remove=True,
    network_mode="bridge"
)
docker_block.save("production-docker")

# Your tasks run in containers automatically
@task
def extract():
    with open("/data/extracted.json", "w") as f:
        f.write('{"data": "extracted"}')

@task
def transform():
    with open("/data/extracted.json", "r") as f:
        data = f.read()
    with open("/data/transformed.json", "w") as f:
        f.write(data.upper())

@flow
def containerized_flow():
    extract()
    transform()

# Deploy with infrastructure block
# prefect deployment build flow.py:containerized_flow \
#   --name prod-deployment \
#   --infrastructure production-docker \
#   --apply
```

### Pros
- Native Prefect integration
- Version controlled configuration
- Easy to switch environments
- Centralized management
- Automatic container lifecycle

### Cons
- Requires Prefect Server/Cloud
- Initial setup complexity
- Need to understand Prefect deployment model

### Best Practices
- Create separate blocks per environment (dev/staging/prod)
- Use environment variables for configuration
- Version control your block definitions
- Document resource requirements

---

## Approach 4: Docker Compose

### When to Use
- Multi-container workflows with dependencies
- Need service orchestration
- Complex networking requirements
- Stateful services (databases, caches)

### Example

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  extractor:
    image: python:3.11-slim
    volumes:
      - pipeline-data:/data
    command: >
      python -c "
      import json;
      with open('/data/raw.json', 'w') as f:
          json.dump({'source': 'api', 'records': 100}, f)
      "
  
  transformer:
    image: python:3.11-slim
    volumes:
      - pipeline-data:/data
    command: >
      python -c "
      import json;
      with open('/data/raw.json') as f: data = json.load(f);
      data['transformed'] = True;
      with open('/data/processed.json', 'w') as f: json.dump(data, f)
      "
    depends_on:
      - extractor
  
  database:
    image: postgres:15
    volumes:
      - db-data:/var/lib/postgresql/data
    environment:
      POSTGRES_PASSWORD: secret

volumes:
  pipeline-data:
  db-data:
```

**Prefect Flow:**
```python
from prefect import flow, task
import subprocess

@task
def run_docker_compose_service(service: str):
    result = subprocess.run(
        ["docker-compose", "run", "--rm", service],
        capture_output=True
    )
    return result.stdout.decode()

@flow
def compose_pipeline():
    run_docker_compose_service("extractor")
    run_docker_compose_service("transformer")
    return "Pipeline complete"
```

### Pros
- Declarative multi-container setup
- Built-in dependency management
- Easy networking between services
- Reproducible environments

### Cons
- Another config file to maintain
- Can be overkill for simple workflows
- Debugging can be complex

### Best Practices
- Use named volumes for data
- Define clear service dependencies
- Use .env files for configuration
- Include health checks

---

## Approach 5: Cloud Object Storage (S3/GCS/Azure Blob)

### When to Use
- Cloud-native deployments
- Need unlimited scalability
- Multi-region workflows
- Long-term data retention

### Example
```python
from prefect import flow, task
import boto3
import json
from datetime import datetime

@task
def save_to_s3(data: dict, bucket: str, key: str):
    s3 = boto3.client('s3')
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data)
    )
    return f"s3://{bucket}/{key}"

@task
def load_from_s3(bucket: str, key: str):
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(obj['Body'].read())

@task
def process_in_container(input_s3_path: str, output_s3_path: str):
    """
    Container pulls from S3, processes, pushes to S3.
    No local volumes needed!
    """
    import docker
    client = docker.from_env()
    
    container = client.containers.run(
        'my-processing-image:latest',
        environment={
            'INPUT_S3': input_s3_path,
            'OUTPUT_S3': output_s3_path,
            'AWS_ACCESS_KEY_ID': '...',
            'AWS_SECRET_ACCESS_KEY': '...'
        },
        detach=True,
        remove=True
    )
    container.wait()

@flow
def s3_pipeline():
    bucket = "my-pipeline-data"
    
    # Stage 1
    data = {"values": [1, 2, 3, 4, 5]}
    s3_input = save_to_s3(data, bucket, "stage1/input.json")
    
    # Stage 2 - process in container
    s3_output = f"s3://{bucket}/stage2/output.json"
    process_in_container(s3_input, s3_output)
    
    # Stage 3 - load results
    result = load_from_s3(bucket, "stage2/output.json")
    return result
```

### Pros
- Unlimited storage
- Multi-region support
- Built-in versioning and lifecycle policies
- No local disk management
- Perfect for distributed systems

### Cons
- API latency
- Network costs
- Requires cloud credentials
- More complex error handling

### Best Practices
- Use versioning for critical data
- Implement retry logic
- Use multipart uploads for large files
- Tag objects for cost tracking
- Implement lifecycle policies

---

## Decision Matrix

### Choose Docker Volumes when:
✅ Running production pipelines locally or on single host  
✅ Need best I/O performance  
✅ Data needs to persist between runs  
✅ Multiple containers need shared data  

### Choose Bind Mounts when:
✅ Developing and debugging  
✅ Need to inspect intermediate files  
✅ Working with existing file structures  
✅ One-off data processing tasks  

### Choose Prefect Infrastructure Blocks when:
✅ Deploying to production  
✅ Using Prefect Cloud/Server  
✅ Need reproducible infrastructure  
✅ Managing multiple environments  

### Choose Docker Compose when:
✅ Multi-container architectures  
✅ Need service dependencies  
✅ Complex networking requirements  
✅ Including stateful services  

### Choose Cloud Storage when:
✅ Cloud-native architecture  
✅ Need unlimited scale  
✅ Multi-region deployments  
✅ Long-term retention requirements  

---

## Hybrid Approach (Best of All Worlds)

For complex production systems, combine approaches:

```python
from prefect import flow, task
import docker
import boto3

@task
def extract_to_volume(volume_name: str):
    """Extract data to local volume for processing"""
    # Fast local I/O
    pass

@task  
def process_in_container(volume_name: str):
    """Heavy processing with volume mount"""
    # Best performance
    pass

@task
def archive_to_s3(volume_name: str, bucket: str):
    """Archive results to S3 for long-term storage"""
    # Scalable storage
    pass

@flow
def hybrid_pipeline():
    vol = "processing-volume"
    extract_to_volume(vol)
    process_in_container(vol)
    archive_to_s3(vol, "archive-bucket")
```

---

## Security Considerations

### Docker Volumes
- Encrypt volumes for sensitive data
- Use Docker secrets for credentials
- Limit volume access with SELinux/AppArmor

### Bind Mounts
- Never mount root (/) or system directories
- Use read-only mounts when possible
- Be careful with user permissions

### Cloud Storage
- Use IAM roles, not hard-coded credentials
- Enable encryption at rest and in transit
- Implement least-privilege access
- Use VPC endpoints for private access

---

## Troubleshooting

### Volume Issues
```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect volume_name

# Check volume data
docker run --rm -v volume_name:/data alpine ls -la /data

# Remove volume
docker volume rm volume_name
```

### Bind Mount Issues
```bash
# Check permissions
ls -la /host/path

# Fix permissions (Linux)
sudo chown -R $(id -u):$(id -g) /host/path

# Test mount
docker run --rm -v /host/path:/container/path alpine ls -la /container/path
```

### Container Issues
```bash
# View container logs
docker logs container_id

# Inspect container
docker inspect container_id

# Execute command in running container
docker exec -it container_id sh
```

---

## Performance Tips

1. **Use local volumes for I/O intensive operations**
2. **Minimize data transfers between host and container**
3. **Use .dockerignore to reduce build context**
4. **Cache intermediate results when possible**
5. **Use multi-stage builds for smaller images**
6. **Consider RAM disk for temporary files** (`tmpfs`)

---

## Recommended Stack by Use Case

### Data Science Pipeline
- **Extract**: Bind mounts (explore data)
- **Process**: Docker volumes (performance)
- **Archive**: S3 (long-term storage)

### ETL Production
- **Infrastructure**: Prefect blocks
- **Data**: Docker volumes
- **Results**: Database or data warehouse

### ML Training
- **Input data**: S3 or mounted dataset
- **Training artifacts**: Docker volumes
- **Model registry**: S3 + DVC

### CI/CD Testing
- **Test data**: Bind mounts
- **Test results**: Bind mounts
- **Artifacts**: Upload to artifact store