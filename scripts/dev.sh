#!/bin/bash

# Development script for the chatbot avatar backend

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
print_status "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found. Creating from template..."
    cp .env.example .env
    print_warning "Please edit .env file with your actual configuration before running the application."
    exit 1
fi

# Run linting
print_status "Running code linting..."
if command -v ruff &> /dev/null; then
    ruff check app/ tests/
    ruff format app/ tests/
else
    print_warning "ruff not installed. Skipping linting."
fi

# Run tests
print_status "Running tests..."
if command -v pytest &> /dev/null; then
    pytest tests/ -v --cov=app
else
    print_error "pytest not installed. Install with: pip install pytest pytest-cov"
    exit 1
fi

# Check for required environment variables
print_status "Checking environment configuration..."
source .env

required_vars=("CLIENT_ID" "TENANT_ID" "CLIENT_SECRET" "COSMOS_ENDPOINT" "COSMOS_KEY" "DATA_AGENT_URL")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    print_error "Missing required environment variables:"
    printf '  %s\n' "${missing_vars[@]}"
    exit 1
fi

print_status "Environment configuration looks good!"

# Start the application
print_status "Starting the application..."
if [ "$APP_ENV" = "dev" ]; then
    uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000} --reload
else
    gunicorn -k uvicorn.workers.UvicornWorker -w 2 -c gunicorn.conf.py app.main:app
fi