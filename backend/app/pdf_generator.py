"""
PDF Report Generator for RACE-Cloud.
Uses ReportLab to produce a professional, readable cost optimization report.
All data is passed in-memory — no credentials are ever included.
"""
import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)


# ── Color palette ──────────────────────────────────────────────────────────────
BRAND_BLUE    = colors.HexColor('#1e40af')
BRAND_PURPLE  = colors.HexColor('#7c3aed')
HIGH_RED      = colors.HexColor('#ef4444')
MEDIUM_AMBER  = colors.HexColor('#f59e0b')
LOW_BLUE      = colors.HexColor('#3b82f6')
SUCCESS_GREEN = colors.HexColor('#059669')
TEXT_DARK     = colors.HexColor('#1e293b')
TEXT_GRAY     = colors.HexColor('#64748b')
BG_LIGHT      = colors.HexColor('#f8fafc')
BORDER_LIGHT  = colors.HexColor('#e2e8f0')

SEVERITY_COLORS = {
    'HIGH':   HIGH_RED,
    'MEDIUM': MEDIUM_AMBER,
    'LOW':    LOW_BLUE,
}


def _build_styles():
    """Create custom ParagraphStyles for the PDF."""
    base = getSampleStyleSheet()

    styles = {
        'title': ParagraphStyle(
            'PDFTitle', parent=base['Title'],
            fontSize=22, leading=28, textColor=BRAND_BLUE,
            spaceAfter=4, alignment=TA_CENTER,
        ),
        'subtitle': ParagraphStyle(
            'PDFSubtitle', parent=base['Normal'],
            fontSize=11, leading=14, textColor=TEXT_GRAY,
            alignment=TA_CENTER, spaceAfter=6,
        ),
        'section': ParagraphStyle(
            'PDFSection', parent=base['Heading2'],
            fontSize=14, leading=18, textColor=BRAND_BLUE,
            spaceBefore=18, spaceAfter=8,
            borderWidth=0, borderPadding=0,
        ),
        'body': ParagraphStyle(
            'PDFBody', parent=base['Normal'],
            fontSize=10, leading=14, textColor=TEXT_DARK,
        ),
        'small': ParagraphStyle(
            'PDFSmall', parent=base['Normal'],
            fontSize=8, leading=10, textColor=TEXT_GRAY,
        ),
        'disclaimer': ParagraphStyle(
            'PDFDisclaimer', parent=base['Normal'],
            fontSize=8, leading=11, textColor=colors.HexColor('#92400e'),
            backColor=colors.HexColor('#fefce8'),
            borderWidth=0.5, borderColor=colors.HexColor('#fde68a'),
            borderPadding=8,
        ),
        'cell': ParagraphStyle(
            'PDFCell', parent=base['Normal'],
            fontSize=9, leading=12, textColor=TEXT_DARK,
        ),
        'cell_bold': ParagraphStyle(
            'PDFCellBold', parent=base['Normal'],
            fontSize=9, leading=12, textColor=TEXT_DARK,
            fontName='Helvetica-Bold',
        ),
    }
    return styles


