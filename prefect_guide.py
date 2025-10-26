"""
Prefect Getting Started Guide
==============================

This file covers key Prefect concepts with practical examples.
"""

from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta
import random


# ====================
# 1. BASIC TASKS & FLOWS
# ====================

@task
def say_hello(name: str):
    """A simple task"""
    return f"Hello, {name}!"


@flow
def hello_flow(name: str = "World"):
    """A simple flow"""
    message = say_hello(name)
    print(message)
    return message


# ====================
# 2. TASK CACHING
# ====================

@task(cache_key_fn=task_input_hash, cache_expiration=timedelta(minutes=5))
def expensive_computation(x: int):
    """This task will be cached for 5 minutes"""
    print(f"Running expensive computation for {x}...")
    import time
    time.sleep(2)  # Simulate expensive operation
    return x ** 2


@flow
def cached_flow():
    """Demonstrates task caching"""
    result1 = expensive_computation(5)  # Will compute
    result2 = expensive_computation(5)  # Will use cache
    print(f"Results: {result1}, {result2}")


# ====================
# 3. RETRIES & ERROR HANDLING
# ====================

@task(retries=3, retry_delay_seconds=2)
def unreliable_task():
    """Task that sometimes fails but will retry"""
    if random.random() < 0.5:
        raise ValueError("Random failure!")
    return "Success!"


@flow
def retry_flow():
    """Demonstrates automatic retries"""
    try:
        result = unreliable_task()
        print(result)
    except Exception as e:
        print(f"Task failed after retries: {e}")


# ====================
# 4. PARALLEL EXECUTION
# ====================

@task
def process_item(item: int):
    """Process a single item"""
    import time
    time.sleep(0.5)
    return item * 2


@flow
def parallel_flow():
    """Process multiple items in parallel"""
    items = [1, 2, 3, 4, 5]
    
    # Submit all tasks at once (they run in parallel)
    futures = [process_item.submit(item) for item in items]
    
    # Wait for all results
    results = [future.result() for future in futures]
    print(f"Processed results: {results}")
    return results


# ====================
# 5. SUBFLOWS
# ====================

@flow
def sub_flow(value: int):
    """A subflow that can be called from another flow"""
    return value + 10


@flow
def parent_flow():
    """Main flow that calls subflows"""
    result1 = sub_flow(5)
    result2 = sub_flow(15)
    total = result1 + result2
    print(f"Total from subflows: {total}")
    return total


# ====================
# 6. PARAMETERS & CONFIGURATION
# ====================

@flow
def configurable_flow(
    batch_size: int = 100,
    environment: str = "development",
    debug: bool = False
):
    """Flow with configurable parameters"""
    print(f"Running in {environment} mode")
    print(f"Batch size: {batch_size}")
    print(f"Debug: {debug}")
    
    if debug:
        print("Debug information here...")
    
    return {"batch_size": batch_size, "environment": environment}


# ====================
# 7. DATA VALIDATION
# ====================

from pydantic import BaseModel, Field

class DataInput(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., gt=0, lt=150)
    email: str


@task
def validate_data(data: DataInput):
    """Task with validated input using Pydantic"""
    return f"Validated: {data.name}, {data.age}, {data.email}"


@flow
def validation_flow():
    """Flow with data validation"""
    data = DataInput(name="Alice", age=30, email="alice@example.com")
    result = validate_data(data)
    print(result)
    return result


# ====================
# MAIN EXECUTION
# ====================

if __name__ == "__main__":
    print("=" * 50)
    print("1. Basic Flow")
    print("=" * 50)
    hello_flow("Prefect")
    
    print("\n" + "=" * 50)
    print("2. Cached Flow")
    print("=" * 50)
    cached_flow()
    
    print("\n" + "=" * 50)
    print("3. Retry Flow")
    print("=" * 50)
    retry_flow()
    
    print("\n" + "=" * 50)
    print("4. Parallel Flow")
    print("=" * 50)
    parallel_flow()
    
    print("\n" + "=" * 50)
    print("5. Subflow Example")
    print("=" * 50)
    parent_flow()
    
    print("\n" + "=" * 50)
    print("6. Configurable Flow")
    print("=" * 50)
    configurable_flow(batch_size=50, environment="production", debug=True)
    
    print("\n" + "=" * 50)
    print("7. Validation Flow")
    print("=" * 50)
    validation_flow()