from pydantic import BaseModel, Field
from typing import Optional, List

class ActivationCodeCreateRequest(BaseModel):
    code: str = Field(..., example="ACME-ABC123")
    description: str = Field(..., example="Tablet para entrada principal - Acme Corp")
    expires_at: Optional[int] = Field(None, example=1706227200000)

class ActivationCodeCreateResponse(BaseModel):
    code: str
    tenant_id: str
    status: str = "pending"
    created_at: int
    expires_at: Optional[int] = None
    description: str

class AdminDeviceResponse(BaseModel):
    device_id: str
    device_name: str
    device_model: str
    registered_at: int
    last_sync_at: Optional[int] = None
    is_active: bool
    pending_records: int = 0 # Placeholder for now

class AdminDevicesListResponse(BaseModel):
    devices: List[AdminDeviceResponse]

class DeviceDeactivateRequest(BaseModel):
    reason: str = Field(..., example="Dispositivo extraviado")

class DeviceDeactivateResponse(BaseModel):
    success: bool = True
    message: str = Field(..., example="Dispositivo desactivado correctamente")
