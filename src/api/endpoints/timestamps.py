from fastapi import APIRouter, Depends, HTTPException
from typing import List
from datetime import datetime

from src.models.worker import TimeLogCreate, TimeLogResponse
from src.services.aws_service import AWSService, aws_service

router = APIRouter()

@router.post("/timestamps", response_model=TimeLogResponse, status_code=201)
async def record_timestamp(
    log_data: TimeLogCreate,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Records a new timestamp event (entry/exit) for a worker.
    """
    try:
        timestamp_response = TimeLogResponse(
            worker_id=log_data.worker_id,
            event_type=log_data.event_type,
            timestamp=datetime.utcnow()
        )
        timestamp_data_for_db = timestamp_response.dict()
        timestamp_data_for_db['timestamp'] = timestamp_data_for_db['timestamp'].isoformat()
        aws.save_timestamp_data(timestamp_data_for_db)
        return timestamp_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record timestamp: {str(e)}")
