from fastapi import FastAPI
from src.api.endpoints import workers, timestamps, devices

app = FastAPI(
    title="Sioma Dashboard API",
    description="API to manage worker data and time tracking for the Sioma project.",
    version="1.0.0"
)

app.include_router(workers.router, prefix="/api", tags=["Workers"])
app.include_router(timestamps.router, prefix="/api", tags=["Timestamps"])
app.include_router(devices.router, prefix="/api", tags=["Devices"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
