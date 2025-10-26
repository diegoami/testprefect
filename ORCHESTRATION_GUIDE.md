# Container Orchestration Evolution Guide
## Docker Compose → Swarm → Stack → Kubernetes (MicroK8s)

## 📊 Quick Comparison Table

| Feature | Compose | Swarm | Stack | MicroK8s/K8s |
|---------|---------|-------|-------|--------------|
| **Complexity** | ⭐ Simple | ⭐⭐ Easy | ⭐⭐ Easy | ⭐⭐⭐⭐ Complex |
| **Multi-Host** | ❌ No | ✅ Yes | ✅ Yes | ✅ Yes |
| **Scaling** | Manual | Auto | Auto | Auto + HPA |
| **Load Balancing** | ❌ No | ✅ Yes | ✅ Yes | ✅ Advanced |
| **Rolling Updates** | ❌ No | ✅ Yes | ✅ Yes | ✅ Advanced |
| **Health Checks** | ✅ Basic | ✅ Good | ✅ Good | ✅ Advanced |
| **Secrets** | ❌ No | ✅ Yes | ✅ Yes | ✅ Advanced |
| **Storage** | Volumes | Volumes | Volumes | PV/PVC/StorageClass |
| **Networking** | Bridge | Overlay | Overlay | CNI Plugins |
| **Ecosystem** | Small | Small | Small | **Huge** |
| **Production** | Dev Only | Small | Small-Med | All Sizes |

---

## 🎯 When to Use What

### Use Docker Compose When:
```
✅ Single-host deployment
✅ Development environment
✅ Simple multi-container apps
✅ Learning Docker
✅ Quick prototypes
✅ CI/CD testing

❌ Need multi-host
❌ Need auto-scaling
❌ Production at scale
```

### Use Docker Swarm When:
```
✅ Easy multi-host orchestration
✅ Simple production deployments
✅ Docker-native solution
✅ Small-to-medium scale
✅ Don't want K8s complexity
✅ Fast setup needed

❌ Need advanced features
❌ Large-scale deployments
❌ Complex networking needs
❌ Need rich ecosystem
```

### Use Docker Stack When:
```
✅ = Docker Swarm (same thing!)
Stack is just Swarm with compose-like files
docker stack deploy = deploy to Swarm
```

### Use MicroK8s/Kubernetes When:
```
✅ Production at any scale
✅ Advanced orchestration
✅ Rich ecosystem needed
✅ Complex requirements
✅ Multi-cloud deployments
✅ Advanced networking
✅ StatefulSets needed
✅ CronJobs/Jobs needed
✅ Need operators/helm

❌ Just learning containers
❌ Simple use cases
❌ Want quick setup
```

---

## 🔄 Migration Path

### Level 1: Docker Compose (Starting Point)
```yaml
# docker-compose.yml
services:
  web:
    image: myapp:latest
    ports:
      - "8080:8080"
```

**Pros:** Dead simple, fast
**Cons:** Single host only

---

### Level 2: Docker Swarm/Stack (Add Multi-Host)
```yaml
# docker-stack.yml (same format!)
services:
  web:
    image: myapp:latest
    ports:
      - "8080:8080"
    deploy:              # ← Only addition!
      replicas: 3        # Scale to 3 instances
      update_config:
        parallelism: 1   # Rolling updates
```

**Command:**
```bash
# Initialize swarm
docker swarm init

# Deploy (same file as compose!)
docker stack deploy -c docker-stack.yml myapp
```

**Pros:** Easy upgrade from Compose, multi-host
**Cons:** Limited features vs K8s

---

### Level 3: MicroK8s/Kubernetes (Full Power)
```yaml
# deployment.yaml (different format)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: web
        image: myapp:latest
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

**Command:**
```bash
# Install MicroK8s
sudo snap install microk8s --classic

