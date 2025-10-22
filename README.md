# Docling PDF Processing API

A FastAPI-based service for processing PDF invoices using IBM's Granite Docling model, optimized for GPU acceleration on TrueNAS Scale.

## Features

- 🚀 GPU-accelerated PDF processing (NVIDIA RTX 3060 support)
- 📄 Convert PDFs to Markdown or structured JSON
- 🧾 Extract invoice-specific fields automatically
- 🔒 Optional API key authentication
- 🐳 Docker containerized with GPU support
- ⚡ Fast processing with model caching
- 🔄 Automatic file cleanup
- 📊 Health check endpoint

## Quick Start

### 1. Clone or create project structure:

```
docling-api/
├── Dockerfile
├── docker-compose.yml
├── app.py
├── config.py
├── requirements.txt
└── README.md
```

### 2. Build and Run

```bash
# Build the image
docker compose build

# Start the service
docker compose up -d

# Check logs
docker compose logs -f
```

### 3. Test the API

```bash
# Health check
curl http://localhost:8000/health

# Process a PDF
curl -X POST "http://localhost:8000/convert/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf"
```

## API Endpoints

### `GET /health`
Health check endpoint
```json
{
  "status": "healthy",
  "timestamp": "2025-10-22T10:30:00",
  "converter_ready": true
}
```

### `POST /convert/markdown`
Convert PDF to Markdown format

**Request:**
```bash
curl -X POST "http://localhost:8000/convert/markdown" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "success": true,
  "document_id": "uuid",
  "format": "markdown",
  "content": {
    "markdown": "# Document Title\n\nContent..."
  },
  "processing_time": 2.5,
  "page_count": 3
}
```

### `POST /convert/json`
Convert PDF to structured JSON

**Request:**
```bash
curl -X POST "http://localhost:8000/convert/json" \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "success": true,
  "document_id": "uuid",
  "format": "json",
  "content": {
    "pages": [...],
    "tables": [...],
    "text": "..."
  },
  "processing_time": 2.8,
  "page_count": 3
}
```

### `POST /extract/invoice`
Extract invoice-specific fields

**Request:**
```bash
curl -X POST "http://localhost:8000/extract/invoice" \
  -F "file=@invoice.pdf"
```

**Response:**
```json
{
  "success": true,
  "invoice_data": {
    "invoice_number": "INV-2024-001",
    "date": "10/22/2025",
    "vendor": "Company Name",
    "total_amount": 1500.00,
    "line_items": [],
    "raw_text": "..."
  },
  "document_text_length": 2500
}
```

## Configuration

### Environment Variables

Set in `docker-compose.yml` or pass to container:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `API_KEY` | `None` | Optional API key for authentication |
| `NVIDIA_VISIBLE_DEVICES` | `all` | GPU devices to use |

### With API Key Authentication

1. Set environment variable:
```yaml
environment:
  - API_KEY=your-secret-key-here
```

2. Include in requests:
```bash
curl -X POST "http://localhost:8000/convert/json" \
  -H "X-API-Key: your-secret-key-here" \
  -F "file=@invoice.pdf"
```

## Integration with Frappe

### Example Frappe DocType Method

```python
import frappe
import requests

@frappe.whitelist()
def process_invoice_attachment(docname):
    """Process attached invoice PDF"""
    
    # Get the document
    doc = frappe.get_doc("Purchase Invoice", docname)
    
    # Get the first PDF attachment
    attachments = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Purchase Invoice",
            "attached_to_name": docname,
            "file_name": ["like", "%.pdf"]
        },
        fields=["file_url", "name"]
    )
    
    if not attachments:
        frappe.throw("No PDF attachment found")
    
    # Get file path
    file_doc = frappe.get_doc("File", attachments[0].name)
    file_path = file_doc.get_full_path()
    
    # Call Docling API
    docling_url = "http://truenas-ip:8000"
    
    with open(file_path, 'rb') as f:
        response = requests.post(
            f"{docling_url}/extract/invoice",
            files={'file': f},
            timeout=300
        )
    
    if response.status_code == 200:
        data = response.json()
        invoice_data = data.get('invoice_data', {})
        
        # Update document fields
        if invoice_data.get('invoice_number'):
            doc.supplier_invoice_no = invoice_data['invoice_number']
        
        if invoice_data.get('date'):
            doc.bill_date = invoice_data['date']
        
        if invoice_data.get('total_amount'):
            doc.grand_total = invoice_data['total_amount']
        
        doc.save()
        frappe.db.commit()
        
        return invoice_data
    else:
        frappe.throw(f"Error processing invoice: {response.text}")
```

### Example Client Script

```javascript
frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Process Invoice PDF'), function() {
                frappe.call({
                    method: 'your_app.api.process_invoice_attachment',
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint(__('Invoice processed successfully'));
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});
```

## Performance Optimization

### GPU Configuration

The service is optimized for NVIDIA RTX 3060 (12GB VRAM):
- Model size: ~300MB
- Typical VRAM usage: 2-4GB per request
- Can handle 2-3 concurrent requests

### Processing Times

Approximate times (varies by document complexity):
- Simple 1-page invoice: 2-4 seconds
- Complex 5-page document: 8-15 seconds
- First run (model download): +30-60 seconds

### Caching

- Models are cached in `/app/models` volume
- First run downloads models (~300MB)
- Subsequent runs reuse cached models

## Troubleshooting

### GPU Not Detected

```bash
# Check GPU availability
docker exec docling-api nvidia-smi

# If not working, verify NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Out of Memory

If you get CUDA out of memory errors:
- Reduce concurrent requests
- Process smaller batches
- Check VRAM usage: `nvidia-smi`

### Slow Processing

- First run is slower (downloads models)
- Check GPU usage: `watch -n 1 nvidia-smi`
- Verify GPU is being used (should show in nvidia-smi)

### Container Won't Start

```bash
# Check logs
docker logs docling-api

# Check disk space
df -h

# Verify permissions
ls -la /mnt/pool/docling-api/
```

## File Limits

- Maximum file size: 50MB
- Allowed formats: PDF only
- Files auto-deleted after 1 hour
- Configurable in `config.py`

## Development

### Local Testing (without GPU)

```python
# In config.py, set:
USE_GPU = False
```

### Adding Custom Extractors

Enhance the invoice extraction in `app.py`:

```python
def extract_vendor_info(text):
    # Add your custom extraction logic
    pass

def extract_line_items(text):
    # Parse line items from tables
    pass
```

## Production Deployment

### Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name docling.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        client_max_body_size 50M;
    }
}
```

### Monitoring

```bash
# Container stats
docker stats docling-api

# GPU monitoring
watch -n 1 nvidia-smi

# Logs
docker logs -f --tail 100 docling-api
```

## Support

For issues related to:
- **Docling**: https://github.com/DS4SD/docling
- **Granite Model**: https://huggingface.co/ibm-granite/granite-docling-258M
- **TrueNAS Scale**: https://www.truenas.com/docs/scale/

## License

This wrapper service follows the same Apache 2.0 license as Granite Docling.

## Credits

- **IBM Research** - Granite Docling model
- **Docling Team** - Document processing library
- Built for property management with Frappe