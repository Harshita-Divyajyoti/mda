import os
import json
import requests
import urllib3  # 🟢 Added to silence SSL warnings in terminal
from datetime import datetime, timedelta
from shapely.geometry import shape

# 🟢 Suppress only the single InsecureRequestWarning from causing clutter
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 📁 Input/Output Configuration (No hardcoded numbers!)
INPUT_GEOJSON_PATH = r"D:\hdj\mda\data\ship_capture_frame_long.geojson"
VERIFIED_OUTPUT_PATH = r"D:\hdj\mda\data\aws_verified_capture.geojson"
STAC_URL = "https://earth-search.aws.element84.com/v1/search"

print("📖 Step 1: Loading simulated map geometry layer dynamically...")
try:
    with open(INPUT_GEOJSON_PATH, "r") as f:
        geojson_data = json.load(f)
    
    # Extract the first feature shape from your layer
    feature = geojson_data["features"][0]
    
    # Unified variable name setup
    sim_time_str = feature["properties"]["simulated_utc"]
    
    # Use Shapely to dynamically compute the true geometric center point
    geom_shape = shape(feature["geometry"])
    center_lon, center_lat = geom_shape.centroid.x, geom_shape.centroid.y
    bbox = list(geom_shape.bounds) # Automatically gets [min_lon, min_lat, max_lon, max_lat]
    
    print(f"🎯 Layer Imported Successfully!")
    print(f"   • Derived BBox: {[round(c, 3) for c in bbox]}")
    print(f"   • Calculated Target Center: ({round(center_lat, 4)}, {round(center_lon, 4)})")
    print(f"   • Simulated Clock Time: {sim_time_str}")

except Exception as e:
    print(f"❌ Failed to parse input GeoJSON layer: {e}")
    exit()

print("\n📡 Step 2: Querying live AWS STAC API Registry...")

try:
    # Convert time string to object to expand your search temporal window dynamically
    dt_obj = datetime.strptime(sim_time_str, "%Y-%m-%d %H:%M:%S")

    # Strategy: Expand window to +/- 6 hours to catch the actual sun-synchronous day pass
    start_window = (dt_obj - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end_window = (dt_obj + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start_window}/{end_window}",
        "limit": 5
    }

    # 🟢 CHANGED: Added verify=False to bypass corporate network certificate checks
    response = requests.post(STAC_URL, json=payload, verify=False, timeout=10)
    
    if response.status_code == 200:
        stac_results = response.json()
        features = stac_results.get("features", [])
        
        if not features:
            print("⚠️ AWS Search complete: 0 physical satellite images match this specific time window.")
            # Fallback output generation using simulated data
            verified_feature = feature
            verified_feature["properties"]["aws_match_status"] = "SIMULATION_ONLY_NO_PASS"
        else:
            print(f"🎉 SUCCESS! Found {len(features)} matching imagery products in AWS Open Data archive.")
            real_scene = features[0] # Grab the closest matching actual scene
            
            # Construct a hybrid feature merging simulated tracking with actual AWS imagery parameters
            verified_feature = {
                "type": "Feature",
                "id": real_scene.get("id"),
                "geometry": real_scene.get("geometry"), # Real 110x110km footprint from AWS
                "properties": {
                    "simulated_utc": sim_time_str,
                    "actual_aws_utc": real_scene["properties"].get("datetime"),
                    "tile_id": str(real_scene["properties"].get("mgrs:utm_zone", "")) + \
                              str(real_scene["properties"].get("mgrs:latitude_band", "")) + \
                              str(real_scene["properties"].get("mgrs:grid_square", "")),
                    "cloud_cover_pct": real_scene["properties"].get("eo:cloud_cover", 0),
                    "aws_match_status": "HISTORICALLY_VERIFIED"
                }
            }
            print(f"   • Real Tile Found: T{verified_feature['properties']['tile_id']}")
            print(f"   • Actual Satellite Shot Time: {verified_feature['properties']['actual_aws_utc']}")
            print(f"   • Verified Cloud Cover: {verified_feature['properties']['cloud_cover_pct']}%")

        # Package into a clean GeoJSON FeatureCollection container
        output_collection = {
            "type": "FeatureCollection",
            "features": [verified_feature]
        }
        
        # Ensure output directory structures exist
        os.makedirs(os.path.dirname(VERIFIED_OUTPUT_PATH), exist_ok=True)
        
        with open(VERIFIED_OUTPUT_PATH, "w") as out_file:
            json.dump(output_collection, out_file, indent=4)
        print(f"\n💾 Verified layer exported cleanly to: {VERIFIED_OUTPUT_PATH}")
    else:
        print(f"❌ AWS Server rejected request with status code: {response.status_code}")

except Exception as e:
    print(f"❌ Connection or processing breakdown: {e}")