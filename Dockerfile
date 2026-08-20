FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run migrations and init database
RUN alembic upgrade head && python init_db.py || true

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
