import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import FastAPI, File, HTTPException, UploadFile, Header, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=config.API_DESCRIPTION
)

# Global converter instance
converter: Optional[DocumentConverter] = None


class ConversionResponse(BaseModel):
    success: bool
    document_id: str
    format: str
    content: dict
    processing_time: float
    page_count: int


class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    vendor: Optional[str] = None
    total_amount: Optional[float] = None
    line_items: list = []
    raw_text: str


class ErrorResponse(BaseModel):
    error: str
    detail: str


def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if configured"""
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )


@app.on_event("startup")
async def startup_event():
    """Initialize the document converter on startup"""
    global converter
    try:
        logger.info("Initializing Docling DocumentConverter...")
        
        # Configure pipeline options for GPU if available
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        
        # Initialize converter
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )
        
        logger.info("DocumentConverter initialized successfully")
        
        # Log GPU availability
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                logger.info(f"GPU available: {gpu_name}")
            else:
                logger.warning("GPU not available, using CPU")
        except Exception as e:
            logger.warning(f"Could not check GPU status: {e}")
            
    except Exception as e:
        logger.error(f"Failed to initialize DocumentConverter: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down...")
    # Clean up temporary files
    cleanup_old_files()


def cleanup_old_files():
    """Remove old uploaded and temporary files"""
    try:
        import time
        current_time = time.time()
        cutoff_time = current_time - (config.KEEP_UPLOADED_FILES_HOURS * 3600)
        
        for directory in [config.UPLOAD_DIR, config.TEMP_DIR]:
            for file_path in directory.glob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    logger.debug(f"Deleted old file: {file_path}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


async def save_upload_file(upload_file: UploadFile) -> Path:
    """Save uploaded file to disk"""
    try:
        # Generate unique filename
        file_ext = Path(upload_file.filename).suffix.lower()
        if file_ext not in config.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {config.ALLOWED_EXTENSIONS}"
            )
        
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = config.UPLOAD_DIR / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            content = await upload_file.read()
            
            # Check file size
            if len(content) > config.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large. Max size: {config.MAX_FILE_SIZE / 1024 / 1024}MB"
                )
            
            await f.write(content)
        
        logger.info(f"Saved uploaded file: {file_path}")
        return file_path
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "converter_ready": converter is not None
    }


@app.post("/convert/markdown", response_model=ConversionResponse)
async def convert_to_markdown(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None)
):
    """Convert PDF to Markdown format"""
    verify_api_key(x_api_key)
    
    if not converter:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    file_path = None
    start_time = datetime.now()
    
    try:
        # Save uploaded file
        file_path = await save_upload_file(file)
        
        # Convert document
        logger.info(f"Converting {file_path} to Markdown...")
        result = converter.convert(str(file_path))
        
        # Export to markdown
        markdown_content = result.document.export_to_markdown()
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = ConversionResponse(
            success=True,
            document_id=str(uuid.uuid4()),
            format="markdown",
            content={"markdown": markdown_content},
            processing_time=processing_time,
            page_count=len(result.document.pages)
        )
        
        logger.info(f"Conversion successful in {processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Cleanup
        if file_path and config.CLEANUP_AFTER_PROCESSING:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")


@app.post("/convert/json", response_model=ConversionResponse)
async def convert_to_json(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None)
):
    """Convert PDF to structured JSON format"""
    verify_api_key(x_api_key)
    
    if not converter:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    file_path = None
    start_time = datetime.now()
    
    try:
        file_path = await save_upload_file(file)
        
        logger.info(f"Converting {file_path} to JSON...")
        result = converter.convert(str(file_path))
        
        # Export to dict
        json_content = result.document.export_to_dict()
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        response = ConversionResponse(
            success=True,
            document_id=str(uuid.uuid4()),
            format="json",
            content=json_content,
            processing_time=processing_time,
            page_count=len(result.document.pages)
        )
        
        logger.info(f"Conversion successful in {processing_time:.2f}s")
        return response
        
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if file_path and config.CLEANUP_AFTER_PROCESSING:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")


@app.post("/extract/invoice")
async def extract_invoice_data(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None)
):
    """Extract invoice-specific fields from PDF"""
    verify_api_key(x_api_key)
    
    if not converter:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    file_path = None
    
    try:
        file_path = await save_upload_file(file)
        
        logger.info(f"Extracting invoice data from {file_path}...")
        result = converter.convert(str(file_path))
        
        # Get text content
        text_content = result.document.export_to_markdown()
        
        # Basic invoice field extraction (you can enhance this with more sophisticated parsing)
        invoice_data = InvoiceData(raw_text=text_content)
        
        # Simple extraction logic - enhance based on your needs
        lines = text_content.split('\n')
        for line in lines:
            line_lower = line.lower()
            if 'invoice' in line_lower and '#' in line:
                # Try to extract invoice number
                parts = line.split('#')
                if len(parts) > 1:
                    invoice_data.invoice_number = parts[1].strip().split()[0]
            
            if 'date' in line_lower:
                # Basic date extraction
                import re
                date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
                match = re.search(date_pattern, line)
                if match:
                    invoice_data.date = match.group(0)
            
            if 'total' in line_lower or 'amount' in line_lower:
                # Basic amount extraction
                import re
                amount_pattern = r'\$?\s*\d+[,.]?\d*\.?\d{0,2}'
                match = re.search(amount_pattern, line)
                if match:
                    try:
                        amount_str = match.group(0).replace('$', '').replace(',', '')
                        invoice_data.total_amount = float(amount_str)
                    except:
                        pass
        
        return {
            "success": True,
            "invoice_data": invoice_data.dict(),
            "document_text_length": len(text_content)
        }
        
    except Exception as e:
        logger.error(f"Invoice extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        if file_path and config.CLEANUP_AFTER_PROCESSING:
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception as e:
                    logger.warning(f"Failed to delete file: {e}")


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "Docling PDF Processing API",
        "version": config.API_VERSION,
        "endpoints": {
            "health": "/health",
            "convert_markdown": "/convert/markdown",
            "convert_json": "/convert/json",
            "extract_invoice": "/extract/invoice",
            "docs": "/docs"
        }
    }