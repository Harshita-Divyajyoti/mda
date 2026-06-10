import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from sgp4.api import Satrec, jday, WGS84
from tqdm import tqdm

# ==========================================
# 1. CORE COORDINATE MATH ENGINES
# ==========================================

def ecef_to_llh(r_ecef):
    """Converts ECEF Cartesian meters to Geodetic LLH coordinates."""
    x, y, z = r_ecef
    a = 6378137.0          # WGS84 Semi-major axis
    f = 1 / 298.257223563  # WGS84 Flattening factor
    
    lon = np.arctan2(y, x)
    p = np.sqrt(x**2 + y**2)
    lat = np.arctan2(z, p * (1 - f))
    
    for _ in range(10):
        N = a / np.sqrt(1 - (f * (2 - f)) * np.sin(lat)**2)
        lat = np.arctan2(z + N * f * np.sin(lat), p)
        
    alt_km = (p / np.cos(lat) - N) / 1000.0
    return np.degrees(lat), np.degrees(lon), alt_km

def gmst_from_jd(jd):
    """Calculates Greenwich Mean Sidereal Time in Radians."""
    T = (jd - 2451545.0) / 36525.0
    GMST = (280.46061837 + 360.98564736629 * (jd - 2451545.0) +
            T**2 * (0.000387933 - T / 38710000.0)) % 360.0
    return np.deg2rad(GMST)

# ==========================================
# 2. SATELLITE INITIALIZATION CONSTRUCTORS
# ==========================================

def init_from_tle(line1, line2):
    """Initializes Satrec directly via standard Two-Line Element strings."""
    return Satrec.twoline2rv(line1.strip(), line2.strip())

def init_from_omm(data):
    """Initializes Satrec via native OMM properties with exact radian/time conversions."""
    # Convert angular measurements: Degrees to Radians
    inclo = np.deg2rad(data['INCLINATION'])
    nodeo = np.deg2rad(data['RA_OF_ASC_NODE'])
    argpo = np.deg2rad(data['ARG_OF_PERICENTER'])
    mo = np.deg2rad(data['MEAN_ANOMALY'])
    
    # Standardize time variables: Revolutions/Day to Radians/Minute units
    no_kozai = (data['MEAN_MOTION'] * 2 * np.pi) / 1440.0
    ndot = (data['MEAN_MOTION_DOT'] * 2 * np.pi) / (1440.0 ** 2)
    nddot = 0.0
    
    # Generate True Julian Day values directly matching the structural Epoch timestamp
    epoch_dt = datetime.fromisoformat(data['EPOCH'].replace('Z', '+00:00')).astimezone(timezone.utc)
    jd_epoch, fr_epoch = jday(epoch_dt.year, epoch_dt.month, epoch_dt.day, 
                              epoch_dt.hour, epoch_dt.minute, epoch_dt.second + epoch_dt.microsecond/1e6)
    
    satellite = Satrec()
    satellite.sgp4init(
        WGS84, 'i', data['NORAD_CAT_ID'], (jd_epoch + fr_epoch) - 2433281.5, 
        data['BSTAR'], ndot, nddot, data['ECCENTRICITY'], argpo, inclo, mo, no_kozai, nodeo
    )
    return satellite

# ==========================================
# 3. COMMON TRACK PROPAGATION ENGINE
# ==========================================

def run_propagation(sat_record, start_time, end_time, step_seconds=60):
    """
    Generates a uniform tracking sequence across any time envelope.
    Accepts customized sample rate intervals (e.g., 2s, 30s, 60s).
    """
    path_points = []
    # Flush timing bounds cleanly down to structural second boundaries
    current_time = start_time.replace(microsecond=0)
    final_time = end_time.replace(microsecond=0)
    
    total_steps = int((final_time - current_time).total_seconds() / step_seconds) + 1
    
    with tqdm(total=total_steps, desc="🛰️ Propagating Track Orbit") as pbar:
        while current_time <= final_time:
            jd, fr = jday(current_time.year, current_time.month, current_time.day, 
                          current_time.hour, current_time.minute, current_time.second)
            
            error_code, r_eci, v_eci = sat_record.sgp4(jd, fr)
            
            if error_code == 0:
                gmst = gmst_from_jd(jd + fr)
                rotation_matrix = np.array([
                    [np.cos(gmst), np.sin(gmst), 0],
                    [-np.sin(gmst), np.cos(gmst), 0],
                    [0, 0, 1]
                ])
                
                # Transform to meters and convert coordinate spaces
                r_ecef = rotation_matrix @ np.array(r_eci) * 1000.0
                lat, lon, alt = ecef_to_llh(r_ecef)
                
                # Enforce standard GIS coordinate boundaries (-180 to +180)
                if lon > 180: lon -= 360
                elif lon < -180: lon += 360
                
                path_points.append({
                    "timestamp_utc": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "latitude": lat,
                    "longitude": lon,
                    "altitude_km": alt
                })
                
            current_time += timedelta(seconds=step_seconds)
            pbar.update(1)
            
    return pd.DataFrame(path_points)

# ==========================================
# 4. CONFIGURATION EXECUTIVE MODES
# ==========================================

if __name__ == '__main__':
    os.makedirs("data", exist_ok=True)
    
    print("🔵 Running AFR-1 12-Hour Synchronized TLE Matrix...")
    
    # 1. Use the direct raw TLE format to eliminate OMM floating-point math errors
    line1 = "1 56964U 23084AJ  26161.22765219  .00004112  00000-0  15094-3 0  9997"
    line2 = "2 56964  97.6260 297.7521 0010593  11.8097 348.3389 15.28496820166162"
    
    sat_object = init_from_tle(line1, line2)
    
    # 2. MATCH THE EXACT TIME INHERENT IN THE TLE Snap-shot (Including microseconds!)
    # Day fraction 0.22765219 translates precisely to 05:27:49 and 149222 microseconds
    start = datetime(2026, 6, 10, 5, 27, 49, 149222, tzinfo=timezone.utc)
    
    # 3. Project the requested 12-hour corridor
    end = start + timedelta(hours=12)
    output_file = "data/afr12_path.csv"
    interval_seconds = 60
    
    # --- Execute and Save ---
    df_result = run_propagation(sat_object, start, end, step_seconds=interval_seconds)
    df_result.to_csv(output_file, index=False)
    print(f"💾 Calculations successfully compiled and exported to 👉 {output_file}\n")