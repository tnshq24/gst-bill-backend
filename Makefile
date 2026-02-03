# Makefile for common development tasks

.PHONY: help install test lint format clean run dev health

# Default target
help:
	@echo "Available commands:"
	@echo "  install    - Install dependencies"
	@echo "  test       - Run tests with coverage"
	@echo "  lint       - Run linting"
	@echo "  format     - Format code"
	@echo "  clean      - Clean cache and temporary files"
	@echo "  run        - Run production server"
	@echo "  dev        - Run development server"
	@echo "  health     - Run health checks"

# Install dependencies
install:
	pip install -r requirements.txt

# Run tests
test:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# Run linting
lint:
	ruff check app/ tests/

# Format code
format:
	ruff format app/ tests/
	black app/ tests/

# Clean cache and temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name "*.pytest_cache" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage

# Run production server
run:
	gunicorn -k uvicorn.workers.UvicornWorker -w 2 -c gunicorn.conf.py app.main:app

# Run development server
dev:
	uvicorn app.main:app --host 0.0.0.0 --port ${APP_PORT:-8000} --reload

# Run health checks
health:
	curl -f http://localhost:${APP_PORT:-8000}/api/v1/health || exit 1
	@echo "Health check passed"

# Docker build (optional)
docker-build:
	docker build -t chatbot-avatar-backend .

# Docker run (optional)
docker-run:
	docker run -p 8000:8000 --env-file .env chatbot-avatar-backend