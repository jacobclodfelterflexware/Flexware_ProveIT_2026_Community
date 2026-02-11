# Multi-stage build for manufacturing data publisher
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Run as non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose health check port
EXPOSE 8090

# Run the application
CMD ["python", "-u", "src/main.py"]
