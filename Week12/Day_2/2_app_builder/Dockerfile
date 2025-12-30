# Multi-stage Dockerfile for Python FastAPI app

# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /app

# Install gcc for building packages
RUN apt-get update && apt-get install -y gcc

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Production Image
FROM python:3.11-slim

WORKDIR /app

# Copy the dependencies from the builder stage
COPY --from=builder /root/.cache /root/.cache

# Copy only necessary files
COPY . .

# Run FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]