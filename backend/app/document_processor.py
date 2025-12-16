# backend/app/document_processor.py
"""
Document and Image Processing for GeneGPT.
Handles OCR for images and text extraction from documents.
"""

import io
import os
import base64
import re
from typing import Optional, Tuple
from PIL import Image
from .logger import get_logger

logger = get_logger()

# Try to import optional dependencies
try:
    import pytesseract
    # Set Tesseract path for Windows
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available - OCR will use vision model only")

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not available - PDF text extraction disabled")


def extract_text_from_image(image_bytes: bytes, filename: str = "") -> Tuple[str, Optional[str]]:
    """
    Extract text from an image using OCR (Tesseract).
    
    Args:
        image_bytes: Raw image bytes
        filename: Original filename for logging
        
    Returns:
        Tuple of (extracted_text, error_message)
    """
    try:
        # Open image with PIL
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB if necessary (for RGBA images)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        if TESSERACT_AVAILABLE:
            # Use Tesseract OCR
            text = pytesseract.image_to_string(image)
            text = text.strip()
            
            if text:
                logger.info(f"OCR extracted {len(text)} characters from {filename}")
                return text, None
            else:
                return "", "No text could be extracted from the image. The image may not contain readable text."
        else:
            # Fallback: return base64 for vision model processing
            return "", "OCR not available. Please install Tesseract for image text extraction."
            
    except Exception as e:
        logger.error(f"Error extracting text from image: {e}")
        return "", f"Error processing image: {str(e)}"


def extract_text_from_pdf(pdf_bytes: bytes, filename: str = "") -> Tuple[str, Optional[str]]:
    """
    Extract text from a PDF document.
    
    Args:
        pdf_bytes: Raw PDF bytes
        filename: Original filename for logging
        
    Returns:
        Tuple of (extracted_text, error_message)
    """
    if not PDF_AVAILABLE:
        return "", "PDF processing not available. Please install PyPDF2."
    
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        total_pages = len(pdf_reader.pages)
        
        logger.info(f"Processing PDF with {total_pages} pages")
        
        for page_num, page in enumerate(pdf_reader.pages):
            page_text = page.extract_text()
            if page_text:
                # Clean up the text
                page_text = page_text.strip()
                # For presentations, mark each page as a slide
                if 'presentation' in filename.lower() or 'slide' in filename.lower() or total_pages > 5:
                    text_parts.append(f"\n=== SLIDE {page_num + 1} of {total_pages} ===\n{page_text}")
                else:
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
        
        full_text = "\n\n".join(text_parts)
        
        if full_text.strip():
            logger.info(f"Extracted {len(full_text)} characters from {total_pages} pages of PDF {filename}")
            return full_text.strip(), None
        else:
            return "", "No text could be extracted from the PDF. It may be image-based (scanned) or encrypted. Try uploading individual screenshots of pages."
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return "", f"Error processing PDF: {str(e)}"


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string for vision model."""
    return base64.b64encode(image_bytes).decode('utf-8')


def process_uploaded_file(file_bytes: bytes, filename: str, content_type: str) -> dict:
    """
    Process an uploaded file and extract text content.
    
    Args:
        file_bytes: Raw file bytes
        filename: Original filename
        content_type: MIME type of the file
        
    Returns:
        Dict with:
        - success: bool
        - text: Extracted text (if any)
        - base64_image: Base64 encoded image (for vision model fallback)
        - file_type: Type of file processed
        - error: Error message (if any)
    """
    filename_lower = filename.lower()
    
    # Determine file type
    if content_type.startswith('image/') or any(filename_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']):
        # Image file
        text, error = extract_text_from_image(file_bytes, filename)
        
        return {
            "success": bool(text) or error is None,
            "text": text,
            "base64_image": image_to_base64(file_bytes),
            "file_type": "image",
            "error": error
        }
    
    elif content_type == 'application/pdf' or filename_lower.endswith('.pdf'):
        # PDF file
        text, error = extract_text_from_pdf(file_bytes, filename)
        
        return {
            "success": bool(text),
            "text": text,
            "base64_image": None,
            "file_type": "pdf",
            "error": error
        }
    
    elif content_type.startswith('text/') or any(filename_lower.endswith(ext) for ext in ['.txt', '.md', '.csv', '.json', '.xml']):
        # Text file - read directly
        try:
            text = file_bytes.decode('utf-8')
            return {
                "success": True,
                "text": text,
                "base64_image": None,
                "file_type": "text",
                "error": None
            }
        except UnicodeDecodeError:
            try:
                text = file_bytes.decode('latin-1')
                return {
                    "success": True,
                    "text": text,
                    "base64_image": None,
                    "file_type": "text",
                    "error": None
                }
            except Exception as e:
                return {
                    "success": False,
                    "text": "",
                    "base64_image": None,
                    "file_type": "text",
                    "error": f"Could not decode text file: {str(e)}"
                }
    
    else:
        return {
            "success": False,
            "text": "",
            "base64_image": None,
            "file_type": "unknown",
            "error": f"Unsupported file type: {content_type}. Supported: images (PNG, JPG, GIF), PDFs, and text files."
        }


def clean_ocr_text(text: str) -> str:
    """
    Clean up OCR-extracted text by removing noise and formatting issues.
    
    Args:
        text: Raw OCR text
        
    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove common OCR artifacts
    text = re.sub(r'[|]{2,}', '', text)
    
    # Fix common OCR mistakes
    text = text.replace('|', 'I')  # Common OCR mistake
    
    return text.strip()
