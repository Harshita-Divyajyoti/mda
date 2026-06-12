from sgp4.api import Satrec
from astropy.time import Time
from astropy.coordinates import TEME, ITRS, CartesianRepresentation
import astropy.units as u
from datetime import datetime, timedelta
import pandas as pd



def propagate_tle_to_csv(
    tle_line1: str,
    tle_line2: str,
    start_time: datetime,
    end_time: datetime,
    step_seconds: int,
    csv_filename: str
):
    """
    Propagate TLE and save ground track to CSV.

    Parameters
    ----------
    tle_line1 : str
    tle_line2 : str
    start_time : datetime (UTC)
    end_time : datetime (UTC)
    step_seconds : int
    csv_filename : str
    """

    sat = Satrec.twoline2rv(tle_line1, tle_line2)

    rows = []

    current_time = start_time

    while current_time <= end_time:

        t = Time(current_time, scale="utc")

        error, r, v = sat.sgp4(t.jd1, t.jd2)

        if error == 0:

            teme = TEME(
                CartesianRepresentation(r * u.km),
                obstime=t
            )

            itrs = teme.transform_to(ITRS(obstime=t))
            loc = itrs.earth_location

            rows.append({
                "timestamp_utc": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                "latitude_deg": loc.lat.deg,
                "longitude_deg": loc.lon.deg,
                "height_km": loc.height.to(u.km).value
            })

        current_time += timedelta(seconds=step_seconds)

    df = pd.DataFrame(rows)
    df.to_csv(csv_filename, index=False)

    print(f"Saved {len(df)} records to {csv_filename}")

    return df
# -------------------------------------------------------
# Example
# -------------------------------------------------------




tle1 = "1 56964U 23084AJ  26161.62044538  .00004039  00000-0  14830-3 0  9990"
tle2 = "2 56964  97.6260 298.1542 0010550  10.4977 349.6480 15.28499881166228"

start_time = datetime(2026, 6, 11, 0, 0, 0)
end_time = datetime(2026, 6, 12, 0, 0, 0)
step_seconds = 60

csv_file = "data/orbit_track_final.csv"

propagate_tle_to_csv(
    tle_line1=tle1,
    tle_line2=tle2,
    start_time=start_time,
    end_time=end_time,
    step_seconds=step_seconds,
    csv_filename=csv_file
)