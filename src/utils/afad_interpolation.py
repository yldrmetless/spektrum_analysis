"""
AFAD TDTH verisi ile uyumlu interpolasyon araçları.

Bu modül, AFAD web uygulamasındaki sonuçlarla hizalanmak amacıyla metre
bazında equirectangular mesafe kullanan IDW (Inverse Distance Weighting)
enterpolasyonunu sağlar.
"""

from typing import Dict, Mapping, Optional

import numpy as np

# Dünya yarıçapı (metre)
EARTH_RADIUS_M = 6_371_000.0


def equirectangular_distance_m(
    lat0: float, lon0: float, lat_arr: np.ndarray, lon_arr: np.ndarray
) -> np.ndarray:
    """
    Küçük mesafeler için yeterli hassasiyette metre bazlı equirectangular mesafe.

    Args:
        lat0 (float): Hedef enlem (derece)
        lon0 (float): Hedef boylam (derece)
        lat_arr (np.ndarray): Nokta enlemleri (derece)
        lon_arr (np.ndarray): Nokta boylamları (derece)

    Returns:
        np.ndarray: Metre cinsinden mesafeler
    """
    lat0_rad = np.radians(lat0)
    x = np.radians(lon_arr - lon0) * np.cos(lat0_rad)
    y = np.radians(lat_arr - lat0)
    return EARTH_RADIUS_M * np.sqrt(x * x + y * y)


def interpolate_idw(
    lat: float,
    lon: float,
    coords_latlon: np.ndarray,
    values_dict: Mapping[str, np.ndarray],
    k: int = 8,
    power: float = 2.0,
) -> Dict[str, Optional[float]]:
    """
    AFAD uyumlu IDW enterpolasyonu (metre bazlı mesafe + k=8, p=2).

    Komşu seçimi ve ağırlıklandırma aynı metre metriğiyle yapılır. Her parametre
    için (PGA, Ss, S1, PGV vb.) ayrı ayrı NaN/0 filtrelenir; geçerli verisi
    olmayan parametreler için None döner. Tam çakışma durumunda değer doğrudan
    döndürülür.

    Args:
        lat (float): Hedef enlem (derece)
        lon (float): Hedef boylam (derece)
        coords_latlon (np.ndarray): Nokta koordinatları (N,2) [enlem, boylam]
        values_dict (Mapping[str, np.ndarray]): Parametre adı -> değer dizisi
        k (int, optional): Alınacak komşu sayısı. Varsayılan 8.
        power (float, optional): IDW üssü. Varsayılan 2.0.

    Returns:
        Dict[str, Optional[float]]: Parametre adı -> enterpolasyon sonucu
    """
    coords = np.asarray(coords_latlon, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2:
        raise ValueError("coords_latlon dizisi (N, 2) boyutunda olmalıdır.")

    distances = equirectangular_distance_m(lat, lon, coords[:, 0], coords[:, 1])
    results: Dict[str, Optional[float]] = {}

    for param, values in values_dict.items():
        arr = np.asarray(values, dtype=float)
        if arr.shape[0] != coords.shape[0]:
            raise ValueError(
                f"{param} için değer sayısı koordinatlarla uyuşmuyor: "
                f"{arr.shape[0]} != {coords.shape[0]}"
            )

        valid_mask = np.isfinite(arr) & (arr > 0)
        if not np.any(valid_mask):
            results[param] = None
            continue

        d_valid = distances[valid_mask]
        v_valid = arr[valid_mask]
        if d_valid.size == 0:
            results[param] = None
            continue

        min_idx = int(np.argmin(d_valid))
        if d_valid[min_idx] <= 1e-9:  # Hedefle aynı koordinat
            results[param] = float(v_valid[min_idx])
            continue

        k_eff = min(int(k) if k is not None else 0, v_valid.size)
        if k_eff <= 0:
            results[param] = None
            continue

        nearest_idx = np.argpartition(d_valid, k_eff - 1)[:k_eff]
        d_sel = d_valid[nearest_idx].astype(float)
        v_sel = v_valid[nearest_idx].astype(float)

        p = float(power)
        if p <= 0:
            results[param] = float(np.nanmean(v_sel))
            continue

        with np.errstate(divide="ignore", invalid="ignore"):
            w = 1.0 / (d_sel ** p)

        mask = np.isfinite(w) & np.isfinite(v_sel)
        if not np.any(mask):
            results[param] = None
            continue

        w = w[mask]
        v = v_sel[mask]
        denom = float(w.sum())
        results[param] = float(np.dot(w, v) / denom) if denom != 0.0 else None

    return results


__all__ = ["interpolate_idw", "equirectangular_distance_m", "EARTH_RADIUS_M"]
