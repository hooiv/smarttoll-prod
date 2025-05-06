FROM python:3.10-slim

WORKDIR /app

# Set environment variables for logging and path
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    LOG_LEVEL=INFO

# Install system dependencies if needed (e.g., for non-binary psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential libpq-dev \
#  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY ./app /app/app

# Command to run the service - executes app/main.py
CMD ["python", "app/main.py"]
