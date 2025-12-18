import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from typing import List
import logging
import time
from io import BytesIO
from PIL import Image
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
        self.metrics_table = self.dynamodb.Table(settings.DYNAMODB_METRICS_TABLE)

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

    def save_metrics_record(self, metrics_data: dict):
        """
        Saves facial recognition metrics to DynamoDB with retry logic.

        Args:
            metrics_data: Dictionary containing metrics information with structure:
                - PK: tenant_id#device_id (e.g., "ACME#device-123")
                - SK: METRICS#metrics_id (e.g., "METRICS#uuid")
                - tenant_id, device_id, metrics_id, local_id
                - attendance_record_id, employee_id, employee_id_number
                - timestamp, recognition_successful, rejected_by_user
                - metrics: nested object with quality and capture metrics
                - synced_at
        """
        max_retries = 3
        retry_delay = 0.1  # Start with 100ms

        for attempt in range(max_retries):
            try:
                self.metrics_table.put_item(Item=metrics_data)
                return  # Success
            except ClientError as e:
                error_code = e.response['Error']['Code']

                # Handle throttling with exponential backoff
                if error_code == 'ProvisionedThroughputExceededException' and attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Throttled writing metrics. Retrying in {sleep_time}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.error(f"Failed to save metrics record to DynamoDB: {e}")
                    raise

    def save_metrics_batch(self, metrics_list: List[dict]):
        """
        Saves multiple metrics records to DynamoDB using batch_writer for efficiency.

        Args:
            metrics_list: List of metrics data dictionaries

        Returns:
            tuple: (successful_count, failed_metrics)
        """
        failed_metrics = []
        successful_count = 0

        try:
            with self.metrics_table.batch_writer() as batch:
                for metrics_data in metrics_list:
                    try:
                        batch.put_item(Item=metrics_data)
                        successful_count += 1
                    except Exception as e:
                        logger.error(f"Failed to batch write metric: {e}")
                        failed_metrics.append(metrics_data)
        except ClientError as e:
            logger.error(f"Batch writer failed: {e}")
            raise

        return successful_count, failed_metrics

    def get_metrics(self, tenant_id: str, device_id: str = None, employee_id: str = None,
                    start_timestamp: int = None, end_timestamp: int = None, limit: int = 100):
        """
        Retrieves facial recognition metrics from DynamoDB with optional filters.

        Args:
            tenant_id: Tenant identifier
            device_id: Optional device identifier
            employee_id: Optional employee filter (uses GSI if provided)
            start_timestamp: Optional start timestamp filter (milliseconds)
            end_timestamp: Optional end timestamp filter (milliseconds)
            limit: Maximum number of records to return

        Returns:
            List of metrics records
        """
        try:
            items = []

            if employee_id:
                # Use GSI to query by employee
                key_condition = boto3.dynamodb.conditions.Key('tenant_id#employee_id').eq(f"{tenant_id}#{employee_id}")

                if start_timestamp and end_timestamp:
                    key_condition = key_condition & boto3.dynamodb.conditions.Key('timestamp').between(start_timestamp, end_timestamp)
                elif start_timestamp:
                    key_condition = key_condition & boto3.dynamodb.conditions.Key('timestamp').gte(start_timestamp)
                elif end_timestamp:
                    key_condition = key_condition & boto3.dynamodb.conditions.Key('timestamp').lte(end_timestamp)

                response = self.metrics_table.query(
                    IndexName='employee-metrics-index',
                    KeyConditionExpression=key_condition,
                    Limit=limit
                )
                items = response.get('Items', [])
            elif device_id:
                # Query by specific device
                key_condition = boto3.dynamodb.conditions.Key('tenant_id#device_id').eq(f"{tenant_id}#{device_id}")
                key_condition = key_condition & boto3.dynamodb.conditions.Key('METRICS#metrics_id').begins_with('METRICS#')

                response = self.metrics_table.query(
                    KeyConditionExpression=key_condition,
                    Limit=limit,
                    ScanIndexForward=False  # Get most recent first
                )
                items = response.get('Items', [])

                # Apply timestamp filters in memory if specified
                if start_timestamp or end_timestamp:
                    filtered_items = []
                    for item in items:
                        timestamp = item.get('timestamp', 0)
                        if start_timestamp and timestamp < start_timestamp:
                            continue
                        if end_timestamp and timestamp > end_timestamp:
                            continue
                        filtered_items.append(item)
                    items = filtered_items
            else:
                # No device_id or employee_id: scan all metrics for the tenant
                # Use FilterExpression to filter by tenant_id
                filter_expression = boto3.dynamodb.conditions.Attr('tenant_id').eq(tenant_id)

                # Add timestamp filters if specified
                if start_timestamp:
                    filter_expression = filter_expression & boto3.dynamodb.conditions.Attr('timestamp').gte(start_timestamp)
                if end_timestamp:
                    filter_expression = filter_expression & boto3.dynamodb.conditions.Attr('timestamp').lte(end_timestamp)

                response = self.metrics_table.scan(
                    FilterExpression=filter_expression,
                    Limit=limit
                )
                items = response.get('Items', [])

            return items

        except ClientError as e:
            logger.error(f"Failed to retrieve metrics from DynamoDB: {e}")
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

    def get_all_devices(self):
        try:
            response = self.devices_table.scan()
            return response.get("Items", [])
        except ClientError as e:
            logger.error(f"Failed to scan devices table: {e}")
            raise

    def upload_images_to_s3(self, worker_id: str, images: List[UploadFile]) -> List[str]:
        """
        Uploads images to S3 with automatic EXIF orientation correction.

        This method:
        1. Reads the image from the upload
        2. Automatically corrects orientation based on EXIF data
        3. Optionally compresses the image to reduce file size
        4. Uploads to S3

        Args:
            worker_id: Unique identifier for the worker
            images: List of uploaded image files

        Returns:
            List of S3 URLs for the uploaded images
        """
        image_urls = []
        for i, image in enumerate(images):
            file_key = f"{worker_id}/face_{i+1}.jpg"
            try:
                # Read the image file
                image_data = image.file.read()
                img = Image.open(BytesIO(image_data))

                # First, try to apply EXIF orientation correction
                exif_rotated = False
                try:
                    # Get EXIF data
                    exif = img.getexif()

                    # EXIF orientation tag is 0x0112 (274 in decimal)
                    orientation = exif.get(0x0112, 1)

                    # Apply rotation based on EXIF orientation
                    if orientation == 3:
                        img = img.rotate(180, expand=True)
                        exif_rotated = True
                    elif orientation == 6:
                        img = img.rotate(270, expand=True)
                        exif_rotated = True
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
                        exif_rotated = True

                    logger.info(f"EXIF orientation for {file_key}: {orientation}, rotated: {exif_rotated}")

                except (AttributeError, KeyError, IndexError) as e:
                    # If there's no EXIF data or it's malformed, just continue
                    logger.info(f"No EXIF orientation data for {file_key}: {e}")

                # ALWAYS rotate 90° to the left (90° counterclockwise) for camera images
                # This is needed because mobile camera images come rotated
                logger.info(f"Applying fixed 90° left rotation to {file_key}")
                img = img.rotate(90, expand=True)

                # Convert to RGB and remove EXIF data
                # This prevents double-rotation if the image is processed again
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                else:
                    img = img.convert('RGB')

                # Save to BytesIO buffer with optimization
                img_buffer = BytesIO()
                img.save(
                    img_buffer,
                    format='JPEG',
                    quality=90,  # Good quality with compression
                    optimize=True  # Optimize file size
                )
                img_buffer.seek(0)

                # Upload the processed image to S3
                self.s3_client.upload_fileobj(
                    img_buffer,
                    settings.S3_BUCKET_NAME,
                    file_key,
                    ExtraArgs={
                        'ContentType': 'image/jpeg',
                        'CacheControl': 'max-age=31536000'  # Cache for 1 year
                    }
                )

                image_url = f"https://{settings.S3_BUCKET_NAME}.s3.amazonaws.com/{file_key}"
                image_urls.append(image_url)

                logger.info(f"Successfully uploaded and processed {file_key}")

            except ClientError as e:
                logger.error(f"Failed to upload {file_key} to S3: {e}")
                raise
            except Exception as e:
                logger.error(f"Failed to process image {file_key}: {e}")
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
        tables = {
            settings.DYNAMODB_ADMIN_USERS_TABLE: {
                'KeySchema': [{'AttributeName': 'email', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'email', 'AttributeType': 'S'}]
            },
            settings.DYNAMODB_WORKERS_TABLE: {
                'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}]
            },
            settings.DYNAMODB_TIMESTAMPS_TABLE: {
                'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [
                    {'AttributeName': 'id', 'AttributeType': 'S'},
                    {'AttributeName': 'worker_id', 'AttributeType': 'S'}
                ],
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'worker_id-index',
                        'KeySchema': [{'AttributeName': 'worker_id', 'KeyType': 'HASH'}],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
                    }
                ]
            },
            settings.DYNAMODB_DEVICES_TABLE: {
                'KeySchema': [{'AttributeName': 'device_id', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [
                    {'AttributeName': 'device_id', 'AttributeType': 'S'},
                    {'AttributeName': 'tenant_id', 'AttributeType': 'S'},
                    {'AttributeName': 'registered_at', 'AttributeType': 'N'}
                ],
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'tenant_id-registered_at-index',
                        'KeySchema': [
                            {'AttributeName': 'tenant_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'registered_at', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
                    }
                ]
            },
            settings.DYNAMODB_ACTIVATION_CODES_TABLE: {
                'KeySchema': [{'AttributeName': 'code', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'code', 'AttributeType': 'S'}]
            },
            settings.DYNAMODB_ATTENDANCE_TABLE: {
                'KeySchema': [{'AttributeName': 'tenant_id#employee_id', 'KeyType': 'HASH'}, {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}],
                'AttributeDefinitions': [
                    {'AttributeName': 'tenant_id#employee_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'},
                    {'AttributeName': 'tenant_id', 'AttributeType': 'S'}
                ],
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'tenant_id-timestamp-index',
                        'KeySchema': [
                            {'AttributeName': 'tenant_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}
                    }
                ]
            },
            settings.DYNAMODB_AUDIT_TABLE: {
                'KeySchema': [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                'AttributeDefinitions': [{'AttributeName': 'id', 'AttributeType': 'S'}]
            },
            settings.DYNAMODB_METRICS_TABLE: {
                'KeySchema': [
                    {'AttributeName': 'tenant_id#device_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'METRICS#metrics_id', 'KeyType': 'RANGE'}
                ],
                'AttributeDefinitions': [
                    {'AttributeName': 'tenant_id#device_id', 'AttributeType': 'S'},
                    {'AttributeName': 'METRICS#metrics_id', 'AttributeType': 'S'},
                    {'AttributeName': 'tenant_id#employee_id', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'N'}
                ],
                'GlobalSecondaryIndexes': [
                    {
                        'IndexName': 'employee-metrics-index',
                        'KeySchema': [
                            {'AttributeName': 'tenant_id#employee_id', 'KeyType': 'HASH'},
                            {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 10}
                    }
                ]
            }
        }

        for table_name, schema in tables.items():
            try:
                # Set higher throughput for metrics table to handle bursts
                if table_name == settings.DYNAMODB_METRICS_TABLE:
                    throughput = {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 10}
                else:
                    throughput = {'ReadCapacityUnits': 1, 'WriteCapacityUnits': 1}

                create_table_args = {
                    'TableName': table_name,
                    'KeySchema': schema['KeySchema'],
                    'AttributeDefinitions': schema['AttributeDefinitions'],
                    'ProvisionedThroughput': throughput
                }
                if schema.get('GlobalSecondaryIndexes'):
                    create_table_args['GlobalSecondaryIndexes'] = schema['GlobalSecondaryIndexes']

                self.dynamodb.create_table(**create_table_args)
                logger.info(f"Table {table_name} created successfully.")

                waiter = self.dynamodb.meta.client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
                logger.info(f"Table {table_name} is active.")

                if schema.get('GlobalSecondaryIndexes'):
                    while True:
                        response = self.dynamodb.meta.client.describe_table(TableName=table_name)
                        all_indexes_active = True
                        if 'GlobalSecondaryIndexes' not in response['Table']:
                            all_indexes_active = False
                        else:
                            for gsi in response['Table']['GlobalSecondaryIndexes']:
                                if gsi['IndexStatus'] != 'ACTIVE':
                                    all_indexes_active = False
                                    break
                        if all_indexes_active:
                            logger.info(f"All GSIs for table {table_name} are active.")
                            break
                        else:
                            logger.info(f"Waiting for GSIs of table {table_name} to become active...")
                            time.sleep(5)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceInUseException':
                    logger.info(f"Table {table_name} already exists.")
                else:
                    logger.error(f"Failed to create table {table_name}: {e}")
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
