from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import List, Optional
import uuid
import time
from decimal import Decimal

from src.models.attendance import (
    AttendanceSyncRequest, AttendanceSyncResponse, SyncedRecord, ConflictRecord, ErrorRecord, AttendanceRecordIn,
    MetricsSyncRequest, MetricsSyncResponse, SyncedMetric
)
from src.core.security import get_current_device_payload
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
    """
    jwt_tenant_id = payload.get("tenant_id")
    jwt_device_id = payload.get("device_id")

    synced_metrics: List[SyncedMetric] = []

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

            # Save to DynamoDB
            aws.save_metrics_record(metrics_data)

            synced_metrics.append(SyncedMetric(
                local_id=metric.local_id,
                server_id=f"metrics-{metrics_id}",
                synced_at=synced_at
            ))

        except Exception as e:
            # According to spec, errors should not be returned in response
            # Just log and continue
            print(f"Error syncing metric {metric.local_id}: {str(e)}")
            continue

    return MetricsSyncResponse(
        synced_count=len(synced_metrics),
        synced_metrics=synced_metrics
    )
