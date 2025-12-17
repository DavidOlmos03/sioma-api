# 1. Base Image
FROM python:3.10-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_NO_INTERACTION 1

# 3. Install system dependencies for Pillow
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Poetry
RUN pip install poetry

# 5. Set up the working directory
WORKDIR /app

# 6. Copy dependency definition files
COPY pyproject.toml poetry.lock* ./

# 7. Install dependencies
# --no-root is important to avoid installing the project itself, only dependencies
# This is a caching optimization. This layer only rebuilds if dependencies change.
RUN poetry install --no-root --only main

# 8. Copy the application code
COPY src/ /app/src/

# 9. Expose the port the app runs on
EXPOSE 8000

# 10. Set the command to run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
