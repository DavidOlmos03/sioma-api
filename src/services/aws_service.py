import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from typing import List
import logging
import time
from src.core.security import get_password_hash

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
        self.attendance_table = self.dynamodb.Table(settings.DYNAMODB_ATTENDANCE_TABLE)
        self.audit_table = self.dynamodb.Table(settings.DYNAMODB_AUDIT_TABLE)
        self.admin_users_table = self.dynamodb.Table(settings.DYNAMODB_ADMIN_USERS_TABLE)

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

    def mark_activation_code_as_used(self, code: str, device_id: str):
        try:
            self.activation_codes_table.update_item(
                Key={'code': code},
                UpdateExpression="SET #s = :s, #ua = :ua, #ubd = :ubd",
                ExpressionAttributeNames={
                    '#s': 'status',
                    '#ua': 'used_at',
                    '#ubd': 'used_by_device_id'
                },
                ExpressionAttributeValues={
                    ':s': 'used',
                    ':ua': int(time.time() * 1000),
                    ':ubd': device_id
                }
            )
        except ClientError as e:
            logger.error(f"Failed to mark activation code {code} as used: {e}")
            raise

    def find_duplicate_attendance(self, tenant_id: str, employee_id: str, timestamp: int):
        partition_key = f"{tenant_id}#{employee_id}"
        min_ts = timestamp - 30000 # 30 seconds
        max_ts = timestamp + 30000 # 30 seconds
        try:
            response = self.attendance_table.query(
                KeyConditionExpression=
                    boto3.dynamodb.conditions.Key('tenant_id#employee_id').eq(partition_key) &
                    boto3.dynamodb.conditions.Key('timestamp').between(min_ts, max_ts)
            )
            return response.get('Items')
        except ClientError as e:
            logger.error(f"DynamoDB query failed: {e}")
            raise

    def save_attendance_record(self, record_data: dict):
        try:
            self.attendance_table.put_item(Item=record_data)
        except ClientError as e:
            logger.error(f"Failed to save attendance record to DynamoDB: {e}")
            raise

    def get_attendance_updates(self, tenant_id: str, since_timestamp: int):
        try:
            # This query finds newly created records.
            # Finding deleted records efficiently would require a different GSI strategy,
            # e.g., on a 'last_updated_at' field.
            response = self.attendance_table.query(
                IndexName='tenant_id-timestamp-index', # As per GSI1 in requirements
                KeyConditionExpression=
                    boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id) &
                    boto3.dynamodb.conditions.Key('timestamp').gt(since_timestamp)
            )
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"DynamoDB query for updates failed: {e}")
            # Handle case where index doesn't exist, which is a common setup error.
            if e.response['Error']['Code'] == 'ValidationException' and 'does not have the specified index' in e.response['Error']['Message']:
                 logger.error("Query failed: The table is missing the 'tenant_id-timestamp-index'. Please create it.")
                 raise ValueError("Required DynamoDB index 'tenant_id-timestamp-index' not found.")
            raise

    def save_audit_records(self, records: List[dict]):
        try:
            with self.audit_table.batch_writer() as batch:
                for record in records:
                    batch.put_item(Item=record)
        except ClientError as e:
            logger.error(f"Failed to save audit records to DynamoDB: {e}")
            raise

    def save_activation_code(self, code_data: dict):
        try:
            self.activation_codes_table.put_item(Item=code_data)
        except ClientError as e:
            logger.error(f"Failed to save activation code to DynamoDB: {e}")
            raise

    def get_devices_by_tenant(self, tenant_id: str):
        try:
            response = self.devices_table.query(
                IndexName='tenant_id-registered_at-index', # As per GSI1 in requirements
                KeyConditionExpression=boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id)
            )
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"DynamoDB query for devices by tenant failed: {e}")
            if e.response['Error']['Code'] == 'ValidationException' and 'does not have the specified index' in e.response['Error']['Message']:
                 logger.error("Query failed: The table is missing the 'tenant_id-registered_at-index'. Please create it.")
                 raise ValueError("Required DynamoDB index 'tenant_id-registered_at-index' not found.")
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
    def deactivate_device(self, device_id: str, reason: str, tenant_id: str):
        try:
            response = self.devices_table.update_item(
                Key={'device_id': device_id},
                ConditionExpression=boto3.dynamodb.conditions.Attr('tenant_id').eq(tenant_id),
                UpdateExpression="SET is_active = :active, deactivated_at = :deactivated_at, deactivation_reason = :reason",
                ExpressionAttributeValues={
                    ':active': False,
                    ':deactivated_at': int(time.time() * 1000),
                    ':reason': reason
                },
                ReturnValues="ALL_NEW"
            )
            return response.get("Attributes")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                logger.error(f"Device {device_id} not found or does not belong to tenant {tenant_id}")
                raise ValueError(f"Device {device_id} not found or does not belong to tenant {tenant_id}")
            logger.error(f"Failed to deactivate device {device_id}: {e}")
            raise

    def create_tables(self):
        try:
            self.dynamodb.create_table(
                TableName=settings.DYNAMODB_ADMIN_USERS_TABLE,
                KeySchema=[
                    {'AttributeName': 'email', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'email', 'AttributeType': 'S'}
                ],
                ProvisionedThroughput={'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
            )
            logger.info(f"Table {settings.DYNAMODB_ADMIN_USERS_TABLE} created successfully.")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                logger.info(f"Table {settings.DYNAMODB_ADMIN_USERS_TABLE} already exists.")
            else:
                logger.error(f"Failed to create table {settings.DYNAMODB_ADMIN_USERS_TABLE}: {e}")
                raise

    def get_admin_user_by_email(self, email: str):
        try:
            response = self.admin_users_table.get_item(Key={'email': email})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get admin user {email}: {e}")
            raise

    def get_all_admin_users(self):
        try:
            response = self.admin_users_table.scan()
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to scan admin users table: {e}")
            raise

    def update_admin_user(self, email: str, user_update: dict):
        update_expression = "SET " + ", ".join(f"#{k}=:{k}" for k in user_update)
        expression_attribute_names = {f"#{k}": k for k in user_update}
        expression_attribute_values = {f":{k}": v for k, v in user_update.items()}

        try:
            response = self.admin_users_table.update_item(
                Key={'email': email},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values,
                ReturnValues="ALL_NEW"
            )
            return response.get("Attributes")
        except ClientError as e:
            logger.error(f"Failed to update admin user {email}: {e}")
            raise

    def delete_admin_user(self, email: str):
        try:
            self.admin_users_table.delete_item(Key={'email': email})
        except ClientError as e:
            logger.error(f"Failed to delete admin user {email}: {e}")
            raise

    def create_initial_admin_user_if_not_exists(self):
        email = "admin@sioma.com"
        user = self.get_admin_user_by_email(email)
        if not user:
            password = "Password_2025"
            hashed_password = get_password_hash(password)

            user_data = {
                "email": email,
                "hashed_password": hashed_password,
                "is_active": True,
                "created_at": int(time.time() * 1000),
            }

            try:
                self.admin_users_table.put_item(Item=user_data)
                logger.info(f"Initial admin user {email} created successfully.")
            except Exception as e:
                logger.error(f"Failed to create initial admin user: {e}")

aws_service = AWSService()
