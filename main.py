import wx
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
from datetime import datetime
import rasterio
import numpy as np
from collections import defaultdict
import math
import csv
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

app = wx.App(False)

dlg = wx.DirDialog(None, "Select folder containing GeoTIFF files", style=wx.DD_DEFAULT_STYLE)
dlg.ShowModal()
folder = dlg.GetPath()
dlg.Destroy()

timestamp = datetime.now().strftime("%Y%m%d%H%M")
filename = f"Quality-Report-{timestamp}.pdf"
path = os.path.join(folder, filename)

geotiff_files = [f for f in os.listdir(folder) if f.lower().endswith(('.tif', '.tiff'))]

# Initialize analysis variables
datum_summary = defaultdict(int)
total_area = 0
pixel_size_summary = defaultdict(int)
quality_issues = []
raster_stats = []

c = canvas.Canvas(path, pagesize=A4)
width, height = A4

def add_line(line):
    global text, c, height
    text.textLine(line)
    if text.getY() < 50:
        c.drawText(text)
        c.showPage()
        text = c.beginText(50, height - 50)
        text.setFont("Helvetica", 10)

def add_section_header(header):
    global text
    text.setFont("Helvetica-Bold", 12)
    add_line("")
    add_line(header)
    add_line("-" * len(header))
    text.setFont("Helvetica", 10)

text = c.beginText(50, height - 50)

# Title
text.setFont("Helvetica-Bold", 16)
add_line("GeoTIFF Quality Report")

