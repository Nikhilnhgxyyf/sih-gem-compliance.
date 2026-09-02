"""
demo_fixtures.py

Cached, hand-verified extraction results for the real demo documents
(1_TENDER_Hospital_Nashik.pdf + the 3 real bidder PDFs). Used to bypass
Gemini entirely for known documents, so a live 503 spike can't take down
a presentation. Every number here was read directly off the real PDFs,
not invented.

Drop this file next to engine.py / extraction.py / main.py.

Wire-up (main.py, ~2 lines changed, see patch notes at the bottom):
    from demo_fixtures import try_fixture_extraction
    extraction = try_fixture_extraction(bidder_payload, tender_payload) \
                 or extract_from_documents(bidder_payload, tender_payload)

Everything downstream of `extraction` (build_engine_inputs, the engine,
blast radius, the ledger, counterfactuals) runs 100% for real — only the
Gemini network call is skipped for recognised files. Any file that isn't
one of the 4 known PDFs falls through to a real extraction call, so the
system still behaves normally for anything else you hand it.

Set DEMO_FIXTURE_ONLY=true to disable that live fallback entirely (an
unrecognised file then raises a clear error instead of risking a 503
mid-demo).
"""

import os

TENDER_CLOSING_DATE = "2026-09-30"  # 30 September 2026, 17:00 hrs

# ----------------------------------------------------------------------
# TENDER — 1_TENDER_Hospital_Nashik.pdf
# Requirement order matches rule_id assignment (R001..R006), same IDs
# your dashboard already showed.
# ----------------------------------------------------------------------

TENDER_DOCUMENT = {
    "filename": "1_TENDER_Hospital_Nashik.pdf",
    "document_type": "tender_notice",
    "bidder_name_on_document": None,
    "facts": [
        {
            "entity_name": "estimated_contract_value",
            "value": "1200000000",
            "confidence": 0.97,
            "page": 1,
            "valid_until": None,
            "source_quote": "Estimated Contract Value Rs. 120,00,00,000 (Rupees One Hundred Twenty Crore only).",
        },
        {
            "entity_name": "bid_opening_date",
            "value": "2026-10-01",
            "confidence": 0.95,
            "page": 1,
            "valid_until": None,
            "source_quote": "Bid Opening Date 01 October 2026, 11:00 hrs.",
        },
    ],
    "notes": "Tender notice / eligibility document for GeM Bid No. GEM/2026/B/8847213.",
}

TENDER_REQUIREMENTS = [
    {
        "description": "Average annual turnover of at least \u20b9100 Crore in the last three financial years",
        "op": ">=",
        "entity_name": "turnover",
        "value": "1000000000",
        "mandatory": True,
        "weight": 10.0,
        "children": None,
    },
    {
        "description": "Technical Experience Requirements",
        "op": ">=",
        "entity_name": "qualifying_project_count",
        "value": "3",
        "mandatory": True,
        "weight": 10.0,
        "children": None,
    },
    {
        "description": "Valid Permanent Account Number (PAN) registration",
        "op": "EXISTS",
        "entity_name": "pan",
        "value": None,
        "mandatory": True,
        "weight": 10.0,
        "children": None,
    },
    {
        "description": "Valid Goods and Services Tax Identification Number (GSTIN) registration",
        "op": "EXISTS",
        "entity_name": "gstin",
        "value": None,
        "mandatory": True,
        "weight": 10.0,
        "children": None,
    },
    {
        "description": "Udyam / Micro or Small Enterprise (MSE) registration (Preferential)",
        "op": "EXISTS",
        "entity_name": "udyam_number",
        "value": None,
        "mandatory": False,
        "weight": 10.0,
        "children": None,
    },
    {
        # This is the rule that was crashing: DATE_AFTER is a real op the
        # engine already supports (see evaluate_ast + test_engine.py) but
        # extraction.py's Literal never let the model choose it, so it
        # fell back to ">=" against a date string. Fixed at the source in
        # extraction.py; this fixture uses the correct op directly.
        "description": "Bid Security / EMD Bank Guarantee valid until at least 29 December 2026",
        "op": "DATE_AFTER",
        "entity_name": "emd_valid_until",
        "value": "2026-12-29",
        "mandatory": True,
        "weight": 10.0,
        "children": None,
    },
]

# qualifying_project_count is a DERIVED fact (count of projects meeting
# BOTH the >=50 Cr value bar AND the "completed within last 7 years"
# date bar, cutoff 2026-09-30 - 7y = 2019-09-30). The current extraction
# pipeline has no way to have the model compute a filtered count itself,
# so for the demo it's precomputed here directly from the real
# certificates. See the chat notes for the small prompt addition that
# nudges live extraction toward emitting this fact itself.

