from fastapi import APIRouter, status, Depends, HTTPException
from src.models.device import DeviceRegisterRequest, DeviceRegisterResponse, DeviceRegisterResponseData
from src.services.aws_service import AWSService, aws_service
from src.core.security import create_device_token
import time

router = APIRouter()

@router.post("/devices/register", response_model=DeviceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    device_data: DeviceRegisterRequest,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Registers a new device in the system using an activation code.
    """
    # 1. Validate activation code
    activation_code = aws.get_activation_code(device_data.activation_code)
    if not activation_code:
        raise HTTPException(status_code=400, detail="Invalid activation code.")

    if activation_code.get('status') != 'pending':
        raise HTTPException(status_code=400, detail="Activation code has already been used.")

    expires_at = activation_code.get('expires_at')
    if expires_at and int(time.time() * 1000) > expires_at:
        raise HTTPException(status_code=400, detail="Activation code has expired.")

    # 2. Check for device conflicts
    if aws.get_device_by_id(device_data.device_id):
        raise HTTPException(status_code=409, detail="Device already registered.")

    # 3. Extract tenant_id and create JWT
    try:
        tenant_id = device_data.activation_code.split('-')[0]
    except IndexError:
        raise HTTPException(status_code=422, detail="Invalid activation_code format. Expected 'TENANT-CODE'.")

    token_data = {"tenant_id": tenant_id, "device_id": device_data.device_id}
    device_token = create_device_token(token_data)

    # 4. Save device registration to DynamoDB
    registered_at_ms = int(time.time() * 1000)
    
    device_registration_data = device_data.dict()
    device_registration_data.update({
        "tenant_id": tenant_id,
        "device_token": device_token,
        "is_active": True,
        "registered_at": registered_at_ms,
        "last_sync_at": None,
        "deactivated_at": None,
        "deactivation_reason": None
    })
    aws.save_device_registration(device_registration_data)

    # TODO: Mark the activation code as "used" in the ActivationCodes table

    # 5. Prepare and return response
    response_data = DeviceRegisterResponseData(
        device_id=device_data.device_id,
        tenant_id=tenant_id,
        device_token=device_token,
        token_expires_at=None, # Per requirements, no expiration by default
        is_active=True,
        registered_at=registered_at_ms
    )

    return DeviceRegisterResponse(success=True, data=response_data)