# Switch back to normal font
text.setFont("Helvetica", 10)
add_line("")
add_line(f"Folder: {folder}")
add_line(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
add_line(f"Total files found: {len(geotiff_files)}")
add_line("")

# First pass: Collect summary statistics
print("Analyzing files...")
for filename in geotiff_files:
    filepath = os.path.join(folder, filename)
    try:
        with rasterio.open(filepath) as src:
            # CRS/Datum analysis
            crs_string = src.crs.to_string() if src.crs else 'No CRS'
            datum_summary[crs_string] += 1
            
            # Area calculation (approximate)
            transform = src.transform
            pixel_area = abs(transform.a * transform.e)
            file_area = pixel_area * src.width * src.height
            total_area += file_area
            
            # Pixel size analysis
            pixel_size = f"{abs(transform.a):.4f}"
            pixel_size_summary[pixel_size] += 1
            
            # Quality checks
            if not src.crs:
                quality_issues.append(f"{filename}: Missing CRS")
            
            if src.nodata is None:
                quality_issues.append(f"{filename}: No NoData value defined")
            
            # Basic statistics for first band
            if src.count > 0:
                band_data = src.read(1, masked=True)
                if band_data.compressed().size > 0:
                    valid_data = band_data.compressed()
                    stats = {
                        'file': filename,
                        'min': float(np.min(valid_data)),
                        'max': float(np.max(valid_data)),
                        'mean': float(np.mean(valid_data)),
                        'std': float(np.std(valid_data)),
                        'valid_pixels': int(valid_data.size),
                        'total_pixels': int(band_data.size)
                    }
                    raster_stats.append(stats)
                    
                    # Check for suspicious values
                    if np.min(valid_data) < -1000 or np.max(valid_data) > 10000:
                        quality_issues.append(f"{filename}: Suspicious data values (min: {np.min(valid_data):.2f}, max: {np.max(valid_data):.2f})")
            
            # Check for very small or very large files
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            if file_size < 1:
                quality_issues.append(f"{filename}: Very small file size ({file_size:.2f} MB)")
            elif file_size > 1000:
                quality_issues.append(f"{filename}: Very large file size ({file_size:.2f} MB)")
                
    except Exception as e:
        quality_issues.append(f"{filename}: Error reading file - {str(e)}")

# SUMMARY SECTION
add_section_header("EXECUTIVE SUMMARY")
add_line(f"Total GeoTIFF files analyzed: {len(geotiff_files)}")
add_line(f"Total approximate area covered: {total_area/1000000:.2f} km²")
add_line(f"Quality issues found: {len(quality_issues)}")
add_line(f"Files with issues: {len(set([issue.split(':')[0] for issue in quality_issues]))}")

# CRS/DATUM ANALYSIS
add_section_header("COORDINATE REFERENCE SYSTEM ANALYSIS")
add_line("CRS Distribution:")
for crs, count in datum_summary.items():
    add_line(f"  {crs}: {count} files ({count/len(geotiff_files)*100:.1f}%)")

if len(datum_summary) > 1:
    add_line("")
    add_line("WARNING: Multiple CRS found! This may cause issues in analysis.")

# PIXEL SIZE ANALYSIS
add_section_header("PIXEL SIZE ANALYSIS")
add_line("Pixel Size Distribution:")
for pixel_size, count in pixel_size_summary.items():
    add_line(f"  {pixel_size} units: {count} files")

if len(pixel_size_summary) > 1:
    add_line("")
    add_line("NOTE: Multiple pixel sizes detected. Consider resampling for consistency.")

# STATISTICAL ANALYSIS
add_section_header("RASTER STATISTICS SUMMARY")
if raster_stats:
    all_mins = [s['min'] for s in raster_stats]
    all_maxs = [s['max'] for s in raster_stats]
    all_means = [s['mean'] for s in raster_stats]
    
    add_line(f"Data Value Range Across All Files:")
    add_line(f"  Global Minimum: {min(all_mins):.4f}")
    add_line(f"  Global Maximum: {max(all_maxs):.4f}")
    add_line(f"  Average of Means: {np.mean(all_means):.4f}")
    add_line(f"  Standard Deviation of Means: {np.std(all_means):.4f}")

# QUALITY ISSUES SECTION
add_section_header("QUALITY ISSUES AND RECOMMENDATIONS")
if quality_issues:
    add_line("Issues found:")
    for issue in quality_issues:
        add_line(f"  • {issue}")
    
    add_line("")
    add_line("Recommendations:")
    if any("Missing CRS" in issue for issue in quality_issues):
        add_line("  • Define coordinate reference system for files missing CRS")
    if any("NoData" in issue for issue in quality_issues):
        add_line("  • Set appropriate NoData values for better data handling")
    if any("Suspicious data values" in issue for issue in quality_issues):
        add_line("  • Review data values for potential errors or outliers")
    if len(datum_summary) > 1:
        add_line("  • Consider reprojecting all files to a common CRS")
    if len(pixel_size_summary) > 1:
        add_line("  • Consider resampling to consistent pixel size")
else:
    add_line("No significant quality issues detected.")

# DETAILED FILE ANALYSIS
add_section_header("DETAILED FILE ANALYSIS")

for filename in geotiff_files:
    filepath = os.path.join(folder, filename)
    add_line(f"File: {filename}")
    try:
        with rasterio.open(filepath) as src:
            # Basic info
            add_line(f"  Dimensions: {src.width} x {src.height} pixels")
            add_line(f"  Bands: {src.count}")
            add_line(f"  Data type: {src.dtypes[0]}")
            add_line(f"  CRS: {src.crs.to_string() if src.crs else 'No CRS'}")

            # Affine transform and pixel size
            transform = src.transform
            add_line(f"  Pixel Size: {abs(transform.a):.6f} x {abs(transform.e):.6f} units")

            # Bounds
            bounds = src.bounds
            add_line(f"  Bounds:")
            add_line(f"    Left: {bounds.left:.6f}")
            add_line(f"    Bottom: {bounds.bottom:.6f}")
            add_line(f"    Right: {bounds.right:.6f}")
            add_line(f"    Top: {bounds.top:.6f}")

            # Coverage area
            coverage_area = (bounds.right - bounds.left) * (bounds.top - bounds.bottom)
            add_line(f"  Coverage Area: {coverage_area:.2f} square units")

            # NoData value
            nodata = src.nodata
            add_line(f"  NoData Value: {nodata if nodata is not None else 'None'}")
            
            # File size
            file_size = os.path.getsize(filepath) / (1024 * 1024)
            add_line(f"  File Size: {file_size:.2f} MB")
            
            # Band statistics
            if src.count > 0:
                try:
                    band_data = src.read(1, masked=True)
                    if band_data.compressed().size > 0:
                        valid_data = band_data.compressed()
                        add_line(f"  Band 1 Statistics:")
                        add_line(f"    Min: {np.min(valid_data):.4f}")
                        add_line(f"    Max: {np.max(valid_data):.4f}")
                        add_line(f"    Mean: {np.mean(valid_data):.4f}")
                        add_line(f"    Std Dev: {np.std(valid_data):.4f}")
                        add_line(f"    Valid Pixels: {valid_data.size:,}")
                        add_line(f"    NoData Pixels: {band_data.size - valid_data.size:,}")
                        add_line(f"    Data Coverage: {(valid_data.size/band_data.size)*100:.1f}%")
                    else:
                        add_line(f"  Band 1: No valid data")
                except Exception as e:
                    add_line(f"  Band statistics error: {str(e)}")

    except Exception as e:
        add_line(f"  Error reading file: {e}")

    add_line("")

# FOOTPRINT ANALYSIS
add_section_header("SPATIAL COVERAGE ANALYSIS")
try:
    # Calculate overlapping areas and gaps
    bounds_list = []
    for filename in geotiff_files:
        filepath = os.path.join(folder, filename)
        try:
            with rasterio.open(filepath) as src:
                bounds_list.append({
                    'file': filename,
                    'bounds': src.bounds
                })
        except:
            continue
    
    if len(bounds_list) > 1:
        # Find overall bounding box
        all_lefts = [b['bounds'].left for b in bounds_list]
        all_rights = [b['bounds'].right for b in bounds_list]
        all_bottoms = [b['bounds'].bottom for b in bounds_list]
        all_tops = [b['bounds'].top for b in bounds_list]
        
        overall_bounds = {
            'left': min(all_lefts),
            'right': max(all_rights),
            'bottom': min(all_bottoms),
            'top': max(all_tops)
        }
        
        add_line("Overall Spatial Extent:")
        add_line(f"  Left: {overall_bounds['left']:.6f}")
        add_line(f"  Right: {overall_bounds['right']:.6f}")
        add_line(f"  Bottom: {overall_bounds['bottom']:.6f}")
        add_line(f"  Top: {overall_bounds['top']:.6f}")
        
        total_extent_area = (overall_bounds['right'] - overall_bounds['left']) * (overall_bounds['top'] - overall_bounds['bottom'])
        add_line(f"  Total Extent Area: {total_extent_area:.2f} square units")
        
        # Check for potential overlaps (simplified)
        overlap_count = 0
        for i, bounds1 in enumerate(bounds_list):
            for j, bounds2 in enumerate(bounds_list[i+1:], i+1):
                b1, b2 = bounds1['bounds'], bounds2['bounds']
                if (b1.left < b2.right and b1.right > b2.left and 
                    b1.bottom < b2.top and b1.top > b2.bottom):
                    overlap_count += 1
        
        add_line(f"  Potential overlapping file pairs: {overlap_count}")
        if overlap_count > 0:
            add_line("  Note: Overlaps detected - consider mosaic creation")

except Exception as e:
    add_line(f"Spatial analysis error: {str(e)}")

# RECOMMENDATIONS SECTION
add_section_header("PROCESSING RECOMMENDATIONS")
add_line("Based on the analysis, consider the following:")
add_line("")

if len(datum_summary) > 1:
    add_line("1. COORDINATE SYSTEM STANDARDIZATION:")
    add_line("   • Reproject all files to a common CRS")
    add_line("   • Consider using UTM zone appropriate for your area")
    add_line("")

if len(pixel_size_summary) > 1:
    add_line("2. PIXEL SIZE HARMONIZATION:")
    add_line("   • Resample files to consistent pixel size")
    add_line("   • Use appropriate resampling method (bilinear, cubic, etc.)")
    add_line("")

if any("Missing CRS" in issue for issue in quality_issues):
    add_line("3. MISSING CRS CORRECTION:")
    add_line("   • Define appropriate coordinate system for files missing CRS")
    add_line("   • Verify spatial alignment after CRS assignment")
    add_line("")

add_line("4. GENERAL RECOMMENDATIONS:")
add_line("   • Create backup copies before processing")
add_line("   • Validate results after any transformations")
add_line("   • Consider creating a mosaic for seamless coverage")
add_line("   • Document all processing steps for reproducibility")

# Generate CSV report
csv_path = os.path.join(folder, f"quality-report-data-{timestamp}.csv")
try:
    with open(csv_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Filename', 'Width', 'Height', 'Bands', 'Data_Type', 'CRS', 'Pixel_Size_X', 'Pixel_Size_Y', 
                        'Bounds_Left', 'Bounds_Bottom', 'Bounds_Right', 'Bounds_Top', 'NoData_Value', 
                        'File_Size_MB', 'Min_Value', 'Max_Value', 'Mean_Value', 'Std_Value', 'Valid_Pixels', 'Coverage_Percent'])
        
        for filename in geotiff_files:
            filepath = os.path.join(folder, filename)
            try:
                with rasterio.open(filepath) as src:
                    transform = src.transform
                    bounds = src.bounds
                    file_size = os.path.getsize(filepath) / (1024 * 1024)
                    
                    # Get band statistics
                    try:
                        band_data = src.read(1, masked=True)
                        if band_data.compressed().size > 0:
                            valid_data = band_data.compressed()
                            min_val = float(np.min(valid_data))
                            max_val = float(np.max(valid_data))
                            mean_val = float(np.mean(valid_data))
                            std_val = float(np.std(valid_data))
                            valid_pixels = int(valid_data.size)
                            coverage_pct = (valid_data.size/band_data.size)*100
                        else:
                            min_val = max_val = mean_val = std_val = valid_pixels = coverage_pct = 'N/A'
                    except:
                        min_val = max_val = mean_val = std_val = valid_pixels = coverage_pct = 'Error'
                    
                    writer.writerow([
                        filename, src.width, src.height, src.count, src.dtypes[0],
                        src.crs.to_string() if src.crs else 'No CRS',
                        abs(transform.a), abs(transform.e),
                        bounds.left, bounds.bottom, bounds.right, bounds.top,
                        src.nodata if src.nodata is not None else 'None',
                        f"{file_size:.2f}", min_val, max_val, mean_val, std_val, valid_pixels, coverage_pct
                    ])
            except Exception as e:
                writer.writerow([filename, 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error',
                               'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', 'Error', str(e)])
    
    add_line("")
    add_line(f"Detailed CSV report saved: {csv_path}")
    
except Exception as e:
    add_line(f"Error creating CSV report: {str(e)}")

c.drawText(text)
c.save()

print(f"Quality Report generated: {path}")
if 'csv_path' in locals():
    print(f"CSV Report generated: {csv_path}")
print(f"Total files analyzed: {len(geotiff_files)}")
print(f"Quality issues found: {len(quality_issues)}")

app.Destroy()