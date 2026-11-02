import pymupdf
import os

def extract_text_from_pdf(file_path: str) -> str:
    """
    Opens a local PDF file and extracts raw text from all pages.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document not found at: {file_path}")
    
    doc = pymupdf.open(file_path)
    text = ""
    for page in doc:
        text += str(page.get_text())
    
    doc.close()
    return text

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits large text into smaller overlapping chunks for semantic embeddings.
    Overlap prevents cutting critical sentences in half.
    """
    words = text.split()
    chunks = []
    
    # Step through the words array, moving forward by (chunk_size - overlap)
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i:i + chunk_size]
        chunk = " ".join(chunk_words)
        chunks.append(chunk)
        
    return chunks