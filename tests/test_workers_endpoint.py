import pytest
from httpx import AsyncClient
from fastapi import FastAPI
import io

# Mock AWS services before importing other modules
from moto import mock_aws

@pytest.fixture(scope="module")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    import os
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["S3_BUCKET_NAME"] = "test-bucket"
    os.environ["DYNAMODB_WORKERS_TABLE"] = "test-workers"
    os.environ["DYNAMODB_TIMESTAMPS_TABLE"] = "test-timestamps"

@pytest.fixture(scope="module")
def app(aws_credentials):
    """Create a FastAPI app instance for testing."""
    from src.main import app
    return app

@pytest.mark.asyncio
@mock_aws
async def test_register_worker(app: FastAPI):
    import boto3
    from src.core.config import settings

    # Create mock S3 bucket and DynamoDB table
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    s3.create_bucket(Bucket=settings.S3_BUCKET_NAME)
    dynamodb = boto3.client("dynamodb", region_name=settings.AWS_REGION)
    dynamodb.create_table(
        TableName=settings.DYNAMODB_WORKERS_TABLE,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 1, "WriteCapacityUnits": 1}
    )

    personal_data = {
        "document_id": "123456789",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com"
    }
    files = [("images", ("face_1.jpg", io.BytesIO(b"face1"), "image/jpeg")) for _ in range(7)]

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/workers",
            data={"personal_data_json": json.dumps(personal_data)},
            files=files
        )

    assert response.status_code == 201
    response_data = response.json()
    assert response_data["first_name"] == "John"
    assert len(response_data["image_urls"]) == 7
    assert response_data["image_urls"][0].startswith(f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/")

    # Verify data in DynamoDB
    dynamo_table = boto3.resource("dynamodb").Table(settings.DYNAMODB_WORKERS_TABLE)
    item = dynamo_table.get_item(Key={"id": response_data["id"]}).get("Item")
    assert item is not None
    assert item["email"] == "john.doe@example.com"
