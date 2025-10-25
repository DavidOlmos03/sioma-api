from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import time

from src.models.admin import AdminUser, AdminUserCreate, AdminUserUpdate
from src.services.aws_service import AWSService, aws_service
from src.core.security import get_current_admin_user, get_password_hash

router = APIRouter()

@router.post("/admin/users", response_model=AdminUser, status_code=status.HTTP_201_CREATED)
async def create_admin_user(
    user_data: AdminUserCreate,
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service)
):
    if aws.get_admin_user_by_email(user_data.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    
    new_user = AdminUser(
        email=user_data.email,
        hashed_password=hashed_password,
        is_active=True,
        created_at=int(time.time() * 1000)
    )

    aws.admin_users_table.put_item(Item=new_user.dict())

    return new_user

@router.get("/admin/users", response_model=List[AdminUser])
async def get_all_admin_users(
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service)
):
    users = aws.get_all_admin_users()
    return users

@router.get("/admin/users/{email}", response_model=AdminUser)
async def get_admin_user(
    email: str,
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service)
):
    user = aws.get_admin_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/admin/users/{email}", response_model=AdminUser)
async def update_admin_user(
    email: str,
    user_data: AdminUserUpdate,
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service)
):
    user = aws.get_admin_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updated_user = aws.update_admin_user(email, user_data.dict())
    return updated_user

@router.delete("/admin/users/{email}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_admin_user(
    email: str,
    current_user: str = Depends(get_current_admin_user),
    aws: AWSService = Depends(lambda: aws_service)
):
    user = aws.get_admin_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    aws.delete_admin_user(email)
