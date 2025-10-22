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
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    python-multipart==0.0.6 \
    docling==2.15.0 \
    torch==2.1.0 \
    transformers==4.36.0 \
    accelerate==0.25.0 \
    pillow==10.1.0 \
    pydantic==2.5.0 \
    aiofiles==23.2.1

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