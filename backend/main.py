from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
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
    return {"status": "online", "message": "GeM AI Vision Parser is Live!"}

@app.post("/api/verify-pdf")
async def verify_pdf(file: UploadFile = File(...)):
    # 1. Read the raw file bytes securely
    content = await file.read()
    mime_type = file.content_type or "application/pdf"
    
    # 2. Send the RAW PDF directly to Gemini AI Vision!
    result = verify_compliance_with_ai(content, mime_type)
    
    return {
        "filename": file.filename, 
        "ai_verification": result
    }
    
