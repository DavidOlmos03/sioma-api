from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import List, Optional
import uuid
import time
from decimal import Decimal

from src.models.attendance import (
    AttendanceSyncRequest, AttendanceSyncResponse, SyncedRecord, ConflictRecord, ErrorRecord, AttendanceRecordIn,
    MetricsSyncRequest, MetricsSyncResponse, SyncedMetric,
    MetricsListResponse, MetricsRecordOut, MetricsDetails, HeadEulerAngles
)
from src.core.security import get_current_device_payload, get_current_admin_user
from src.services.aws_service import AWSService, aws_service

def convert_floats_to_decimal(obj):
    """
    Recursively converts all float values to Decimal for DynamoDB compatibility.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

router = APIRouter()

@router.post("/attendance/sync", response_model=AttendanceSyncResponse)
async def sync_attendance(
    sync_request: AttendanceSyncRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    payload: dict = Depends(get_current_device_payload),
    aws: AWSService = Depends(lambda: aws_service)
):
    jwt_tenant_id = payload.get("tenant_id")
    jwt_device_id = payload.get("device_id")

    # Validation from requirements
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required.")
    
    if jwt_tenant_id != x_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant ID in token does not match X-Tenant-ID header.")

    if len(sync_request.records) > 100:
        raise HTTPException(status_code=413, detail="Payload too large. Maximum 100 records allowed.")

    synced_records: List[SyncedRecord] = []
    conflicts: List[ConflictRecord] = []
    errors: List[ErrorRecord] = []

    for record in sync_request.records:
        try:
            # Validate device_id in record
            if record.device_id != jwt_device_id:
                errors.append(ErrorRecord(local_id=record.local_id, error="DEVICE_ID_MISMATCH", message="Record device_id does not match authenticated device."))
                continue

            # Check for duplicates
            duplicates = aws.find_duplicate_attendance(jwt_tenant_id, record.employee_id, record.timestamp)
            if duplicates:
                conflicts.append(ConflictRecord(
                    local_id=record.local_id,
                    reason="DUPLICATE_TIMESTAMP",
                    message="An existing record for this employee is too close to this timestamp.",
                    existing_record=duplicates[0]
                ))
                continue

            # Process valid record
            server_id = str(uuid.uuid4())
            synced_at = int(time.time() * 1000)

            record_to_save = record.dict()
            record_to_save.update({
                "tenant_id#employee_id": f"{jwt_tenant_id}#{record.employee_id}",
                "record_id": server_id,
                "tenant_id": jwt_tenant_id,
                "synced_at": synced_at,
                "sync_status": "synced"
            })

            # Convert all float values to Decimal for DynamoDB
            record_to_save = convert_floats_to_decimal(record_to_save)

            aws.save_attendance_record(record_to_save)

            synced_records.append(SyncedRecord(
                local_id=record.local_id,
                server_id=server_id,
                synced_at=synced_at
            ))

        except Exception as e:
            errors.append(ErrorRecord(local_id=record.local_id, error="SERVER_ERROR", message=str(e)))

    return AttendanceSyncResponse(
        synced_count=len(synced_records),
        synced_records=synced_records,
        conflicts=conflicts,
        errors=errors
    )

@router.post("/attendance/metrics/sync", response_model=MetricsSyncResponse)
async def sync_metrics(
    sync_request: MetricsSyncRequest,
    payload: dict = Depends(get_current_device_payload),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Synchronizes facial recognition metrics from devices to the server for analysis and model evaluation.

    This endpoint stores detailed metrics about each recognition attempt (successful or failed),
    including quality scores, pose angles, confidence levels, and processing times.

    Uses batch processing for efficiency and handles DynamoDB throttling.
    """
    import logging
    logger = logging.getLogger(__name__)

    jwt_tenant_id = payload.get("tenant_id")
    jwt_device_id = payload.get("device_id")

    # Prepare all metrics data first
    metrics_to_save = []
    metrics_mapping = {}  # Map metrics_id to local_id for response

    for metric in sync_request.metrics:
        try:
            # Generate server ID and timestamp
            metrics_id = str(uuid.uuid4())
            synced_at = int(time.time() * 1000)

            # Prepare metrics data for DynamoDB
            metrics_data = {
                "tenant_id#device_id": f"{jwt_tenant_id}#{jwt_device_id}",
                "METRICS#metrics_id": f"METRICS#{metrics_id}",
                "tenant_id": jwt_tenant_id,
                "device_id": jwt_device_id,
                "metrics_id": metrics_id,
                "local_id": metric.local_id,
                "attendance_record_id": metric.attendance_record_id,
                "employee_id": metric.employee_id,
                "employee_id_number": metric.employee_id_number,
                "timestamp": metric.timestamp,
                "recognition_successful": metric.recognition_successful,
                "rejected_by_user": metric.rejected_by_user,
                "metrics": {
                    "overall_quality": metric.overall_quality,
                    "blur_score": metric.blur_score,
                    "brightness_score": metric.brightness_score,
                    "confidence": metric.confidence,
                    "euclidean_distance": metric.euclidean_distance,
                    "embedding_index": metric.embedding_index,
                    "processing_time_ms": metric.processing_time_ms,
                    "face_size_score": metric.face_size_score,
                    "pose_score": metric.pose_score,
                    "head_euler_angles": {
                        "x": metric.head_euler_angle_x,
                        "y": metric.head_euler_angle_y,
                        "z": metric.head_euler_angle_z
                    },
                    "used_faiss": metric.used_faiss,
                    "threshold_used": metric.threshold_used
                },
                "synced_at": synced_at
            }

            # Add GSI key if employee_id is present
            if metric.employee_id:
                metrics_data["tenant_id#employee_id"] = f"{jwt_tenant_id}#{metric.employee_id}"

            # Convert all float values to Decimal for DynamoDB
            metrics_data = convert_floats_to_decimal(metrics_data)

            metrics_to_save.append(metrics_data)
            metrics_mapping[metrics_id] = {
                'local_id': metric.local_id,
                'synced_at': synced_at
            }

        except Exception as e:
            logger.error(f"Error preparing metric {metric.local_id}: {str(e)}", exc_info=True)
            continue

    # Batch save to DynamoDB
    synced_metrics: List[SyncedMetric] = []

    if metrics_to_save:
        try:
            successful_count, failed_metrics = aws.save_metrics_batch(metrics_to_save)

            logger.info(f"Batch sync: {successful_count} successful, {len(failed_metrics)} failed out of {len(metrics_to_save)}")

            # Build response for successful metrics
            for metrics_data in metrics_to_save:
                if metrics_data not in failed_metrics:
                    metrics_id = metrics_data['metrics_id']
                    mapping = metrics_mapping[metrics_id]

                    synced_metrics.append(SyncedMetric(
                        local_id=mapping['local_id'],
                        server_id=f"metrics-{metrics_id}",
                        synced_at=mapping['synced_at']
                    ))

        except Exception as e:
            logger.error(f"Batch save failed: {str(e)}", exc_info=True)
            # Fall back to individual saves if batch fails
            logger.warning("Falling back to individual saves")

            for metrics_data in metrics_to_save:
                try:
                    aws.save_metrics_record(metrics_data)

                    metrics_id = metrics_data['metrics_id']
                    mapping = metrics_mapping[metrics_id]

                    synced_metrics.append(SyncedMetric(
                        local_id=mapping['local_id'],
                        server_id=f"metrics-{metrics_id}",
                        synced_at=mapping['synced_at']
                    ))

                except Exception as e2:
                    logger.error(f"Individual save failed for metric local_id {metrics_data['local_id']}: {str(e2)}")
                    continue

    return MetricsSyncResponse(
        synced_count=len(synced_metrics),
        synced_metrics=synced_metrics
    )

