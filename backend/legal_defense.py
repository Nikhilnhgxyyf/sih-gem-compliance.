"""
legal_defense.py

REJECTION JUSTIFICATION GENERATOR ("Annexure A")
=================================================
When GEMA rejects a bid, the officer signing off on that rejection is the
one who has to answer an RTI query or a court notice about it -- not GEMA.
This module turns a decision the engine already computed into a formal,
citable document: which clause failed, what evidence caused it, the exact
sentence and page it came from, and the ledger hash backing it up.

Nothing here is invented at generation time. Every fact placed in the PDF
(clause text, source document, page number, quoted sentence, ledger hash)
already exists in the engine's own state -- this module only formats it.

HONESTY NOTE (say this if asked): this is NOT a legally binding digital
signature in the Digital Signature Certificate / PKI sense. It is a
formatted report whose content is backed by the engine's own SHA-256
hash-chained ledger entry -- so the *content* is provably unaltered after
generation, which is the part that actually matters for an RTI or court
dispute. Calling it "cryptographically signed" would overstate what's
here; "ledger-backed" is the accurate, defensible claim.
"""

from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether
)

NAVY = colors.HexColor("#1F497D")
GRAY_TEXT = colors.HexColor("#3F4550")
GRAY_LIGHT = colors.HexColor("#6E7580")
RED = colors.HexColor("#B23A2E")
LIGHT_BG = colors.HexColor("#F5F6F9")

_styles = getSampleStyleSheet()

_title_style = ParagraphStyle("title", parent=_styles["Title"], fontName="Helvetica-Bold", fontSize=17, textColor=NAVY, spaceAfter=2)
_meta_style = ParagraphStyle("meta", parent=_styles["Normal"], fontName="Helvetica", fontSize=9.5, textColor=GRAY_LIGHT, spaceAfter=12)
_section_style = ParagraphStyle("section", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=12.5, textColor=colors.white)
_clause_style = ParagraphStyle("clause", parent=_styles["Normal"], fontName="Helvetica-Bold", fontSize=11.5, textColor=colors.black, spaceAfter=4)
_body_style = ParagraphStyle("body", parent=_styles["Normal"], fontName="Helvetica", fontSize=10, textColor=GRAY_TEXT, leading=14)
_quote_style = ParagraphStyle("quote", parent=_styles["Normal"], fontName="Helvetica-Oblique", fontSize=9.7, textColor=colors.black, leading=13, leftIndent=10, borderColor=NAVY, borderWidth=0, backColor=LIGHT_BG)
_hash_style = ParagraphStyle("hash", parent=_styles["Normal"], fontName="Courier", fontSize=8, textColor=GRAY_LIGHT)


def _section_bar(title: str):
    t = Table([[Paragraph(title, _section_style)]], colWidths=[6.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def _failed_rule_block(rule_id, rule, evaluation, evidence_nodes):
    parts = [Paragraph(f"{rule_id} \u2014 {rule.clause_text}", _clause_style)]
    parts.append(Paragraph(f"<b>Mandatory:</b> {'Yes' if rule.is_mandatory else 'No'}", _body_style))
    parts.append(Paragraph(f"<b>Reasoning:</b> {evaluation.reasoning}", _body_style))

    for eid in evaluation.evidence_ids:
        node = evidence_nodes.get(eid)
        if not node:
            continue
        loc = f"{node.source_doc}" + (f", page {node.page_number}" if node.page_number else "")
        parts.append(Spacer(1, 4))
        parts.append(Paragraph(f"<b>Evidence {eid}</b> ({loc}) \u2014 extracted value: {node.extracted_value}", _body_style))
        if node.source_quote:
            parts.append(Paragraph(f"\u201c{node.source_quote}\u201d", _quote_style))

    parts.append(Spacer(1, 10))
    return KeepTogether(parts)


def generate_rejection_annexure(
    engine,
    decision,
    bidder_label: str,
    tender_filename: str = "",
    output_path: str = "/tmp/rejection_annexure.pdf",
) -> str:
    """
    engine: the ProcurementIntelligenceEngine instance holding the real
            rule_nodes / evidence_nodes / ledger for this session.
    decision: the DecisionResult already returned by
              engine.calculate_overall_compliance(...) for this bidder --
              generated fresh, not recomputed here, so the PDF always
              matches exactly what the dashboard showed the officer.
    Returns the output_path the PDF was written to.
    """
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
    )
    story = []

    story.append(Paragraph("Annexure A \u2014 Rejection Justification", _title_style))
    story.append(Paragraph(
        f"Bidder: <b>{bidder_label}</b> &nbsp;&middot;&nbsp; Tender: {tender_filename or 'N/A'} "
        f"&nbsp;&middot;&nbsp; Audit ID: {engine.audit_id}<br/>"
        f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}",
        _meta_style,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=10))

    story.append(Paragraph(
        f"<b>Decision: {decision.decision}</b> &nbsp;&middot;&nbsp; "
        f"Compliance score: {decision.compliance_score:.2f}/100 &nbsp;&middot;&nbsp; "
        f"{len(decision.mandatory_failures)} mandatory requirement(s) failed.",
        _body_style,
    ))
    story.append(Spacer(1, 12))

    story.append(_section_bar("MANDATORY REQUIREMENTS NOT SATISFIED"))
    story.append(Spacer(1, 8))

    if not decision.mandatory_failures:
        story.append(Paragraph("None \u2014 this bidder satisfied every mandatory requirement.", _body_style))
    else:
        for rule_id in decision.mandatory_failures:
            rule = engine.rule_nodes.get(rule_id)
            evaluation = engine.current_rule_evaluations.get(rule_id)
            if not rule or not evaluation:
                continue
            story.append(_failed_rule_block(rule_id, rule, evaluation, engine.evidence_nodes))

    story.append(Spacer(1, 6))
    story.append(_section_bar("AUDIT TRAIL"))
    story.append(Spacer(1, 8))
    latest_hash = engine.ledger[-1].event_hash if engine.ledger else "N/A"
    story.append(Paragraph(
        "This decision is backed by a SHA-256 hash-chained, Merkle-rooted audit ledger entry. "
        "Any retroactive alteration of the evidence or reasoning behind this decision would break "
        "the chain below and is independently verifiable.",
        _body_style,
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Latest ledger entry hash: {latest_hash}", _hash_style))
    story.append(Paragraph(f"Ledger length at time of generation: {len(engine.ledger)} event(s)", _hash_style))

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Note: this document formats decisions already computed by a deterministic rule engine; "
        "it is not a Digital Signature Certificate under the IT Act. Its evidentiary value rests on "
        "the tamper-evident ledger entry cited above, which can be independently re-verified.",
        ParagraphStyle("note", parent=_body_style, fontName="Helvetica-Oblique", fontSize=8.5, textColor=GRAY_LIGHT),
    ))

    doc.build(story)
    return output_path
