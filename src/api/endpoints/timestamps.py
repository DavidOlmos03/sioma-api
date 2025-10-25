from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from datetime import datetime

from src.models.worker import TimeLogCreate, TimeLogResponse, TimeLogUpdate
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

@router.get("/timestamps", response_model=List[TimeLogResponse])
async def get_timestamps(
    worker_id: str | None = Query(None, description="Filter timestamps by worker ID"),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Retrieves a list of timestamps. Can be filtered by worker_id.
    """
    try:
        if worker_id:
            items = aws.get_timestamps_by_worker_id(worker_id)
        else:
            items = aws.get_all_timestamps()
        return items
    except ValueError as e:
        # Raised from the service if the GSI doesn't exist
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve timestamps: {str(e)}")

@router.get("/timestamps/{timestamp_id}", response_model=TimeLogResponse)
async def get_timestamp(
    timestamp_id: str,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Retrieves a single timestamp by its ID.
    """
    try:
        timestamp = aws.get_timestamp_by_id(timestamp_id)
        if not timestamp:
            raise HTTPException(status_code=404, detail="Timestamp not found")
        return timestamp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve timestamp: {str(e)}")

@router.put("/timestamps/{timestamp_id}", response_model=TimeLogResponse)
async def update_timestamp(
    timestamp_id: str,
    timestamp_update: TimeLogUpdate,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Updates a timestamp's information.
    """
    update_data = timestamp_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    try:
        updated_timestamp = aws.update_timestamp(timestamp_id, update_data)
        if not updated_timestamp:
            raise HTTPException(status_code=404, detail="Timestamp not found")
        return updated_timestamp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update timestamp: {str(e)}")

@router.delete("/timestamps/{timestamp_id}", status_code=204)
async def delete_timestamp(
    timestamp_id: str,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Deletes a timestamp.
    """
    try:
        # First, check if the timestamp exists
        timestamp = aws.get_timestamp_by_id(timestamp_id)
        if not timestamp:
            raise HTTPException(status_code=404, detail="Timestamp not found")
        
        aws.delete_timestamp(timestamp_id)
        return
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete timestamp: {str(e)}")
