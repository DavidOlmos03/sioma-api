from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    S3_BUCKET_NAME: str
    DYNAMODB_WORKERS_TABLE: str
    DYNAMODB_TIMESTAMPS_TABLE: str

    class Config:
        env_file = ".env"

settings = Settings()
