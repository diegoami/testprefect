# Prefect Quick Start Guide

## Installation
```bash
# With uv (fast)
uv pip install prefect

# With pip
pip install prefect
```

## Core Concepts

### 1. Tasks
Tasks are Python functions that represent a discrete unit of work.

```python
from prefect import task

@task
def my_task(x: int):
    return x * 2
```

**Task Options:**
- `retries` - Number of retry attempts
- `retry_delay_seconds` - Delay between retries
- `cache_key_fn` - Function to generate cache keys
- `cache_expiration` - How long to cache results
- `timeout_seconds` - Task timeout
- `log_prints` - Capture print statements

### 2. Flows
Flows are containers for workflow logic and orchestrate tasks.

```python
from prefect import flow

@flow
def my_flow():
    result = my_task(5)
    return result
```

**Flow Options:**
- `name` - Flow name
- `description` - Flow description
- `log_prints` - Capture print statements
- `timeout_seconds` - Flow timeout
- `retries` - Number of retry attempts

### 3. Running Flows

```python
# Direct execution
if __name__ == "__main__":
    my_flow()

# With parameters
my_flow(param1="value")

# Get return value
result = my_flow()
```

## Common Patterns

### Parallel Execution
```python
@flow
def parallel_flow():
    futures = [my_task.submit(i) for i in range(10)]
    results = [f.result() for f in futures]
    return results
```

### Task Dependencies
```python
@flow
def sequential_flow():
    result1 = task_a()
    result2 = task_b(result1)  # Depends on task_a
    result3 = task_c(result1)  # Also depends on task_a
    return task_d(result2, result3)
```

### Error Handling
```python
@task(retries=3, retry_delay_seconds=5)
def risky_task():
    # Task will retry 3 times with 5 second delays
    pass

@flow
def error_flow():
    try:
        result = risky_task()
    except Exception as e:
        print(f"Task failed: {e}")
        # Handle error
```

### Caching
```python
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=1))
def cached_task(x):
    # Expensive operation here
    return x ** 2
```

## CLI Commands

```bash
# Start Prefect server (for UI)
prefect server start

# View flows
prefect flow ls

# View deployments
prefect deployment ls

# View work pools
prefect work-pool ls

# Create a deployment
prefect deploy

# Run a deployment
prefect deployment run 'flow-name/deployment-name'
```

## Prefect UI

Access the UI at: `http://localhost:4200` (after running `prefect server start`)

The UI provides:
- Flow run history and logs
- Real-time monitoring
- Manual flow triggers
- Scheduling configuration
- Work pool management

## Scheduling

```python
from prefect import flow
from prefect.client.schemas.schedules import CronSchedule

@flow
def scheduled_flow():
    print("Running on schedule")

# Deploy with schedule
if __name__ == "__main__":
    scheduled_flow.serve(
        name="my-deployment",
        cron="0 9 * * *"  # Daily at 9 AM
    )
```

## Best Practices

1. **Keep tasks focused** - Each task should do one thing well
2. **Use retries** - Make tasks resilient with retry logic
3. **Add logging** - Use `log_prints=True` or Python logging
4. **Handle errors** - Don't let one failure crash the entire flow
5. **Use type hints** - Makes code more maintainable
6. **Cache expensive operations** - Use task caching for repeated work
7. **Parameterize flows** - Make flows reusable with parameters

## Next Steps

1. Run the example files:
   ```bash
   python prefect_intro.py
   python prefect_guide.py
   ```

2. Start the Prefect UI:
   ```bash
   prefect server start
   ```

3. Explore deployments and scheduling

4. Check out the docs: https://docs.prefect.io

## Common Use Cases

- **Data pipelines** - ETL/ELT workflows
- **ML workflows** - Training, evaluation, deployment
- **API orchestration** - Coordinating multiple API calls
- **Report generation** - Scheduled report creation
- **Infrastructure automation** - Cloud resource management
- **Web scraping** - Scheduled data collection