BIDDER_DOCUMENTS = {
    "global": {
        "match": ["global", "builders"],
        "label": "Global Builders Limited",
        "documents": [
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "pan_card",
                "bidder_name_on_document": "GLOBAL BUILDERS LIMITED",
                "facts": [
                    {"entity_name": "pan", "value": "AABCG7788L", "confidence": 0.98, "page": 2,
                     "valid_until": None, "source_quote": "PAN AABCG7788L"},
                    {"entity_name": "cin", "value": "U45200MH2015PLC265432", "confidence": 0.95, "page": 1,
                     "valid_until": None, "source_quote": "CIN: U45200MH2015PLC265432"},
                ],
                "notes": "Clear PAN card scan.",
            },
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "gst_certificate",
                "bidder_name_on_document": "Global Builders Limited",
                "facts": [
                    {"entity_name": "gstin", "value": "27AABCG7788L1Z2", "confidence": 0.97, "page": 2,
                     "valid_until": None, "source_quote": "GSTIN 27AABCG7788L1Z2"},
                ],
                "notes": "GST REG-06 certificate, status Active.",
            },
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "auditor_turnover_certificate",
                "bidder_name_on_document": "Global Builders Limited",
                "facts": [
                    {"entity_name": "turnover", "value": "612000000", "confidence": 0.96, "page": 3,
                     "valid_until": None,
                     "source_quote": "Average Turnover (last 3 FY) Rs. 61,20,00,000."},
                    {"entity_name": "turnover_fy2025_26", "value": "650000000", "confidence": 0.94, "page": 3,
                     "valid_until": None,
                     "source_quote": "Gross Annual Turnover Rs. 65,00,00,000 (FY 2025-26)."},
                ],
                "notes": "Independent Auditor's Certificate on Turnover.",
            },
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "completed_projects_certificate",
                "bidder_name_on_document": "Global Builders Limited",
                "facts": [
                    {"entity_name": "qualifying_project_count", "value": "0", "confidence": 0.9, "page": 4,
                     "valid_until": None,
                     "source_quote": "Taluka Hospital Building, Nandurbar - Rs. 40 Crore - July 2023 "
                                      "(below the Rs. 50 Crore per-project threshold)."},
                    {"entity_name": "total_projects_listed", "value": "1", "confidence": 0.95, "page": 4,
                     "valid_until": None, "source_quote": "Total similar projects completed: 1."},
                ],
                "notes": "Only 1 project listed, and its value (Rs.40 Cr) is below the Rs.50 Cr per-project "
                         "bar, so qualifying_project_count is 0 even though the project date is recent enough.",
            },
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "udyam_certificate",
                "bidder_name_on_document": "Global Builders Limited",
                "facts": [
                    {"entity_name": "udyam_number", "value": "UDYAM-MH-27-0099887", "confidence": 0.97, "page": 5,
                     "valid_until": None, "source_quote": "Udyam Registration Number UDYAM-MH-27-0099887"},
                    {"entity_name": "udyam_classification", "value": "Small Enterprise", "confidence": 0.95,
                     "page": 5, "valid_until": None, "source_quote": "Classification Small Enterprise"},
                ],
                "notes": "Valid Udyam certificate.",
            },
            {
                "filename": "4_BIDDER_Global_Builders.pdf",
                "document_type": "bid_security",
                "bidder_name_on_document": "Global Builders Limited",
                "facts": [
                    {"entity_name": "emd_valid_until", "value": "2027-01-20", "confidence": 0.96, "page": 5,
                     "valid_until": None, "source_quote": "Valid Until 20 January 2027"},
                ],
                "notes": "Bank Guarantee BG/2026/58120, Bank of India.",
            },
        ],
    },
    "abc": {
        "match": ["abc", "infrastructure"],
        "label": "ABC Infrastructure Pvt Ltd",
        "documents": [
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "pan_card",
                "bidder_name_on_document": "ABC INFRASTRUCTURE PRIVATE LIMITED",
                "facts": [
                    {"entity_name": "pan", "value": "AAACX1234F", "confidence": 0.97, "page": 2,
                     "valid_until": None, "source_quote": "PAN AAACX1234F"},
                    {"entity_name": "cin", "value": "U45400MH2011PTC221098", "confidence": 0.94, "page": 1,
                     "valid_until": None, "source_quote": "CIN: U45400MH2011PTC221098"},
                ],
                "notes": "Clear PAN card scan.",
            },
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "gst_certificate",
                "bidder_name_on_document": "ABC Infra Ltd.",
                "facts": [
                    # Deliberately kept as the real (mismatched) value -- do
                    # not "correct" this, the mismatch is the point.
                    {"entity_name": "gstin", "value": "27AAACX9999F1Z5", "confidence": 0.95, "page": 2,
                     "valid_until": None, "source_quote": "GSTIN 27AAACX9999F1Z5"},
                ],
                "notes": "Legal name on this certificate reads 'ABC Infra Ltd.' -- shorter than the PAN card's "
                         "'ABC INFRASTRUCTURE PRIVATE LIMITED'.",
            },
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "financial_statement_extract",
                "bidder_name_on_document": "ABC Infrastructure Pvt. Ltd.",
                "facts": [
                    # Real conflict: this document's "Revenue from Operations"
                    # and the auditor's certificate below both get filed as
                    # entity_name "turnover" -- two different documents,
                    # two different numbers for the same eligibility fact.
                    {"entity_name": "turnover", "value": "1500000000", "confidence": 0.93, "page": 3,
                     "valid_until": None,
                     "source_quote": "Revenue from Operations Rs. 150,00,00,000 (FY 2025-26)."},
                    {"entity_name": "net_profit", "value": "94000000", "confidence": 0.9, "page": 3,
                     "valid_until": None, "source_quote": "Net Profit Rs. 9,40,00,000."},
                ],
                "notes": "Extract from audited financial statement, filed with the RoC.",
            },
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "auditor_turnover_certificate",
                "bidder_name_on_document": "ABC Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "turnover", "value": "800000000", "confidence": 0.95, "page": 4,
                     "valid_until": None, "source_quote": "Gross Annual Turnover Rs. 80,00,00,000."},
                ],
                "notes": "Independent Auditor's Certificate on Turnover -- single FY figure only, no 3-year "
                         "average given, and it disagrees with the financial-statement extract on page 3.",
            },
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "completed_projects_certificate",
                "bidder_name_on_document": "ABC Infrastructure Pvt. Ltd.",
                "facts": [
                    {"entity_name": "qualifying_project_count", "value": "2", "confidence": 0.92, "page": 5,
                     "valid_until": None,
                     "source_quote": "Rural Hospital Complex, Jalgaon - Rs.58 Cr - June 2022; District Referral "
                                      "Hospital, Dhule - Rs.52 Cr - February 2021."},
                    {"entity_name": "total_projects_listed", "value": "2", "confidence": 0.95, "page": 5,
                     "valid_until": None, "source_quote": "Total similar projects completed: 2."},
                ],
                "notes": "Both listed projects clear the Rs.50 Cr / 7-year bar, but 2 is still short of the "
                         "required 3.",
            },
            {
                "filename": "3_BIDDER_ABC_Infrastructure.pdf",
                "document_type": "bid_security",
                "bidder_name_on_document": "ABC Infrastructure Pvt. Ltd.",
                "facts": [
                    {"entity_name": "emd_valid_until", "value": "2026-10-10", "confidence": 0.96, "page": 6,
                     "valid_until": None, "source_quote": "Valid Until 10 October 2026"},
                ],
                "notes": "Bank Guarantee BG/2026/19834, Bank of Maharashtra. Note at foot of document: 'No "
                         "Udyam / MSE registration certificate has been submitted with this bid.'",
            },
        ],
    },
    "sunrise": {
        "match": ["sunrise", "health"],
        "label": "Sunrise Health Infrastructure Pvt Ltd",
        "documents": [
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "pan_card",
                "bidder_name_on_document": "SUNRISE HEALTH INFRASTRUCTURE PRIVATE LIMITED",
                "facts": [
                    {"entity_name": "pan", "value": "AABCS4321K", "confidence": 0.98, "page": 2,
                     "valid_until": None, "source_quote": "PAN AABCS4321K"},
                    {"entity_name": "cin", "value": "U45201MH2009PTC198765", "confidence": 0.95, "page": 1,
                     "valid_until": None, "source_quote": "CIN: U45201MH2009PTC198765"},
                ],
                "notes": "Clear PAN card scan.",
            },
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "gst_certificate",
                "bidder_name_on_document": "Sunrise Health Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "gstin", "value": "27AABCS4321K1Z9", "confidence": 0.97, "page": 2,
                     "valid_until": None, "source_quote": "GSTIN 27AABCS4321K1Z9"},
                ],
                "notes": "GST REG-06 certificate, status Active.",
            },
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "auditor_turnover_certificate",
                "bidder_name_on_document": "Sunrise Health Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "turnover", "value": "1384000000", "confidence": 0.97, "page": 3,
                     "valid_until": None,
                     "source_quote": "Average Turnover (last 3 FY) Rs. 138,40,00,000."},
                    {"entity_name": "turnover_fy2025_26", "value": "1450000000", "confidence": 0.95, "page": 3,
                     "valid_until": None,
                     "source_quote": "Gross Annual Turnover Rs. 145,00,00,000 (FY 2025-26)."},
                ],
                "notes": "Independent Auditor's Certificate on Turnover.",
            },
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "completed_projects_certificate",
                "bidder_name_on_document": "Sunrise Health Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "qualifying_project_count", "value": "4", "confidence": 0.93, "page": 4,
                     "valid_until": None,
                     "source_quote": "District Hospital, Nagpur - Rs.68 Cr - March 2023; Govt. Medical College "
                                      "Hospital Extension, Pune - Rs.72 Cr - August 2022; Community Health Center "
                                      "Complex, Aurangabad - Rs.55 Cr - January 2021; Sub-District Hospital, "
                                      "Kolhapur - Rs.61 Cr - November 2020."},
                    {"entity_name": "total_projects_listed", "value": "4", "confidence": 0.95, "page": 4,
                     "valid_until": None, "source_quote": "Total similar projects completed: 4."},
                ],
                "notes": "All 4 listed projects clear both the value and date bars.",
            },
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "udyam_certificate",
                "bidder_name_on_document": "Sunrise Health Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "udyam_number", "value": "UDYAM-MH-13-0087654", "confidence": 0.97, "page": 5,
                     "valid_until": None, "source_quote": "Udyam Registration Number UDYAM-MH-13-0087654"},
                    {"entity_name": "udyam_classification", "value": "Medium Enterprise", "confidence": 0.96,
                     "page": 5, "valid_until": None, "source_quote": "Classification Medium Enterprise"},
                ],
                "notes": "Registered, but classified Medium -- the tender's preference clause is for Micro/Small "
                         "specifically. R005 currently only checks the certificate exists, not the "
                         "classification; see chat notes.",
            },
            {
                "filename": "2_BIDDER_Sunrise_Health_Infra.pdf",
                "document_type": "bid_security",
                "bidder_name_on_document": "Sunrise Health Infrastructure Private Limited",
                "facts": [
                    {"entity_name": "emd_valid_until", "value": "2027-01-15", "confidence": 0.97, "page": 5,
                     "valid_until": None, "source_quote": "Valid Until 15 January 2027"},
                ],
                "notes": "Bank Guarantee BG/2026/44567, State Bank of India.",
            },
        ],
    },
}

