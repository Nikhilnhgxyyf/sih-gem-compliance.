import google.generativeai as genai
import os
import json

# Fetch the API key we saved in Render
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def verify_compliance_with_ai(file_bytes: bytes, mime_type: str = "application/pdf"):
    # Initialize the fast, multimodal free tier model
    model = genai.GenerativeModel("gemini-3.6-flash")
    
    # We upgraded the prompt to also summarize what it sees
    prompt = """
    You are an expert Indian Government Procurement Auditor and Document Analyzer. 
    Look at the attached document (it might be a scanned image or handwritten).
    
    Check for:
    1. Udyam Registration number
    2. GSTIN number
    3. PAN number
    
    If this document is NOT a government document (e.g., homework, a resume, or an assignment), output 'MISSING' for the government IDs, but summarize what the document ACTUALLY is in the "summary" field.
    
    Respond STRICTLY in this JSON format:
    {
        "compliance_score": 0,
        "checks": [
            {"rule": "Udyam Registration", "status": "Pass/Fail", "found_value": "Value or MISSING"},
            {"rule": "GSTIN", "status": "Fail", "found_value": "MISSING"}
        ],
        "summary": "Brief explanation of what this document actually contains."
    }
    """
    
    try:
        # We now pass the RAW FILE BYTES directly to Gemini!
        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": file_bytes}
        ])
        
        # Clean the response to ensure it is valid JSON
        json_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_text)
    except Exception as e:
        return {"error": str(e), "status": "AI Verification Failed"}
        
