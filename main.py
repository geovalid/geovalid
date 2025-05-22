from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

def create_pdf_report(filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 1 * inch, "Monthly Report")

    # Subtitle
    c.setFont("Helvetica", 14)
    c.drawCentredString(width / 2, height - 1.5 * inch, "Sales & Revenue Overview")

    # Body text
    text = c.beginText(1 * inch, height - 2.5 * inch)
    text.setFont("Helvetica", 12)
    lines = [
        "This report provides an overview of sales performance,",
        "revenue trends, and customer acquisition metrics for the month.",
        "",
        "Key Highlights:",
        "- Total Sales: $45,000",
        "- New Customers: 120",
        "- Top Product: SmartWatch X200",
        "",
        "Recommendations:",
        "1. Increase social media campaigns.",
        "2. Focus on customer retention strategies.",
    ]
    for line in lines:
        text.textLine(line)

    c.drawText(text)

    # Save the PDF
    c.save()
    print(f"PDF report saved as: {filename}")

# Usage
create_pdf_report("monthly_report.pdf")
