import arcpy
import pythonaddins

def check_builtup_within_parcel(builtup_layer, parcel_layer):
    # Create a feature layer from the builtup area
    if arcpy.Exists("builtup_lyr"):
        arcpy.Delete_management("builtup_lyr")
    arcpy.MakeFeatureLayer_management(builtup_layer, "builtup_lyr")
    
    # Create a feature layer from the parcel area
    if arcpy.Exists("parcel_lyr"):
        arcpy.Delete_management("parcel_lyr")
    arcpy.MakeFeatureLayer_management(parcel_layer, "parcel_lyr")
    
    # Select builtup features that are not within any parcel
    arcpy.SelectLayerByLocation_management("builtup_lyr", "WITHIN", "parcel_lyr", invert_spatial_relationship=True)
    
    # Create a new layer for the selected features
    if arcpy.Exists("in_memory\\builtup_not_in_parcel"):
        arcpy.Delete_management("in_memory\\builtup_not_in_parcel")
    arcpy.CopyFeatures_management("builtup_lyr", "in_memory\\builtup_not_in_parcel")
    
    # Add the new layer to the map
    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    new_layer = arcpy.mapping.Layer("in_memory\\builtup_not_in_parcel")
    arcpy.mapping.AddLayer(df, new_layer, "TOP")
    
    arcpy.RefreshActiveView()
    arcpy.RefreshTOC()
    
    # Get the count of builtup and parcel features
    builtup_count = int(arcpy.GetCount_management(builtup_layer).getOutput(0))
    parcel_count = int(arcpy.GetCount_management(parcel_layer).getOutput(0))
    
    # Display the counts in a popup
    message = "Number of builtup features: {}\nNumber of parcel features: {}".format(builtup_count, parcel_count)
    pythonaddins.MessageBox(message, "Feature Counts")

if __name__ == "__main__":
    builtup_layer = arcpy.GetParameterAsText(0)
    parcel_layer = arcpy.GetParameterAsText(1)
    check_builtup_within_parcel(builtup_layer, parcel_layer)

import arcpy
import os
import csv

def datum_check_report(input_gdbs, output_folder):
    # Prepare the CSV file path
    csv_file_path = os.path.join(output_folder, "datumcheckreport.csv")
    
    # Open the CSV file for writing
    with open(csv_file_path, mode='wb') as csv_file:
        csv_writer = csv.writer(csv_file)
        
        # Write the header row
        csv_writer.writerow(["Geodatabase", "Feature Class", "Datum_Projection"])
        
        # Iterate through each input geodatabase
        for input_gdb in input_gdbs:
            # Set the workspace to the input geodatabase
            arcpy.env.workspace = input_gdb
            
            # Get a list of all feature classes in the geodatabase
            feature_classes = arcpy.ListFeatureClasses()
            
            if feature_classes is None:
                arcpy.AddMessage("No feature classes found in the geodatabase: {}".format(input_gdb))
                continue
            
            # Iterate through each feature class
            for fc in feature_classes:
                # Get the spatial reference of the feature class
                spatial_ref = arcpy.Describe(fc).spatialReference
                # arcpy.AddMessage("Spatial Ref: {}".format(spatial_ref.datumName))
                # # Initialize datum properties
                # datum_name = "Unknown"
                # datum_code = "Unknown"
                # datum_type = "Unknown"
                
                # # Check if the coordinate system is geographic
                # if spatial_ref.type == "Geographic":
                #     gcs = spatial_ref.geographicCoordinateSystem
                #     datum_name = gcs.datumName
                #     datum_code = gcs.datumCode
                #     datum_type = gcs.datumType
                
                # Get the projection
                projection = spatial_ref.name
                
                # Write the geodatabase, feature class name, datum properties, and projection to the CSV file
                csv_writer.writerow([input_gdb, fc, projection])
                
                # Add message with the coordinate system of the feature class
                #arcpy.AddMessage("Feature Class: {}, Coordinate System: {}".format(fc, projection))
    
    arcpy.AddMessage("Datum check report generated at: {}".format(csv_file_path))

