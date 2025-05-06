FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO \
    # Tell uvicorn where to find the app
    APP_MODULE="app.main:app"

# Install system dependencies if needed
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app
COPY alembic.ini .
COPY alembic/ ./alembic/ # Copy migration environment

# Expose the port the app runs on (defined by BIND_PORT env var, default 8000)
EXPOSE 8000

# Command to run migrations (optional, often done as a separate step/job) and start the server
# Using Gunicorn + Uvicorn workers is recommended for production process management.
# CMD alembic upgrade head && uvicorn ${APP_MODULE} --host 0.0.0.0 --port 8000
# For simplicity in this example, just run uvicorn:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
