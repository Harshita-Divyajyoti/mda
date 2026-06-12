import os
import json
from turtle import pd
import requests
import urllib3
from datetime import datetime, timedelta
import pandas as pd
from shapely.geometry import shape, mapping

# Suppress corporate network SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# INPUT_GEOJSON_PATH = r"D:\hdj\mda\data\ship_capture_frame_long.geojson"
INPUT_GEOJSON_PATH = r"D:\hdj\mda\data\frame10_2b.geojson"
VERIFIED_OUTPUT_PATH = r"D:\hdj\mda\data\verifycapture10_2b.geojson"
STAC_URL = "https://earth-search.aws.element84.com/v1/search"

print("📖 Step 1: Loading simulated map geometry layer dynamically...")
try:
    with open(INPUT_GEOJSON_PATH, "r") as f:
        geojson_data = json.load(f)
    
    feature = geojson_data["features"][0]
    sim_time_str = feature["properties"]["simulated_utc"]
    
    sim_polygon = shape(feature["geometry"])
    bbox = list(sim_polygon.bounds)
    
    print(f"🎯 Layer Imported! Raw Input Clock Time: {sim_time_str}")

except Exception as e:
    print(f"❌ Failed to parse input GeoJSON layer: {e}")
    exit()

print("\n📡 Step 2: Querying live AWS STAC API Registry & Calculating IoU...")

try:
    # 1. Parse the incoming time string directly as standard True UTC
    # dt_utc = datetime.strptime(sim_time_str, "%Y-%m-%d %H:%M:%S")
    # Replace your current datetime.strptime line with this:
    dt_utc = pd.to_datetime(sim_time_str).to_pydatetime()
    print(f"🌍 Timeline Anchor: Using Native {dt_utc} UTC (No local timezone shift required)")

# 2. Create a stable 15-minute search window around the true UTC time
    start_window = (dt_utc - timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_window = (dt_utc + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    print(f"⏱️ Strict Pass Window (UTC Search): {start_window} / {end_window}\n")

    # FIX 1: Pass both collections together in a single key list
    payload = {
        "collections": ["sentinel-2-l2a", "sentinel-1-grd"],
        "bbox": bbox,
        "datetime": f"{start_window}/{end_window}",
        "limit": 20
    }

    response = requests.post(STAC_URL, json=payload, verify=False, timeout=15)
    
    if response.status_code == 200:
        stac_results = response.json()
        features = stac_results.get("features", [])
        
        if not features:
            print("⚠️ AWS Search complete: 0 physical satellite images match this window.")
            print("💡 Check: If tracking at night, Sentinel-2 will be empty. Ensure Sentinel-1 has an exact orbit pass scheduled.")
        else:
            print(f"🔍 Analyzing {len(features)} intersecting grid tiles:")
            print("=" * 85)
            
            verified_features_list = []

            for scene in features:
                properties = scene["properties"]
                scene_id = scene.get("id")
                assets = scene.get("assets", {})
                
                real_poly = shape(scene.get("geometry"))
                
                intersection_area = sim_polygon.intersection(real_poly).area
                union_area = sim_polygon.union(real_poly).area
                iou_score = intersection_area / union_area if union_area > 0 else 0
                
                # FIX 2: Safe fallback handling for Sentinel-1 missing MGRS properties
                if "mgrs:utm_zone" in properties:
                    tile_id = (str(properties.get("mgrs:utm_zone", "")) + 
                               str(properties.get("mgrs:latitude_band", "")) + 
                               str(properties.get("mgrs:grid_square", "")))
                    tile_label = f"T{tile_id}"
                else:
                    # Fallback to the platform sensor name / orbit ID for SAR tracks
                    tile_label = properties.get("sat:relative_orbit", f"SAR-Orbit-{scene_id[-4:]}")

                tile_feature = {
                    "type": "Feature",
                    "id": scene_id,
                    "geometry": scene.get("geometry"),
                    "properties": {
                        "simulated_utc": sim_time_str,
                        "actual_aws_utc": properties.get("datetime"),
                        "tile_id": tile_label,
                        "cloud_cover_pct": round(properties.get("eo:cloud_cover", 0), 2) if properties.get("eo:cloud_cover") is not None else 0.0,
                        "spatial_iou": round(iou_score, 4),
                        "image_url": assets.get("visual", {}).get("href") or assets.get("rendered_preview", {}).get("href") or assets.get("preview", {}).get("href")
                    }
                }
                
                verified_features_list.append(tile_feature)
                
                print(f"📡 Track/Tile: {tile_label:<12} | Spatial IoU: {iou_score * 100:6.2f}% | Platform: {properties.get('platform', 'Unknown')}")
                print(f"🔗 URL: {tile_feature['properties']['image_url']}\n" + "-" * 85)

            output_collection = {
                "type": "FeatureCollection",
                "features": verified_features_list
            }
            
            os.makedirs(os.path.dirname(VERIFIED_OUTPUT_PATH), exist_ok=True)
            with open(VERIFIED_OUTPUT_PATH, "w") as out_file:
                json.dump(output_collection, out_file, indent=4)
            
            print(f"\n💾 SUCCESS: Cleaned tiles exported to:\n   {VERIFIED_OUTPUT_PATH}")
    else:
        print(f"❌ AWS Server rejected request with status code: {response.status_code}")

except Exception as e:
    print(f"❌ Processing breakdown: {e}")