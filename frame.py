import os
import json
import pandas as pd
from math import cos, radians

# Paths
# INTERSECTION_CSV = r"D:\hdj\mda\data\satellite_ship_intersections.csv"
# OUTPUT_GEOJSON = r"D:\hdj\mda\data\ship_capture_frame.geojson"
INTERSECTION_CSV = r"D:\hdj\mda\data\satellite_ship_intersections_long.csv"
OUTPUT_GEOJSON = r"D:\hdj\mda\data\ship_capture_frame_long.geojson"

print("📖 Reading match results dynamically...")
try:
    df_matches = pd.read_csv(INTERSECTION_CSV)
    if df_matches.empty:
        print("❌ The intersection file is empty. Run intersectionship.py first!")
        exit()
        
    best_match = df_matches.iloc[0]
    match_time_str = best_match['Timestamp_UTC']
    match_lat = float(best_match['Satellite_Lat'])
    match_lon = float(best_match['Satellite_Lon'])
    
    print(f"🎯 Target Acquired Locally!")
    print(f"   • Time: {match_time_str}")
    print(f"   • Center Coordinates: ({match_lat}, {match_lon})")

except Exception as e:
    print(f"❌ Error reading intersection file: {e}")
    exit()

print("\n📐 Calculating 100x100 km standard satellite imagery frame...")

# Degree approximations for a standard satellite tile grid footprint
# 1 degree latitude = ~111.32 km
lat_offset = 50.0 / 111.32  # 50km half-width up and down

# Longitude degree length shrinks as we move away from the equator
lon_offset = 50.0 / (111.32 * cos(radians(match_lat))) # 50km half-width left and right

# Define the 4 corners of our 100x100km square imagery scene
min_lat = match_lat - lat_offset
max_lat = match_lat + lat_offset
min_lon = match_lon - lon_offset
max_lon = match_lon + lon_offset

# Build a structurally flawless GeoJSON Frame feature for QGIS mapping
feature_node = {
    "type": "Feature",
    "id": "SIMULATED_SENTINEL_FRAME_035400",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [min_lon, min_lat],  # Bottom-Left
            [max_lon, min_lat],  # Bottom-Right
            [max_lon, max_lat],  # Top-Right
            [min_lon, max_lat],  # Top-Left
            [min_lon, min_lat]   # Close the polygon loop back at Bottom-Left
        ]]
    },
    "properties": {
        "scene_id": "Simulated_Capture_Scene_Gulf",
        "simulated_utc": match_time_str,
        "calculated_center": f"{round(match_lat, 4)}, {round(match_lon, 4)}",
        "swath_width": "100km x 100km standard tile"
    }
}

output_geojson = {
    "type": "FeatureCollection",
    "features": [feature_node]
}

# Ensure the output directory exists
os.makedirs(os.path.dirname(OUTPUT_GEOJSON), exist_ok=True)

with open(OUTPUT_GEOJSON, "w") as f:
    json.dump(output_geojson, f, indent=4)

print("================== GENERATION REPORT ==================")
print(f"🎉 SUCCESS! Generated local geometry frame footprint.")
print(f"💾 Saved boundary layer to: {OUTPUT_GEOJSON}")
print("=======================================================")