# Example usage
if __name__ == "__main__":
    input_gdbs = arcpy.GetParameterAsText(0).split(";")  # Input Geodatabases (semicolon-separated)
    output_folder = arcpy.GetParameterAsText(1)  # Output Folder
    
    datum_check_report(input_gdbs, output_folder)

import arcpy
import os

def mark_status_with_intersects(target_layer, available_layer):
    """Marks target shapes as 'completed' if they are within or contained by available shapes, else 'pending'.
    Adds a separate layer for pending shapes and loads it into the ArcMap canvas."""
    
    # Set workspace and overwrite settings
    arcpy.env.overwriteOutput = True

    # Detect OID field dynamically
    oid_field = arcpy.Describe(target_layer).OIDFieldName

    # Add status field if it doesn't exist
    if "status" not in [field.name for field in arcpy.ListFields(target_layer)]:
        arcpy.AddField_management(target_layer, "status", "TEXT", field_length=10)

    # Check CRS consistency
    target_crs = arcpy.Describe(target_layer).spatialReference
    available_crs = arcpy.Describe(available_layer).spatialReference

    if target_crs.name != available_crs.name:
        #print(f"Reprojecting layers to match CRS: {target_crs.name}")
        scratch_gdb = arcpy.env.scratchGDB
        reprojected_available = os.path.join(scratch_gdb, "reprojected_available")
        arcpy.Project_management(available_layer, reprojected_available, target_crs)
        available_layer = reprojected_available

    # Create a pending layer with the same features as the target layer initially
    pending_layer = os.path.join(arcpy.env.scratchGDB, "Pending_Areas")
    arcpy.CopyFeatures_management(target_layer, pending_layer)

    # Update the status field for the target layer
    with arcpy.da.UpdateCursor(target_layer, [oid_field, "SHAPE@", "status"]) as target_cursor:
        for target_row in target_cursor:
            target_shape = target_row[1]
            intersected = False

            with arcpy.da.SearchCursor(available_layer, ["SHAPE@"]) as available_cursor:
                for avail_row in available_cursor:
                    available_shape = avail_row[0]

                    if target_shape.within(available_shape) or available_shape.contains(target_shape):
                        intersected = True
                        break

            target_row[2] = "completed" if intersected else "pending"
            target_cursor.updateRow(target_row)

    # Remove completed shapes from the pending layer
    with arcpy.da.UpdateCursor(pending_layer, ["SHAPE@"]) as pending_cursor:
        with arcpy.da.SearchCursor(target_layer, ["SHAPE@", "status"]) as status_cursor:
            completed_shapes = [row[0] for row in status_cursor if row[1] == "completed"]

            for pending_row in pending_cursor:
                if any(pending_row[0].equals(comp_shape) for comp_shape in completed_shapes):
                    pending_cursor.deleteRow()

    # Add the pending layer to the ArcMap canvas
    if arcpy.mapping.MapDocument("CURRENT"):
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]

        pending_layer_obj = arcpy.mapping.Layer(pending_layer)
        arcpy.mapping.AddLayer(df, pending_layer_obj, "TOP")
       # print(f"✅ Pending layer added to canvas: {pending_layer}")
    else:
        print("⚠️ Could not load the pending layer into the canvas. Make sure you are running this in ArcMap.")

    #print(f"✅ Process completed successfully! Pending shapes saved in: {pending_layer}")

# Example usage
input_target_layer = arcpy.GetParameterAsText(0)  # Target layer from ArcToolbox
input_available_layer = arcpy.GetParameterAsText(1)  # Available layer from ArcToolbox

mark_status_with_intersects(input_target_layer, input_available_layer)

import arcpy
import os
import csv