# Deploy
microk8s kubectl apply -f deployment.yaml
```

**Pros:** All features, huge ecosystem, production-ready
**Cons:** Steeper learning curve

---

## 📁 Files Provided

### 1. [docker_compose_prefect.py](computer:///mnt/user-data/outputs/docker_compose_prefect.py)
**Level:** Beginner
**Use for:** Single-host ML pipelines

### 2. [docker_compose_advanced.py](computer:///mnt/user-data/outputs/docker_compose_advanced.py)
**Level:** Intermediate  
**Use for:** Full-featured local platform

### 3. [docker_swarm_prefect.py](computer:///mnt/user-data/outputs/docker_swarm_prefect.py)
**Level:** Intermediate
**Use for:** Multi-host without K8s complexity

### 4. [microk8s_prefect.py](computer:///mnt/user-data/outputs/microk8s_prefect.py)
**Level:** Advanced
**Use for:** Production-grade deployments

---

## 🚀 Quick Start Guides

### Quick Start: Docker Compose
```bash
cd ~/projects/github/testprefect

# Run example
python docker_compose_prefect.py

# Services start on single host
# Perfect for development!
```

---

### Quick Start: Docker Swarm
```bash
# 1. Setup
python docker_swarm_prefect.py

# This will:
# - Initialize swarm
# - Generate docker-stack.yml
# - Deploy services across nodes

# 2. View services
docker service ls

# 3. Scale a service
docker service scale ml-pipeline_training-service=5

# 4. View in browser (visualizer)
http://localhost:8080
```

**Key Swarm Commands:**
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-stack.yml mystack

# List stacks
docker stack ls

# List services in stack
docker stack services mystack

# Scale service
docker service scale mystack_web=5

# Remove stack
docker stack rm mystack

# Leave swarm
docker swarm leave --force
```

---

### Quick Start: MicroK8s
```bash
# 1. Install MicroK8s
sudo snap install microk8s --classic

# 2. Wait for ready
microk8s status --wait-ready

# 3. Enable addons
microk8s enable dns storage metrics-server

# 4. Run example
python microk8s_prefect.py

# This will:
# - Generate Kubernetes manifests
# - Deploy to MicroK8s
# - Create deployments, services, jobs

# 5. View resources
microk8s kubectl get all -n ml-pipeline

# 6. Access service
microk8s kubectl port-forward svc/model-serving 8000:80 -n ml-pipeline
```

**Key kubectl Commands:**
```bash
# Get resources
microk8s kubectl get pods -n ml-pipeline
microk8s kubectl get services -n ml-pipeline
microk8s kubectl get deployments -n ml-pipeline

# Describe resource
microk8s kubectl describe pod <pod-name> -n ml-pipeline

# Logs
microk8s kubectl logs <pod-name> -n ml-pipeline

# Execute in pod
microk8s kubectl exec -it <pod-name> -n ml-pipeline -- bash

# Scale deployment
microk8s kubectl scale deployment model-serving --replicas=5 -n ml-pipeline

# Delete resources
microk8s kubectl delete -f manifest.yaml
```

---

## 🏗️ Architecture Comparison

### Docker Compose Architecture
```
┌─────────────────────────────────────┐
│         Single Host (Docker)        │
│                                     │
│  ┌──────────┐  ┌──────────┐        │
│  │ Service1 │  │ Service2 │        │
│  └──────────┘  └──────────┘        │
│                                     │
│       Bridge Network                │
│       Local Volumes                 │
└─────────────────────────────────────┘
```

### Docker Swarm Architecture
```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Node 1    │  │   Node 2    │  │   Node 3    │
│  (Manager)  │  │  (Worker)   │  │  (Worker)   │
│             │  │             │  │             │
│ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │
│ │Service  │ │  │ │Service  │ │  │ │Service  │ │
│ │Replica 1│ │  │ │Replica 2│ │  │ │Replica 3│ │
│ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                   Overlay Network
              Load Balanced Ingress
```

