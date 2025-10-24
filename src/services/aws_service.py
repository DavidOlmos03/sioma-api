import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from typing import List
import logging

from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AWSService:
    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.dynamodb = boto3.resource(
            "dynamodb",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.workers_table = self.dynamodb.Table(settings.DYNAMODB_WORKERS_TABLE)
        self.timestamps_table = self.dynamodb.Table(settings.DYNAMODB_TIMESTAMPS_TABLE)

    def upload_images_to_s3(self, worker_id: str, images: List[UploadFile]) -> List[str]:
        image_urls = []
        for i, image in enumerate(images):
            file_key = f"{worker_id}/face_{i+1}.jpg"
            try:
                self.s3_client.upload_fileobj(
                    image.file,
                    settings.S3_BUCKET_NAME,
                    file_key,
                    ExtraArgs={'ContentType': image.content_type}
                )
                image_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
                image_urls.append(image_url)
            except ClientError as e:
                logger.error(f"Failed to upload {file_key} to S3: {e}")
                raise
        return image_urls

    def save_worker_data(self, worker_data: dict):
        try:
            self.workers_table.put_item(Item=worker_data)
        except ClientError as e:
            logger.error(f"Failed to save worker data to DynamoDB: {e}")
            raise

    def save_timestamp_data(self, timestamp_data: dict):
        try:
            self.timestamps_table.put_item(Item=timestamp_data)
        except ClientError as e:
            logger.error(f"Failed to save timestamp to DynamoDB: {e}")
            raise

    def get_all_workers(self):
        try:
            response = self.workers_table.scan()
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to scan workers table: {e}")
            raise

aws_service = AWSService()
