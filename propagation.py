from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
from skyfield.api import EarthSatellite, load, wgs84
from tqdm import tqdm  # Imported tqdm for the progress bar

# Disable the annoying SSL warnings in your terminal console
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# STEP 1: FETCH RAW ORBITAL DATA (TLE) WITH SSL BYPASS
# ==========================================
norad_id = 40697 #sentinel2a

print(f"📡 Downloading current TLE data for NORAD ID {norad_id}...")
tle_url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad_id}&FORMAT=TLE"

# FIX: Added verify=False to bypass the self-signed certificate error
raw_tle = requests.get(tle_url, verify=False).text.strip().split('\n')

if len(raw_tle) < 3:
    raise ValueError("Could not fetch a valid TLE frame from Celestrak.")

line0 = raw_tle[0].strip() # Satellite Name
line1 = raw_tle[1].strip() # TLE Line 1
line2 = raw_tle[2].strip() # TLE Line 2

# ==========================================
# STEP 2: INITIALIZE ENVIRONMENT WITH SSL BYPASS
# ==========================================
# FIX: Skyfield automatically attempts to download files over HTTPS.
# We explicitly tell its built-in downloader to ignore SSL verification drops too.
session = requests.Session()
session.verify = False
load.session = session

# Load astronomical timescales (downloads leap second data safely now)
ts = load.timescale()

# Instantiate the satellite object into the SGP4 engine
satellite = EarthSatellite(line1, line2, line0, ts)
print(f"✅ Loaded Satellite: {satellite.name}")
print(f"📅 TLE Data Baseline Epoch: {satellite.epoch.utc_jpl()}")

# ==========================================
# STEP 3: DEFINE THE PROPAGATION WINDOW
# ==========================================
start_time = datetime.now(timezone.utc)
duration_hours = 240
time_step_minutes = 1

path_points = []

print(f"⚡ Propagating orbit forward for {duration_hours} hours...")
current_time = start_time
end_time = start_time + timedelta(hours=duration_hours)

# Calculate total iterations for tqdm to display a proper percentage bar
total_steps = int((duration_hours * 60) / time_step_minutes) + 1

# Initialize tqdm progress bar
with tqdm(total=total_steps, desc="Orbit Propagation", unit="step") as pbar:
    while current_time <= end_time:
        skyfield_time = ts.from_datetime(current_time)
        geocentric_position = satellite.at(skyfield_time)
        subpoint = wgs84.subpoint(geocentric_position)
        
        path_points.append({
            "timestamp_utc": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "latitude": subpoint.latitude.degrees,
            "longitude": subpoint.longitude.degrees,
            "altitude_km": subpoint.elevation.km
        })
        
        current_time += timedelta(minutes=time_step_minutes)
        pbar.update(1) # Move progress bar forward by 1 step

# ==========================================
# STEP 4: OUTPUT GROUND TRACK PATH
# ==========================================
df_path = pd.DataFrame(path_points)
print("\n🌍 Generated Ground Track Path Preview:")
print(df_path.head(10))

# Note: Sent directly to your data/ directory to keep things organized!
df_path.to_csv("data/propagated_satellite_path240.csv", index=False)
print("\n💾 Path data exported cleanly to 'data/propagated_satellite_path240.csv'")