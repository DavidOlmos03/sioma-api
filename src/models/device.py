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
