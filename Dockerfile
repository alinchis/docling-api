FROM nvidia/cuda:12.6.2-runtime-ubuntu22.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    poppler-utils \
    tesseract-ocr \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    python-multipart \
    docling \
    aiofiles \
    requests

# Create app directory
WORKDIR /app

# Create directories for temporary file storage
RUN mkdir -p /app/uploads /app/temp /app/models

# Copy application files
COPY app.py /app/
COPY config.py /app/

# Set environment variables for GPU
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]