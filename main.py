from tkinter import Tk, filedialog
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os


# Open folder selection dialog
root = Tk()
root.withdraw()
folder = filedialog.askdirectory(title="Select Folder to Save PDF")

# Build file path directly (no check)
path = os.path.join(folder, "report.pdf")

# Create PDF canvas
c = canvas.Canvas(path, pagesize=A4)
width, height = A4

# Start writing text
text = c.beginText(50, height - 50)
text.setFont("Helvetica", 12)

lines = [
    "Monthly Report",
    "Sales & Revenue Overview",
    "",
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
c.save()

print("PDF saved to:", path)
