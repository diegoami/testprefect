"""
Real-World Example: ETL Pipeline with Prefect
==============================================

This demonstrates a practical ETL (Extract, Transform, Load) pipeline
that processes data from multiple sources.
"""

from prefect import flow, task
from datetime import datetime
import json


# ====================
# EXTRACT TASKS
# ====================

@task(retries=2, retry_delay_seconds=5)
def extract_from_api(api_url: str):
    """Extract data from an API"""
    print(f"Extracting data from API: {api_url}")
    
    # Simulate API call
    data = {
        "users": [
            {"id": 1, "name": "Alice", "age": 30, "city": "New York"},
            {"id": 2, "name": "Bob", "age": 25, "city": "San Francisco"},
            {"id": 3, "name": "Charlie", "age": 35, "city": "Los Angeles"},
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"Extracted {len(data['users'])} records")
    return data


@task(retries=2)
def extract_from_database(table_name: str):
    """Extract data from a database"""
    print(f"Extracting data from table: {table_name}")
    
    # Simulate database query
    data = {
        "orders": [
            {"order_id": 101, "user_id": 1, "amount": 250.50},
            {"order_id": 102, "user_id": 2, "amount": 175.00},
            {"order_id": 103, "user_id": 1, "amount": 320.75},
        ],
        "timestamp": datetime.now().isoformat()
    }
    
    print(f"Extracted {len(data['orders'])} orders")
    return data


# ====================
# TRANSFORM TASKS
# ====================

@task
def clean_user_data(raw_data: dict):
    """Clean and validate user data"""
    print("Cleaning user data...")
    
    users = raw_data.get("users", [])
    cleaned_users = []
    
    for user in users:
        # Clean and validate
        cleaned_user = {
            "id": user["id"],
            "name": user["name"].strip().title(),
            "age": max(0, user["age"]),  # Ensure positive age
            "city": user["city"].strip().title()
        }
        cleaned_users.append(cleaned_user)
    
    print(f"Cleaned {len(cleaned_users)} user records")
    return cleaned_users


@task
def aggregate_orders(orders_data: dict):
    """Aggregate order data by user"""
    print("Aggregating order data...")
    
    orders = orders_data.get("orders", [])
    user_totals = {}
    
    for order in orders:
        user_id = order["user_id"]
        amount = order["amount"]
        
        if user_id not in user_totals:
            user_totals[user_id] = {"total_orders": 0, "total_amount": 0}
        
        user_totals[user_id]["total_orders"] += 1
        user_totals[user_id]["total_amount"] += amount
    
    print(f"Aggregated orders for {len(user_totals)} users")
    return user_totals


@task
def join_user_orders(users: list, order_aggregates: dict):
    """Join user data with order aggregates"""
    print("Joining user and order data...")
    
    enriched_users = []
    
    for user in users:
        user_id = user["id"]
        order_info = order_aggregates.get(user_id, {
            "total_orders": 0,
            "total_amount": 0
        })
        
        enriched_user = {
            **user,
            "total_orders": order_info["total_orders"],
            "total_amount": round(order_info["total_amount"], 2),
            "avg_order_value": round(
                order_info["total_amount"] / order_info["total_orders"], 2
            ) if order_info["total_orders"] > 0 else 0
        }
        enriched_users.append(enriched_user)
    
    print(f"Enriched {len(enriched_users)} user records")
    return enriched_users


# ====================
# LOAD TASKS
# ====================

@task
def validate_data(data: list):
    """Validate data before loading"""
    print("Validating data...")
    
    valid_records = []
    invalid_records = []
    
    for record in data:
        # Simple validation rules
        if (record.get("id") and 
            record.get("name") and 
            record.get("age", 0) > 0):
            valid_records.append(record)
        else:
            invalid_records.append(record)
    
    print(f"Valid: {len(valid_records)}, Invalid: {len(invalid_records)}")
    
    if invalid_records:
        print(f"Warning: {len(invalid_records)} invalid records found")
    
    return valid_records


@task
def load_to_warehouse(data: list, target: str):
    """Load data to data warehouse"""
    print(f"Loading {len(data)} records to {target}...")
    
    # Simulate loading to warehouse
    # In real scenario, this would write to a database or data lake
    
    for record in data:
        # Simulate insert
        pass
    
    print(f"Successfully loaded {len(data)} records")
    return {
        "status": "success",
        "records_loaded": len(data),
        "target": target,
        "timestamp": datetime.now().isoformat()
    }


@task
def generate_report(data: list):
    """Generate summary report"""
    print("Generating report...")
    
    total_users = len(data)
    total_orders = sum(u["total_orders"] for u in data)
    total_revenue = sum(u["total_amount"] for u in data)
    avg_revenue = total_revenue / total_users if total_users > 0 else 0
    
    report = {
        "summary": {
            "total_users": total_users,
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "avg_revenue_per_user": round(avg_revenue, 2)
        },
        "generated_at": datetime.now().isoformat()
    }
    
    print(f"Report: {json.dumps(report, indent=2)}")
    return report


# ====================
# MAIN ETL FLOW
# ====================

@flow(name="ETL Pipeline", log_prints=True)
def etl_pipeline(
    api_url: str = "https://api.example.com/users",
    db_table: str = "orders",
    warehouse_target: str = "analytics.user_metrics"
):
    """
    Main ETL pipeline that orchestrates data extraction,
    transformation, and loading.
    """
    
    print("=" * 60)
    print("Starting ETL Pipeline")
    print("=" * 60)
    
    # EXTRACT
    print("\n[EXTRACT PHASE]")
    raw_users = extract_from_api(api_url)
    raw_orders = extract_from_database(db_table)
    
    # TRANSFORM
    print("\n[TRANSFORM PHASE]")
    cleaned_users = clean_user_data(raw_users)
    order_aggregates = aggregate_orders(raw_orders)
    enriched_data = join_user_orders(cleaned_users, order_aggregates)
    
    # VALIDATE
    print("\n[VALIDATION PHASE]")
    valid_data = validate_data(enriched_data)
    
    # LOAD
    print("\n[LOAD PHASE]")
    load_result = load_to_warehouse(valid_data, warehouse_target)
    
    # REPORT
    print("\n[REPORTING PHASE]")
    report = generate_report(valid_data)
    
    print("\n" + "=" * 60)
    print("ETL Pipeline Completed Successfully")
    print("=" * 60)
    
    return {
        "load_result": load_result,
        "report": report
    }


# ====================
# SCHEDULED ETL FLOW
# ====================

@flow
def scheduled_daily_etl():
    """Wrapper flow for scheduled execution"""
    result = etl_pipeline(
        api_url="https://api.example.com/users",
        db_table="orders",
        warehouse_target="analytics.daily_user_metrics"
    )
    return result


if __name__ == "__main__":
    # Run the ETL pipeline
    result = etl_pipeline()
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS:")
    print(json.dumps(result, indent=2))
    print("=" * 60)