### Kubernetes (MicroK8s) Architecture
```
┌─────────────────────────────────────────────────┐
│              Control Plane                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │API Server│ │Scheduler │ │Controller│       │
│  └──────────┘ └──────────┘ └──────────┘       │
└────────────────────┬────────────────────────────┘
                     │
    ┌────────────────┼────────────────┐
    │                │                │
┌───▼────┐      ┌───▼────┐      ┌───▼────┐
│ Node 1 │      │ Node 2 │      │ Node 3 │
│        │      │        │      │        │
│ ┌────┐ │      │ ┌────┐ │      │ ┌────┐ │
│ │Pod │ │      │ │Pod │ │      │ │Pod │ │
│ │ 1  │ │      │ │ 2  │ │      │ │ 3  │ │
│ └────┘ │      │ └────┘ │      │ └────┘ │
│        │      │        │      │        │
│ Kubelet│      │ Kubelet│      │ Kubelet│
└────────┘      └────────┘      └────────┘
     │               │               │
     └───────────────┼───────────────┘
             CNI Network Plugin
          Services & Ingress Controllers
```

---

## 🎯 Feature Deep Dive

### Scaling Comparison

**Compose:**
```bash
# Manual only
docker-compose up --scale web=3
```

**Swarm:**
```bash
# Declarative scaling
docker service scale mystack_web=5

# Or in stack file:
deploy:
  replicas: 5
```

**Kubernetes:**
```bash
# Declarative
kubectl scale deployment web --replicas=5

# Auto-scaling (HPA)
kubectl autoscale deployment web --min=3 --max=10 --cpu-percent=70
```

---

### Updates Comparison

**Compose:**
```bash
# Stop everything, update, restart
docker-compose down
docker-compose pull
docker-compose up -d
# = Downtime!
```

**Swarm:**
```bash
# Rolling update (zero downtime)
docker service update --image myapp:v2 mystack_web

# Or configure in stack:
deploy:
  update_config:
    parallelism: 2      # Update 2 at a time
    delay: 10s          # Wait 10s between
    order: start-first  # Start new before stopping old
```

**Kubernetes:**
```bash
# Rolling update (zero downtime)
kubectl set image deployment/web web=myapp:v2

# Or:
kubectl apply -f deployment.yaml  # Declarative

# Rollback if needed
kubectl rollout undo deployment/web

# Configure in manifest:
spec:
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

---

### Networking Comparison

**Compose:**
- Bridge network (single host)
- Services reach each other by name
- Port mapping for external access

**Swarm:**
- Overlay network (multi-host)
- Built-in load balancing
- Routing mesh for ingress
- Service discovery

**Kubernetes:**
- CNI plugins (Calico, Flannel, etc.)
- Services (ClusterIP, NodePort, LoadBalancer)
- Ingress controllers (nginx, traefik)
- Network policies for security
- DNS-based service discovery

---

### Storage Comparison

**Compose:**
```yaml
volumes:
  data-volume:    # Named volume
  
services:
  app:
    volumes:
      - data-volume:/data
      - ./local:/app  # Bind mount
```

**Swarm:**
```yaml
# Same as Compose!
volumes:
  data-volume:
    driver: local
    # Or use volume plugins (NFS, etc.)
```

**Kubernetes:**
```yaml
# PersistentVolumeClaim
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: data-pvc
spec:
  accessModes:
    - ReadWriteMany  # Can be shared
  resources:
    requests:
      storage: 10Gi
  storageClassName: fast-ssd  # Different storage tiers
---
# Use in Pod
spec:
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: data-pvc
```

---

### Secrets Comparison

**Compose:**
```yaml
# NO built-in secrets!
# Use environment files (not secure)
env_file:
  - .env
```

**Swarm:**
```yaml
# Encrypted secrets
secrets:
  db_password:
    file: ./db_password.txt

services:
  app:
    secrets:
      - db_password
# Available at: /run/secrets/db_password
```

**Kubernetes:**
```yaml
# Multiple types of secrets
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
type: Opaque
data:
  password: cGFzc3dvcmQ=  # base64 encoded
