#!/bin/bash

set -e

# Ensure is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit
fi

# Define variables
IMAGE_NAME="generated-app:latest"

# Pull latest image (dummy implementation for example)
echo "Pulling latest image..."
docker pull $IMAGE_NAME

# Stop and remove current container (dummy implementation for example)
echo "Stopping current container..."
docker-compose -f docker-compose.prod.yml down

# Run the application

echo "Starting application..."
docker-compose -f docker-compose.prod.yml up -d

echo "Deployment complete."