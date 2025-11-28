# Use Python 3.11 base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        pkg-config \
        python3-dev \
        libopus0 \
        libopus-dev \
        opus-tools \
        libsndfile1 \
        libsndfile1-dev \
        portaudio19-dev \
        libportaudio2 \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir opuslib==3.0.1 && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose ports
EXPOSE 5001 5002

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV LD_LIBRARY_PATH=/usr/local/lib:/usr/lib:/lib
ENV PYTHONPATH=/app

# Startup command
CMD ["python3", "app.py"] 