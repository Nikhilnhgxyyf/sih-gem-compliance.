# AI Coding Rules & Boundaries

## What to Do
*   **Modularity:** Keep API routes separate from heavy processing logic in the backend. 
*   **Strict Typing:** Use Pydantic in FastAPI for all incoming/outgoing data to ensure the frontend doesn't crash from bad AI responses.
*   **Vibe-Coding friendly:** Write clean, modern React code (Tailwind, Lucide icons) so v0/Cursor can easily iterate on the UI.
*   **LLM JSON Mode:** Always prompt the Gemini API to return `application/json`. Force it to strictly adhere to our compliance schema.

## What to Avoid
*   **NO Streamlit:** We are building a production-ready Next.js + FastAPI stack.
*   **NO Paid APIs:** Do not use OpenAI, Claude, or AWS Textract. Rely entirely on Gemini API (free tier) and open-source Python libraries.
*   **NO Blocking the Main Thread:** PDF parsing can be slow. Use FastAPI `async` definitions and `BackgroundTasks` if file sizes exceed 5MB.

## Error Handling
*   **Unreadable PDFs:** If PyMuPDF extracts < 50 characters, gracefully fallback to `EasyOCR`. If OCR fails, return a specific error flag to the UI: `"DOCUMENT_UNREADABLE"`.
*   **AI Hallucination:** The AI must only cite information present in the document. Prompt instruction must include: `"If the document does not contain the information, output 'MISSING'. Do not guess."`
*   
