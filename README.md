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
