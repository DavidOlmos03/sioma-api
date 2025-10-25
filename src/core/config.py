from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str
    DYNAMODB_WORKERS_TABLE: str
    DYNAMODB_TIMESTAMPS_TABLE: str = "timestamps"
    DYNAMODB_DEVICES_TABLE: str = "devices"
    DYNAMODB_ACTIVATION_CODES_TABLE: str = "activation_codes"
    DYNAMODB_ATTENDANCE_TABLE: str = "attendances"
    DYNAMODB_AUDIT_TABLE: str = "audits"
    DYNAMODB_ADMIN_USERS_TABLE: str = "admin_users"

    ADMIN_TOKEN: str = "default_admin_token"

    SECRET_KEY: str = "a_secure_default_secret_key"
    CORS_ORIGINS_DEV: str = "http://localhost:3000"
    CORS_ORIGINS_PROD: str = "http://localhost:8080"

    class Config:
        env_file = ".env"

settings = Settings()