def generate_pdf(report_data: dict) -> bytes:
    """
    Generate a PDF report in-memory from structured report data.
    Returns raw PDF bytes ready for download or email attachment.

    Security: This function receives ONLY analysis output.
    AWS Access Keys, Secret Keys, JWTs, and passwords are NEVER passed in.
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title='RACE-Cloud Cost Optimization Report',
        author='RACE-Cloud Platform',
    )

    styles = _build_styles()
    elements = []

    meta    = report_data.get('report_metadata', {})
    account = report_data.get('account_summary', {})
    recs    = report_data.get('optimization_recommendations', [])
    summary = report_data.get('summary_statistics', {})
    sev     = summary.get('severity_breakdown', {})

    # ── Header ─────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 8 * mm))
    elements.append(Paragraph('RACE-Cloud', styles['title']))
    elements.append(Paragraph(
        'Cloud-Native Resource Monitoring &amp; Cost Optimization Report',
        styles['subtitle']
    ))
    elements.append(Paragraph(
        f"Generated: {meta.get('generated_at', 'N/A')}",
        styles['subtitle']
    ))
    elements.append(Spacer(1, 2 * mm))
    elements.append(HRFlowable(
        width='100%', thickness=1, color=BORDER_LIGHT,
        spaceAfter=4 * mm, spaceBefore=2 * mm
    ))

    # ── Account Summary ────────────────────────────────────────────────────────
    elements.append(Paragraph('Account Summary', styles['section']))

    info_data = [
        ['Account ID', account.get('account_id', 'N/A'),
         'Region', account.get('region', 'N/A')],
        ['Prepared For', account.get('prepared_for', 'N/A'),
         'Analysis Date', account.get('analysis_date', 'N/A')],
    ]

    info_table = Table(info_data, colWidths=[80, 155, 80, 155])
    info_table.setStyle(TableStyle([
        ('FONTNAME',   (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',   (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('TEXTCOLOR',  (0, 0), (0, -1), TEXT_GRAY),
        ('TEXTCOLOR',  (2, 0), (2, -1), TEXT_GRAY),
        ('TEXTCOLOR',  (1, 0), (1, -1), TEXT_DARK),
        ('TEXTCOLOR',  (3, 0), (3, -1), TEXT_DARK),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BACKGROUND',    (0, 0), (-1, -1), BG_LIGHT),
        ('BOX',        (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('INNERGRID',  (0, 0), (-1, -1), 0.3, BORDER_LIGHT),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Summary Statistics ─────────────────────────────────────────────────────
    elements.append(Paragraph('Summary Statistics', styles['section']))

    stats_data = [
        ['Total Issues Found', 'High Severity', 'Medium Severity',
         'Low Severity', 'Est. Monthly Savings'],
        [
            str(summary.get('total_issues_found', 0)),
            str(sev.get('HIGH', 0)),
            str(sev.get('MEDIUM', 0)),
            str(sev.get('LOW', 0)),
            f"${summary.get('total_estimated_monthly_savings', 0):.2f}",
        ],
    ]

    stats_table = Table(stats_data, colWidths=[94] * 5)
    stats_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND',  (0, 0), (-1, 0), BRAND_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0), colors.white),
        ('FONTNAME',    (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0), 9),
        ('ALIGNMENT',   (0, 0), (-1, -1), 'CENTER'),
        # Data row
        ('FONTSIZE',    (0, 1), (-1, 1), 16),
        ('FONTNAME',    (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('TEXTCOLOR',   (0, 1), (0, 1), TEXT_DARK),
        ('TEXTCOLOR',   (1, 1), (1, 1), HIGH_RED),
        ('TEXTCOLOR',   (2, 1), (2, 1), MEDIUM_AMBER),
        ('TEXTCOLOR',   (3, 1), (3, 1), LOW_BLUE),
        ('TEXTCOLOR',   (4, 1), (4, 1), SUCCESS_GREEN),
        ('BACKGROUND',  (0, 1), (-1, 1), BG_LIGHT),
        # Spacing
        ('TOPPADDING',  (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BOX',         (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ('INNERGRID',   (0, 0), (-1, -1), 0.3, BORDER_LIGHT),
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 4 * mm))

    # ── Recommendations Table ──────────────────────────────────────────────────
    elements.append(Paragraph('Optimization Recommendations', styles['section']))

    if recs:
        header = ['#', 'Resource', 'Type', 'Recommendation', 'Severity', 'Savings/mo']
        table_data = [header]

        for i, rec in enumerate(recs, 1):
            sev_color = SEVERITY_COLORS.get(rec.get('severity', ''), TEXT_GRAY)
            table_data.append([
                str(i),
                Paragraph(str(rec.get('resource', '')), styles['cell']),
                Paragraph(str(rec.get('resource_type', '')), styles['cell']),
                Paragraph(str(rec.get('suggested_action', '')), styles['cell']),
                Paragraph(
                    f"<font color='{sev_color}'><b>{rec.get('severity', '')}</b></font>",
                    styles['cell']
                ),
                Paragraph(
                    f"<b>${rec.get('estimated_savings', 0):.2f}</b>",
                    styles['cell']
                ),
            ])

        col_widths = [22, 80, 60, 190, 55, 63]
        rec_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        rec_table.setStyle(TableStyle([
            # Header
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_BLUE),
            ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
            ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0, 0), (-1, 0), 9),
            ('ALIGNMENT',  (0, 0), (-1, 0), 'CENTER'),
            # Body
            ('FONTSIZE',   (0, 1), (-1, -1), 9),
            ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 4),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
            # Alternating rows
            *[('BACKGROUND', (0, r), (-1, r), BG_LIGHT)
              for r in range(2, len(table_data), 2)],
            # Grid
            ('BOX',       (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER_LIGHT),
        ]))
        elements.append(rec_table)
    else:
        elements.append(Paragraph(
            'No optimization issues found. Your AWS resources are well-configured.',
            styles['body']
        ))

    elements.append(Spacer(1, 6 * mm))

    # ── Total Savings Highlight ────────────────────────────────────────────────
    total = summary.get('total_estimated_monthly_savings', 0)
    savings_data = [[
        Paragraph(
            f'<b>Total Estimated Monthly Savings: ${total:.2f}</b>',
            ParagraphStyle('savings', parent=styles['body'],
                           fontSize=13, textColor=colors.white,
                           alignment=TA_CENTER)
        )
    ]]
    savings_table = Table(savings_data, colWidths=[470])
    savings_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SUCCESS_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0, SUCCESS_GREEN),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(savings_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Disclaimer ─────────────────────────────────────────────────────────────
    disclaimer_text = report_data.get('disclaimer', '')
    elements.append(Paragraph(
        f'<b>Advisory Disclaimer:</b> {disclaimer_text}',
        styles['disclaimer']
    ))
    elements.append(Spacer(1, 8 * mm))

    # ── Footer ─────────────────────────────────────────────────────────────────
    elements.append(HRFlowable(
        width='100%', thickness=0.5, color=BORDER_LIGHT,
        spaceAfter=3 * mm, spaceBefore=2 * mm
    ))
    elements.append(Paragraph(
        'RACE-Cloud Platform — Academic SGP Project  |  '
        f'Report Version {meta.get("report_version", "1.0")}',
        styles['small']
    ))
    elements.append(Paragraph(
        'This report does not contain any AWS credentials, '
        'passwords, or sensitive authentication data.',
        styles['small']
    ))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
