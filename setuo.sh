#!/bin/bash

echo "Setting up Scholly..."

# Create virtual environment for backend
echo "Creating Python virtual environment..."
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd ../frontend
npm install

# Copy environment files
echo "Setting up environment files..."
cd ../backend
cp .env.example .env
cd ../frontend
cp .env.example .env

# Initialize database
echo "Initializing database..."
cd ../backend
python init_db.py

echo "Setup complete!"
echo ""
echo "To start the application:"
echo "  Backend: cd backend && python run.py"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Or use Docker:"
echo "  docker-compose up -d"