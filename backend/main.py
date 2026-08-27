from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF for reading PDFs
from ai_engine import verify_compliance_with_ai

app = FastAPI(title="GeM Compliance AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "message": "GeM AI Document Parser is Live!"}

@app.post("/api/verify-pdf")
async def verify_pdf(file: UploadFile = File(...)):
    # 1. Read PDF file securely
    content = await file.read()
    
    # 2. Extract text using PyMuPDF
    doc = fitz.open(stream=content, filetype="pdf")
    extracted_text = ""
    for page in doc:
        extracted_text += page.get_text()
        
    if not extracted_text.strip():
        return {"error": "DOCUMENT_UNREADABLE", "message": "Could not extract text. Might be a scanned image."}
        
    # 3. Send text to Gemini AI for compliance checking
    result = verify_compliance_with_ai(extracted_text)
    
    return {
        "filename": file.filename, 
        "ai_verification": result
    }
    
