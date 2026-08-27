# Product Requirements Document (PRD)

## Project Overview
**Problem Statement:** SIH26100 - AI-Powered Integrated Bid Compliance Verification Platform for GeM Procurement. 
**Goal:** Build a 100% free-to-deploy, AI-driven platform that automates the verification of bidder compliance documents (Udyam, GSTN, PAN, Make in India, etc.) for government procurement officers. 

## Target Users
*   **Primary:** GeM Procurement Officers (need quick, reliable compliance scoring and decision support). 
*   **Secondary:** Internal Government Auditors (need downloadable logs of the AI's decision-making process). 

## Core Features
1.  **Multi-Document Ingestion Engine:** Upload multiple bidder PDFs (Tender specs, Technical Bids, Financials, Statutory docs).
2.  **AI Verification Engine:** Extracts data and cross-verifies against Udyam, GST, PAN, and specific tender rules. 
3.  **Compliance Scorecard:** An instant dashboard showing a percentage match, risk level (Low, Medium, High), and an AI recommendation (Pass/Fail). 
4.  **Evidence-Based Flagging:** Highlights the exact page/text where a document fails compliance.
5.  **Audit Trail:** Downloadable PDF report of the compliance check for record-keeping. 

## Out of Scope (For Prototype)
*   Live API integration with actual government databases (we will simulate this using the LLM's cross-referencing of uploaded PDFs).
*   
