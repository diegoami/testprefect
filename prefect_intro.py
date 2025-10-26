"""
Simple Prefect Introduction Example
This demonstrates basic Prefect concepts: flows, tasks, and execution
"""

from prefect import flow, task
import time


@task
def fetch_data(source: str):
    """Simulate fetching data from a source"""
    print(f"Fetching data from {source}...")
    time.sleep(1)
    return {"source": source, "records": 100}


@task
def process_data(data: dict):
    """Process the fetched data"""
    print(f"Processing {data['records']} records from {data['source']}...")
    time.sleep(1)
    processed_count = data['records'] * 2
    return {"processed": processed_count, "status": "success"}


@task
def save_results(results: dict):
    """Save the processed results"""
    print(f"Saving {results['processed']} processed records...")
    time.sleep(1)
    return f"Saved {results['processed']} records successfully"


@flow(name="Data Pipeline", log_prints=True)
def data_pipeline(source: str = "API"):
    """Main workflow that orchestrates the data pipeline"""
    print(f"Starting data pipeline for source: {source}")
    
    # Fetch data
    raw_data = fetch_data(source)
    
    # Process data
    processed_data = process_data(raw_data)
    
    # Save results
    final_result = save_results(processed_data)
    
    print(f"Pipeline completed: {final_result}")
    return final_result


if __name__ == "__main__":
    # Run the flow
    result = data_pipeline(source="Database")