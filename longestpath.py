import os
import pandas as pd
import numpy as np

# Configuration
AIS_FOLDER = r"D:\hdj\mda\data\5dayship"
OUTPUT_POINTS_CSV = r"D:\hdj\mda\data\longest_pathpoints.csv"

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on Earth in km."""
    R = 6371.0  # Earth's radius in km
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    delta_phi = np.radians(lat2 - lat1)
    delta_lambda = np.radians(lon2 - lon1)
    
    a = np.sin(delta_phi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0)**2
    c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
    return R * c

# Step 1: Scan and group raw data points per vessel
csv_files = sorted([f for f in os.listdir(AIS_FOLDER) if f.endswith('.csv')])
print(f"📋 Found {len(csv_files)} files. Extracting raw vessel coordinates...")

ship_tracks = {}

for file_name in csv_files:
    file_path = os.path.join(AIS_FOLDER, file_name)
    print(f"⚡ Processing: {file_name}...")
    
    # Process in chunks to keep memory clean
    for chunk in pd.read_csv(file_path, chunksize=150000, low_memory=False):
        chunk.columns = [c.lower() for c in chunk.columns]
        
        mmsi_col = [c for c in chunk.columns if 'mmsi' in c or 'id' in c][0]
        lat_col = [c for c in chunk.columns if 'lat' in c][0]
        lon_col = [c for c in chunk.columns if 'lon' in c or 'lng' in c][0]
        time_col = [c for c in chunk.columns if 'time' in c or 'date' in c][0]
        
        chunk = chunk.dropna(subset=[mmsi_col, lat_col, lon_col, time_col])
        
        for mmsi, group in chunk.groupby(mmsi_col):
            mmsi = int(mmsi)
            # Store timestamp, latitude, and longitude
            points = list(zip(group[time_col], group[lat_col], group[lon_col]))
            
            if mmsi not in ship_tracks:
                ship_tracks[mmsi] = []
            ship_tracks[mmsi].extend(points)

print(f"\n📐 Aggregation complete. Analyzing journeys for {len(ship_tracks)} unique vessels...")

# Step 2: Calculate cumulative distances and sort chronologically
vessel_rankings = []

for mmsi, tracking_data in ship_tracks.items():
    # Sort points chronologically right here based on their true time string
    tracking_data.sort(key=lambda x: x[0])
    
    total_distance = 0.0
    clean_points_list = []
    
    for i in range(len(tracking_data)):
        t_str, lat, lon = tracking_data[i]
        clean_points_list.append({
            'timestamp_utc': t_str,
            'latitude': lat,
            'longitude': lon,
            'mmsi': mmsi
        })
        
        if i > 0:
            dist = haversine_distance(tracking_data[i-1][1], tracking_data[i-1][2], lat, lon)
            # Ignore massive telemetry GPS glitches (>100km jumps within consecutive pings)
            if dist < 100.0:
                total_distance += dist
                
    # Filter out stationary buoys or ships with fewer than 10 pings
    if len(clean_points_list) >= 10:
        vessel_rankings.append({
            'mmsi': mmsi,
            'distance_km': total_distance,
            'points': clean_points_list
        })

# Step 3: Isolate the absolute longest path winner
longest_path_winner = max(vessel_rankings, key=lambda x: x['distance_km'])

# Step 4: Write clean individual points directly to your destination path
print(f"\n🏆 Longest Path Identified!")
print(f"   • MMSI: {longest_path_winner['mmsi']}")
print(f"   • Total Trajectory Length: {round(longest_path_winner['distance_km'], 2)} KM")

df_output = pd.DataFrame(longest_path_winner['points'])
df_output['rank'] = 1  # Keeping your rank key label active

os.makedirs(os.path.dirname(OUTPUT_POINTS_CSV), exist_ok=True)
df_output.to_csv(OUTPUT_POINTS_CSV, index=False)

print("=======================================================")
print(f"🎉 SUCCESS! Clean point rows saved to:\n   {OUTPUT_POINTS_CSV}")
print("=======================================================")