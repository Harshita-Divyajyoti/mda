import os
import pandas as pd
from tqdm import tqdm

# Configuration
AIS_FOLDER = r"D:\hdj\mda\5dayship"
TARGET_MMSI = 338492683
OUTPUT_CSV = r"D:\hdj\mda\data\isolated_target_ship.csv"

# Ensure output directory exists
os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

# List all CSV files in the folder
csv_files = [f for f in os.listdir(AIS_FOLDER) if f.endswith('.csv')]
print(f"📋 Found {len(csv_files)} AIS CSV files to process.")

all_vessel_tracks = []

for file_name in csv_files:
    file_path = os.path.join(AIS_FOLDER, file_name)
    print(f"\n⚡ Scanning {file_name} for MMSI {TARGET_MMSI}...")
    
    chunk_size = 100000
    try:
        sample = pd.read_csv(file_path, nrows=5)
        mmsi_col = [col for col in sample.columns if 'mmsi' in col.lower() or 'id' in col.lower()]
        
        if not mmsi_col:
            print(f"❌ Could not find an ID/MMSI column in {file_name}. Skipping.")
            continue
            
        actual_mmsi_col = mmsi_col[0]
        
        for chunk in pd.read_csv(file_path, chunksize=chunk_size, low_memory=False):
            # Filtering for our synthetic ship identifier
            matched_rows = chunk[chunk[actual_mmsi_col] == TARGET_MMSI]
            if not matched_rows.empty:
                all_vessel_tracks.append(matched_rows)
                
    except Exception as e:
        print(f"⚠️ Error processing file {file_name}: {e}")

# Save the unified track
if all_vessel_tracks:
    final_df = pd.concat(all_vessel_tracks, ignore_index=True)
    
    time_col = [col for col in final_df.columns if 'time' in col.lower() or 'date' in col.lower()]
    if time_col:
        final_df = final_df.sort_values(by=time_col[0])
        
    final_df.to_csv(OUTPUT_CSV, index=False)
    print("\n================== EXTRACTION REPORT ==================")
    print(f"🎉 SUCCESS! Extracted {len(final_df)} data points for synthetic ship {TARGET_MMSI}.")
    print(f"💾 Combined 5-day path saved to: {OUTPUT_CSV}")
    print("=======================================================")
else:
    print(f"\n❌ Finished scanning. No data points found for MMSI {TARGET_MMSI}.")