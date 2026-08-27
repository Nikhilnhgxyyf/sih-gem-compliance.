# Implementation Phases

## Phase 1: Scaffolding & Setup
*   Initialize Next.js project with Tailwind and Shadcn UI.
*   Initialize Python FastAPI backend.
*   Set up Supabase project, get API keys, and configure storage buckets.
*   Verify frontend-backend basic connection (Health check endpoint).

## Phase 2: Document Ingestion Pipeline
*   Build frontend drag-and-drop file uploader.
*   Write backend `pdf_parser.py` using PyMuPDF.
*   Implement OCR fallback for scanned tender stamps.
*   Test text extraction on sample GeM documents.

## Phase 3: The AI Verification Engine
*   Set up Gemini API connection.
*   Engineer the prompt template: *"You are an expert Indian Government Procurement Auditor..."*
*   Define the JSON output schema (Compliance Score, Rule matched, Page number cited).
*   Test AI extraction against mock PAN, Udyam, and GST docs. 

## Phase 4: UI & Dashboard Generation
*   Build the `Dashboard` view in Next.js.
*   Create visual components: Circular Progress (Score), Red/Green Status Badges, and side-by-side PDF preview.
*   Wire up the frontend to the backend AI JSON response.

## Phase 5: Deployment & Polish
*   Deploy backend to Render.
*   Deploy frontend to Vercel.
*   Add download functionality for the final PDF Audit Report.
*   Final QA and video pitch recording.
*   
