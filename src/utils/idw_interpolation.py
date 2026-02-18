import numpy as np
import pandas as pd
from typing import Dict, Iterable, Optional


def bilinear_interpolate(df: pd.DataFrame,
                         lat: float,
                         lon: float,
                         value_columns: Iterable[str],
                         lat_col: str = "Enlem",
                         lon_col: str = "Boylam") -> Dict[str, Optional[float]]:
    """
    Sadece ve sadece 4 grid kosesi de mevcutsa Bilineer Enterpolasyon yapar.
    Aksi takdirde (kiyi seridi, eksik veri) None doner.
    """
    results = {col: None for col in value_columns}
    tolerance = 1e-5

    lat_unique = np.sort(df[lat_col].unique())
    lon_unique = np.sort(df[lon_col].unique())

    i = np.searchsorted(lat_unique, lat)
    j = np.searchsorted(lon_unique, lon)

    if i == 0 or i >= len(lat_unique) or j == 0 or j >= len(lon_unique):
        return results

    lat1, lat2 = lat_unique[i - 1], lat_unique[i]
    lon1, lon2 = lon_unique[j - 1], lon_unique[j]

    corners = []
    try:
        for c_lat in (lat1, lat2):
            for c_lon in (lon1, lon2):
                mask = (np.abs(df[lat_col] - c_lat) < tolerance) & (
                    np.abs(df[lon_col] - c_lon) < tolerance
                )
                if not mask.any():
                    return results
                corners.append(df.loc[mask].iloc[0])
    except Exception:
        return results

    q11, q12, q21, q22 = corners[0], corners[1], corners[2], corners[3]

    x_norm = (lon - lon1) / (lon2 - lon1)
    y_norm = (lat - lat1) / (lat2 - lat1)

    for col in value_columns:
        try:
            v11 = float(q11[col])
            v12 = float(q12[col])
            v21 = float(q21[col])
            v22 = float(q22[col])

            val = (v11 * (1 - x_norm) * (1 - y_norm) +
                   v12 * x_norm * (1 - y_norm) +
                   v21 * (1 - x_norm) * y_norm +
                   v22 * x_norm * y_norm)
            results[col] = val
        except Exception:
            results[col] = None

    return results
