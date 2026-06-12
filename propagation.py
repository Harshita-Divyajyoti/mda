
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



# tle1= "1 39634U 14016A   25210.12189729  .00000090  00000+0  28832-4 0  9991"
# tle2= "2 39634  98.1801 217.3353 0001371  89.3809 270.7548 14.59199222602934"

tle1="1 56964U 23084AJ  25177.06026622  .00003125  00000+0  13143-3 0  9998"
tle2="2 56964  97.5829 302.5014 0012488 145.0958 215.1100 15.24110342112908"

start_time = datetime(2025, 6, 26, 17, 00, 00)
end_time = datetime(2025, 6, 26, 17, 10, 0)
csv_file = "data/afr1_26jun25.csv"

step_seconds = 1



propagate_tle_to_csv(
    tle_line1=tle1,
    tle_line2=tle2,
    start_time=start_time,
    end_time=end_time,
    step_seconds=step_seconds,
    csv_filename=csv_file
)