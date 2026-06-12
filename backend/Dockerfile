# Backend: FastAPI + SSE deliberation engine
FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
EXPOSE 8000

# JURY_* flags (beliefs/tom/stream/reflect) and *_API_KEY come from the environment
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
