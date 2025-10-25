from pydantic import BaseModel, Field
from typing import List, Optional, Any

class AuditRecordIn(BaseModel):
    local_id: int
    attendance_id: Optional[str] = None # Can be null
    action: str
    employee_id_detected: Optional[str] = None
    employee_id_actual: Optional[str] = None
    performed_by_user_id: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[str] = None # JSON string
    timestamp: int

class AuditSyncRequest(BaseModel):
    audits: List[AuditRecordIn]

class SyncedAudit(BaseModel):
    local_id: int
    server_id: str
    synced_at: int

class AuditSyncResponse(BaseModel):
    success: bool = True
    synced_count: int
    synced_audits: List[SyncedAudit]
