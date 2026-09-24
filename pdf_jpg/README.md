# pdf_jpg

Convert PDF pages to JPG images. Uses [PyMuPDF](https://pymupdf.readthedocs.io/) for rendering — no system dependencies (no poppler, no ImageMagick).

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Basic: convert each page to JPG, output to {pdf_name}_jpg/
python -m pdf_jpg document.pdf

# Custom output directory
python -m pdf_jpg document.pdf -o images/

# Higher resolution
python -m pdf_jpg document.pdf --dpi 300

# Adjust JPEG quality (1–100)
python -m pdf_jpg document.pdf -q 85
```

## API

```python
from pdf_jpg import pdf_to_jpg

paths = pdf_to_jpg(
    pdf_path="document.pdf",
    output_dir="images/",   # optional, defaults to {pdf_name}_jpg/
    dpi=150,                # optional, default 150
    quality=92,             # optional, default 92
)
```
