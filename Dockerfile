# 1. Base Image
FROM python:3.10-slim

# 2. Set Environment Variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_NO_INTERACTION 1

# 3. Install Poetry
RUN pip install poetry

# 4. Set up the working directory
WORKDIR /app

# 5. Copy dependency definition files
COPY pyproject.toml poetry.lock* ./

# 6. Install dependencies
# --no-root is important to avoid installing the project itself, only dependencies
# This is a caching optimization. This layer only rebuilds if dependencies change.
RUN poetry install --no-root --only main

# 7. Copy the application code
COPY src/ /app/src/

# 8. Expose the port the app runs on
EXPOSE 8000

# 9. Set the command to run the application
CMD ["poetry", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
