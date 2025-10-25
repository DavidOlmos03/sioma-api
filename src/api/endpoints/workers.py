from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import List
import json
from datetime import datetime

from src.models.worker import WorkerCreate, WorkerResponse, WorkerPersonalData, WorkerUpdate
from src.services.aws_service import AWSService, aws_service

router = APIRouter()

@router.post("/workers", response_model=WorkerResponse, status_code=201)
async def register_worker(
    personal_data_json: str = Form(...),
    images: List[UploadFile] = File(..., max_uploads=7),
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Registers a new worker:
    - **personal_data_json**: A JSON string with worker's personal data.
    - **images**: A list of 7 face images.
    """
    try:
        personal_data_dict = json.loads(personal_data_json)
        worker_create = WorkerCreate(personal_data=WorkerPersonalData(**personal_data_dict))
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid personal_data format: {e}")

    if len(images) != 7:
        raise HTTPException(status_code=400, detail="Exactly 7 images are required.")

    worker_id = worker_create.personal_data.id

    try:
        image_urls = aws.upload_images_to_s3(worker_id, images)
        
        worker_response = WorkerResponse(
            **worker_create.personal_data.dict(),
            image_urls=image_urls,
            created_at=datetime.utcnow()
        )

        worker_data_for_db = worker_response.dict()
        worker_data_for_db['created_at'] = worker_data_for_db['created_at'].isoformat()
        aws.save_worker_data(worker_data_for_db)

        return worker_response

    except Exception as e:
        # TODO: Add cleanup logic for S3 if DynamoDB write fails
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.get("/workers", response_model=List[WorkerResponse])
async def get_all_workers(aws: AWSService = Depends(lambda: aws_service)):
    """
    Retrieves a list of all registered workers.
    """
    try:
        workers = aws.get_all_workers()
        return workers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve workers: {str(e)}")

@router.get("/workers/{worker_id}", response_model=WorkerResponse)
async def get_worker(
    worker_id: str,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Retrieves a single worker by their ID.
    """
    try:
        worker = aws.get_worker_by_id(worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        return worker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve worker: {str(e)}")

@router.put("/workers/{worker_id}", response_model=WorkerResponse)
async def update_worker(
    worker_id: str,
    worker_update: WorkerUpdate,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Updates a worker's information.
    """
    update_data = worker_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    try:
        updated_worker = aws.update_worker(worker_id, update_data)
        if not updated_worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        return updated_worker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update worker: {str(e)}")

@router.delete("/workers/{worker_id}", status_code=204)
async def delete_worker(
    worker_id: str,
    aws: AWSService = Depends(lambda: aws_service)
):
    """
    Deletes a worker.
    """
    try:
        # First, check if the worker exists
        worker = aws.get_worker_by_id(worker_id)
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")
        
        aws.delete_worker(worker_id)
        return
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete worker: {str(e)}")
