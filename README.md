# sih-gem-compliance.

#  GeM AI Auditor — Automated Procurement Compliance Engine

> **SIH Problem Statement:** Smart Document Parser and Verification Engine for GeM Portal Procurement.  
> **Live Demo:** [frontend-link](https://sih-gem-compliance.vercel.app)  
> **Backend API:** [backend-link](https://sih-gem-compliance.onrender.com/docs)

---

## Problem Overview
Government procurement officers process thousands of vendor compliance documents (PDFs, scanned images, handwritten declarations). Manual verification leads to bottlenecks, human errors, and potential fraud.

**GeM AI Auditor** leverages **Gemini Vision AI** to automate statutory document auditing, extracting critical identity numbers (Udyam, GSTIN, PAN) and generating verifiable audit trails in seconds.

---

##  Key Features
*  **Multimodal OCR & Vision:** Reads native PDFs, scanned low-quality documents, stamps, and handwritten text.
*  **Automated Compliance Scoring:** Generates a 0–100 compliance rating based on government statutory requirements.
*  **Audit Trail Generation:** Instant downloadable, print-optimized PDF Audit Certificates for official records.
*  **High-Speed Microservice Backend:** Built on FastAPI & deployed with sub-second response times.

---

## Architecture & Tech Stack

[ User UI (Vercel) ]
│ (Multipart Form Data)
▼
[ FastAPI Backend (Render) ] ──▶ [ Google Gemini 3.5 Multimodal Engine ]
│                                     │
└─── (JSON Audit Score & Summary) ◄───┘

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, Tailwind CSS, Lucide Icons, Mobile-First UI |
| **Backend** | Python 3.11, FastAPI, Uvicorn |
| **AI Engine** | Google Gemini Vision API (Flash Series) |
| **Deployment** | Vercel (Frontend), Render (Backend) |

---

##  API Reference

### `POST /api/verify-pdf`
Uploads a document for AI verification.

* **Payload:** `multipart/form-data` (`file`: PDF or Image)
* **Response:**
```json
{
  "filename": "sample_document.pdf",
  "ai_verification": {
    "compliance_score": 100,
    "checks": [
      {"rule": "Udyam Registration", "status": "Pass", "found_value": "UDYAM-MH-12-0098765"},
      {"rule": "GSTIN", "status": "Pass", "found_value": "27AAAAA0000A1Z5"},
      {"rule": "PAN", "status": "Pass", "found_value": "ABCDE1234F"}
    ],
    "summary": "Verified official compliance certificate."
  }
}

