from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from src.core.security import create_admin_token, verify_password
from src.models.auth import Token
from src.services.aws_service import aws_service, AWSService
from src.models.admin import AdminUser

router = APIRouter()

@router.post("/admin/login", response_model=Token)
async def login_for_access_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], aws: AWSService = Depends(lambda: aws_service)):
    user = aws.get_admin_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user['is_active']:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token = create_admin_token(data={"sub": user['email']})
    return {"access_token": access_token, "token_type": "bearer"}