---
# Use in Pod
spec:
  containers:
  - name: app
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
```

---

## 📈 Scaling Your ML Pipeline

### Phase 1: Development (Compose)
```bash
# Start with Compose
docker-compose up -d

# Benefits:
✅ Fast iteration
✅ Easy debugging
✅ Simple setup
```

### Phase 2: Small Production (Swarm)
```bash
# Graduate to Swarm
docker swarm init
docker stack deploy -c docker-stack.yml ml-pipeline

# Benefits:
✅ Multi-host
✅ Auto-recovery
✅ Load balancing
✅ Rolling updates
✅ Still simple!
```

### Phase 3: Scale-up (Kubernetes)
```bash
# Move to Kubernetes
microk8s kubectl apply -f k8s-manifests/

# Benefits:
✅ Advanced scheduling
✅ Auto-scaling (HPA)
✅ Rich ecosystem
✅ StatefulSets
✅ CronJobs
✅ Operators
✅ Service mesh
```

---

## 🛠️ Real-World ML Pipeline Examples

### Example 1: Training Pipeline

**Compose (Dev):**
```yaml
services:
  trainer:
    image: tensorflow/tensorflow:latest
    volumes:
      - ./data:/data
      - ./models:/models
```

**Swarm (Production):**
```yaml
services:
  trainer:
    image: tensorflow/tensorflow:latest
    volumes:
      - data-volume:/data
      - model-volume:/models
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
```

**Kubernetes (Scale):**
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: training-job
spec:
  parallelism: 10  # Train 10 models in parallel
  completions: 10
  template:
    spec:
      containers:
      - name: trainer
        image: tensorflow/tensorflow:latest
        resources:
          limits:
            nvidia.com/gpu: 1  # Request GPU
```

---

### Example 2: Serving API

**Compose:**
```yaml
serving:
  image: my-model-api:latest
  ports:
    - "8000:8000"
```

**Swarm:**
```yaml
serving:
  image: my-model-api:latest
  deploy:
    replicas: 5
    update_config:
      parallelism: 1
      delay: 10s
  # Automatic load balancing!
```

**Kubernetes:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: serving
spec:
  replicas: 5
  template:
    spec:
      containers:
      - name: serving
        image: my-model-api:latest
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: serving-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: serving
  minReplicas: 5
  maxReplicas: 50  # Auto-scale based on load!
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 🎓 Learning Recommendation

### Week 1: Docker Compose
- Run `docker_compose_prefect.py`
- Understand services, volumes, networks
- Build your first pipeline

### Week 2: Docker Swarm
- Run `docker_swarm_prefect.py`
- Learn multi-host orchestration
- Deploy to "production" (local swarm)

### Week 3: Kubernetes Basics
- Install MicroK8s
- Run `microk8s_prefect.py`
- Learn Pods, Deployments, Services

### Week 4: Advanced K8s
- Jobs, CronJobs
- StatefulSets
- Helm charts
- Operators

---

## 🎯 Decision Tree

```
Start Here
    │
    ├─ Need multi-host?
    │  ├─ No → Docker Compose
    │  └─ Yes ───┐
    │            │
    │            ├─ Want simplicity?
    │            │  ├─ Yes → Docker Swarm
    │            │  └─ No ───┐
    │            │           │
    │            │           ├─ Need advanced features?
    │            │           │  ├─ Yes → Kubernetes
    │            │           │  └─ Not sure → Start with Swarm
    │            │           │                upgrade to K8s later
    │            │           │
    │            └───────────┘
    │
    └─ Just learning?
       └─ Start with Compose!
```

---

## 🎉 Summary

**Progression:**
1. **Compose** - Learn containers (Dev)
2. **Swarm** - Learn orchestration (Small Prod)
3. **Kubernetes** - Learn at scale (Large Prod)

**Best for ML:**
- **Development:** Compose
- **Small Teams:** Swarm
- **Enterprise:** Kubernetes

**All files provided work with Prefect!** 🚀

Choose based on your needs, not hype! 📊