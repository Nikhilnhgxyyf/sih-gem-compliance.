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

Future Roadmap
[ ] Integration with GSTN & MCA live validation APIs.
[ ] Multi-document batch processing for bulk tender evaluation.
[ ] Fraud & forgery detection via document metadata analysis

5. Tap **Commit changes**.

---

### Step 2: The 3-Minute SIH Demo Pitch Script

When presenting to judges, follow this structure:

| Time | Slide / Action | What to Say |
|---|---|---|
| **0:00 - 0:45** | **The Problem** | *"Manual document auditing in government procurement causes massive delays and human errors. Officers often have to manually check hundreds of scanned PDFs, PANs, and Udyam certificates."* |
| **0:45 - 1:30** | **Live Failed Demo** | Upload the handwritten notes file (`1.3 ed.pdf`). Show how the AI detects it's an assignment, flags missing credentials, and scores it **0/100**. |
| **1:30 - 2:15** | **Live Passed Demo** | Upload the valid text screenshot. Show how it instantly extracts the Udyam, GSTIN, and PAN numbers, gives a **100/100 score**, and turns green. |
| **2:15 - 3:00** | **The Impact & PDF Export** | Tap **Download Official PDF Report** and show the print view. *"With one tap, the procurement officer gets an official audit certificate to attach to the tender file, reducing processing time from hours to 5 seconds."* |

---

### Final Project Status Checklist

- [x] Backend live on Render (`FastAPI`)
- [x] Vision AI connected (`Gemini 3.5 Flash`)
- [x] Frontend UI live on Vercel (`Tailwind CSS`)
- [x] Dynamic Pass/Fail status & scoring
- [x] PDF Audit Certificate export
- [x] Repository documentation (`README.md`)
