FROM python:3.11-slim

WORKDIR /app

COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/main.py .

EXPOSE 50000

CMD ["python", "main.py"]
