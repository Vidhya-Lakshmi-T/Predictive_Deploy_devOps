# =============================================================================
# Dockerfile — Backend FastAPI Service
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Create log file location
RUN touch /app/rollback.log

WORKDIR /app/backend

EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
