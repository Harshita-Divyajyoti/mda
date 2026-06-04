from datetime import datetime, timedelta
import json
import pandas as pd
import requests
from tqdm import tqdm

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🔄 Loading 5-day propagated track data...")
df_path = pd.read_csv("data/propagated_satellite_pathJune.csv")

print("🔍 Scanning coordinates for ALL active land-facing scenes...")
stac_url = "https://earth-search.aws.element84.com/v1/search"

# This list will hold our map features for QGIS
geojson_features = []
matched_records = []

# Step through the track jumping 15 minutes at a time
for idx in tqdm(range(1500, len(df_path), 15), desc="Scanning Archive"):
    row = df_path.iloc[idx]
    sim_time = row["timestamp_utc"]
    sim_lon = float(row["longitude"])
    sim_lat = float(row["latitude"])
    
    if sim_lat < -55 or sim_lat > 75:
        continue
        
    bbox = [sim_lon - 0.5, sim_lat - 0.5, sim_lon + 0.5, sim_lat + 0.5]
    dt_obj = datetime.strptime(sim_time, "%Y-%m-%d %H:%M:%S")
    min_time = (dt_obj - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    max_time = (dt_obj + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{min_time}/{max_time}",
        "limit": 1
    }
    
    try:
        response = requests.post(stac_url, json=payload, headers={"Content-Type": "application/json"}, verify=False, timeout=5)
        if response.status_code == 200:
            stac_data = response.json()
            features = stac_data.get("features", [])
            
            if features:
                scene = features[0]
                scene_id = scene.get("id")
                
                # Prevent adding duplicate scenes if the satellite hovers near one
                if scene_id not in [m["scene_id"] for m in matched_records]:
                    matched_records.append({
                        "scene_id": scene_id,
                        "time": sim_time,
                        "lon": sim_lon,
                        "lat": sim_lat
                    })
                    
                    # Create a GeoJSON polygon feature for QGIS mapping
                    feature_node = {
                        "type": "Feature",
                        "id": scene_id,
                        "geometry": scene.get("geometry"),  # This is the real 100x100km square boundary!
                        "properties": {
                            "scene_id": scene_id,
                            "simulated_utc": sim_time,
                            "cloud_cover": scene["properties"].get("eo:cloud_cover", 0)
                        }
                    }
                    geojson_features.append(feature_node)
    except Exception:
        continue

# Save the map layers
print("\n================== EXPORT REPORT ==================")
if geojson_features:
    output_geojson_path = "data/verified_satellite_scenes.geojson"
    geojson_wrapper = {
        "type": "FeatureCollection",
        "features": geojson_features
    }
    
    with open(output_geojson_path, "w") as f:
        json.dump(geojson_wrapper, f)
        
    print(f"🎉 SUCCESS! Found {len(matched_records)} unique verified image scenes across the timeline.")
    print(f"💾 Map data saved cleanly to: {output_geojson_path}")
    print("\nTop matched frames:")
    for m in matched_records[:5]:
        print(f"   - {m['time']} -> Scene: {m['scene_id']}")
else:
    print("❌ No scenes collected. Double check your file tracks.")
print("===================================================")