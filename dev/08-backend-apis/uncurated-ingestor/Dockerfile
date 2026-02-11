FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY dev/08-backend-apis/uncurated-ingestor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library
COPY lib/ /app/lib/

# Copy service code
COPY dev/08-backend-apis/uncurated-ingestor/src/ /app/src/

# Set Python path to include lib and src
ENV PYTHONPATH=/app/src:/app/lib

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s \
    CMD curl -f http://localhost:YOUR_API_PORT/health || exit 1

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run
CMD ["python", "-m", "main"]
