import wx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from datetime import datetime

app = wx.App(False)

dlg = wx.DirDialog(None, "Select folder to save PDF", style=wx.DD_DEFAULT_STYLE)
dlg.ShowModal()
folder = dlg.GetPath()
dlg.Destroy()

# Generate timestamp string
timestamp = datetime.now().strftime("%Y%m%d%H%M")
filename = f"Quality-Report-{timestamp}.pdf"
path = os.path.join(folder, filename)

c = canvas.Canvas(path, pagesize=A4)
width, height = A4

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
