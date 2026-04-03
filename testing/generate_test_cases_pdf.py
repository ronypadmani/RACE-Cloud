"""
Generate RACE-Cloud Test Cases PDF in the same format as the reference document.
Table format: Test ID | Type | Category | Scenario/Focus | Input Data | Expected Output | Status
"""

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "RACE-Cloud_Test_Cases.pdf")

# ========== TEST CASE DATA ==========

# Page 1 & 2: Test ID, Type, Category, Scenario/Focus
test_case_summary = [
    # --- Gray Box: Authentication ---
    ["GB-AUTH-01", "Gray Box", "Authentication", "Successful User Registration"],
    ["GB-AUTH-02", "Gray Box", "Authentication", "Registration with Existing Email"],
    ["GB-AUTH-03", "Gray Box", "Authentication", "Successful User Login"],
    ["GB-AUTH-04", "Gray Box", "Authentication", "Invalid Login Attempt"],
    ["GB-AUTH-05", "Gray Box", "Authentication", "Access Secure Endpoints Without Token"],
    ["GB-AUTH-06", "Gray Box", "Authentication", "Password Validation (Weak Password)"],
    ["GB-AUTH-07", "Gray Box", "Authentication", "JWT Token Storage After Login"],
    # --- Gray Box: AWS Setup ---
    ["GB-AWS-01", "Gray Box", "AWS Setup", "Submit Valid AWS Credentials"],
    ["GB-AWS-02", "Gray Box", "AWS Setup", "Submit Invalid AWS Key Format"],
    ["GB-AWS-03", "Gray Box", "AWS Setup", "Check AWS Connection Status"],
    ["GB-AWS-04", "Gray Box", "AWS Setup", "Get Supported AWS Regions"],
    # --- Gray Box: Resource Management ---
    ["GB-RES-01", "Gray Box", "Resource Management", "Fetch AWS Resources Summary"],
    ["GB-RES-02", "Gray Box", "Resource Management", "Display EC2 Instances Tab"],
    ["GB-RES-03", "Gray Box", "Resource Management", "Display EBS Volumes Tab"],
    ["GB-RES-04", "Gray Box", "Resource Management", "Display S3 Buckets Tab"],
    ["GB-RES-05", "Gray Box", "Resource Management", "Display RDS Instances Tab"],
    # --- Gray Box: Cost Analysis ---
    ["GB-COST-01", "Gray Box", "Cost Analysis", "Run Cost Analysis"],
    ["GB-COST-02", "Gray Box", "Cost Analysis", "Get Cost Recommendations"],
    ["GB-COST-03", "Gray Box", "Cost Analysis", "Dismiss a Recommendation"],
    ["GB-COST-04", "Gray Box", "Cost Analysis", "Filter Recommendations by Severity"],
    # --- Gray Box: AI Decision ---
    ["GB-AI-01", "Gray Box", "AI Decision", "Get AI Action Plan"],
    ["GB-AI-02", "Gray Box", "AI Decision", "AI Architecture Suggestion"],
    ["GB-AI-03", "Gray Box", "AI Decision", "Record User Behavior Action"],
    ["GB-AI-04", "Gray Box", "AI Decision", "AI Budget Priority Selection"],
    # --- Gray Box: Forecast ---
    ["GB-FOR-01", "Gray Box", "Forecast & Budget", "Get Cost Prediction"],
    ["GB-FOR-02", "Gray Box", "Forecast & Budget", "Detect Cost Anomalies"],
    ["GB-FOR-03", "Gray Box", "Forecast & Budget", "Set Monthly Budget"],
    ["GB-FOR-04", "Gray Box", "Forecast & Budget", "Get Budget Status"],
    # --- Gray Box: UI ---
    ["GB-UI-01", "Gray Box", "UI Layout", "Responsive Design Check"],
    ["GB-UI-02", "Gray Box", "UI Layout", "Graceful Error Displays"],
    ["GB-UI-03", "Gray Box", "UI Layout", "Navigation Sidebar Links"],
    # --- Gray Box: Reports ---
    ["GB-REP-01", "Gray Box", "Reports", "Generate Latest Report"],
    ["GB-REP-02", "Gray Box", "Reports", "Download HTML Report"],
    ["GB-REP-03", "Gray Box", "Reports", "Download PDF Report"],
    ["GB-REP-04", "Gray Box", "Reports", "Email Report to User"],
    ["GB-REP-05", "Gray Box", "Reports", "Dashboard Statistics Display"],
    # --- White Box: Unit Tests ---
    ["WB-UNIT-01", "White Box", "Unit Test", "Security Module — Password Hashing"],
    ["WB-UNIT-02", "White Box", "Unit Test", "Database Connection (database.py)"],
    ["WB-UNIT-03", "White Box", "Unit Test", "Cost Rules Engine Module"],
    ["WB-UNIT-04", "White Box", "Unit Test", "EC2 Rules Processing"],
    ["WB-UNIT-05", "White Box", "Unit Test", "EBS Rules Processing"],
    ["WB-UNIT-06", "White Box", "Unit Test", "JWT Token Generation & Validation"],
    ["WB-UNIT-07", "White Box", "Unit Test", "JWT Token Expiration Check"],
    # --- White Box: Integration Tests ---
    ["WB-INT-01", "White Box", "Integration Test", "AWS Client Factory Initialization"],
    ["WB-INT-02", "White Box", "Integration Test", "Full Analysis Pipeline"],
    ["WB-INT-03", "White Box", "Integration Test", "Database Session Handling"],
    ["WB-INT-04", "White Box", "Integration Test", "Demo Data Loading"],
    ["WB-INT-05", "White Box", "Integration Test", "Dependency Chain Detection"],
    ["WB-INT-06", "White Box", "Integration Test", "Simulation Engine Processing"],
    # --- White Box: Error Flows ---
    ["WB-ERR-01", "White Box", "Error Flow", "Invalid API Request Validation"],
    ["WB-ERR-02", "White Box", "Error Flow", "AWS Credential Decryption Failure"],
    ["WB-ERR-03", "White Box", "Error Flow", "Concurrent API Request Handling"],
]

