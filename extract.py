import os
import json
import pandas as pd
import numpy as np
from datetime import datetime

# Configuration
AIS_FOLDER = r"D:\hdj\mda\data\5dayship"
OUTPUT_GEOJSON = r"D:\hdj\mda\data\top_3_longest_tracks.geojson"

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth in kilometers."""
    R = 6371.0  # Earth's radius in km
    
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    
    a = np.sin(delta_phi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# Step 1: Collect tracking history for all unique ships
csv_files = sorted([f for f in os.listdir(AIS_FOLDER) if f.endswith('.csv')])
print(f"📋 Found {len(csv_files)} files. Starting global multi-day tracking sweep...")

ship_tracks = {}

for file_name in csv_files:
    file_path = os.path.join(AIS_FOLDER, file_name)
    print(f"⚡ Processing: {file_name}...")
    
    for chunk in pd.read_csv(file_path, chunksize=150000, low_memory=False):
        chunk.columns = [c.lower() for c in chunk.columns]
        
        mmsi_col = [c for c in chunk.columns if 'mmsi' in c or 'id' in c][0]
        lat_col = [c for c in chunk.columns if 'lat' in c][0]
        lon_col = [c for c in chunk.columns if 'lon' in c or 'lng' in c][0]
        time_col = [c for c in chunk.columns if 'time' in c or 'date' in c][0]
        
        # Drop rows with missing tracking coordinates
        chunk = chunk.dropna(subset=[mmsi_col, lat_col, lon_col, time_col])
        
        for mmsi, group in chunk.groupby(mmsi_col):
            mmsi = int(mmsi)
            points = list(zip(group[time_col], group[lat_col], group[lon_col]))
            
            if mmsi not in ship_tracks:
                ship_tracks[mmsi] = []
            ship_tracks[mmsi].extend(points)

print(f"\n📐 Aggregation complete. Found {len(ship_tracks)} unique vessels.")
print("Calculating cumulative voyage lengths...")

# Step 2: Compute chronological distance per ship
ranked_ships = []

for mmsi, tracking_data in ship_tracks.items():
    # Sort history chronologically
    tracking_data.sort(key=lambda x: x[0])
    
    total_distance = 0.0
    valid_coords = []
    
    for i in range(len(tracking_data)):
        current_time, lat, lon = tracking_data[i]
        valid_coords.append([float(lon), float(lat)]) # GeoJSON expects [Lon, Lat]
        
        if i > 0:
            _, prev_lat, prev_lon = tracking_data[i-1]
            dist = haversine_distance(prev_lat, prev_lon, lat, lon)
            # Filter out extreme GPS jumps/teleportation errors (> 100km/min)
            if dist < 100.0:
                total_distance += dist
                
    # Ignore stationary ports/buoys with fewer than 10 movement coordinate logs
    if len(valid_coords) >= 10 and total_distance > 5.0:
        ranked_ships.append({
            'mmsi': mmsi,
            'distance_km': total_distance,
            'coordinates': valid_coords,
            'start_time': tracking_data[0][0],
            'end_time': tracking_data[-1][0]
        })

# Sort to isolate the top 3 highest distance accumulation paths
top_3_ships = sorted(ranked_ships, key=lambda x: x['distance_km'], reverse=True)[:3]

# Step 3: Build a unified multi-track GeoJSON File
geojson_features = []
colors = ["#FF5733", "#33FF57", "#3357FF"] # Distinct visual colors for QGIS styles

print("\n================ RANKING WINNERS ================")
for rank, ship in enumerate(top_3_ships, 1):
    print(f"🥇 Rank {rank}: MMSI {ship['mmsi']} | Total Distance: {round(ship['distance_km'], 2)} KM")
    
    feature = {
        "type": "Feature",
        "id": f"TRACK_RANK_{rank}",
        "geometry": {
            "type": "LineString",
            "coordinates": ship['coordinates']
        },
        "properties": {
            "rank": rank,
            "mmsi": str(ship['mmsi']),
            "total_distance_km": round(ship['distance_km'], 2),
            "voyage_start": ship['start_time'],
            "voyage_end": ship['end_time'],
            "layer_color": colors[rank-1]
        }
    }
    geojson_features.append(feature)

output_geojson = {
    "type": "FeatureCollection",
    "features": geojson_features
}

os.makedirs(os.path.dirname(OUTPUT_GEOJSON), exist_ok=True)
with open(OUTPUT_GEOJSON, "w") as f:
    json.dump(output_geojson, f, indent=4)

print("=======================================================")
print(f"💾 Multi-line GeoJSON layer successfully saved to:\n   {OUTPUT_GEOJSON}")