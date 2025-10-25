from fastapi import APIRouter, Depends, status
from typing import List
import uuid
import time

from src.models.audit import AuditSyncRequest, AuditSyncResponse, SyncedAudit
from src.core.security import get_current_device_payload
from src.services.aws_service import AWSService, aws_service

router = APIRouter()

@router.post("/audit/sync", response_model=AuditSyncResponse, status_code=status.HTTP_200_OK)
async def sync_audit_logs(
    sync_request: AuditSyncRequest,
    payload: dict = Depends(get_current_device_payload),
    aws: AWSService = Depends(lambda: aws_service)
):
    tenant_id = payload.get("tenant_id")
    device_id = payload.get("device_id")

    records_to_save = []
    synced_audits = []
    synced_at = int(time.time() * 1000)

    for audit in sync_request.audits:
        server_id = str(uuid.uuid4())
        
        # The PK is tenant_id#attendance_id, but attendance_id can be null.
        # If null, we can use the audit_id itself to ensure uniqueness for the PK.
        attendance_id_part = audit.attendance_id if audit.attendance_id else server_id

        record = audit.dict()
        record.update({
            "tenant_id#attendance_id": f"{tenant_id}#{attendance_id_part}",
            "audit_id": server_id,
            "tenant_id": tenant_id,
            "device_id": device_id, # Add device_id from token
            "synced_at": synced_at
        })
        records_to_save.append(record)
        synced_audits.append(SyncedAudit(local_id=audit.local_id, server_id=server_id, synced_at=synced_at))

    if records_to_save:
        aws.save_audit_records(records_to_save)

    return AuditSyncResponse(
        success=True,
        synced_count=len(synced_audits),
        synced_audits=synced_audits
    )
