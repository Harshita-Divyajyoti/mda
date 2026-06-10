from datetime import datetime, timedelta
import pandas as pd
from geopy.distance import geodesic
from tqdm import tqdm

# Configuration
# SATELLITE_PATH = r"D:\hdj\mda\data\propagated_satellite_pathJune.csv"
SATELLITE_PATH = r"D:\hdj\mda\data\propagated_satellite_2b.csv"
SHIP_PATH = r"D:\hdj\mda\data\next_10_ships\rank5_pathpoints.csv"
OUTPUT_INTERSECTIONS = r"D:\hdj\mda\data\intersections5_2b.csv"

# Sentinel-2 has a 290 km total swath width. 
# Looking straight down, it sweeps 145 km to the left and 145 km to the right.
SWATH_RADIUS_KM = 145.0 

print("🔄 Loading datasets...")
df_sat = pd.read_csv(SATELLITE_PATH)
df_ship = pd.read_csv(SHIP_PATH)

# Clean up column headers (handles capitalization differences)
df_sat.columns = [c.lower() for c in df_sat.columns]
df_ship.columns = [c.lower() for c in df_ship.columns]

# Find the right column names dynamically
sat_time_col = [c for c in df_sat.columns if 'time' in c][0]
ship_time_col = [c for c in df_ship.columns if 'time' in c or 'date' in c][0]

# Standardize times to datetime objects for accurate 1-to-1 matching
df_sat['dt'] = pd.to_datetime(df_sat[sat_time_col])
df_ship['dt'] = pd.to_datetime(df_ship[ship_time_col])

# Truncate seconds to match points on the exact same minute
df_sat['match_minute'] = df_sat['dt'].dt.strftime('%Y-%m-%d %H:%M')
df_ship['match_minute'] = df_ship['dt'].dt.strftime('%Y-%m-%d %H:%M')

print("🔍 Analyzing timeline for spatial intersections...")
intersections = []

# Group ship data by minute for fast dictionary lookups
ship_dict = {row['match_minute']: row for _, row in df_ship.iterrows()}

# Scan the satellite path minute-by-minute
for _, sat_row in tqdm(df_sat.iterrows(), total=len(df_sat), desc="Checking Matches"):
    minute = sat_row['match_minute']
    
    # Check if the ship has a recorded position at this exact minute
    if minute in ship_dict:
        ship_row = ship_dict[minute]
        
        sat_coords = (sat_row['latitude'], sat_row['longitude'])
        ship_coords = (ship_row['latitude'], ship_row['longitude'])
        
        # Calculate the real-world surface distance between the satellite and the ship
        distance_km = geodesic(sat_coords, ship_coords).km
        
        # If the ship falls inside the 290km camera swath footprint
        if distance_km <= SWATH_RADIUS_KM:
            intersections.append({
                "Timestamp_UTC": minute + ":00",
                "Satellite_Lat": sat_row['latitude'],
                "Satellite_Lon": sat_row['longitude'],
                "Ship_Lat": ship_row['latitude'],
                "Ship_Lon": ship_row['longitude'],
                "Distance_KM": round(distance_km, 2),
                "Status": "Visible inside Swath"
            })

# Save the matched window results
print("\n================== INTERSECTION REPORT ==================")
if intersections:
    df_out = pd.DataFrame(intersections)
    df_out.to_csv(OUTPUT_INTERSECTIONS, index=False)
    print(f"🎉 SUCCESS! Found {len(df_out)} minutes of active window coverage.")
    print(f"💾 Intersecting path timestamps saved to: {OUTPUT_INTERSECTIONS}")
    print("\nFirst 3 matching contact points:")
    print(df_out[['Timestamp_UTC', 'Distance_KM']].head(3).to_string(index=False))
else:
    print("❌ No direct intersection found. The satellite didn't cross this ship during these 5 days.")
print("=========================================================")

