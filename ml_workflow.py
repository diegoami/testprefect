"""
Real-World Example: ML Training Pipeline with Docker + Prefect (FULLY FIXED)
===============================================================

All f-string escaping issues resolved.
"""

from prefect import flow, task
from prefect.logging import get_run_logger
import docker
from pathlib import Path
import json
from datetime import datetime
import hashlib
from typing import Optional, List


# ====================
# CONFIGURATION
# ====================

class PipelineConfig:
    """Central configuration for ML pipeline"""
    
    # Volume names
    DATA_VOLUME = "ml-pipeline-data"
    MODEL_VOLUME = "ml-pipeline-models"
    ARTIFACT_VOLUME = "ml-pipeline-artifacts"
    
    # Container paths
    DATA_PATH = "/data"
    MODEL_PATH = "/models"
    ARTIFACT_PATH = "/artifacts"
    
    # Docker images
    DATA_PROCESSOR_IMAGE = "python:3.11-slim"
    FEATURE_ENGINE_IMAGE = "python:3.11-slim"
    TRAINER_IMAGE = "tensorflow/tensorflow:latest"
    
    # Workspace
    HOST_WORKSPACE = "/tmp/ml-pipeline-workspace"


# ====================
# VOLUME MANAGEMENT
# ====================

@task
def setup_pipeline_volumes():
    """Create all required volumes for the pipeline"""
    logger = get_run_logger()
    client = docker.from_env()
    
    volumes_created = []
    for volume_name in [
        PipelineConfig.DATA_VOLUME,
        PipelineConfig.MODEL_VOLUME,
        PipelineConfig.ARTIFACT_VOLUME
    ]:
        try:
            volume = client.volumes.get(volume_name)
            logger.info(f"Volume '{volume_name}' already exists")
        except docker.errors.NotFound:
            volume = client.volumes.create(name=volume_name)
            logger.info(f"Created volume '{volume_name}'")
        
        volumes_created.append(volume.name)
    
    return volumes_created


@task
def cleanup_pipeline_volumes(force: bool = False):
    """Clean up pipeline volumes"""
    logger = get_run_logger()
    client = docker.from_env()
    
    for volume_name in [
        PipelineConfig.DATA_VOLUME,
        PipelineConfig.MODEL_VOLUME,
        PipelineConfig.ARTIFACT_VOLUME
    ]:
        try:
            volume = client.volumes.get(volume_name)
            volume.remove(force=force)
            logger.info(f"Removed volume '{volume_name}'")
        except Exception as e:
            logger.warning(f"Could not remove volume '{volume_name}': {e}")


# ====================
# STAGE 1: DATA EXTRACTION
# ====================

