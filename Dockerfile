# =============================================================================
# DineMate AI Foodbot - Production Containerfile
# =============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies for audio processing, speech synthesis, and DB connectors
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    espeak \
    ffmpeg \
    libasound2-dev \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Ensure wav_files directory exists for audio handling
RUN mkdir -p app/wav_files

# Expose Streamlit default web port
EXPOSE 8501

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch DineMate Streamlit Application
CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
