import wx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from datetime import datetime
import rasterio

app = wx.App(False)

dlg = wx.DirDialog(None, "Select folder containing GeoTIFF files", style=wx.DD_DEFAULT_STYLE)
dlg.ShowModal()
folder = dlg.GetPath()
dlg.Destroy()

timestamp = datetime.now().strftime("%Y%m%d%H%M")
filename = f"Quality-Report-{timestamp}.pdf"
path = os.path.join(folder, filename)

geotiff_files = [f for f in os.listdir(folder) if f.lower().endswith(('.tif', '.tiff'))]

c = canvas.Canvas(path, pagesize=A4)
width, height = A4

text = c.beginText(50, height - 50)
text.setFont("Helvetica", 10)

def add_line(line):
    global text, c, height
    text.textLine(line)
    if text.getY() < 50:
        c.drawText(text)
        c.showPage()
        text = c.beginText(50, height - 50)
        text.setFont("Helvetica", 10)

if not geotiff_files:
    add_line("No GeoTIFF files found in the selected folder.")
else:
    add_line("Quality Report")
    add_line(f"Folder: {folder}")
    add_line(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    add_line("")
    add_line("")

    for filename in geotiff_files:
        filepath = os.path.join(folder, filename)
        add_line(f"File: {filename}")
        try:
            with rasterio.open(filepath) as src:
                # Basic info
                add_line(f"  Driver: {src.driver}")
                add_line(f"  Width x Height (pixels): {src.width} x {src.height}")
                add_line(f"  Number of bands: {src.count}")
                add_line(f"  Data type: {src.dtypes[0]}")
                add_line(f"  CRS (EPSG or PROJ): {src.crs.to_string() if src.crs else 'None'}")
                add_line(f"  CRS (WKT): {src.crs.wkt if src.crs else 'None'}")

                # Affine transform and pixel size
                transform = src.transform
                add_line(f"  Pixel Size: {transform.a:.4f} x {transform.e:.4f} (units)")

                # Bounds
                bounds = src.bounds
                add_line(f"  Bounds:")
                add_line(f"    Left: {bounds.left:.4f}")
                add_line(f"    Bottom: {bounds.bottom:.4f}")
                add_line(f"    Right: {bounds.right:.4f}")
                add_line(f"    Top: {bounds.top:.4f}")

                # Nodata value
                nodata = src.nodata
                add_line(f"  NoData Value: {nodata if nodata is not None else 'None'}")

        except Exception as e:
            add_line(f"  Error reading file: {e}")

        add_line("")

c.drawText(text)
c.save()

print("Quality Report saved to:", path)