def datum_check_report(input_gdbs, output_folder):
    # Prepare the CSV file path
    csv_file_path = os.path.join(output_folder, "datumcheckreport.csv")
    
    # Open the CSV file for writing
    with open(csv_file_path, mode='wb') as csv_file:
        csv_writer = csv.writer(csv_file)
        
        # Write the header row
        csv_writer.writerow(["Geodatabase", "Feature Class", "Datum_Projection"])
        
        # Iterate through each input geodatabase
        for input_gdb in input_gdbs:
            # Set the workspace to the input geodatabase
            arcpy.env.workspace = input_gdb
            
            # Get a list of all feature classes in the geodatabase
            feature_classes = arcpy.ListFeatureClasses()
            
            if feature_classes is None:
                arcpy.AddMessage("No feature classes found in the geodatabase: {}".format(input_gdb))
                continue
            
            # Iterate through each feature class
            for fc in feature_classes:
                # Get the spatial reference of the feature class
                spatial_ref = arcpy.Describe(fc).spatialReference
                
                
                # Get the projection
                projection = spatial_ref.name
                
                # Write the geodatabase, feature class name, datum properties, and projection to the CSV file
                csv_writer.writerow([input_gdb, fc, projection])
                
                # Add message with the coordinate system of the feature class
                #arcpy.AddMessage("Feature Class: {}, Coordinate System: {}".format(fc, projection))
    
    arcpy.AddMessage("Datum check report generated at: {}".format(csv_file_path))

# Example usage
if __name__ == "__main__":
    input_gdbs = arcpy.GetParameterAsText(0).split(";")  # Input Geodatabases (semicolon-separated)
    output_folder = arcpy.GetParameterAsText(1)  # Output Folder
    
    datum_check_report(input_gdbs, output_folder)

import arcpy
import math
import csv
import os

def calculate_height_rmse(elevation_raster, gcp_layer, height_field, output_folder):
    """Calculates the RMSE of height differences between elevation raster and GCP height values.
    Saves the results in 'report.csv' in the specified output folder."""

    arcpy.env.overwriteOutput = True

    # Validate output folder
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    output_csv = os.path.join(output_folder, "report.csv")

    # Validate the height field
    fields = [field.name for field in arcpy.ListFields(gcp_layer)]
    if height_field not in fields:
        arcpy.AddError("Field does not exist in the GCP layer.")
        return

    # Identify OID field in the GCP layer
    gcp_oid_field = arcpy.Describe(gcp_layer).OIDFieldName

    # Calculate height differences
    differences = []
    valid_points = 0

    with arcpy.da.SearchCursor(gcp_layer, [gcp_oid_field, "SHAPE@", height_field]) as gcp_cursor:
        for gcp_id, gcp_shape, gcp_height in gcp_cursor:
            
            # Get raster value at the GCP location
            result = arcpy.GetCellValue_management(elevation_raster, "{0} {1}".format(gcp_shape.centroid.X, gcp_shape.centroid.Y))
            raster_height = float(result.getOutput(0)) if result.getOutput(0) != "NoData" else None

            if raster_height is not None:
                height_diff = gcp_height - raster_height
                differences.append((gcp_id, gcp_height, raster_height, height_diff))
                valid_points += 1

    # Calculate RMSE only if there are valid points
    if valid_points > 0:
        squared_sum = sum(d[3] ** 2 for d in differences)
        rmse = math.sqrt(squared_sum / valid_points)
    else:
        rmse = "N/A (No valid height points)"

    # Save results to CSV
    with open(output_csv, mode='w') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["GCP_ID", "GCP_Height", "Raster_Height", "Height_Difference (m)"])

        for gcp_id, gcp_height, raster_height, diff in differences:
            writer.writerow([gcp_id, gcp_height, raster_height, diff])

        writer.writerow([])
        writer.writerow(["RMSE", rmse])

# Example usage
input_elevation_raster = arcpy.GetParameterAsText(0)    # Elevation Raster Layer
input_gcp_layer = arcpy.GetParameterAsText(1)           # GCP Point Layer
input_height_field = arcpy.GetParameterAsText(2)        # Height field in GCP layer
output_folder = arcpy.GetParameterAsText(3)             # Output folder for CSV

calculate_height_rmse(input_elevation_raster, input_gcp_layer, input_height_field, output_folder)

import arcpy
from arcpy.sa import *
import os

