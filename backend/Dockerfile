# --- Base stage ---
FROM python:3.11-slim-bullseye as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser

# Set work directory
WORKDIR /app

# Install system dependencies (only what’s necessary)
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Change to non-root user
USER appuser

# Expose port for FastAPI
EXPOSE 8000

# Add a simple healthcheck
HEALTHCHECK --interval=30s --timeout=3s CMD curl --fail http://localhost:8000/health || exit 1

# Run with Uvicorn
CMD ["uvicorn", "reflects.main:app", "--host", "0.0.0.0", "--port", "8000"]
