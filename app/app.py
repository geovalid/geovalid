"""
GeoTIFF Quality Report Generator
Main application module
"""

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


class GeoTiffAnalyzer:
    """Main class for analyzing GeoTIFF files and generating quality reports"""
    
    def __init__(self):
        self.folder = None
        self.geotiff_files = []
        self.datum_summary = defaultdict(int)
        self.total_area = 0
        self.pixel_size_summary = defaultdict(int)
        self.quality_issues = []
        self.raster_stats = []
        self.canvas = None
        self.text = None
        self.width = None
        self.height = None
    
    def select_folder(self):
        """Open folder selection dialog"""
        app = wx.App(False)
        dlg = wx.DirDialog(None, "Select folder containing GeoTIFF files", style=wx.DD_DEFAULT_STYLE)
        dlg.ShowModal()
        self.folder = dlg.GetPath()
        dlg.Destroy()
        app.Destroy()
        
        if not self.folder:
            return False
            
        self.geotiff_files = [f for f in os.listdir(self.folder) if f.lower().endswith(('.tif', '.tiff'))]
        return True
    
    def setup_pdf(self):
        """Initialize PDF canvas and text object"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        filename = f"Quality-Report-{timestamp}.pdf"
        path = os.path.join(self.folder, filename)
        
        self.canvas = canvas.Canvas(path, pagesize=A4)
        self.width, self.height = A4
        self.text = self.canvas.beginText(50, self.height - 50)
        
        return path
    
    def add_line(self, line):
        """Add a line to the PDF, handling page breaks"""
        self.text.textLine(line)
        if self.text.getY() < 50:
            self.canvas.drawText(self.text)
            self.canvas.showPage()
            self.text = self.canvas.beginText(50, self.height - 50)
            self.text.setFont("Helvetica", 10)
    
    def add_section_header(self, header):
        """Add a section header to the PDF"""
        self.text.setFont("Helvetica-Bold", 12)
        self.add_line("")
        self.add_line(header)
        self.add_line("-" * len(header))
        self.text.setFont("Helvetica", 10)
    
    def analyze_files(self):
        """Analyze all GeoTIFF files in the selected folder"""
        print("Analyzing files...")
        
        for filename in self.geotiff_files:
            filepath = os.path.join(self.folder, filename)
            try:
                with rasterio.open(filepath) as src:
                    self._analyze_single_file(src, filename, filepath)
            except Exception as e:
                self.quality_issues.append(f"{filename}: Error reading file - {str(e)}")
    
    def _analyze_single_file(self, src, filename, filepath):
        """Analyze a single GeoTIFF file"""
        # CRS/Datum analysis
        crs_string = src.crs.to_string() if src.crs else 'No CRS'
        self.datum_summary[crs_string] += 1
        
        # Area calculation (approximate)
        transform = src.transform
        pixel_area = abs(transform.a * transform.e)
        file_area = pixel_area * src.width * src.height
        self.total_area += file_area
        
        # Pixel size analysis
        pixel_size = f"{abs(transform.a):.4f}"
        self.pixel_size_summary[pixel_size] += 1
        
        # Quality checks
        if not src.crs:
            self.quality_issues.append(f"{filename}: Missing CRS")
        
        if src.nodata is None:
            self.quality_issues.append(f"{filename}: No NoData value defined")
        
        # Basic statistics for first band
        if src.count > 0:
            self._analyze_band_statistics(src, filename)
            
        # Check file size
        self._check_file_size(filename, filepath)
    
    def _analyze_band_statistics(self, src, filename):
        """Analyze statistics for the first band of a raster"""
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
            self.raster_stats.append(stats)
            
            # Check for suspicious values
            if np.min(valid_data) < -1000 or np.max(valid_data) > 10000:
                self.quality_issues.append(
                    f"{filename}: Suspicious data values (min: {np.min(valid_data):.2f}, max: {np.max(valid_data):.2f})"
                )
    
    def _check_file_size(self, filename, filepath):
        """Check for very small or very large files"""
        file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
        if file_size < 1:
            self.quality_issues.append(f"{filename}: Very small file size ({file_size:.2f} MB)")
        elif file_size > 1000:
            self.quality_issues.append(f"{filename}: Very large file size ({file_size:.2f} MB)")
    
    def generate_summary_section(self):
        """Generate the overall summary section"""
        self.add_section_header("OVERALL SUMMARY")
        self.add_line(f"Total GeoTIFF files analyzed: {len(self.geotiff_files)}")
        self.add_line(f"Total approximate area covered: {self.total_area/1000000:.2f} km²")
        self.add_line(f"Quality issues found: {len(self.quality_issues)}")
        self.add_line(f"Files with issues: {len(set([issue.split(':')[0] for issue in self.quality_issues]))}")
    
    def generate_crs_analysis(self):
        """Generate the CRS/Datum analysis section"""
        self.add_section_header("COORDINATE REFERENCE SYSTEM ANALYSIS")
        self.add_line("CRS Distribution:")
        for crs, count in self.datum_summary.items():
            self.add_line(f"  {crs}: {count} files ({count/len(self.geotiff_files)*100:.1f}%)")
        
        if len(self.datum_summary) > 1:
            self.add_line("")
            self.add_line("WARNING: Multiple CRS found! This may cause issues in analysis.")
    
    def generate_pixel_size_analysis(self):
        """Generate the pixel size analysis section"""
        self.add_section_header("PIXEL SIZE ANALYSIS")
        self.add_line("Pixel Size Distribution:")
        for pixel_size, count in self.pixel_size_summary.items():
            self.add_line(f"  {pixel_size} units: {count} files")
        
        if len(self.pixel_size_summary) > 1:
            self.add_line("")
            self.add_line("NOTE: Multiple pixel sizes detected. Consider resampling for consistency.")
    
    def generate_statistical_analysis(self):
        """Generate the statistical analysis section"""
        self.add_section_header("RASTER STATISTICS SUMMARY")
        if self.raster_stats:
            all_mins = [s['min'] for s in self.raster_stats]
            all_maxs = [s['max'] for s in self.raster_stats]
            all_means = [s['mean'] for s in self.raster_stats]
            
            self.add_line(f"Data Value Range Across All Files:")
            self.add_line(f"  Global Minimum: {min(all_mins):.4f}")
            self.add_line(f"  Global Maximum: {max(all_maxs):.4f}")
            self.add_line(f"  Average of Means: {np.mean(all_means):.4f}")
            self.add_line(f"  Standard Deviation of Means: {np.std(all_means):.4f}")
    
    def generate_quality_issues_section(self):
        """Generate the quality issues and recommendations section"""
        self.add_section_header("QUALITY ISSUES AND RECOMMENDATIONS")
        if self.quality_issues:
            self.add_line("Issues found:")
            for issue in self.quality_issues:
                self.add_line(f"  • {issue}")
            
            self.add_line("")
            self.add_line("Recommendations:")
            if any("Missing CRS" in issue for issue in self.quality_issues):
                self.add_line("  • Define coordinate reference system for files missing CRS")
            if any("NoData" in issue for issue in self.quality_issues):
                self.add_line("  • Set appropriate NoData values for better data handling")
            if any("Suspicious data values" in issue for issue in self.quality_issues):
                self.add_line("  • Review data values for potential errors or outliers")
            if len(self.datum_summary) > 1:
                self.add_line("  • Consider reprojecting all files to a common CRS")
            if len(self.pixel_size_summary) > 1:
                self.add_line("  • Consider resampling to consistent pixel size")
        else:
            self.add_line("No significant quality issues detected.")
    
    def generate_detailed_file_analysis(self):
        """Generate detailed analysis for each file"""
        self.add_section_header("DETAILED FILE ANALYSIS")
        
        for filename in self.geotiff_files:
            filepath = os.path.join(self.folder, filename)
            self.add_line(f"File: {filename}")
            try:
                with rasterio.open(filepath) as src:
                    self._generate_file_details(src, filename, filepath)
            except Exception as e:
                self.add_line(f"  Error reading file: {e}")
            
            self.add_line("")
    
    def _generate_file_details(self, src, filename, filepath):
        """Generate detailed information for a single file"""
        # Basic info
        self.add_line(f"  Dimensions: {src.width} x {src.height} pixels")
        self.add_line(f"  Bands: {src.count}")
        self.add_line(f"  Data type: {src.dtypes[0]}")
        self.add_line(f"  CRS: {src.crs.to_string() if src.crs else 'No CRS'}")
        
        # Affine transform and pixel size
        transform = src.transform
        self.add_line(f"  Pixel Size: {abs(transform.a):.6f} x {abs(transform.e):.6f} units")
        
        # Bounds
        bounds = src.bounds
        self.add_line(f"  Bounds:")
        self.add_line(f"    Left: {bounds.left:.6f}")
        self.add_line(f"    Bottom: {bounds.bottom:.6f}")
        self.add_line(f"    Right: {bounds.right:.6f}")
        self.add_line(f"    Top: {bounds.top:.6f}")
        
        # Coverage area
        coverage_area = (bounds.right - bounds.left) * (bounds.top - bounds.bottom)
        self.add_line(f"  Coverage Area: {coverage_area:.2f} square units")
        
        # NoData value
        nodata = src.nodata
        self.add_line(f"  NoData Value: {nodata if nodata is not None else 'None'}")
        
        # File size
        file_size = os.path.getsize(filepath) / (1024 * 1024)
        self.add_line(f"  File Size: {file_size:.2f} MB")
        
        # Band statistics
        if src.count > 0:
            self._generate_band_details(src)
    
    def _generate_band_details(self, src):
        """Generate detailed band statistics"""
        try:
            band_data = src.read(1, masked=True)
            if band_data.compressed().size > 0:
                valid_data = band_data.compressed()
                self.add_line(f"  Band 1 Statistics:")
                self.add_line(f"    Min: {np.min(valid_data):.4f}")
                self.add_line(f"    Max: {np.max(valid_data):.4f}")
                self.add_line(f"    Mean: {np.mean(valid_data):.4f}")
                self.add_line(f"    Std Dev: {np.std(valid_data):.4f}")
                self.add_line(f"    Valid Pixels: {valid_data.size:,}")
                self.add_line(f"    NoData Pixels: {band_data.size - valid_data.size:,}")
                self.add_line(f"    Data Coverage: {(valid_data.size/band_data.size)*100:.1f}%")
            else:
                self.add_line(f"  Band 1: No valid data")
        except Exception as e:
            self.add_line(f"  Band statistics error: {str(e)}")
    
    def generate_spatial_coverage_analysis(self):
        """Generate spatial coverage analysis section"""
        self.add_section_header("SPATIAL COVERAGE ANALYSIS")
        try:
            bounds_list = []
            for filename in self.geotiff_files:
                filepath = os.path.join(self.folder, filename)
                try:
                    with rasterio.open(filepath) as src:
                        bounds_list.append({
                            'file': filename,
                            'bounds': src.bounds
                        })
                except:
                    continue
            
            if len(bounds_list) > 1:
                self._analyze_spatial_extent(bounds_list)
        except Exception as e:
            self.add_line(f"Spatial analysis error: {str(e)}")
    
    def _analyze_spatial_extent(self, bounds_list):
        """Analyze overall spatial extent and overlaps"""
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
        
        self.add_line("Overall Spatial Extent:")
        self.add_line(f"  Left: {overall_bounds['left']:.6f}")
        self.add_line(f"  Right: {overall_bounds['right']:.6f}")
        self.add_line(f"  Bottom: {overall_bounds['bottom']:.6f}")
        self.add_line(f"  Top: {overall_bounds['top']:.6f}")
        
        total_extent_area = (overall_bounds['right'] - overall_bounds['left']) * (overall_bounds['top'] - overall_bounds['bottom'])
        self.add_line(f"  Total Extent Area: {total_extent_area:.2f} square units")
        
        # Check for potential overlaps (simplified)
        overlap_count = 0
        for i, bounds1 in enumerate(bounds_list):
            for j, bounds2 in enumerate(bounds_list[i+1:], i+1):
                b1, b2 = bounds1['bounds'], bounds2['bounds']
                if (b1.left < b2.right and b1.right > b2.left and 
                    b1.bottom < b2.top and b1.top > b2.bottom):
                    overlap_count += 1
        
        self.add_line(f"  Potential overlapping file pairs: {overlap_count}")
        if overlap_count > 0:
            self.add_line("  Note: Overlaps detected - consider mosaic creation")
    
    def generate_recommendations_section(self):
        """Generate processing recommendations section"""
        self.add_section_header("PROCESSING RECOMMENDATIONS")
        self.add_line("Based on the analysis, consider the following:")
        self.add_line("")
        
        if len(self.datum_summary) > 1:
            self.add_line("1. COORDINATE SYSTEM STANDARDIZATION:")
            self.add_line("   • Reproject all files to a common CRS")
            self.add_line("   • Consider using UTM zone appropriate for your area")
            self.add_line("")
        
        if len(self.pixel_size_summary) > 1:
            self.add_line("2. PIXEL SIZE HARMONIZATION:")
            self.add_line("   • Resample files to consistent pixel size")
            self.add_line("   • Use appropriate resampling method (bilinear, cubic, etc.)")
            self.add_line("")
        
        if any("Missing CRS" in issue for issue in self.quality_issues):
            self.add_line("3. MISSING CRS CORRECTION:")
            self.add_line("   • Define appropriate coordinate system for files missing CRS")
            self.add_line("   • Verify spatial alignment after CRS assignment")
            self.add_line("")
        
        self.add_line("4. GENERAL RECOMMENDATIONS:")
        self.add_line("   • Create backup copies before processing")
        self.add_line("   • Validate results after any transformations")
        self.add_line("   • Consider creating a mosaic for seamless coverage")
        self.add_line("   • Document all processing steps for reproducibility")
        self.add_line("")
    
    def generate_report(self):
        """Generate the complete PDF report"""
        if not self.folder or not self.geotiff_files:
            print("No folder selected or no GeoTIFF files found.")
            return None
        
        # Setup PDF
        pdf_path = self.setup_pdf()
        
        # Title
        self.text.setFont("Helvetica-Bold", 16)
        self.add_line("GeoTIFF Quality Report")
        
        # Switch back to normal font
        self.text.setFont("Helvetica", 10)
        self.add_line("")
        self.add_line(f"Folder: {self.folder}")
        self.add_line(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.add_line(f"Total files found: {len(self.geotiff_files)}")
        self.add_line("")
        
        # Analyze files
        self.analyze_files()
        
        # Generate all sections
        self.generate_summary_section()
        self.generate_crs_analysis()
        self.generate_pixel_size_analysis()
        self.generate_statistical_analysis()
        self.generate_quality_issues_section()
        self.generate_detailed_file_analysis()
        self.generate_spatial_coverage_analysis()
        self.generate_recommendations_section()
        
        # Finalize PDF
        self.canvas.drawText(self.text)
        self.canvas.save()
        
        return pdf_path


def main():
    """Main function to run the GeoTIFF analyzer"""
    analyzer = GeoTiffAnalyzer()
    
    # Select folder
    if not analyzer.select_folder():
        print("No folder selected. Exiting.")
        return
    
    if not analyzer.geotiff_files:
        print("No GeoTIFF files found in the selected folder.")
        return
    
    # Generate report
    pdf_path = analyzer.generate_report()
    
    if pdf_path:
        print(f"Quality Report generated: {pdf_path}")
        print(f"Total files analyzed: {len(analyzer.geotiff_files)}")
        print(f"Quality issues found: {len(analyzer.quality_issues)}")
    else:
        print("Failed to generate report.")


if __name__ == "__main__":
    main()