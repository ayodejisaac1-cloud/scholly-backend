.PHONY: help install backend frontend docker-up docker-down test clean

help:
	@echo "Available commands:"
	@echo "  make install      Install all dependencies"
	@echo "  make backend      Run backend server"
	@echo "  make frontend     Run frontend server"
	@echo "  make docker-up    Start Docker containers"
	@echo "  make docker-down  Stop Docker containers"
	@echo "  make test         Run tests"
	@echo "  make clean        Clean temporary files"

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && python run.py

frontend:
	cd frontend && npm run dev

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

test:
	cd backend && pytest
	cd frontend && npm test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "node_modules" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +