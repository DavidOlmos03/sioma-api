from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional, List
import time

from src.models.admin import ActivationCodeCreateRequest, ActivationCodeCreateResponse, AdminDevicesListResponse, AdminDeviceResponse, DeviceDeactivateRequest, DeviceDeactivateResponse
from src.core.security import verify_admin_token
from src.services.aws_service import AWSService, aws_service

router = APIRouter()

@router.post("/admin/activation-codes", response_model=ActivationCodeCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_activation_code(
    request: ActivationCodeCreateRequest,
    is_admin: bool = Depends(verify_admin_token),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Admin endpoint to create a new activation code.
    """
    try:
        tenant_id = request.code.split('-')[0]
    except IndexError:
        raise HTTPException(status_code=422, detail="Invalid code format. Expected 'TENANT-CODE'.")

    # TODO: Validate that the admin belongs to the tenant_id.

    created_at = int(time.time() * 1000)
    code_data = {
        "code": request.code,
        "tenant_id": tenant_id,
        "description": request.description,
        "expires_at": request.expires_at,
        "status": "pending",
        "created_at": created_at,
        "used_at": None,
        "used_by_device_id": None
    }

    aws.save_activation_code(code_data)

    return ActivationCodeCreateResponse(**code_data)

@router.get("/admin/devices", response_model=AdminDevicesListResponse)
async def list_devices(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    is_admin: bool = Depends(verify_admin_token),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Admin endpoint to list all registered devices for a tenant.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required.")

    # TODO: Validate that the admin has access to this tenant_id.

    devices_data = aws.get_devices_by_tenant(x_tenant_id)
    
    devices_response: List[AdminDeviceResponse] = []
    for device in devices_data:
        # TODO: Implement actual pending_records count
        pending_records_count = 0

        devices_response.append(AdminDeviceResponse(
            device_id=device.get('device_id'),
            device_name=device.get('device_name'),
            device_model=device.get('device_model'),
            registered_at=device.get('registered_at'),
            last_sync_at=device.get('last_sync_at'),
            is_active=device.get('is_active'),
            pending_records=pending_records_count
        ))

    return AdminDevicesListResponse(devices=devices_response)

@router.put("/admin/devices/{device_id}/deactivate", response_model=DeviceDeactivateResponse)
async def deactivate_device(
    device_id: str,
    request: DeviceDeactivateRequest,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    is_admin: bool = Depends(verify_admin_token),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Admin endpoint to deactivate a specific device.
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required.")

    # TODO: Validate that the admin has access to this tenant_id.

    try:
        updated_device = aws.deactivate_device(device_id, request.reason, x_tenant_id)
        if not updated_device:
            raise HTTPException(status_code=404, detail="Device not found or already deactivated.")
        return DeviceDeactivateResponse(success=True, message="Dispositivo desactivado correctamente")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deactivate device: {str(e)}")