def create_footprints_from_folders(input_folders, output_layer_name):
    # Check out the ArcGIS Spatial Analyst extension license
    arcpy.CheckOutExtension("Spatial")
    
    # Set workspace to default.gdb
    arcpy.env.workspace = arcpy.env.scratchGDB
    arcpy.env.overwriteOutput = True
    
    # Create an empty list to hold polygon layers
    polygon_layers = []
    
    # Loop through all folders and find TIF files
    for folder in input_folders.split(';'):
        if os.path.exists(folder):
            arcpy.AddMessage("Processing folder: {}".format(folder))
            tif_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith('.tif') and os.path.isfile(os.path.join(folder, f))]
            arcpy.AddMessage("Found TIF files: {}".format(tif_files))
            for tif in tif_files:
                arcpy.AddMessage("Processing TIF file: {}".format(tif))
                raster = Raster(tif)
                
                # Convert all DN values to 1
                converted_raster = Con(raster > 0, 1, 0)
                
                # Save the converted raster to default.gdb
                raster_name = os.path.splitext(os.path.basename(tif))[0] + "_raster"
                output_raster_path = os.path.join(arcpy.env.scratchGDB, raster_name)
                arcpy.AddMessage("Saving converted raster to: {}".format(output_raster_path))
                
                # Check if the raster already exists and delete it if necessary
                if arcpy.Exists(output_raster_path):
                    arcpy.AddMessage("Raster already exists. Deleting: {}".format(output_raster_path))
                    arcpy.Delete_management(output_raster_path)
                
                try:
                    converted_raster.save(output_raster_path)
                except Exception as e:
                    arcpy.AddError("Failed to save raster: {}".format(e))
                    continue
                
                # Convert the raster to polygon
                polygon_name = os.path.splitext(os.path.basename(tif))[0] + "_polygon"
                output_polygon_path = os.path.join(arcpy.env.scratchGDB, polygon_name)
                arcpy.AddMessage("Converting raster to polygon: {}".format(output_polygon_path))
                arcpy.RasterToPolygon_conversion(in_raster=output_raster_path, 
                                                 out_polygon_features=output_polygon_path, 
                                                 simplify="NO_SIMPLIFY", 
                                                 raster_field="Value")
                
                polygon_layers.append(output_polygon_path)
        else:
            arcpy.AddMessage("Folder does not exist: {}".format(folder))
    
    if polygon_layers:
        # Merge all polygon layers into a single layer
        merged_layer_path = os.path.join(arcpy.env.scratchGDB, "merged_footprints")
        if arcpy.Exists(merged_layer_path):
            arcpy.Delete_management(merged_layer_path)
        arcpy.AddMessage("Merging polygon layers into: {}".format(merged_layer_path))
        arcpy.Merge_management(polygon_layers, merged_layer_path)
        
        # Dissolve the merged layer into a single shape
        dissolved_layer_path = os.path.join(arcpy.env.scratchGDB, output_layer_name)
        if arcpy.Exists(dissolved_layer_path):
            arcpy.Delete_management(dissolved_layer_path)
        arcpy.AddMessage("Dissolving merged layer into: {}".format(dissolved_layer_path))
        arcpy.Dissolve_management(merged_layer_path, dissolved_layer_path)
        
        # Add the dissolved layer as ORI availability to the map (ArcMap compatibility)
        mxd = arcpy.mapping.MapDocument("CURRENT")
        df = arcpy.mapping.ListDataFrames(mxd)[0]
        ori_layer = arcpy.mapping.Layer(dissolved_layer_path)
        ori_layer.name = "ORI_availability"
        arcpy.AddMessage("Adding ORI availability layer to the map")
        arcpy.mapping.AddLayer(df, ori_layer, "TOP")
        
        # Refresh the map view
        arcpy.RefreshActiveView()
        arcpy.RefreshTOC()
    else:
        arcpy.AddMessage("No polygon layers to merge.")
    
    # Check in the ArcGIS Spatial Analyst extension license
    arcpy.CheckInExtension("Spatial")

# Example usage
input_folders = arcpy.GetParameterAsText(0)  # Get folder paths from ArcToolbox (semicolon-separated)
output_layer_name = "dissolved_footprint"
create_footprints_from_folders(input_folders, output_layer_name)

import arcpy
import os
import math
import csv

