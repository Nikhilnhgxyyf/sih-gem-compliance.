import google.generativeai as genai
import os
import json

# Fetch the API key we just saved in Render
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def verify_compliance_with_ai(extracted_text: str):
    # Initialize the fast, free tier model
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    # The Prompt: Instructing the AI on how to audit
    prompt = f"""
    You are an expert Indian Government Procurement Auditor. 
    Analyze the following extracted text from a bidder's PDF and check for compliance.
    
    Check for:
    1. Udyam Registration number
    2. GSTIN number
    3. PAN number
    
    If a document does not contain the information, output 'MISSING'. Do not guess.
    
    Respond STRICTLY in this JSON format:
    {{
        "compliance_score": 80,
        "checks": [
            {{"rule": "Udyam Registration", "status": "Pass", "found_value": "UDYAM-XX-00-0000000"}},
            {{"rule": "GSTIN", "status": "Fail", "found_value": "MISSING"}}
        ]
    }}
    
    Extracted Text:
    {extracted_text}
    """
    
    try:
        # Ask Gemini to process it
        response = model.generate_content(prompt)
        
        # Clean the response to ensure it is valid JSON for our frontend
        json_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_text)
    except Exception as e:
        return {"error": str(e), "status": "AI Verification Failed"}
      