@router.get("/attendance/metrics", response_model=MetricsListResponse)
async def get_metrics(
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service),
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    device_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    recognition_successful: Optional[bool] = None,
    rejected_by_user: Optional[bool] = None,
    start_timestamp: Optional[int] = None,
    end_timestamp: Optional[int] = None,
    limit: int = 100
):
    """
    Retrieves facial recognition metrics with optional filters.

    **Autenticación:** Bearer Token (Admin)

    **Headers Requeridos:**
    - X-Tenant-ID: ID del tenant

    **Query Parameters:**
    - device_id: Filter by specific device (optional)
    - employee_id: Filter by specific employee (optional)
    - recognition_successful: Filter by success status (true/false)
    - rejected_by_user: Filter by user rejection (true/false)
    - start_timestamp: Filter metrics from this timestamp (milliseconds)
    - end_timestamp: Filter metrics until this timestamp (milliseconds)
    - limit: Maximum number of records to return (default: 100, max: 1000)
    """
    # Validate tenant_id header
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required.")

    # Limit the maximum records
    if limit > 1000:
        limit = 1000

    try:
        # Query metrics from DynamoDB
        raw_metrics = aws.get_metrics(
            tenant_id=x_tenant_id,
            device_id=device_id,
            employee_id=employee_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            limit=limit
        )

        # Convert Decimal to float and format response
        metrics_list = []
        for item in raw_metrics:
            # Convert Decimal values to float
            metrics_obj = item.get('metrics', {})

            # Apply filters if specified
            if recognition_successful is not None and item.get('recognition_successful') != recognition_successful:
                continue
            if rejected_by_user is not None and item.get('rejected_by_user') != rejected_by_user:
                continue

            metrics_record = MetricsRecordOut(
                metrics_id=item['metrics_id'],
                tenant_id=item['tenant_id'],
                device_id=item['device_id'],
                local_id=item['local_id'],
                attendance_record_id=item.get('attendance_record_id'),
                employee_id=item.get('employee_id'),
                employee_id_number=item.get('employee_id_number'),
                timestamp=item['timestamp'],
                recognition_successful=item['recognition_successful'],
                rejected_by_user=item['rejected_by_user'],
                metrics=MetricsDetails(
                    overall_quality=float(metrics_obj['overall_quality']),
                    blur_score=float(metrics_obj['blur_score']),
                    brightness_score=float(metrics_obj['brightness_score']),
                    confidence=float(metrics_obj['confidence']) if metrics_obj.get('confidence') is not None else None,
                    euclidean_distance=float(metrics_obj['euclidean_distance']) if metrics_obj.get('euclidean_distance') is not None else None,
                    embedding_index=metrics_obj.get('embedding_index'),
                    processing_time_ms=metrics_obj['processing_time_ms'],
                    face_size_score=float(metrics_obj['face_size_score']),
                    pose_score=float(metrics_obj['pose_score']),
                    head_euler_angles=HeadEulerAngles(
                        x=float(metrics_obj['head_euler_angles']['x']),
                        y=float(metrics_obj['head_euler_angles']['y']),
                        z=float(metrics_obj['head_euler_angles']['z'])
                    ),
                    used_faiss=metrics_obj['used_faiss'],
                    threshold_used=float(metrics_obj['threshold_used']) if metrics_obj.get('threshold_used') is not None else None
                ),
                synced_at=item['synced_at']
            )
            metrics_list.append(metrics_record)

        return MetricsListResponse(
            count=len(metrics_list),
            metrics=metrics_list
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve metrics: {str(e)}")