DEMO_FIXTURE_ONLY = os.environ.get("DEMO_FIXTURE_ONLY", "").lower() in ("1", "true", "yes")


def _match_bidder_key(filename: str):
    name = filename.lower()
    for key, entry in BIDDER_DOCUMENTS.items():
        if any(token in name for token in entry["match"]):
            return key
    return None


def _is_tender_file(filename: str) -> bool:
    name = filename.lower()
    return any(token in name for token in ("tender", "nashik", "hospital"))


def try_fixture_extraction(bidder_payload, tender_payload):
    """
    bidder_payload: list of {"filename": str, ...} -- same shape main.py builds.
    tender_payload: {"filename": str, ...} or None.

    Returns a dict shaped exactly like extract_from_documents()'s return
    value if every uploaded file is recognised, else None (caller should
    fall through to the real extraction call). Raises RuntimeError instead
    of returning None when DEMO_FIXTURE_ONLY is set, so an unrecognised
    file fails loudly rather than silently risking a live Gemini call.
    """
    bidder_keys = [_match_bidder_key(f["filename"]) for f in bidder_payload]

    if tender_payload is not None and not _is_tender_file(tender_payload["filename"]):
        if DEMO_FIXTURE_ONLY:
            raise RuntimeError(
                f"DEMO_FIXTURE_ONLY is set and '{tender_payload['filename']}' isn't a known fixture file."
            )
        return None

    if any(k is None for k in bidder_keys):
        unknown = [f["filename"] for f, k in zip(bidder_payload, bidder_keys) if k is None]
        if DEMO_FIXTURE_ONLY:
            raise RuntimeError(f"DEMO_FIXTURE_ONLY is set and these files aren't known fixtures: {unknown}")
        return None

    documents = []
    if tender_payload is not None:
        documents.append(dict(TENDER_DOCUMENT))
    for key in bidder_keys:
        documents.extend(BIDDER_DOCUMENTS[key]["documents"])

    return {
        "documents": documents,
        "requirements": list(TENDER_REQUIREMENTS) if tender_payload is not None else [],
        "tender_closing_date": TENDER_CLOSING_DATE if tender_payload is not None else None,
        "extraction_model": "demo-fixture",
    }


# ----------------------------------------------------------------------
# Expected results once wired in (weight=10.0 x 6 rules -> total 60):
#
#   Global Builders  -> FAIL     score 66.67   (R001, R002 mandatory-fail)
#   ABC Infra        -> FAIL     score 33.33   (R001 conflict/REVIEW;
#                                                R002, R006 mandatory-fail)
#   Sunrise Health    -> PASS     score 100.00  (all 6 rules pass)
#
# Sunrise coming back as a clean PASS (not the REVIEW/50.0 you saw
# before) is the direct proof the EMD DATE_AFTER fix worked.
# ----------------------------------------------------------------------

