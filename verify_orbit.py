import os
import json
import requests
import pandas as pd
from tqdm import tqdm
import urllib3

# 🟢 Keep your corporate firewall warning bypass active
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

print("🔄 Loading 5-day propagated track data...")
df_path = pd.read_csv("data/propagated_satellite_pathJune.csv")

stac_url = "https://earth-search.aws.element84.com/v1/search"
geojson_features = []
matched_records = []

print("🔍 Validating Orbit via Direct Point Intersection (No Guesswork BBoxes)...")

# Step through the track jumping 15 minutes at a time
for idx in tqdm(range(1500, len(df_path), 15), desc="Scanning Archive"):
    row = df_path.iloc[idx]
    sim_time = row["timestamp_utc"]
    sim_lon = float(row["longitude"])
    sim_lat = float(row["latitude"])
    
    # 🟢 Your original latitude boundary constraints preserved
    if sim_lat < -55 or sim_lat > 75:
        continue
        
    # ⚡ ARCHITECTURAL UPGRADE: Zero BBox logic. Point-In-Polygon Matching.
    payload = {
        "collections": ["sentinel-2-l2a"],
        "intersects": {
            "type": "Point",
            "coordinates": [sim_lon, sim_lat]
        },
        "datetime": f"{pd.to_datetime(sim_time).strftime('%Y-%m-%dT%H:%M:%SZ')}/{(pd.to_datetime(sim_time) + pd.to_timedelta('15m')).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "limit": 1
    }

    try:
        response = requests.post(stac_url, json=payload, verify=False, timeout=5)
        if response.status_code == 200:
            stac_data = response.json()
            features = stac_data.get("features", [])
            
            if features:
                scene = features[0]
                scene_id = scene.get("id")
                
                if scene_id not in [m["scene_id"] for m in matched_records]:
                    matched_records.append({
                        "scene_id": scene_id,
                        "time": sim_time,
                        "lon": sim_lon,
                        "lat": sim_lat
                    })
                    
                    geojson_features.append({
                        "type": "Feature",
                        "id": scene_id,
                        "geometry": scene.get("geometry"),  # ⚡ Real official ESA footprint boundary!
                        "properties": {
                            "scene_id": scene_id,
                            "simulated_utc": sim_time,
                            "cloud_cover": scene["properties"].get("eo:cloud_cover", 0)
                        }
                    })
    except Exception:
        continue

# Save the map layers
print("\n================== EXPORT REPORT ==================")
if geojson_features:
    output_geojson_path = "data/verified_satellite_scenes_new.geojson"
    os.makedirs(os.path.dirname(output_geojson_path), exist_ok=True)
    with open(output_geojson_path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": geojson_features}, f, indent=4)
    print(f"🎉 SUCCESS! Found {len(matched_records)} unique verified image scenes.")