from pydantic import BaseModel, Field, EmailStr
from typing import List
from datetime import datetime
import uuid

class WorkerPersonalData(BaseModel):
    id: str = Field(default_factory=lambda: f"worker-{uuid.uuid4()}")
    document_id: str
    first_name: str
    last_name: str
    email: EmailStr
    
class WorkerCreate(BaseModel):
    personal_data: WorkerPersonalData
    
class WorkerResponse(WorkerPersonalData):
    image_urls: List[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class TimeLogCreate(BaseModel):
    worker_id: str
    event_type: str # "entry" or "exit"

class TimeLogResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"log-{uuid.uuid4()}")
    worker_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