def calculate_rmse(target_layer, gcp_layer, output_folder):
    """Calculates the RMSE of distances from target points to nearest GCP points in meters.
    Omits points where the nearest distance > 5m.
    Saves the results to 'report.csv' in the specified output folder."""

    arcpy.env.overwriteOutput = True

    # Validate output folder
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    output_csv = os.path.join(output_folder, "report.csv")

    def get_utm_zone(longitude):
        """Determine UTM zone based on longitude."""
        return int((longitude + 180) / 6) + 1

    def reproject_to_utm(layer, output_name):
        """Reproject the layer to UTM Zone 43N or 44N based on its extent."""
        extent = arcpy.Describe(layer).extent
        center_longitude = (extent.XMin + extent.XMax) / 2
        utm_zone = get_utm_zone(center_longitude)
        epsg_code = 32600 + utm_zone  # EPSG code for WGS 84 UTM Northern Hemisphere
        utm_crs = arcpy.SpatialReference(epsg_code)
        temp_layer = os.path.join("in_memory", output_name)
        arcpy.management.Project(layer, temp_layer, utm_crs)
        return temp_layer

    # Reproject layers to UTM if necessary
    if not arcpy.Describe(target_layer).spatialReference.PCSCode:
        arcpy.AddMessage("Reprojecting target layer to UTM...")
        target_layer = reproject_to_utm(target_layer, "target_utm")

    if not arcpy.Describe(gcp_layer).spatialReference.PCSCode:
        arcpy.AddMessage("Reprojecting GCP layer to UTM...")
        gcp_layer = reproject_to_utm(gcp_layer, "gcp_utm")

    # Ensure both layers are in the same UTM zone
    target_crs = arcpy.Describe(target_layer).spatialReference
    gcp_crs = arcpy.Describe(gcp_layer).spatialReference
    if target_crs.PCSCode != gcp_crs.PCSCode:
        arcpy.AddMessage("Reprojecting GCP layer to match target layer's UTM zone...")
        gcp_layer = arcpy.management.Project(gcp_layer, "in_memory/gcp_utm", target_crs)

    # Identify OID field in the target layer dynamically
    target_oid_field = arcpy.Describe(target_layer).OIDFieldName

    # Calculate distances
    results = []
    valid_points = 0
    squared_sum_easting = 0.0
    squared_sum_northing = 0.0

    with arcpy.da.SearchCursor(target_layer, [target_oid_field, "SHAPE@XY"]) as target_cursor:
        for target_id, target_point in target_cursor:
            target_x, target_y = target_point

            nearest_distance = float("inf")
            nearest_gcp_x, nearest_gcp_y = None, None

            with arcpy.da.SearchCursor(gcp_layer, ["SHAPE@XY"]) as gcp_cursor:
                for gcp_point in gcp_cursor:
                    gcp_x, gcp_y = gcp_point[0]

                    # Calculate Euclidean distance in meters
                    distance = math.sqrt((target_x - gcp_x)**2 + (target_y - gcp_y)**2)
                    if distance < nearest_distance:
                        nearest_distance = distance
                        nearest_gcp_x, nearest_gcp_y = gcp_x, gcp_y

            # Only include points with distance ≤ 5m
            if nearest_distance <= 5:
                diff_easting = target_x - nearest_gcp_x
                diff_northing = target_y - nearest_gcp_y
                squared_sum_easting += diff_easting ** 2
                squared_sum_northing += diff_northing ** 2
                results.append((target_id, target_x, target_y, nearest_gcp_x, nearest_gcp_y, diff_easting, diff_northing, nearest_distance))
                valid_points += 1

    # Calculate RMSE for Easting and Northing
    if valid_points > 0:
        rmse_easting = math.sqrt(squared_sum_easting / valid_points)
        rmse_northing = math.sqrt(squared_sum_northing / valid_points)
    else:
        rmse_easting = "N/A (No points within 5m)"
        rmse_northing = "N/A (No points within 5m)"

    # Save results to CSV
    with open(output_csv, mode='w') as csv_file:  # ArcGIS compatibility without 'newline'
        writer = csv.writer(csv_file)
        writer.writerow(["Target_ID", "Target_Easting", "Target_Northing", "GCP_Easting", "GCP_Northing", "Difference_Easting", "Difference_Northing", "Distance (m)"])

        for target_id, target_x, target_y, gcp_x, gcp_y, diff_easting, diff_northing, dist in results:
            writer.writerow([target_id, target_x, target_y, gcp_x, gcp_y, diff_easting, diff_northing, dist])

        writer.writerow([])
        writer.writerow(["RMSE_Easting", rmse_easting])
        writer.writerow(["RMSE_Northing", rmse_northing])

