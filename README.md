# Sioma Dashboard API

API to manage worker data and time tracking for the Sioma project, designed to run entirely within a Docker environment.

## Prerequisites

- Docker
- Docker Compose

## Setup

1.  **Create an environment file:**

    Copy the example environment file `.env.example` to a new file named `.env`.

    ```bash
    cp .env.example .env
    ```

2.  **Update environment variables:**

    Open the `.env` file and replace the placeholder values with your actual AWS credentials and desired service names.

    ```
    AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
    AWS_REGION=us-east-1

    S3_BUCKET_NAME=sioma-face-images
    DYNAMODB_WORKERS_TABLE=sioma-workers
    DYNAMODB_TIMESTAMPS_TABLE=sioma-timestamps
    ```

    **Note:** The AWS services (S3 bucket, DynamoDB tables) must be created in your AWS account beforehand for the application to connect to them.

## Running the Application

1.  **Build and start the services:**

    Run the following command to build the Docker image and start the API service in detached mode.

    ```bash
    docker-compose up --build -d
    ```

2.  **Access the API:**

    The API will be available at `http://localhost:8000`.

3.  **API Documentation (Swagger):**

    Interactive API documentation is available at `http://localhost:8000/docs`.

## Running Tests

To run the unit tests, execute the following command. This will start a temporary container, run the tests against a mocked AWS environment, and then remove the container.

```bash
docker-compose run --rm api poetry run pytest
```

## API Endpoints

Below is a summary of the available API endpoints.

### Health Check

- `GET /health`: Checks the operational status of the API.

### Device (Client-Facing)

- `POST /api/devices/register`: Registers a new device using a one-time activation code.
- `GET /api/devices/status`: Retrieves the status of the currently authenticated device.

### Attendance (Client-Facing)

- `POST /api/attendance/sync`: Uploads a batch of attendance records from a device.
- `GET /api/attendance/updates`: Downloads attendance records created or modified since a given timestamp.

### Audit (Client-Facing)

- `POST /api/audit/sync`: Uploads a batch of audit log records from a device.

### Admin

- `POST /api/admin/activation-codes`: (Admin) Creates a new activation code for device registration.
- `GET /api/admin/devices`: (Admin) Lists all registered devices for a specific tenant.
- `PUT /api/admin/devices/{device_id}/deactivate`: (Admin) Deactivates a device, preventing it from syncing.

### Legacy Endpoints

These endpoints appear to be part of a separate or legacy feature set.

- **Workers**
  - `POST /api/workers`: Register a new worker with face images.
  - `GET /api/workers`: Get a list of all workers.
  - `GET /api/workers/{worker_id}`: Get a single worker by ID.
  - `PUT /api/workers/{worker_id}`: Update a worker's information.
  - `DELETE /api/workers/{worker_id}`: Delete a worker.

- **Timestamps**
  - `POST /api/timestamps`: Record a new timestamp event for a worker.
  - `GET /api/timestamps`: Get a list of all timestamps, optionally filtered by `worker_id`.
  - `GET /api/timestamps/{timestamp_id}`: Get a single timestamp by ID.
  - `PUT /api/timestamps/{timestamp_id}`: Update a timestamp.
  - `DELETE /api/timestamps/{timestamp_id}`: Delete a timestamp.


## Project Structure

-   `src/`: Main application source code.
    -   `api/`: FastAPI endpoints.
    -   `core/`: Configuration and settings.
    -   `models/`: Pydantic data models.
    -   `services/`: Business logic, including the AWS service wrapper.
    -   `main.py`: FastAPI application entry point.
-   `tests/`: Unit and integration tests.
-   `pyproject.toml`: Project dependencies managed by Poetry.
-   `Dockerfile`: Instructions to build the application's Docker image.
-   `docker-compose.yml`: Orchestration of the Docker services.
-   `.env`: Local environment variables (gitignored).
-   `.env.example`: Example environment file.
