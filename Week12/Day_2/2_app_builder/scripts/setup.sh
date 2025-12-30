#!/bin/bash

# Ensure script fails on any error
set -e

# Print all commands being executed
set -x

# Load environment variables
if [ -f .env ]; then
  export $(cat .env | xargs)
fi

# Create virtual environment if not exists
if [ ! -d "env" ]; then
  python3 -m venv env
fi

# Activate virtual environment
source env/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Start the application
uvicorn main:app --reload