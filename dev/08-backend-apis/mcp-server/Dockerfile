FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# MCP Server configuration
ENV MCP_TRANSPORT=http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=YOUR_API_PORT

# Default backend URLs (override in K8s deployment)
ENV MIDDLEWARE_URL=http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT
ENV INGESTOR_URL=http://YOUR_K8S_SERVICE_HOST:YOUR_API_PORT

EXPOSE 8080 8081

CMD ["python", "-m", "src.server"]
