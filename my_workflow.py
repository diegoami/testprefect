from prefect import flow


@flow
def my_workflow() -> str:
    return "Hello, world!"