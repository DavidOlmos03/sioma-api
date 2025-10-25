from pydantic import BaseModel, Field
from typing import List, Optional, Any

class AttendanceRecordIn(BaseModel):
    local_id: int
    employee_id: str
    type: str # "ENTRY" or "EXIT"
    timestamp: int
    confidence: float
    liveness_passed: bool
    device_id: str
    created_at: int

class AttendanceSyncRequest(BaseModel):
    records: List[AttendanceRecordIn]

class SyncedRecord(BaseModel):
    local_id: int
    server_id: str
    synced_at: int

class ConflictRecord(BaseModel):
    local_id: int
    reason: str
    message: str
    existing_record: Optional[dict[str, Any]] = None

class ErrorRecord(BaseModel):
    local_id: int
    error: str
    message: str

class AttendanceSyncResponse(BaseModel):
    success: bool = True
    synced_count: int
    synced_records: List[SyncedRecord]
    conflicts: List[ConflictRecord]
    errors: List[ErrorRecord]

class AttendanceUpdateRecord(BaseModel):
    server_id: str
    employee_id: str
    type: str
    timestamp: int
    device_id: str
    action: str # CREATED, DELETED
    # Fields for DELETED action
    deleted_by_admin_id: Optional[int] = None
    deletion_reason: Optional[str] = None

class AttendanceUpdatesResponse(BaseModel):
    updates: List[AttendanceUpdateRecord]
    last_sync_timestamp: int
