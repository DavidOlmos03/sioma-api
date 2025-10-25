from fastapi import APIRouter, Depends, Header, HTTPException, status
from typing import List, Optional
import uuid
import time

from src.models.attendance import AttendanceSyncRequest, AttendanceSyncResponse, SyncedRecord, ConflictRecord, ErrorRecord, AttendanceRecordIn
from src.core.security import get_current_device_payload
from src.services.aws_service import AWSService, aws_service

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
