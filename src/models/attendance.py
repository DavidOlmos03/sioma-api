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

# Metrics models
class MetricsRecordIn(BaseModel):
    local_id: int
    attendance_record_id: Optional[str] = None
    employee_id: Optional[str] = None
    employee_id_number: Optional[str] = None
    timestamp: int
    recognition_successful: bool
    rejected_by_user: bool
    # Quality metrics (High priority)
    overall_quality: float
    blur_score: float
    brightness_score: float
    confidence: Optional[float] = None
    euclidean_distance: Optional[float] = None
    embedding_index: Optional[int] = None
    processing_time_ms: int
    # Capture metrics (Medium priority)
    face_size_score: float
    pose_score: float
    head_euler_angle_x: float
    head_euler_angle_y: float
    head_euler_angle_z: float
    used_faiss: bool
    threshold_used: Optional[float] = None

class MetricsSyncRequest(BaseModel):
    metrics: List[MetricsRecordIn]

class SyncedMetric(BaseModel):
    local_id: int
    server_id: str
    synced_at: int

class MetricsSyncResponse(BaseModel):
    success: bool = True
    synced_count: int
    synced_metrics: List[SyncedMetric]

# Models for GET metrics endpoint
class HeadEulerAngles(BaseModel):
    x: float
    y: float
    z: float

class MetricsDetails(BaseModel):
    overall_quality: float
    blur_score: float
    brightness_score: float
    confidence: Optional[float] = None
    euclidean_distance: Optional[float] = None
    embedding_index: Optional[int] = None
    processing_time_ms: int
    face_size_score: float
    pose_score: float
    head_euler_angles: HeadEulerAngles
    used_faiss: bool
    threshold_used: Optional[float] = None

class MetricsRecordOut(BaseModel):
    metrics_id: str
    tenant_id: str
    device_id: str
    local_id: int
    attendance_record_id: Optional[str] = None
    employee_id: Optional[str] = None
    employee_id_number: Optional[str] = None
    timestamp: int
    recognition_successful: bool
    rejected_by_user: bool
    metrics: MetricsDetails
    synced_at: int

class MetricsListResponse(BaseModel):
    success: bool = True
    count: int
    metrics: List[MetricsRecordOut]