# Example usage
input_target_layer = arcpy.GetParameterAsText(0)   # Target layer from ArcToolbox
input_gcp_layer = arcpy.GetParameterAsText(1)      # GCP layer from ArcToolbox
output_folder = arcpy.GetParameterAsText(2)        # Output folder for CSV file

calculate_rmse(input_target_layer, input_gcp_layer, output_folder)

import arcpy
import pythonaddins

def check_builtup_within_parcel(builtup_layer, parcel_layer):
    # Create a feature layer from the builtup area
    if arcpy.Exists("builtup_lyr"):
        arcpy.Delete_management("builtup_lyr")
    arcpy.MakeFeatureLayer_management(builtup_layer, "builtup_lyr")
    
    # Create a feature layer from the parcel area
    if arcpy.Exists("parcel_lyr"):
        arcpy.Delete_management("parcel_lyr")
    arcpy.MakeFeatureLayer_management(parcel_layer, "parcel_lyr")
    
    # Select builtup features that are not within any parcel
    arcpy.SelectLayerByLocation_management("builtup_lyr", "WITHIN", "parcel_lyr", invert_spatial_relationship=True)
    
    # Create a new layer for the selected features
    if arcpy.Exists("in_memory\\builtup_not_in_parcel"):
        arcpy.Delete_management("in_memory\\builtup_not_in_parcel")
    arcpy.CopyFeatures_management("builtup_lyr", "in_memory\\builtup_not_in_parcel")
    
    # Add the new layer to the map
    mxd = arcpy.mapping.MapDocument("CURRENT")
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    new_layer = arcpy.mapping.Layer("in_memory\\builtup_not_in_parcel")
    arcpy.mapping.AddLayer(df, new_layer, "TOP")
    
    # Select features that intersect the parcel layer
    arcpy.SelectLayerByLocation_management("builtup_lyr", "INTERSECT", "parcel_lyr")
    
    # Exclude features that are entirely within the parcel layer
    arcpy.SelectLayerByLocation_management(
        "builtup_lyr", 
        "WITHIN", 
        "parcel_lyr", 
        invert_spatial_relationship=False, 
        selection_type="REMOVE_FROM_SELECTION"
    )
    
    # Create a new layer for the crossing features
    if arcpy.Exists("in_memory\\builtup_crossing_parcel"):
        arcpy.Delete_management("in_memory\\builtup_crossing_parcel")
    arcpy.CopyFeatures_management("builtup_lyr", "in_memory\\builtup_crossing_parcel")
    
    # Add the crossing layer to the map
    crossing_layer = arcpy.mapping.Layer("in_memory\\builtup_crossing_parcel")
    arcpy.mapping.AddLayer(df, crossing_layer, "TOP")
    
    arcpy.RefreshActiveView()
    arcpy.RefreshTOC()
    
    # Get the count of builtup and parcel features
    builtup_count = int(arcpy.GetCount_management(builtup_layer).getOutput(0))
    parcel_count = int(arcpy.GetCount_management(parcel_layer).getOutput(0))
    crossing_count = int(arcpy.GetCount_management("in_memory\\builtup_crossing_parcel").getOutput(0))
    
    # Display the counts in a popup
    message = (
        "Number of builtup features: {}\n"
        "Number of parcel features: {}\n"
        "Number of crossing features: {}".format(builtup_count, parcel_count, crossing_count)
    )
    pythonaddins.MessageBox(message, "Feature Counts")

if __name__ == "__main__":
    builtup_layer = arcpy.GetParameterAsText(0)
    parcel_layer = arcpy.GetParameterAsText(1)
    check_builtup_within_parcel(builtup_layer, parcel_layer)