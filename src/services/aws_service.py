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
        self.devices_table = self.dynamodb.Table(settings.DYNAMODB_DEVICES_TABLE)
        self.activation_codes_table = self.dynamodb.Table(settings.DYNAMODB_ACTIVATION_CODES_TABLE)

    def get_activation_code(self, code: str):
        try:
            response = self.activation_codes_table.get_item(Key={'code': code})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get activation code {code}: {e}")
            raise

    def save_device_registration(self, device_data: dict):
        try:
            self.devices_table.put_item(Item=device_data)
        except ClientError as e:
            logger.error(f"Failed to save device data to DynamoDB: {e}")
            raise

    def get_device_by_id(self, device_id: str):
        try:
            response = self.devices_table.get_item(Key={'device_id': device_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get device {device_id}: {e}")
            raise

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

    def get_worker_by_id(self, worker_id: str):
        try:
            response = self.workers_table.get_item(Key={'id': worker_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get worker {worker_id}: {e}")
            raise

    def delete_worker(self, worker_id: str):
        try:
            # TODO: Add logic to delete associated images from S3
            self.workers_table.delete_item(Key={'id': worker_id})
        except ClientError as e:
            logger.error(f"Failed to delete worker {worker_id}: {e}")
            raise

    def update_worker(self, worker_id: str, worker_update: dict):
        update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in worker_update)
        expression_attribute_names = {f"#{k}": k for k in worker_update}
        expression_attribute_values = {f":{k}": v for k, v in worker_update.items()}
        
        try:
            response = self.workers_table.update_item(
                Key={'id': worker_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get("Attributes")
        except ClientError as e:
            logger.error(f"Failed to update worker {worker_id}: {e}")
            raise

    def get_all_timestamps(self):
        try:
            response = self.timestamps_table.scan()
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to scan timestamps table: {e}")
            raise

    def get_timestamps_by_worker_id(self, worker_id: str):
        try:
            response = self.timestamps_table.query(
                IndexName='worker_id-index', # Assumes a GSI on worker_id
                KeyConditionExpression='worker_id = :worker_id',
                ExpressionAttributeValues={':worker_id': worker_id}
            )
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to query timestamps for worker {worker_id}: {e}")
            # This is a common error if the index doesn't exist
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                raise ValueError("Timestamps by worker ID query requires a 'worker_id-index' Global Secondary Index on the table.")
            raise

    def get_timestamp_by_id(self, timestamp_id: str):
        try:
            response = self.timestamps_table.get_item(Key={'id': timestamp_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get timestamp {timestamp_id}: {e}")
            raise

    def delete_timestamp(self, timestamp_id: str):
        try:
            self.timestamps_table.delete_item(Key={'id': timestamp_id})
        except ClientError as e:
            logger.error(f"Failed to delete timestamp {timestamp_id}: {e}")
            raise
    
    def update_timestamp(self, timestamp_id: str, timestamp_update: dict):
        update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in timestamp_update)
        expression_attribute_names = {f"#{k}": k for k in timestamp_update}
        expression_attribute_values = {f":{k}": v for k, v in timestamp_update.items()}

        try:
            response = self.timestamps_table.update_item(
                Key={'id': timestamp_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get("Attributes")
        except ClientError as e:
            logger.error(f"Failed to update timestamp {timestamp_id}: {e}")
            raise

aws_service = AWSService()