# Page 3+: Detailed test cases with Input/Expected Output
test_case_details = [
    # Authentication
    ["GB-AUTH-01", "Valid Email, Password (8+ chars, uppercase, digit), Username (3-30 chars)",
     "User account created, JWT token generated, redirects to /aws-setup.", "Pending"],
    ["GB-AUTH-02", "Existing Email, Valid Password, Username",
     "Error: 'Email already exists'.", "Pending"],
    ["GB-AUTH-03", "Valid Registered Email & Password",
     "Login successful, JWT auth token generated, redirects to /dashboard.", "Pending"],
    ["GB-AUTH-04", "Invalid Password / Non-existent Email",
     "Error: 'Invalid credentials' displayed on login page.", "Pending"],
    ["GB-AUTH-05", "No Auth Header / Expired Token in API request",
     "401 Unauthorized Error returned.", "Pending"],
    ["GB-AUTH-06", "Password without uppercase / without digit / < 8 chars",
     "Error: Password does not meet strength requirements.", "Pending"],
    ["GB-AUTH-07", "Valid login credentials submitted via UI",
     "JWT token stored in browser localStorage after successful login.", "Pending"],
    # AWS Setup
    ["GB-AWS-01", "Access Key (AKIA format), Secret Key (30+ chars), Region (e.g., us-east-1)",
     "AWS credentials encrypted & stored, Account ID (masked) returned.", "Pending"],
    ["GB-AWS-02", "Invalid Access Key format (not starting with AKIA), short Secret Key",
     "Error: 'Invalid AWS credential format'.", "Pending"],
    ["GB-AWS-03", "Authentication Token",
     "Returns configured status, region, masked account_id, demo_mode flag.", "Pending"],
    ["GB-AWS-04", "Authentication Token",
     "Returns list of 13 supported AWS regions.", "Pending"],
    # Resource Management
    ["GB-RES-01", "Authentication Token + AWS configured",
     "Returns resource counts: EC2, EBS, S3, RDS, Elastic IPs with details.", "Pending"],
    ["GB-RES-02", "Click EC2 tab on Resources page",
     "Table displays instance ID, state, type, AZ, public IP.", "Pending"],
    ["GB-RES-03", "Click EBS tab on Resources page",
     "Table displays volume ID, type, size, state, attachment info.", "Pending"],
    ["GB-RES-04", "Click S3 tab on Resources page",
     "Table displays bucket name, size, object count.", "Pending"],
    ["GB-RES-05", "Click RDS tab on Resources page",
     "Table displays instance ID, engine, class, storage, status.", "Pending"],
    # Cost Analysis
    ["GB-COST-01", "Click 'Run Analysis' button on Dashboard",
     "Analysis runs, returns total_findings, total_estimated_savings, resource_summary.", "Pending"],
    ["GB-COST-02", "Navigate to Recommendations page",
     "Returns list of recommendations with severity, resource_id, savings.", "Pending"],
    ["GB-COST-03", "Click 'Dismiss' button on a recommendation card",
     "Recommendation status set to DISMISSED, removed from active list.", "Pending"],
    ["GB-COST-04", "Click filter buttons: ALL / HIGH / MEDIUM / LOW",
     "Only recommendations matching selected severity are displayed.", "Pending"],
    # AI Decision
    ["GB-AI-01", "Authentication Token + completed analysis",
     "Returns ranked action list with top 3 actions, savings, confidence %.", "Pending"],
    ["GB-AI-02", "User input: 'Build real-time chat app with 10k users', Budget: $100, Priority: balanced",
     "Returns AI architecture suggestion with 3 cost options (CHEAP/BALANCED/PERFORMANCE).", "Pending"],
    ["GB-AI-03", "Click 'I did this' or 'Dismiss' on action card",
     "User behavior recorded (applied/dismissed), preferences updated.", "Pending"],
    ["GB-AI-04", "Select priority: cheap / balanced / performance via UI buttons",
     "AI suggestion updates to reflect selected budget priority.", "Pending"],
    # Forecast
    ["GB-FOR-01", "Authentication Token",
     "Returns predicted_monthly_cost, daily_avg, trend (increasing/decreasing/stable), confidence.", "Pending"],
    ["GB-FOR-02", "Authentication Token",
     "Returns daily costs with threshold, anomaly_count, anomaly list with severity.", "Pending"],
    ["GB-FOR-03", "Budget amount: $500 in input field, click 'Set Budget'",
     "Budget updated, progress bar shows predicted vs budget percentage.", "Pending"],
    ["GB-FOR-04", "Authentication Token + Budget set",
     "Returns alert_level (NONE/MEDIUM/HIGH), percentage, remaining amount.", "Pending"],
    # UI Layout
    ["GB-UI-01", "Mobile device viewport (iPhone/tablet sizing)",
     "Elements stack correctly, no horizontal scrolling, sidebar collapses.", "Pending"],
    ["GB-UI-02", "Trigger a 500 error from backend",
     "Frontend displays error message/toast, does not crash.", "Pending"],
    ["GB-UI-03", "Click each sidebar link: Dashboard, Resources, Recommendations, Forecast, Reports, Decision",
     "Each link navigates to correct page without errors.", "Pending"],
    # Reports
    ["GB-REP-01", "Authentication Token + completed analysis",
     "Returns JSON report with account_summary, recommendations, statistics.", "Pending"],
    ["GB-REP-02", "Click 'Download HTML' button on Reports page",
     "HTML file downloaded: RACE-Cloud_Report_YYYYMMDD.html with styled content.", "Pending"],
    ["GB-REP-03", "Click 'Download PDF' button on Reports page",
     "PDF file downloaded: racecloud_cost_report_YYYYMMDD.pdf generated in-memory.", "Pending"],
    ["GB-REP-04", "Click 'Email Report' button on Reports page",
     "PDF generated and sent via SMTP to logged-in user's email address.", "Pending"],
    ["GB-REP-05", "Authentication Token on Dashboard",
     "Dashboard displays total savings, total issues, HIGH/MEDIUM/LOW counts.", "Pending"],
    # White Box: Unit Tests
    ["WB-UNIT-01", "Raw password string into hash function (security.py)",
     "Produces valid bcrypt hash differing from input string.", "Pending"],
    ["WB-UNIT-02", "DATABASE_URL connection string (database.py)",
     "Engine connects to SQLite; session factory works without timeout.", "Pending"],
    ["WB-UNIT-03", "Mock resource data into cost_rules.py",
     "Cost rules correctly identify over-provisioned resources.", "Pending"],
    ["WB-UNIT-04", "Mock EC2 instance data with low CPU utilization",
     "EC2 rules flag idle instances, return downsize/terminate recommendation.", "Pending"],
    ["WB-UNIT-05", "Mock EBS volume data (unattached volumes)",
     "EBS rules detect unattached volumes, calculate waste amount.", "Pending"],
    ["WB-UNIT-06", "User ID and secret key into JWT generation",
     "Valid JWT token generated with correct payload and expiry.", "Pending"],
    ["WB-UNIT-07", "Generated token with manipulated expiry timestamp",
     "Validation logic catches expired token, returns Unauthorized.", "Pending"],
    # White Box: Integration Tests
    ["WB-INT-01", "AWS credentials + region into client_factory.py",
     "Boto3 clients for EC2, S3, RDS, CloudWatch created correctly.", "Pending"],
    ["WB-INT-02", "Run analysis pipeline: collect data → apply rules → store results",
     "End-to-end analysis resolves cleanly, recommendations stored in DB.", "Pending"],
    ["WB-INT-03", "CRUD operations with active DB session monitoring",
     "SQLAlchemy sessions correctly close/commit on exit or failure.", "Pending"],
    ["WB-INT-04", "Load demo scenario: idle_resources / high_cost / optimized",
     "Demo JSON data loaded correctly, analysis auto-triggers.", "Pending"],
    ["WB-INT-05", "Resources with cross-service dependencies",
     "Dependency engine detects linked waste chains (e.g., stopped EC2 + unattached EBS).", "Pending"],
    ["WB-INT-06", "Action type + resource ID into simulation engine",
     "Returns cost impact: before/after costs, estimated savings.", "Pending"],
    # White Box: Error Flows
    ["WB-ERR-01", "Null/missing required fields in API request body",
     "400 Bad Request with clean validation error message.", "Pending"],
    ["WB-ERR-02", "Corrupted/invalid encryption key for AWS credential decryption",
     "Error handled gracefully, returns 'AWS configuration error'.", "Pending"],
    ["WB-ERR-03", "Heavy concurrent API requests to analysis endpoints",
     "Flask handles parallel requests without deadlocks or crashes.", "Pending"],
]


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=landscape(A4),
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"],
                                  fontSize=18, spaceAfter=6, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle("SubTitle", parent=styles["Normal"],
                                     fontSize=11, alignment=TA_CENTER, spaceAfter=12,
                                     textColor=colors.HexColor("#555555"))
    header_style = ParagraphStyle("HeaderStyle", parent=styles["Heading2"],
                                   fontSize=13, spaceAfter=6, spaceBefore=12)
    cell_style = ParagraphStyle("CellStyle", parent=styles["Normal"],
                                 fontSize=7.5, leading=10)
    cell_bold = ParagraphStyle("CellBold", parent=cell_style,
                                fontName="Helvetica-Bold")
    cell_header = ParagraphStyle("CellHeader", parent=styles["Normal"],
                                  fontSize=8, fontName="Helvetica-Bold",
                                  textColor=colors.white, leading=10)

    elements = []

    # ============ TITLE PAGE ============
    elements.append(Spacer(1, 80))
    elements.append(Paragraph("RACE-Cloud — Test Cases Document", title_style))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(
        "Resource Analysis & Cost Engine for Cloud<br/>"
        "Software Engineering — Practical Examination", subtitle_style))
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(
        "Testing Types: Black Box Testing | White Box Testing | Gray Box Testing<br/>"
        "Manual and Automated Testing (Selenium WebDriver + Python unittest)", subtitle_style))
    elements.append(Spacer(1, 30))

    # Info table
    info_data = [
        ["Project Name", "RACE-Cloud (Resource Analysis & Cost Engine for Cloud)"],
        ["Testing Tool", "Selenium WebDriver (Python) + unittest Framework"],
        ["Total Test Cases", str(len(test_case_summary))],
        ["Testing Types", "Gray Box (35 cases) | White Box (16 cases)"],
        ["Categories", "Authentication, AWS Setup, Resources, Cost Analysis, AI Decision,\nForecast, Reports, UI, Unit Tests, Integration Tests, Error Flows"],
    ]
    info_table = Table(info_data, colWidths=[150, 400])
    info_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#F8F9FA")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    elements.append(PageBreak())

    # ============ TABLE 1: TEST CASE SUMMARY ============
    elements.append(Paragraph("Table 1: Test Case Summary", header_style))

    summary_header = [
        Paragraph("Test ID", cell_header),
        Paragraph("Type", cell_header),
        Paragraph("Category", cell_header),
        Paragraph("Scenario / Focus", cell_header),
    ]

    summary_data = [summary_header]
    for row in test_case_summary:
        summary_data.append([
            Paragraph(row[0], cell_bold),
            Paragraph(row[1], cell_style),
            Paragraph(row[2], cell_style),
            Paragraph(row[3], cell_style),
        ])

    col_widths_summary = [85, 70, 120, 500]
    summary_table = Table(summary_data, colWidths=col_widths_summary, repeatRows=1)

    # Alternating row colors
    table_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(summary_data)):
        bg = colors.HexColor("#F8F9FA") if i % 2 == 0 else colors.white
        table_style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    summary_table.setStyle(TableStyle(table_style_cmds))
    elements.append(summary_table)
    elements.append(PageBreak())

    # ============ TABLE 2: DETAILED TEST CASES ============
    elements.append(Paragraph("Table 2: Detailed Test Cases — Input Data & Expected Output", header_style))

    detail_header = [
        Paragraph("Test ID", cell_header),
        Paragraph("Input Data", cell_header),
        Paragraph("Expected Output", cell_header),
        Paragraph("Status", cell_header),
    ]

    detail_data = [detail_header]
    for row in test_case_details:
        status_color = "#27AE60" if row[3] == "Passed" else "#E67E22" if row[3] == "Pending" else "#E74C3C"
        detail_data.append([
            Paragraph(row[0], cell_bold),
            Paragraph(row[1], cell_style),
            Paragraph(row[2], cell_style),
            Paragraph(f'<font color="{status_color}"><b>{row[3]}</b></font>', cell_style),
        ])

    col_widths_detail = [80, 280, 370, 55]
    detail_table = Table(detail_data, colWidths=col_widths_detail, repeatRows=1)

    detail_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(detail_data)):
        bg = colors.HexColor("#F8F9FA") if i % 2 == 0 else colors.white
        detail_style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    detail_table.setStyle(TableStyle(detail_style_cmds))
    elements.append(detail_table)

    # ============ BUILD ============
    doc.build(elements)
    print(f"PDF generated: {os.path.abspath(OUTPUT_PATH)}")


if __name__ == "__main__":
    build_pdf()
