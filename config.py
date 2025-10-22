import os
from pathlib import Path

# Directory Configuration
BASE_DIR = Path("/app")
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
MODEL_CACHE_DIR = BASE_DIR / "models"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# File Upload Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {".pdf"}
UPLOAD_TIMEOUT = 300  # 5 minutes

# Model Configuration
MODEL_NAME = "ibm-granite/granite-docling-258M"
USE_GPU = True
GPU_DEVICE = 0

# API Configuration
API_TITLE = "Docling PDF Processing API"
API_VERSION = "1.0.0"
API_DESCRIPTION = """
Process PDF invoices and documents using IBM Granite Docling.

## Features
- PDF to Markdown conversion
- PDF to structured JSON extraction
- GPU-accelerated processing
- Invoice data extraction

## Endpoints
- POST /convert/markdown - Convert PDF to Markdown
- POST /convert/json - Convert PDF to structured JSON
- POST /extract/invoice - Extract invoice-specific fields
- GET /health - Health check
"""

# Processing Configuration
CLEANUP_AFTER_PROCESSING = True
KEEP_UPLOADED_FILES_HOURS = 1

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Security
API_KEY = os.getenv("API_KEY", None)  # Optional: set for authentication