@task(retries=3, retry_delay_seconds=5)
def extract_training_data(data_source: str):
    """Extract training data from source and save to data volume"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Extracting data from: {data_source}")
    
    # FIXED: Use triple-quoted string without f-string to avoid escaping issues
    extraction_code = '''
import json
import random
from datetime import datetime

# Simulate data extraction
data = {
    'source': '%(source)s',
    'extracted_at': datetime.now().isoformat(),
    'samples': [
        {'features': [random.random() for _ in range(10)], 'label': random.choice([0, 1])}
        for _ in range(1000)
    ],
    'metadata': {
        'total_samples': 1000,
        'feature_count': 10,
        'class_distribution': {'0': 500, '1': 500}
    }
}

# Save to volume
with open('%(data_path)s/raw_data.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Extracted " + str(len(data['samples'])) + " samples")
''' % {'source': data_source, 'data_path': PipelineConfig.DATA_PATH}
    
    container = client.containers.run(
        PipelineConfig.DATA_PROCESSOR_IMAGE,
        command=['python', '-c', extraction_code],  # FIXED: Pass as list, not f-string
        volumes={
            PipelineConfig.DATA_VOLUME: {
                'bind': PipelineConfig.DATA_PATH,
                'mode': 'rw'
            }
        },
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()  # FIXED
    
    logger.info(f"Extraction logs:\n{logs}")
    
    return {
        "status": "completed" if result['StatusCode'] == 0 else "failed",
        "samples_extracted": 1000,
        "data_path": f"{PipelineConfig.DATA_VOLUME}:{PipelineConfig.DATA_PATH}/raw_data.json"
    }


# ====================
# STAGE 2: DATA PREPROCESSING
# ====================

@task
def preprocess_data():
    """Preprocess raw data in isolated container"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info("Preprocessing data...")
    
    # FIXED: Avoid f-string nesting
    preprocessing_code = '''
import json
import random

# Load raw data
with open('/data/raw_data.json', 'r') as f:
    raw_data = json.load(f)

samples = raw_data['samples']

# Split data (70/15/15)
random.shuffle(samples)
total = len(samples)
train_end = int(0.7 * total)
val_end = int(0.85 * total)

splits = {
    'train': samples[:train_end],
    'validation': samples[train_end:val_end],
    'test': samples[val_end:],
}

# Save splits
for split_name, split_data in splits.items():
    with open('/data/' + split_name + '_data.json', 'w') as f:
        json.dump({
            'samples': split_data,
            'count': len(split_data)
        }, f)
    print(split_name + ": " + str(len(split_data)) + " samples")

# Save preprocessing metadata
metadata = {
    'preprocessed_at': raw_data['extracted_at'],
    'splits': {k: len(v) for k, v in splits.items()},
    'preprocessing_steps': ['shuffle', 'split']
}

with open('/data/preprocessing_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print("Preprocessing complete")
'''
    
    container = client.containers.run(
        PipelineConfig.DATA_PROCESSOR_IMAGE,
        command=['python', '-c', preprocessing_code],
        volumes={
            PipelineConfig.DATA_VOLUME: {
                'bind': PipelineConfig.DATA_PATH,
                'mode': 'rw'
            }
        },
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()  # FIXED
    
    logger.info(f"Preprocessing logs:\n{logs}")
    
    return {
        "status": "completed" if result['StatusCode'] == 0 else "failed",
        "splits": ["train", "validation", "test"]
    }


# ====================
# STAGE 3: FEATURE ENGINEERING
# ====================

@task
def engineer_features():
    """Feature engineering in container with specialized libraries"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info("Engineering features...")
    
    feature_code = '''
import json

# Load training data
with open('/data/train_data.json', 'r') as f:
    train_data = json.load(f)

samples = train_data['samples']

# Engineer features (simplified example)
for sample in samples:
    features = sample['features']
    # Add engineered features
    sample['features_engineered'] = [
        sum(features),  # sum
        max(features),  # max
        min(features),  # min
        sum(features) / len(features),  # mean
    ]

# Save engineered features
with open('/data/train_features.json', 'w') as f:
    json.dump({'samples': samples, 'count': len(samples)}, f)

print("Engineered features for " + str(len(samples)) + " samples")

# Save feature metadata
feature_metadata = {
    'original_features': 10,
    'engineered_features': 4,
    'total_features': 14,
    'feature_names': ['feature_' + str(i) for i in range(10)] + 
                     ['sum', 'max', 'min', 'mean']
}

with open('/data/feature_metadata.json', 'w') as f:
    json.dump(feature_metadata, f, indent=2)
'''
    
    container = client.containers.run(
        PipelineConfig.FEATURE_ENGINE_IMAGE,
        command=['python', '-c', feature_code],
        volumes={
            PipelineConfig.DATA_VOLUME: {
                'bind': PipelineConfig.DATA_PATH,
                'mode': 'rw'
            }
        },
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()  # FIXED
    
    logger.info(f"Feature engineering logs:\n{logs}")
    
    return {
        "status": "completed" if result['StatusCode'] == 0 else "failed",
        "total_features": 14
    }


# ====================
# STAGE 4: MODEL TRAINING
# ====================

@task(retries=1, retry_delay_seconds=10)
def train_model(model_name: str = "classifier_v1"):
    """Train ML model in specialized container"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Training model: {model_name}")
    
    # Generate model ID
    model_id = hashlib.md5(
        f"{model_name}_{datetime.now().isoformat()}".encode()
    ).hexdigest()[:8]
    
    training_code = '''
import json
from datetime import datetime

model_id = "%(model_id)s"
model_name = "%(model_name)s"

# Load training features
with open('/data/train_features.json', 'r') as f:
    train_data = json.load(f)

print("Training on " + str(train_data['count']) + " samples...")

# Simulate training (in production: actual model training)
training_metrics = {
    'model_id': model_id,
    'model_name': model_name,
    'trained_at': datetime.now().isoformat(),
    'training_samples': train_data['count'],
    'epochs': 10,
    'metrics': {
        'accuracy': 0.92,
        'precision': 0.91,
        'recall': 0.93,
        'f1_score': 0.92
    },
    'hyperparameters': {
        'learning_rate': 0.001,
        'batch_size': 32,
        'optimizer': 'adam'
    }
}

# Save model (placeholder - in production: actual model file)
model_data = {
    'model_id': model_id,
    'model_name': model_name,
    'model_type': 'classifier',
    'features': 14,
    'classes': 2
}

with open('/models/' + model_id + '.json', 'w') as f:
    json.dump(model_data, f, indent=2)

# Save training metrics
with open('/artifacts/training_metrics_' + model_id + '.json', 'w') as f:
    json.dump(training_metrics, f, indent=2)

print("Model trained: " + model_id)
print("Accuracy: " + str(training_metrics['metrics']['accuracy']))
''' % {'model_id': model_id, 'model_name': model_name}
    
    container = client.containers.run(
        PipelineConfig.TRAINER_IMAGE,
        command=['python', '-c', training_code],
        volumes={
            PipelineConfig.DATA_VOLUME: {
                'bind': PipelineConfig.DATA_PATH,
                'mode': 'ro'  # Read-only for training
            },
            PipelineConfig.MODEL_VOLUME: {
                'bind': PipelineConfig.MODEL_PATH,
                'mode': 'rw'
            },
            PipelineConfig.ARTIFACT_VOLUME: {
                'bind': PipelineConfig.ARTIFACT_PATH,
                'mode': 'rw'
            }
        },
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()  # FIXED
    
    logger.info(f"Training logs:\n{logs}")
    
    return {
        "status": "completed" if result['StatusCode'] == 0 else "failed",
        "model_id": model_id,
        "model_name": model_name,
        "accuracy": 0.92
    }


# ====================
# STAGE 5: MODEL EVALUATION
# ====================

@task
def evaluate_model(model_id: str):
    """Evaluate trained model on validation and test sets"""
    logger = get_run_logger()
    client = docker.from_env()
    
    logger.info(f"Evaluating model: {model_id}")
    
    evaluation_code = '''
import json

model_id = "%(model_id)s"

# Load model
with open('/models/' + model_id + '.json', 'r') as f:
    model = json.load(f)

# Load validation data
with open('/data/validation_data.json', 'r') as f:
    val_data = json.load(f)

# Simulate evaluation
evaluation = {
    'model_id': model_id,
    'validation_metrics': {
        'accuracy': 0.89,
        'precision': 0.88,
        'recall': 0.90,
        'f1_score': 0.89
    },
    'test_metrics': {
        'accuracy': 0.87,
        'precision': 0.86,
        'recall': 0.88,
        'f1_score': 0.87
    },
    'validation_samples': val_data['count'],
    'passed': True  # Simple threshold check
}

# Save evaluation results
with open('/artifacts/evaluation_' + model_id + '.json', 'w') as f:
    json.dump(evaluation, f, indent=2)

print("Validation accuracy: " + str(evaluation['validation_metrics']['accuracy']))
print("Test accuracy: " + str(evaluation['test_metrics']['accuracy']))
print("Evaluation: " + ("PASSED" if evaluation['passed'] else "FAILED"))
''' % {'model_id': model_id}
    
    container = client.containers.run(
        PipelineConfig.TRAINER_IMAGE,
        command=['python', '-c', evaluation_code],
        volumes={
            PipelineConfig.DATA_VOLUME: {
                'bind': PipelineConfig.DATA_PATH,
                'mode': 'ro'
            },
            PipelineConfig.MODEL_VOLUME: {
                'bind': PipelineConfig.MODEL_PATH,
                'mode': 'ro'
            },
            PipelineConfig.ARTIFACT_VOLUME: {
                'bind': PipelineConfig.ARTIFACT_PATH,
                'mode': 'rw'
            }
        },
        detach=True,
        remove=False  # FIXED
    )
    
    result = container.wait()
    logs = container.logs().decode('utf-8')
    container.remove()  # FIXED
    
    logger.info(f"Evaluation logs:\n{logs}")
    
    return {
        "status": "completed" if result['StatusCode'] == 0 else "failed",
        "model_id": model_id,
        "validation_accuracy": 0.89,
        "test_accuracy": 0.87,
        "passed": True
    }


# ====================
# MAIN PIPELINE
# ====================

@flow(name="ML Training Pipeline", log_prints=True)
def ml_training_pipeline(
    data_source: str = "production_db",
    model_name: str = "classifier_v1"
):
    """Complete ML training pipeline with Docker containers and volumes"""
    
    logger = get_run_logger()
    
    print("=" * 70)
    print("ML TRAINING PIPELINE")
    print("=" * 70)
    
    # Setup
    logger.info("Setting up pipeline volumes...")
    volumes = setup_pipeline_volumes()
    
    # Stage 1: Extract
    logger.info("\n[STAGE 1: DATA EXTRACTION]")
    extraction_result = extract_training_data(data_source)
    
    # Stage 2: Preprocess
    logger.info("\n[STAGE 2: DATA PREPROCESSING]")
    preprocess_result = preprocess_data()
    
    # Stage 3: Feature Engineering
    logger.info("\n[STAGE 3: FEATURE ENGINEERING]")
    feature_result = engineer_features()
    
    # Stage 4: Train
    logger.info("\n[STAGE 4: MODEL TRAINING]")
    training_result = train_model(model_name)
    
    # Stage 5: Evaluate
    logger.info("\n[STAGE 5: MODEL EVALUATION]")
    evaluation_result = evaluate_model(training_result["model_id"])
    
    # Final results
    pipeline_result = {
        "pipeline_id": hashlib.md5(datetime.now().isoformat().encode()).hexdigest()[:8],
        "completed_at": datetime.now().isoformat(),
        "stages": {
            "extraction": extraction_result,
            "preprocessing": preprocess_result,
            "features": feature_result,
            "training": training_result,
            "evaluation": evaluation_result
        },
        "model": {
            "id": training_result["model_id"],
            "name": model_name,
            "validation_accuracy": evaluation_result["validation_accuracy"],
            "test_accuracy": evaluation_result["test_accuracy"],
            "ready_for_deployment": evaluation_result["passed"]
        },
        "volumes": volumes
    }
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"Model ID: {pipeline_result['model']['id']}")
    print(f"Test Accuracy: {pipeline_result['model']['test_accuracy']}")
    print(f"Ready for deployment: {pipeline_result['model']['ready_for_deployment']}")
    print("=" * 70)
    
    return pipeline_result


# ====================
# CLEANUP FLOW
# ====================

@flow
def cleanup_pipeline():
    """Clean up all pipeline resources"""
    cleanup_pipeline_volumes(force=True)
    return {"status": "cleaned"}


# ====================
# MAIN
# ====================

if __name__ == "__main__":
    # Run the pipeline
    result = ml_training_pipeline()
    
    print("\n" + "=" * 70)
    print("FINAL PIPELINE RESULTS:")
    print("=" * 70)
    print(json.dumps(result, indent=2))
    print("=" * 70)
    
    # Optionally cleanup
    # cleanup_pipeline()