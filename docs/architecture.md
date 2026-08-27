# System Architecture & Tech Stack

## Tech Stack (100% Free Tier)
*   **Frontend:** Next.js (React), TailwindCSS, Shadcn UI.
*   **Backend:** Python FastAPI.
*   **Database & File Storage:** Supabase (Free tier PostgreSQL + Storage bucket).
*   **AI / LLM:** Gemini 1.5 Flash API (Generous free tier, handles up to 1M tokens—perfect for massive tender PDFs).
*   **Document Parsing:** PyMuPDF, EasyOCR (fallback for scanned documents).
*   **Hosting:** Vercel (Frontend), Render (Backend).

## App Flow
1. **User Action:** Procurement officer uploads a Tender Requirement PDF and Bidder Submission PDFs via the Next.js UI.
2. **Storage:** Next.js sends files to Supabase Storage and passes the secure URLs to the FastAPI backend.
3. **Extraction:** FastAPI downloads PDFs, uses PyMuPDF to extract text, and runs OCR on images.
4. **AI Processing:** FastAPI sends extracted text + validation rules to Gemini 1.5 Flash with a strictly typed JSON schema prompt.
5. **Response:** AI returns a JSON array of compliance checks (pass/fail/reasons).
6. **UI Render:** Next.js fetches this JSON and visualizes the Compliance Dashboard.

## Folder Structure
```text
/sih-gem-compliance
│
├── /frontend               # Next.js App
│   ├── /components         # Shadcn UI components
│   ├── /app                # Next.js pages (dashboard, upload)
│   └── package.json
│
├── /backend                # FastAPI App
│   ├── main.py             # API Endpoints
│   ├── services/
│   │   ├── pdf_parser.py   # PyMuPDF & OCR logic
│   │   └── ai_engine.py    # Gemini API integration
│   └── requirements.txt
│
└── /docs                   # Project documentation (PRD, rules, etc.)

