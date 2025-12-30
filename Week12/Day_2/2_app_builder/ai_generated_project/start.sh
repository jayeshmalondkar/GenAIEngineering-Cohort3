#!/bin/bash
# Startup script for the generated application

echo "🚀 Starting application..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations (if needed)
echo "Setting up database..."
# Add your database setup commands here

# Start the application
echo "Starting FastAPI application..."
cd backend
python main.py
