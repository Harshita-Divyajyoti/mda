# import os
# import pandas as pd
# import numpy as np

# # Configuration
# AIS_FOLDER = r"D:\hdj\mda\data\5dayship"
# OUTPUT_POINTS_CSV = r"D:\hdj\mda\data\longest_pathpoints_2ndpath.csv"

# def haversine_distance(lat1, lon1, lat2, lon2):
#     """Calculate the great-circle distance between two points on Earth in km."""
#     R = 6371.0  # Earth's radius in km
#     phi1, phi2 = np.radians(lat1), np.radians(lat2)
#     delta_phi = np.radians(lat2 - lat1)
#     delta_lambda = np.radians(lon2 - lon1)
    
#     a = np.sin(delta_phi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(delta_lambda / 2.0)**2
#     c = 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))
#     return R * c

# # Step 1: Scan and group raw data points per vessel
# csv_files = sorted([f for f in os.listdir(AIS_FOLDER) if f.endswith('.csv')])
# print(f"📋 Found {len(csv_files)} files. Extracting raw vessel coordinates...")

# ship_tracks = {}

# for file_name in csv_files:
#     file_path = os.path.join(AIS_FOLDER, file_name)
#     print(f"⚡ Processing: {file_name}...")
    
#     # Process in chunks to keep memory clean
#     for chunk in pd.read_csv(file_path, chunksize=150000, low_memory=False):
#         chunk.columns = [c.lower() for c in chunk.columns]
        
#         mmsi_col = [c for c in chunk.columns if 'mmsi' in c or 'id' in c][0]
#         lat_col = [c for c in chunk.columns if 'lat' in c][0]
#         lon_col = [c for c in chunk.columns if 'lon' in c or 'lng' in c][0]
#         time_col = [c for c in chunk.columns if 'time' in c or 'date' in c][0]
        
#         chunk = chunk.dropna(subset=[mmsi_col, lat_col, lon_col, time_col])
        
#         for mmsi, group in chunk.groupby(mmsi_col):
#             mmsi = int(mmsi)
#             # Store timestamp, latitude, and longitude
#             points = list(zip(group[time_col], group[lat_col], group[lon_col]))
            
#             if mmsi not in ship_tracks:
#                 ship_tracks[mmsi] = []
#             ship_tracks[mmsi].extend(points)

# print(f"\n📐 Aggregation complete. Analyzing journeys for {len(ship_tracks)} unique vessels...")

# # Step 2: Calculate cumulative distances and sort chronologically
# vessel_rankings = []

# for mmsi, tracking_data in ship_tracks.items():
#     # Sort points chronologically right here based on their true time string
#     tracking_data.sort(key=lambda x: x[0])
    
#     total_distance = 0.0
#     clean_points_list = []
    
#     for i in range(len(tracking_data)):
#         t_str, lat, lon = tracking_data[i]
#         clean_points_list.append({
#             'timestamp_utc': t_str,
#             'latitude': lat,
#             'longitude': lon,
#             'mmsi': mmsi
#         })
        
#         if i > 0:
#             dist = haversine_distance(tracking_data[i-1][1], tracking_data[i-1][2], lat, lon)
#             # Ignore massive telemetry GPS glitches (>100km jumps within consecutive pings)
#             if dist < 100.0:
#                 total_distance += dist
                
#     # Filter out stationary buoys or ships with fewer than 10 pings
#     if len(clean_points_list) >= 10:
#         vessel_rankings.append({
#             'mmsi': mmsi,
#             'distance_km': total_distance,
#             'points': clean_points_list
#         })

# # Step 3: Isolate the absolute longest path winner
# # Step 3: Sort all vessels by distance in descending order (Longest -> Shortest)
# vessel_rankings.sort(key=lambda x: x['distance_km'], reverse=True)

# # Make sure we actually have at least 2 unique vessels in our data list
# if len(vessel_rankings) >= 2:
#     second_longest_winner = vessel_rankings[1]  # Index 0 is 1st, Index 1 is 2nd!
# else:
#     print("⚠️ Warning: Less than 2 vessels found in dataset. Defaulting to 1st place.")
#     second_longest_winner = vessel_rankings[0]

# # Step 4: Write clean individual points directly to your destination path
# print(f"\n 2nd Longest Path ")
# print(f"   • MMSI: {second_longest_winner['mmsi']}")
# print(f"   • Total Trajectory Length: {round(second_longest_winner['distance_km'], 2)} KM")

# df_output = pd.DataFrame(second_longest_winner['points'])
# df_output['rank'] = 2  # Now this label matches the actual data!

# # # Step 4: Write clean individual points directly to your destination path
# # print(f"\n🏆 Longest Path Identified!")
# # print(f"   • MMSI: {longest_path_winner['mmsi']}")
# # print(f"   • Total Trajectory Length: {round(longest_path_winner['distance_km'], 2)} KM")

# # df_output = pd.DataFrame(longest_path_winner['points'])
# # df_output['rank'] = 2  # Keeping your rank key label active

# os.makedirs(os.path.dirname(OUTPUT_POINTS_CSV), exist_ok=True)
# df_output.to_csv(OUTPUT_POINTS_CSV, index=False)

# print("=======================================================")
# print(f"🎉 SUCCESS! Clean point rows saved to:\n   {OUTPUT_POINTS_CSV}")
# print("=======================================================")



import os
import csv
import pandas as pd
import numpy as np

# Configuration
AIS_FOLDER = r"D:\hdj\mda\data\5dayship"
OUTPUT_FOLDER = r"D:\hdj\mda\data\next_10_ships"

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
            points = list(zip(group[time_col], group[lat_col], group[lon_col]))
            
            if mmsi not in ship_tracks:
                ship_tracks[mmsi] = []
            ship_tracks[mmsi].extend(points)

print(f"\n📐 Aggregation complete. Analyzing journeys for {len(ship_tracks)} unique vessels...")

# Step 2: Calculate cumulative distances and sort chronologically
vessel_rankings = []

for mmsi, tracking_data in ship_tracks.items():
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
            if dist < 100.0:  # Skip tracking telemetry anomalies
                total_distance += dist
                
    if len(clean_points_list) >= 10:
        vessel_rankings.append({
            'mmsi': mmsi,
            'distance_km': total_distance,
            'points': clean_points_list
        })

# Step 3: Sort descending and isolate ranks #3 through #12
vessel_rankings.sort(key=lambda x: x['distance_km'], reverse=True)

# Index 2 is the 3rd longest path (Rank 3)
next_10_ships = vessel_rankings[2:12] 

print(f"\n🎯 Found {len(next_10_ships)} ships within target ranking bounds (Ranks 3-12). Exporting data...")
print("=" * 70)

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Step 4: Iteratively save each path to its own file
for index, ship_data in enumerate(next_10_ships):
    # Current rank calculation (index 0 corresponds to Rank 3)
    current_rank = index + 3
    mmsi = ship_data['mmsi']
    distance = round(ship_data['distance_km'], 2)
    
    filename = f"rank{current_rank}_pathpoints.csv"
    file_save_path = os.path.join(OUTPUT_FOLDER, filename)
    
    # Compile points to DataFrame
    df_output = pd.DataFrame(ship_data['points'])
    df_output['rank'] = current_rank
    
    # Write to disk
    df_output.to_csv(file_save_path, index=False)
    print(f"💾 Rank {current_rank:02d} | MMSI: {mmsi:<10} | Distance: {distance:<8} KM -> Saved to: {filename}")

print("=" * 70)
print(f"🎉 SUCCESS! 10 separate ship tracks are safely stored at:\n👉 {OUTPUT_FOLDER}")