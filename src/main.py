from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.endpoints import workers, timestamps, devices, attendance, audit, admin, auth, admin_users
from src.core.config import settings
from src.services.aws_service import aws_service

app = FastAPI(
    title="Sioma Dashboard API",
    description="API to manage worker data and time tracking for the Sioma project.",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    aws_service.create_tables()
    aws_service.create_initial_admin_user_if_not_exists()

origins = [
    settings.CORS_ORIGINS_DEV,
    settings.CORS_ORIGINS_PROD,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workers.router, prefix="/api", tags=["Workers"])
app.include_router(timestamps.router, prefix="/api", tags=["Timestamps"])
app.include_router(devices.router, prefix="/api", tags=["Devices"])
app.include_router(attendance.router, prefix="/api", tags=["Attendance"])
app.include_router(audit.router, prefix="/api", tags=["Audit"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(admin_users.router, prefix="/api", tags=["Admin Users"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}

