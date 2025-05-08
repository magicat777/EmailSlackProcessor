FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/data /app/logs /app/secrets

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Args that can be passed at build time
ARG GOOGLE_CLOUD_PROJECT=""
ENV GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}

# Copy application code
# We do this last to better leverage Docker caching
COPY . .

# Command to run when container starts
ENTRYPOINT ["/app/entrypoint.sh"]