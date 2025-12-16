from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

class DeviceRegisterRequest(BaseModel):
    activation_code: str = Field(..., example="ACME-ABC123")
    device_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    device_name: str = Field(..., example="Tablet Entrada Principal")
    device_model: str = Field(..., example="Samsung Galaxy Tab A7")
    device_manufacturer: str = Field(..., example="Samsung")
    android_version: str = Field(..., example="13")

class DeviceRegisterResponseData(BaseModel):
    device_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    tenant_id: str = Field(..., example="ACME")
    device_token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...")
    token_expires_at: Optional[int] = Field(None, example=None)
    is_active: bool = Field(True, example=True)
    registered_at: int = Field(..., example=1706140800000)

class DeviceRegisterResponse(BaseModel):
    success: bool = Field(True, example=True)
    data: DeviceRegisterResponseData

class DeviceStatusResponse(BaseModel):
    device_id: str = Field(..., example="550e8400-e29b-41d4-a716-446655440000")
    device_name: str = Field(..., example="Tablet Entrada Principal")
    is_active: bool = Field(..., example=True)
    last_sync_at: Optional[int] = Field(None, example=1706140800000)
    pending_records: int = Field(..., example=5)

class Device(BaseModel):
    device_id: str
    device_name: str
    device_model: str
    device_manufacturer: str
    android_version: str
    is_active: bool
    registered_at: int
    last_sync_at: Optional[int] = None
    tenant_id: str

class DeviceListResponse(BaseModel):
    success: bool = True
    data: list[Device]
