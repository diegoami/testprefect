"""
MicroK8s + Prefect: Kubernetes ML Pipeline
===========================================

MicroK8s is a lightweight Kubernetes distribution perfect for:
- Local development
- Edge computing
- CI/CD
- IoT
- Small production deployments

Advantages over Docker Swarm:
- Full Kubernetes API
- Rich ecosystem (Helm, operators, etc.)
- Better resource management
- Advanced networking (NetworkPolicies)
- StatefulSets for stateful workloads
- Job and CronJob support
- Namespace isolation

This example shows how to:
1. Deploy ML pipeline to MicroK8s
2. Use Kubernetes Jobs for training
3. Scale deployments
4. Manage secrets and ConfigMaps
5. Use persistent volumes
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import subprocess
import time
import json
import yaml
from pathlib import Path
from typing import Dict, List, Optional


# ====================
# MICROK8S MANAGEMENT
# ====================

@task
def check_microk8s():
    """Check if MicroK8s is installed and running"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["microk8s", "status", "--format", "short"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(f"MicroK8s status: {result.stdout}")
        return {"status": "running", "output": result.stdout}
    else:
        logger.warning("MicroK8s not running or not installed")
        logger.info("Install with: sudo snap install microk8s --classic")
        return {"status": "not_running"}


@task
def enable_microk8s_addons(addons: List[str]):
    """Enable MicroK8s addons"""
    logger = get_run_logger()
    
    for addon in addons:
        logger.info(f"Enabling addon: {addon}")
        result = subprocess.run(
            ["microk8s", "enable", addon],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info(f"Enabled: {addon}")
        else:
            logger.error(f"Failed to enable {addon}: {result.stderr}")
    
    return {"addons": addons}


# ====================
# KUBERNETES MANIFESTS
# ====================

@task
def generate_k8s_manifests():
    """Generate Kubernetes YAML manifests"""
    logger = get_run_logger()
    
    manifests_dir = Path("k8s-manifests")
    manifests_dir.mkdir(exist_ok=True)
    
    # Namespace
    namespace_yaml = """
apiVersion: v1
kind: Namespace
metadata:
  name: ml-pipeline
  labels:
    name: ml-pipeline
"""
    
    # ConfigMap
    configmap_yaml = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: ml-config
  namespace: ml-pipeline
data:
  DATABASE_URL: "postgresql://mluser:mlpassword@postgres:5432/mlpipeline"
  REDIS_URL: "redis://redis:6379"
  MODEL_PATH: "/models"
  DATA_PATH: "/data"
"""
    
    # Secret
    secret_yaml = """
apiVersion: v1
kind: Secret
metadata:
  name: ml-secrets
  namespace: ml-pipeline
type: Opaque
stringData:
  db-password: "mlpassword"
  redis-password: "redispassword"
"""
    
    # PostgreSQL Deployment
    postgres_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: ml-pipeline
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        env:
        - name: POSTGRES_USER
          value: "mluser"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ml-secrets
              key: db-password
        - name: POSTGRES_DB
          value: "mlpipeline"
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
          requests:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: ml-pipeline
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
"""
    
    # Redis Deployment
    redis_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: ml-pipeline
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
          requests:
            memory: "256Mi"
            cpu: "250m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: ml-pipeline
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
  type: ClusterIP
"""
    
    # Training Job (Kubernetes Job)
    training_job_yaml = """
apiVersion: batch/v1
kind: Job
metadata:
  name: ml-training-job
  namespace: ml-pipeline
spec:
  template:
    metadata:
      labels:
        app: training
    spec:
      restartPolicy: OnFailure
      containers:
      - name: trainer
        image: tensorflow/tensorflow:latest
        command: ["python", "-c"]
        args:
        - |
          import time
          import json
          print("Starting training job...")
          for epoch in range(5):
              print(f"Epoch {epoch + 1}/5")
              time.sleep(2)
          print("Training complete!")
          
          # Save model metadata
          with open('/models/model_metadata.json', 'w') as f:
              json.dump({'status': 'trained', 'accuracy': 0.95}, f)
        envFrom:
        - configMapRef:
            name: ml-config
        volumeMounts:
        - name: data-storage
          mountPath: /data
        - name: model-storage
          mountPath: /models
        resources:
          limits:
            memory: "4Gi"
            cpu: "2000m"
          requests:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: data-storage
        persistentVolumeClaim:
          claimName: data-pvc
      - name: model-storage
        persistentVolumeClaim:
          claimName: model-pvc
"""
    
    # Serving Deployment (with HPA)
    serving_yaml = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving
  namespace: ml-pipeline
spec:
  replicas: 3
  selector:
    matchLabels:
      app: model-serving
  template:
    metadata:
      labels:
        app: model-serving
    spec:
      containers:
      - name: serving
        image: python:3.11-slim
        command: ["sh", "-c"]
        args:
        - |
          pip install fastapi uvicorn && 
          python -c "
          from fastapi import FastAPI
          import uvicorn
          app = FastAPI()
          @app.get('/')
          def root():
              return {'service': 'model-serving', 'status': 'ready'}
          @app.post('/predict')
          def predict(data: dict):
              return {'prediction': 0.95, 'model': 'v1'}
          uvicorn.run(app, host='0.0.0.0', port=8000)
          "
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: ml-config
        volumeMounts:
        - name: model-storage
          mountPath: /models
          readOnly: true
        resources:
          limits:
            memory: "1Gi"
            cpu: "1000m"
          requests:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: model-serving
  namespace: ml-pipeline
spec:
  selector:
    app: model-serving
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving-hpa
  namespace: ml-pipeline
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: model-serving
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
"""
    
    # PersistentVolumeClaims
    pvc_yaml = """
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: ml-pipeline
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
  namespace: ml-pipeline
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: model-pvc
  namespace: ml-pipeline
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 5Gi
"""
    
    # Write manifests
    manifests = {
        "01-namespace.yaml": namespace_yaml,
        "02-configmap.yaml": configmap_yaml,
        "03-secret.yaml": secret_yaml,
        "04-pvc.yaml": pvc_yaml,
        "05-postgres.yaml": postgres_yaml,
        "06-redis.yaml": redis_yaml,
        "07-training-job.yaml": training_job_yaml,
        "08-serving.yaml": serving_yaml,
    }
    
    for filename, content in manifests.items():
        filepath = manifests_dir / filename
        filepath.write_text(content)
        logger.info(f"Generated: {filepath}")
    
    return {"manifests_dir": str(manifests_dir), "files": list(manifests.keys())}


# ====================
# KUBECTL OPERATIONS
# ====================

@task
def kubectl_apply(manifest_path: str):
    """Apply Kubernetes manifest"""
    logger = get_run_logger()
    
    logger.info(f"Applying: {manifest_path}")
    
    result = subprocess.run(
        ["microk8s", "kubectl", "apply", "-f", manifest_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(result.stdout)
        return {"status": "applied", "output": result.stdout}
    else:
        logger.error(f"Failed to apply: {result.stderr}")
        raise Exception(result.stderr)


@task
def kubectl_delete(manifest_path: str):
    """Delete Kubernetes resources"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["microk8s", "kubectl", "delete", "-f", manifest_path],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Resources deleted")
        return {"status": "deleted"}
    else:
        logger.warning(f"Delete warning: {result.stderr}")
        return {"status": "warning"}


@task
def get_pods(namespace: str = "ml-pipeline"):
    """Get pods in namespace"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        pods_data = json.loads(result.stdout)
        pods = pods_data.get('items', [])
        
        logger.info(f"Found {len(pods)} pods")
        for pod in pods:
            name = pod['metadata']['name']
            status = pod['status']['phase']
            logger.info(f"  - {name}: {status}")
        
        return pods
    else:
        return []


@task
def get_services(namespace: str = "ml-pipeline"):
    """Get services in namespace"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["microk8s", "kubectl", "get", "svc", "-n", namespace, "-o", "json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        svc_data = json.loads(result.stdout)
        services = svc_data.get('items', [])
        
        logger.info(f"Found {len(services)} services")
        for svc in services:
            name = svc['metadata']['name']
            svc_type = svc['spec']['type']
            logger.info(f"  - {name} ({svc_type})")
        
        return services
    else:
        return []


@task
def scale_deployment(deployment: str, replicas: int, namespace: str = "ml-pipeline"):
    """Scale a deployment"""
    logger = get_run_logger()
    
    logger.info(f"Scaling {deployment} to {replicas} replicas")
    
    result = subprocess.run(
        ["microk8s", "kubectl", "scale", "deployment", deployment,
         f"--replicas={replicas}", "-n", namespace],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info("Deployment scaled")
        return {"status": "scaled", "replicas": replicas}
    else:
        logger.error(f"Failed to scale: {result.stderr}")
        raise Exception(result.stderr)


@task
def create_job(job_name: str, namespace: str = "ml-pipeline"):
    """Create/trigger a Kubernetes Job"""
    logger = get_run_logger()
    
    job_yaml = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {job_name}
  namespace: {namespace}
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
      - name: worker
        image: python:3.11-slim
        command: ["python", "-c", "print('Job {job_name} executed!'); import time; time.sleep(5); print('Done!')"]
"""
    
    # Write temporary job file
    job_file = Path(f"/tmp/{job_name}.yaml")
    job_file.write_text(job_yaml)
    
    result = subprocess.run(
        ["microk8s", "kubectl", "apply", "-f", str(job_file)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(f"Job {job_name} created")
        return {"status": "created", "job": job_name}
    else:
        logger.error(f"Failed to create job: {result.stderr}")
        raise Exception(result.stderr)


@task
def wait_for_job_completion(job_name: str, namespace: str = "ml-pipeline", timeout: int = 300):
    """Wait for a job to complete"""
    logger = get_run_logger()
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        result = subprocess.run(
            ["microk8s", "kubectl", "get", "job", job_name, "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            job_data = json.loads(result.stdout)
            status = job_data.get('status', {})
            
            succeeded = status.get('succeeded', 0)
            failed = status.get('failed', 0)
            
            if succeeded > 0:
                logger.info(f"Job {job_name} completed successfully")
                return {"status": "succeeded"}
            elif failed > 0:
                logger.error(f"Job {job_name} failed")
                return {"status": "failed"}
            else:
                logger.info(f"Job {job_name} still running...")
        
        time.sleep(5)
    
    raise TimeoutError(f"Job {job_name} did not complete within {timeout} seconds")


@task
def get_pod_logs(pod_name: str, namespace: str = "ml-pipeline"):
    """Get logs from a pod"""
    logger = get_run_logger()
    
    result = subprocess.run(
        ["microk8s", "kubectl", "logs", pod_name, "-n", namespace],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        logger.info(f"Logs for {pod_name}:\n{result.stdout}")
        return result.stdout
    else:
        logger.error(f"Failed to get logs: {result.stderr}")
        return ""


# ====================
# MAIN FLOWS
# ====================

@flow(name="Setup MicroK8s Pipeline")
def setup_microk8s_pipeline():
    """Setup ML pipeline on MicroK8s"""
    
    print("=" * 70)
    print("SETTING UP MICROK8S ML PIPELINE")
    print("=" * 70)
    
    # Check MicroK8s
    print("\n[1/3] Checking MicroK8s...")
    status = check_microk8s()
    
    if status['status'] != 'running':
        print("\nMicroK8s is not running!")
        print("Install with: sudo snap install microk8s --classic")
        print("Then run: microk8s status --wait-ready")
        return {"error": "microk8s_not_running"}
    
    # Enable addons
    print("\n[2/3] Enabling addons...")
    enable_microk8s_addons(["dns", "storage", "metrics-server"])
    
    # Generate manifests
    print("\n[3/3] Generating Kubernetes manifests...")
    manifests = generate_k8s_manifests()
    
    print("\n" + "=" * 70)
    print("SETUP COMPLETE")
    print("=" * 70)
    print(f"\nManifests directory: {manifests['manifests_dir']}")
    print(f"Generated {len(manifests['files'])} manifest files")
    print("\nNext: Run deploy_to_microk8s() to deploy")
    
    return manifests


@flow(name="Deploy to MicroK8s")
def deploy_to_microk8s():
    """Deploy ML pipeline to MicroK8s"""
    
    print("=" * 70)
    print("DEPLOYING TO MICROK8S")
    print("=" * 70)
    
    manifests_dir = Path("k8s-manifests")
    
    if not manifests_dir.exists():
        print("Manifests not found. Run setup_microk8s_pipeline() first")
        return {"error": "manifests_not_found"}
    
    # Apply manifests in order
    manifest_files = sorted(manifests_dir.glob("*.yaml"))
    
    for i, manifest_file in enumerate(manifest_files, 1):
        print(f"\n[{i}/{len(manifest_files)}] Applying {manifest_file.name}...")
        kubectl_apply(str(manifest_file))
        time.sleep(2)
    
    # Wait for pods
    print("\n[Waiting for pods to be ready...]")
    time.sleep(10)
    
    # Check status
    print("\n[Checking deployment status...]")
    pods = get_pods()
    services = get_services()
    
    print("\n" + "=" * 70)
    print("DEPLOYMENT COMPLETE")
    print("=" * 70)
    print(f"\nPods: {len(pods)}")
    print(f"Services: {len(services)}")
    print("\nAccess serving API:")
    print("  microk8s kubectl port-forward svc/model-serving 8000:80 -n ml-pipeline")
    print("  Then visit: http://localhost:8000")
    print("=" * 70)
    
    return {
        "pods": len(pods),
        "services": len(services)
    }


@flow(name="Run Training Job")
def run_training_job():
    """Run ML training as Kubernetes Job"""
    
    print("=" * 70)
    print("RUNNING TRAINING JOB")
    print("=" * 70)
    
    job_name = f"training-{int(time.time())}"
    
    print(f"\n[1/3] Creating job: {job_name}")
    create_job(job_name)
    
    print("\n[2/3] Waiting for completion...")
    result = wait_for_job_completion(job_name)
    
    print("\n[3/3] Getting job logs...")
    # Get pod for this job
    pods = get_pods()
    job_pod = next((p for p in pods if job_name in p['metadata']['name']), None)
    
    if job_pod:
        logs = get_pod_logs(job_pod['metadata']['name'])
    
    print("\n" + "=" * 70)
    print("TRAINING JOB COMPLETE")
    print("=" * 70)
    
    return result


@flow(name="Scale MicroK8s Services")
def scale_microk8s_services():
    """Scale services on MicroK8s"""
    
    print("=" * 70)
    print("SCALING SERVICES")
    print("=" * 70)
    
    print("\n[Scaling model-serving to 5 replicas...]")
    scale_deployment("model-serving", 5)
    
    time.sleep(10)
    
    pods = get_pods()
    
    print("\n" + "=" * 70)
    print("SCALING COMPLETE")
    print("=" * 70)
    print(f"\nTotal pods: {len(pods)}")
    
    return {"pods": len(pods)}


@flow(name="Cleanup MicroK8s")
def cleanup_microk8s():
    """Remove all resources from MicroK8s"""
    
    print("=" * 70)
    print("CLEANING UP MICROK8S")
    print("=" * 70)
    
    # Delete namespace (cascades to all resources)
    result = subprocess.run(
        ["microk8s", "kubectl", "delete", "namespace", "ml-pipeline"],
        capture_output=True,
        text=True
    )
    
    print("\nNamespace deleted")
    print("Cleanup complete")
    
    return {"status": "cleaned"}


# ====================
# MAIN
# ====================

if __name__ == "__main__":
    print("MicroK8s + Prefect ML Pipeline")
    print("=" * 70)
    print("\nMicroK8s provides:")
    print("  - Full Kubernetes API")
    print("  - Lightweight (runs on laptop)")
    print("  - Production-grade features")
    print("  - Easy local development")
    print("=" * 70)
    
    # Setup
    print("\n[Running: Setup]")
    setup_result = setup_microk8s_pipeline()
    
    if 'error' not in setup_result:
        # Deploy
        print("\n[Running: Deploy]")
        deploy_result = deploy_to_microk8s()
        
        # Optional: Run training
        # run_training_job()
        
        # Optional: Scale
        # scale_microk8s_services()
    
    # Optional: Cleanup
    # cleanup_microk8s()