from datetime import datetime
import json
import pandas as pd
import requests
from shapely.geometry import Polygon, Point

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. LOAD SHIP DATA
# ==========================================
print("🔄 Loading ship data...")
df = pd.read_csv("D:/hdj/mda/GT_Test_Data_Excel_1.csv")
df.columns = df.columns.str.strip().str.lower()
df["base_date_time"] = pd.to_datetime(df["base_date_time"], dayfirst=True)

all_scenes = []

# ==========================================
# 2. LOOP AND QUERY AWS BY UNIQUE PATH_ID
# ==========================================
unique_paths = df["path_id"].unique()
print(f"🛤️ Found {len(unique_paths)} unique ship paths to analyze.")

for pid in unique_paths:
    path_df = df[df["path_id"] == pid]
    if path_df.empty:
        continue
    
    # Calculate a tight bounding box around ONLY this specific ship's route
    bbox = [
        path_df["longitude"].min(),
        path_df["latitude"].min(),
        path_df["longitude"].max(),
        path_df["latitude"].max()
    ]
    
    print(f"🌐 Querying AWS for Ship Path ID: {pid}...")
    url = "https://earth-search.aws.element84.com/v1/search"
    payload = {
        "collections": ["landsat-c2-l2", "sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": "2025-02-27T00:00:00Z/2025-02-27T23:59:59Z",
        "limit": 10,
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, verify=False, timeout=30)
        stac_data = response.json()
        all_scenes.extend(stac_data.get("features", []))
    except Exception as e:
        print(f"❌ Query failed for Path {pid}: {e}")

print(f"📡 Found {len(all_scenes)} total targeted satellite frames across all paths!")

# ==========================================
# 3. RUN THE MATCHING MATH & CLEAN GEOMETRIES
# ==========================================
print("⚡ Executing intersection matching pipeline...")
intersections_found = 0
match_records = []
clean_features = []
unique_ids = set()

# Remove duplicate frames grabbed by multiple paths if their boxes overlapped
unique_scenes = {scene['id']: scene for scene in all_scenes}.values()

for scene in unique_scenes:
    geometry = scene.get("geometry", {})
    properties = scene.get("properties", {})
    if not geometry or "coordinates" not in geometry:
        continue

    sat_polygon = Polygon(geometry["coordinates"][0])
    sat_time = pd.to_datetime(properties.get("datetime")).replace(tzinfo=None)

    # Clean the satellite footprint properties to keep the GeoJSON flat and clean
    if scene['id'] not in unique_ids:
        unique_ids.add(scene['id'])
        clean_features.append({
            "type": "Feature",
            "id": scene.get("id"),
            "geometry": geometry,
            "properties": {
                "satellite": scene.get("id").split("_")[0],
                "datetime": properties.get("datetime")
            }
        })

    # Check against all ships
    for index, row in df.iterrows():
        ship_point = Point(row["longitude"], row["latitude"])

        if sat_polygon.contains(ship_point):
            match_records.append({
                "sno": row["sno"],
                "path_id": row["path_id"],
                "ship_time": row["base_date_time"],
                "satellite_id": scene.get("id"),
                "satellite_time": sat_time,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "cloud_cover": properties.get("eo:cloud_cover", 0),
            })
            intersections_found += 1

# ==========================================
# 4. EXPORT BOTH FILES WITH UNIQUE NAMES
# ==========================================
print("\n================== REPORT ==================")
if intersections_found > 0:
    results_df = pd.DataFrame(match_records).drop_duplicates()
    
    # 1. Save CSV with a distinct name
    csv_output_path = "D:/hdj/mda/path_verified_intersections.csv"
    results_df.to_csv(csv_output_path, index=False)
    
    # 2. Save clean GeoJSON with a distinct name
    geojson_output_path = "D:/hdj/mda/satellite_frames_path_mode.geojson"
    geojson_output = {"type": "FeatureCollection", "features": clean_features}
    with open(geojson_output_path, "w") as f:
        json.dump(geojson_output, f)
        
    print(f"🎉 SUCCESS! Found {len(results_df)} unique verified intersections!")
    print(f"💾 CSV Data Saved to: {csv_output_path}")
    print(f"🌍 Clean GeoJSON Saved to: {geojson_output_path}")
    print("\nPreview of matches:")
    print(results_df[["sno", "path_id", "satellite_id"]].head())
else:
    print("❌ Zero matches found using the path_id pipeline approach.")
print("============================================")









