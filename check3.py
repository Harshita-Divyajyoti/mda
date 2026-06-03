from datetime import datetime
import json
import pandas as pd
import requests
from shapely.geometry import Polygon, Point
import numpy as np

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. LOAD SHIP DATA
# ==========================================
print("🔄 Loading ship data...")
df = pd.read_csv("D:/hdj/mda/GT_Test_Data_Excel_1.csv")
df.columns = df.columns.str.strip().str.lower()
df["base_date_time"] = pd.to_datetime(df["base_date_time"], dayfirst=True)

# Clean up any bad data globally before looping
df = df.dropna(subset=["longitude", "latitude", "base_date_time"])

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
    
    # CRITICAL FIX: Extract coordinates and make sure no NaNs or Infs slip through
    lons = path_df["longitude"].replace([np.inf, -np.inf], np.nan).dropna()
    lats = path_df["latitude"].replace([np.inf, -np.inf], np.nan).dropna()
    times = path_df["base_date_time"].dropna()
    
    # If this path has no valid coordinates left, skip it safely
    if lons.empty or lats.empty or times.empty:
        print(f"⚠️ Skipping Path {pid}: No valid coordinate or time data found.")
        continue

    # Calculate a clean, valid bounding box
    bbox = [lons.min(), lats.min(), lons.max(), lats.max()]
    
    # DYNAMIC DATETIME FIX: Format time window based on actual ship path times
    # Expands window by a few hours on either side to be safe
    min_time = (times.min() - pd.Timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    max_time = (times.max() + pd.Timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    time_string = f"{min_time}/{max_time}"
    
    print(f"🌐 Querying AWS for Ship Path ID: {pid} (Time window: {time_string})...")
    url = "https://earth-search.aws.element84.com/v1/search"
    payload = {
        "collections": ["landsat-c2-l2", "sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": time_string,  # Now dynamically tied to the ship track!
        "limit": 100,             # Increased from 10 to protect against missing frames
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

landsat_features = []
sentinel_features = []
unique_ids = set()

unique_scenes = {scene['id']: scene for scene in all_scenes}.values()

for scene in unique_scenes:
    geometry = scene.get("geometry", {})
    properties = scene.get("properties", {})
    if not geometry or "coordinates" not in geometry:
        continue

    sat_polygon = Polygon(geometry["coordinates"][0])
    sat_time = pd.to_datetime(properties.get("datetime")).replace(tzinfo=None)
    scene_id = scene.get("id")

    sat_prefix = scene_id.split("_")[0].lower()
    if sat_prefix.startswith("l"):
        sat_type = "landsat"
    elif sat_prefix.startswith("s"):
        sat_type = "sentinel"
    else:
        collection = scene.get("collection", "").lower()
        if "landsat" in collection:
            sat_type = "landsat"
        elif "sentinel" in collection:
            sat_type = "sentinel"
        else:
            sat_type = "other"

    if scene_id not in unique_ids:
        unique_ids.add(scene_id)
        feature_node = {
            "type": "Feature",
            "id": scene_id,
            "geometry": geometry,
            "properties": {
                "satellite": sat_type.upper(),
                "datetime": properties.get("datetime")
            }
        }
        
        if sat_type == "landsat":
            landsat_features.append(feature_node)
        elif sat_type == "sentinel":
            sentinel_features.append(feature_node)

    for index, row in df.iterrows():
        ship_point = Point(row["longitude"], row["latitude"])

        if sat_polygon.contains(ship_point):
            match_records.append({
                "sno": row["sno"],
                "path_id": row["path_id"],
                "ship_time": row["base_date_time"],
                "satellite_id": scene_id,
                "satellite_time": sat_time,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "cloud_cover": properties.get("eo:cloud_cover", 0),
            })
            intersections_found += 1

# ==========================================
# 4. EXPORT ALL INDIVIDUAL REPOS
# ==========================================
print("\n================== REPORT ==================")
if intersections_found > 0:
    results_df = pd.DataFrame(match_records).drop_duplicates()
    
    csv_output_path = "D:/hdj/mda/path_verified_intersections.csv"
    results_df.to_csv(csv_output_path, index=False)
    print(f"💾 CSV Data Saved to: {csv_output_path}")
    
    landsat_output_path = "D:/hdj/mda/satellite_frames_landsat.geojson"
    landsat_geojson = {"type": "FeatureCollection", "features": landsat_features}
    with open(landsat_output_path, "w") as f:
        json.dump(landsat_geojson, f)
    print(f"🌍 Landsat GeoJSON Saved to: {landsat_output_path} ({len(landsat_features)} frames)")
        
    sentinel_output_path = "D:/hdj/mda/satellite_frames_sentinel.geojson"
    sentinel_geojson = {"type": "FeatureCollection", "features": sentinel_features}
    with open(sentinel_output_path, "w") as f:
        json.dump(sentinel_geojson, f)
    print(f"🌍 Sentinel GeoJSON Saved to: {sentinel_output_path} ({len(sentinel_features)} frames)")
        
    print(f"\n🎉 SUCCESS! Found {len(results_df)} unique verified intersections!")
    print("\nPreview of matches:")
    print(results_df[["sno", "path_id", "satellite_id"]].head())
else:
    print("❌ Zero matches found using the path_id pipeline approach.")
print("============================================")