# response_spectrum.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import re
import csv
import math
import pathlib
import numpy as np
import matplotlib.pyplot as plt

# Mevcut yardımcılar (birim dönüşümü vb.)
from .earthquake_stats import EarthquakeStats

# Performans için Numba JIT (opsiyonel)
try:
    from numba import jit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Numba yoksa dummy decorator
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def prange(x):
        return range(x)

G = EarthquakeStats.G_STANDARD  # 9.80665 m/s²
# Newmark scheme (Linear Acceleration)
NEWMARK_GAMMA = 0.5
NEWMARK_BETA  = 1.0 / 6.0

# ------------------------ Ayarlar & Sonuç kapsayıcıları ------------------------

@dataclass
class SpectrumSettings:
    damping_list: Iterable[float] = (5.0,)   # % cinsinden
    Tmin: float = 0.01
    Tmax: float = 10.0
    nT: int = 500
    logspace: bool = True
    accel_unit: str = "g"                    # 'g','m/s²','cm/s²','mm/s²'
    baseline: str = "linear"                 # 'none'|'demean'|'linear'|'poly2'|'poly3'
    compute_abs_acc: bool = False            # mutlak ivme spektrumu (opsiyonel)
    compute_true_sv: bool = True             # göreceli hız tepe değeri
    compute_rel_acc: bool = False            # göreceli ivme tepe değeri (opsiyonel)
    enforce_dt_over_T: Optional[float] = None
    # örn. 0.05 -> dt/T <= 0.05 sağlanırsa uyarı yok, aşarsa alt-örnekleme (interpolasyon) opsiyonel

@dataclass
class SpectrumCurves:
    T: np.ndarray               # [s]
    Sd: np.ndarray              # [m]
    Sv_p: np.ndarray            # [m/s]
    Sa_p: np.ndarray            # [m/s²]
    Sa_p_g: np.ndarray          # [g]
    Sa_abs: Optional[np.ndarray] = None  # [m/s²]
    Sv_true: Optional[np.ndarray] = None  # [m/s]
    Sa_rel: Optional[np.ndarray] = None   # [m/s²]

# ------------------------ Kayıt okuma yardımcıları ------------------------

_AT2_DT = re.compile(r"DT\s*=\s*([0-9Ee\.\+\-]+)")
_AT2_NPTS = re.compile(r"NPTS\s*=\s*([0-9]+)")

def read_at2(path: str) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """
    PEER .AT2 dosyasını okur.
    Returns: (time[s], accel[orijinal birimde], dt, accel_unit_guess)
    Not: Başlıktaki birimler (genelde 'g' veya 'cm/s/s') değişebilir.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().strip().splitlines()

    if len(lines) < 5:
        raise ValueError(".AT2 dosyası beklenen başlık yapısında değil (>=5 satır).")

    # 3. satır genelde birimleri barındırır
    header3 = lines[2].upper()
    if "G" in header3 and "UNIT" in header3 or "UNITS" in header3:
        unit_guess = "g"
    elif "CM/S" in header3:
        unit_guess = "cm/s²"
    elif "MM/S" in header3:
        unit_guess = "mm/s²"
    else:
        unit_guess = "g"  # varsayım

    # 4. satırdan NPTS ve DT çek
    header4 = lines[3]
    m_dt = _AT2_DT.search(header4)
    m_np = _AT2_NPTS.search(header4)
    if not (m_dt and m_np):
        # Eski formatlarda bu anahtarlar başka yerde olabilir → tüm başlıkta ara
        hdr = "\n".join(lines[:10])
        m_dt = _AT2_DT.search(hdr)
        m_np = _AT2_NPTS.search(hdr)
    if not (m_dt and m_np):
        raise ValueError(".AT2 başlığında NPTS ve/veya DT bulunamadı.")

    dt = float(m_dt.group(1))
    npts = int(m_np.group(1))

    # Veri: 5. satırdan itibaren, bilimsel gösterimler dahil
    data_str = " ".join(lines[4:])
    data = np.fromstring(data_str.replace("D", "E"), sep=" ")
    if data.size < npts:
        raise ValueError(f".AT2 veri uzunluğu beklenenden kısa: {data.size} < {npts}")
    data = data[:npts]

    time = np.arange(npts, dtype=float) * dt
    return time, data.astype(float), dt, unit_guess

def read_timeseries_auto(path: str, dt_hint: Optional[float] = None
                         ) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """
    Yolu verilen dosyadan zaman–ivme serisini okur (.AT2/.CSV/.TXT)
    CSV/TXT: tek sütun (ivme) veya iki sütun (zaman, ivme).
    """
    p = pathlib.Path(path)
    ext = p.suffix.lower()

    if ext == ".at2":
        return read_at2(str(p))

    # CSV/TXT: genfromtxt ile, sayı olmayan satırları yoksay
    try:
        delim = ',' if ext == '.csv' else None
        arr = np.genfromtxt(str(p), delimiter=delim, dtype=float, autostrip=True)
    except Exception as e:
        raise ValueError(f"Dosya okunamadı: {path} ({e})")

    # np.genfromtxt tek sütunlu dosyalarda 1D dönebilir
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    else:
        arr = np.atleast_2d(arr)
    arr = arr[~np.all(~np.isfinite(arr), axis=1)]  # tamamen NaN satırları at

    if arr.shape[1] == 1:
        if dt_hint is None:
            raise ValueError("Tek sütunlu veri için dt_hint gerekli.")
        accel = arr[:, 0]
        time = np.arange(len(accel), dtype=float) * float(dt_hint)
        unit_guess = "g"
        return time, accel, float(dt_hint), unit_guess

    # İki+ sütun → ilk sütun zaman, ikincisi ivme varsayımı
    # float format yuvarlama farklarını minimize etmek için asıl dosyadan tekrar oku
    try:
        with open(str(p), "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().strip().splitlines()
        cols0, cols1 = [], []
        for line in lines:
            parts = line.strip().split(',') if ext == '.csv' else line.split()
            if len(parts) >= 2:
                cols0.append(float(parts[0]))
                cols1.append(float(parts[1]))
        time = np.asarray(cols0, dtype=float)
        accel = np.asarray(cols1, dtype=float)
    except Exception:
        time = arr[:, 0]
        accel = arr[:, 1]
    # dt: median fark
    finite_time = time[np.isfinite(time)]
    # Tekil zaman değeri durumunda expected dt_hint'e dön
    diffs = np.diff(finite_time)
    if diffs.size == 0:
        if dt_hint is None:
            raise ValueError("Zaman sütunu geçersiz; dt_hint gerekli.")
        dt = float(dt_hint)
    # Hiçbir değişiklik yapmadan ham veriyi döndür (testler birebir eşleşme bekliyor)
    else:
        dt = float(np.median(diffs))
    unit_guess = "g"
    return time, accel, dt, unit_guess

# ------------------------ Sinyal hazırlama ------------------------

def _baseline_correct(acc: np.ndarray, dt: float, method: str) -> np.ndarray:
    """Basit baseline düzeltmeleri (polinom detrend dahil)."""
    if method == "none" or method is None:
        return acc.copy()
    t = np.arange(len(acc)) * dt
    if method == "demean":
        return acc - np.nanmean(acc)
    deg = {"linear": 1, "poly2": 2, "poly3": 3}.get(method, 1)
    coeff = np.polyfit(t, acc, deg)
    trend = np.polyval(coeff, t)
    return acc - trend

def _resample_if_needed(t: np.ndarray, a: np.ndarray, T_min: float,
                        max_dt_over_T: Optional[float]) -> Tuple[np.ndarray, np.ndarray, float, bool]:
    """
    dt/T sınırına göre gerekirse lineer enterpolasyon ile alt-örnekleme yapar.
    Döndürür: (t_new, a_new, dt_new, changed)
    """
    dt = float(np.median(np.diff(t)))
    if not max_dt_over_T:
        return t, a, dt, False
    limit = max_dt_over_T * float(T_min)
    if dt <= limit:
        return t, a, dt, False
    # Daha küçük dt hedefi
    dt_new = limit
    # en yakın daha küçük dt: dt / ceil(dt/dt_new)
    r = math.ceil(dt / dt_new)
    dt_new = dt / r
    t_new = np.arange(0.0, t[-1] + 0.5*dt_new, dt_new)
    a_new = np.interp(t_new, t, a)
    return t_new, a_new, dt_new, True

# ------------------------ Newmark-β çekirdeği ------------------------

@jit(nopython=True, cache=True)
def _newmark_peaks_jit(acc_ms2: np.ndarray, dt: float, omega: float, zeta: float
                      ) -> Tuple[float, float, float, float, float, float]:
    """
    Newmark-β Linear Acceleration (γ = 0.5, β = 1/6) ile tek SDOF için
    tepe değerleri hesaplar. JIT-optimized version.
    Döndürür: (Sd_max, Sv_p_max, Sa_p_max, Sa_abs_max, Sv_true_max, Sa_rel_max)
    """
    beta = NEWMARK_BETA
    gamma = NEWMARK_GAMMA
    c = 2.0 * zeta * omega
    k = omega * omega

    a0 = 1.0 / (beta * dt * dt)
    a1 = gamma / (beta * dt)
    a2 = 1.0 / (beta * dt)
    a3 = 1.0 / (2.0 * beta) - 1.0
    a4 = gamma / beta - 1.0
    a5 = dt * (gamma / (2.0 * beta) - 1.0)
    k_hat = k + a0 + c * a1

    u = 0.0
    v = 0.0
    a_rel = -acc_ms2[0]

    Sd_max = 0.0
    Sv_p_max = 0.0
    Sa_p_max = 0.0
    Sa_abs_max = abs(a_rel + acc_ms2[0])
    Sv_true_max = 0.0
    Sa_rel_max = abs(a_rel)

    for i in range(len(acc_ms2) - 1):
        p_eff = (-acc_ms2[i + 1]
                 + a0 * u + a2 * v + a3 * a_rel
                 + c * (a1 * u + a4 * v + a5 * a_rel))

        u1 = p_eff / k_hat
        v1 = a1 * (u1 - u) - a4 * v - a5 * a_rel
        a1_rel = a0 * (u1 - u) - a2 * v - a3 * a_rel
        a_abs = a1_rel + acc_ms2[i + 1]

        Sd_max = max(Sd_max, abs(u1))
        Sv_p_max = max(Sv_p_max, abs(omega * u1))
        Sa_p_max = max(Sa_p_max, abs(omega * omega * u1))
        Sa_abs_max = max(Sa_abs_max, abs(a_abs))
        Sv_true_max = max(Sv_true_max, abs(v1))
        Sa_rel_max = max(Sa_rel_max, abs(a1_rel))

        u, v, a_rel = u1, v1, a1_rel

    return Sd_max, Sv_p_max, Sa_p_max, Sa_abs_max, Sv_true_max, Sa_rel_max

def _newmark_peaks(acc_ms2: np.ndarray, dt: float, omega: float, zeta: float
                   ) -> Tuple[float, float, float, float, float, float]:
    """
    Newmark-β Linear Acceleration (γ = 0.5, β = 1/6) ile tek SDOF için
    tepe değerleri hesaplar.
    Döndürür: (Sd_max, Sv_p_max, Sa_p_max, Sa_abs_max, Sv_true_max, Sa_rel_max)
    """
    if NUMBA_AVAILABLE:
        return _newmark_peaks_jit(acc_ms2, dt, omega, zeta)
    
    # Fallback: orijinal Python implementasyonu (Linear Acceleration)
    beta = NEWMARK_BETA
    gamma = NEWMARK_GAMMA
    c = 2.0 * zeta * omega
    k = omega * omega

    a0 = 1.0 / (beta * dt * dt)
    a1 = gamma / (beta * dt)
    a2 = 1.0 / (beta * dt)
    a3 = 1.0 / (2.0 * beta) - 1.0
    a4 = gamma / beta - 1.0
    a5 = dt * (gamma / (2.0 * beta) - 1.0)
    k_hat = k + a0 + c * a1

    u = 0.0
    v = 0.0
    a_rel = -acc_ms2[0]

    Sd_max = 0.0
    Sv_p_max = 0.0
    Sa_p_max = 0.0
    Sa_abs_max = abs(a_rel + acc_ms2[0])
    Sv_true_max = 0.0
    Sa_rel_max = abs(a_rel)

    for i in range(len(acc_ms2) - 1):
        p_eff = (-acc_ms2[i + 1]
                 + a0 * u + a2 * v + a3 * a_rel
                 + c * (a1 * u + a4 * v + a5 * a_rel))

        u1 = p_eff / k_hat
        v1 = a1 * (u1 - u) - a4 * v - a5 * a_rel
        a1_rel = a0 * (u1 - u) - a2 * v - a3 * a_rel
        a_abs = a1_rel + acc_ms2[i + 1]

        Sd_max = max(Sd_max, abs(u1))
        Sv_p_max = max(Sv_p_max, abs(omega * u1))
        Sa_p_max = max(Sa_p_max, abs(omega * omega * u1))
        Sa_abs_max = max(Sa_abs_max, abs(a_abs))
        Sv_true_max = max(Sv_true_max, abs(v1))
        Sa_rel_max = max(Sa_rel_max, abs(a1_rel))

        u, v, a_rel = u1, v1, a1_rel

    return Sd_max, Sv_p_max, Sa_p_max, Sa_abs_max, Sv_true_max, Sa_rel_max

@jit(nopython=True, parallel=True, cache=True)
def _compute_spectrum_vectorized(acc_ms2: np.ndarray, dt: float, 
                                T_array: np.ndarray, zeta: float,
                                compute_abs_acc: bool = False,
                                compute_true_sv: bool = True,
                                compute_rel_acc: bool = False
                                ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Vektörize edilmiş spektrum hesaplaması - tüm periyotları paralel olarak hesaplar.
    Döndürür: Sd, Sv_p, Sa_p, Sa_abs, Sv_true, Sa_rel dizileri.
    """
    n_periods = len(T_array)
    Sd = np.zeros(n_periods)
    Sv_p = np.zeros(n_periods)
    Sa_p = np.zeros(n_periods)
    
    # Numba None tipini desteklemiyor, bu yüzden her zaman array döndürüyoruz
    Sa_abs = np.zeros(n_periods)
    Sv_true = np.zeros(n_periods)
    Sa_rel = np.zeros(n_periods)
    
    for j in prange(n_periods):
        omega = 2.0 * math.pi / T_array[j]
        sd, svp, sap, sa_abs, sv_true, sa_rel = _newmark_peaks_jit(acc_ms2, dt, omega, zeta)
        Sd[j] = sd
        Sv_p[j] = svp
        Sa_p[j] = sap
        if compute_abs_acc:
            Sa_abs[j] = sa_abs
        if compute_true_sv:
            Sv_true[j] = sv_true
        if compute_rel_acc:
            Sa_rel[j] = sa_rel
    
    return Sd, Sv_p, Sa_p, Sa_abs, Sv_true, Sa_rel

# ------------------------ Dış API ------------------------

def compute_elastic_response_spectrum(
    time: np.ndarray,
    acceleration: np.ndarray,
    settings: SpectrumSettings,
) -> Dict[float, SpectrumCurves]:
    """
    Zaman-ivme kaydından ERS üretir. Dönüş: { damping(%) : SpectrumCurves }
    """
    if time is None or len(time) < 2:
        raise ValueError("time dizisi gerekli.")

    # dt belirle
    dt = float(np.median(np.diff(time)))
    # ivmeyi SI'a çevir
    acc_ms2 = EarthquakeStats._convert_acceleration_to_ms2(
        np.asarray(acceleration, dtype=float), settings.accel_unit
    )

    # baseline düzelt
    acc_ms2 = _baseline_correct(acc_ms2, dt, settings.baseline)

    # periyotlar
    T = np.exp(np.linspace(np.log(settings.Tmin), np.log(settings.Tmax), settings.nT)) \
        if settings.logspace else np.linspace(settings.Tmin, settings.Tmax, settings.nT)

    # dt/T oranı kontrolü ve opsiyonel alt-örnekleme
    t_used = time
    a_used = acc_ms2
    if settings.enforce_dt_over_T:
        t_used, a_used, dt, changed = _resample_if_needed(time, acc_ms2, T.min(), settings.enforce_dt_over_T)
        if changed:
            print(f"ℹ️ Alt-örnekleme: dt {float(np.median(np.diff(time))):.6f}s → {dt:.6f}s "
                  f"(hedef dt/T ≤ {settings.enforce_dt_over_T:g})")

    results: Dict[float, SpectrumCurves] = {}

    # Vektörize edilmiş hesaplama (Numba varsa çok daha hızlı)
    if NUMBA_AVAILABLE:
        for z_pct in settings.damping_list:
            z = float(z_pct) / 100.0
            Sd, Sv_p, Sa_p, Sa_abs_raw, Sv_true_raw, Sa_rel_raw = _compute_spectrum_vectorized(
                a_used, dt, T, z,
                settings.compute_abs_acc,
                settings.compute_true_sv,
                settings.compute_rel_acc,
            )
            # Sa_abs'ı isteğe göre None yap
            Sa_abs = Sa_abs_raw if settings.compute_abs_acc else None
            Sv_true = Sv_true_raw if settings.compute_true_sv else None
            Sa_rel = Sa_rel_raw if settings.compute_rel_acc else None
            curves = SpectrumCurves(
                T=T, Sd=Sd, Sv_p=Sv_p, Sa_p=Sa_p, Sa_p_g=Sa_p / G,
                Sa_abs=Sa_abs, Sv_true=Sv_true, Sa_rel=Sa_rel
            )
            results[float(z_pct)] = curves
    else:
        # Fallback: orijinal döngü tabanlı hesaplama
        for z_pct in settings.damping_list:
            z = float(z_pct) / 100.0
            Sd = np.zeros_like(T)
            Sv_p = np.zeros_like(T)
            Sa_p = np.zeros_like(T)
            Sa_abs = np.zeros_like(T) if settings.compute_abs_acc else None
            Sv_true = np.zeros_like(T) if settings.compute_true_sv else None
            Sa_rel = np.zeros_like(T) if settings.compute_rel_acc else None

            for j, Tj in enumerate(T):
                omega = 2.0 * math.pi / Tj
                sd, svp, sap, sa_abs, sv_true_val, sa_rel_val = _newmark_peaks(a_used, dt, omega, z)
                Sd[j], Sv_p[j], Sa_p[j] = sd, svp, sap
                if Sa_abs is not None:
                    Sa_abs[j] = sa_abs
                if Sv_true is not None:
                    Sv_true[j] = sv_true_val
                if Sa_rel is not None:
                    Sa_rel[j] = sa_rel_val

            curves = SpectrumCurves(
                T=T, Sd=Sd, Sv_p=Sv_p, Sa_p=Sa_p, Sa_p_g=Sa_p / G,
                Sa_abs=Sa_abs, Sv_true=Sv_true, Sa_rel=Sa_rel
            )
            results[float(z_pct)] = curves

    return results

# ------------------------ CSV ve Grafik dışa aktarma ------------------------

def export_spectra_to_csv(curves_by_z: Dict[float, SpectrumCurves], out_path: str) -> str:
    """
    Tüm sönüm eğrilerini TEK dosyada 'wide' formatta yazar.
    Sütunlar: T, Sd_[ζ%](m), Svp_[ζ%](m/s), Sap_[ζ%](m/s²), Sap_[ζ%](g)
    """
    p = pathlib.Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)

    # Sütun başlıkları
    headers = ["T[s]"]
    dampings = sorted(curves_by_z.keys())
    for z in dampings:
        c = curves_by_z[z]
        headers.append(f"Sd_{z:.1f}%[m]")
        if c.Sv_true is not None:
            headers.append(f"Sv_true_{z:.1f}%[m/s]")
        if c.Sa_rel is not None:
            headers.append(f"Sa_rel_{z:.1f}%[m/s²]")
        if c.Sa_abs is not None:
            headers.append(f"Sa_abs_{z:.1f}%[m/s²]")
            headers.append(f"Sa_abs_{z:.1f}%[g]")
        headers += [
            f"Sv_p_{z:.1f}%[m/s]",
            f"Sa_p_{z:.1f}%[m/s²]",
            f"Sa_p_{z:.1f}%[g]",
        ]

    # T eksenini seç (ilk sönüm)
    T = curves_by_z[dampings[0]].T
    rows = []
    for i in range(len(T)):
        row = [f"{T[i]:.8g}"]
        for z in dampings:
            c = curves_by_z[z]
            row.append(f"{c.Sd[i]:.8g}")
            if c.Sv_true is not None:
                row.append(f"{c.Sv_true[i]:.8g}")
            if c.Sa_rel is not None:
                row.append(f"{c.Sa_rel[i]:.8g}")
            if c.Sa_abs is not None:
                sa_abs_val = c.Sa_abs[i]
                row.append(f"{sa_abs_val:.8g}")
                row.append(f"{(sa_abs_val / G):.8g}")
            row += [
                f"{c.Sv_p[i]:.8g}",
                f"{c.Sa_p[i]:.8g}",
                f"{c.Sa_p_g[i]:.8g}",
            ]
        rows.append(row)

    with open(p, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    return str(p)

def plot_spectra(curves_by_z: Dict[float, SpectrumCurves],
                 ytype: str = "sa", xaxis: str = "period",
                 title: Optional[str] = None, outfile: Optional[str] = None) -> Optional[str]:
    """
    ytype: 'sa'|'sv'|'sd'|'sa_abs'|'sv_true'|'sa_rel'
    xaxis: 'period'|'frequency'
    """
    dampings = sorted(curves_by_z.keys())

    # X verisi
    T = curves_by_z[dampings[0]].T
    x = T if xaxis == "period" else 1.0 / T
    xlabel = "Periyot, T [s]" if xaxis == "period" else "Frekans, f [Hz]"

    def _extract_series(curves: SpectrumCurves) -> np.ndarray:
        if ytype == "sa":
            return curves.Sa_p_g
        if ytype == "sv":
            return curves.Sv_p
        if ytype == "sd":
            return curves.Sd
        if ytype == "sa_abs":
            if curves.Sa_abs is None:
                raise ValueError("Sa_abs verisi bu sonuçta mevcut değil.")
            return curves.Sa_abs / G
        if ytype == "sv_true":
            if curves.Sv_true is None:
                raise ValueError("Sv_true verisi bu sonuçta mevcut değil.")
            return curves.Sv_true
        if ytype == "sa_rel":
            if curves.Sa_rel is None:
                raise ValueError("Sa_rel verisi bu sonuçta mevcut değil.")
            return curves.Sa_rel
        raise ValueError(f"Bilinmeyen ytype: {ytype}")

    ylabel_map = {
        "sa": "Pseudo-Sa [g]",
        "sv": "Pseudo-Sv [m/s]",
        "sd": "Sd [m]",
        "sa_abs": "Absolute Sa [g]",
        "sv_true": "True Sv [m/s]",
        "sa_rel": "Relative Sa [m/s²]",
    }
    ylabel = ylabel_map.get(ytype, "Spektrum")

    plt.figure()
    for z in dampings:
        c = curves_by_z[z]
        y = _extract_series(c)
        label = f"zeta = {z:.1f}%"
        plt.plot(x, y, label=label)

    plt.grid(True, which="both", linestyle=":")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    if xaxis == "period":
        plt.xscale("log")
    plt.legend()
    if title:
        plt.title(title)
    plt.tight_layout()

    if outfile:
        outpath = pathlib.Path(outfile)
        outpath.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(outpath, dpi=150)
        plt.close()
        return str(outpath)
    return None

# ------------------------ CLI (opsiyonel) ------------------------

def main_cli():
    import argparse
    ap = argparse.ArgumentParser(
        description="Elastic Response Spectrum (ERS) üretimi. "
                    "Integrator: Newmark-β (γ=0.5, β=1/6) Linear Acceleration.")
    ap.add_argument("-i", "--input", required=True, help="Girdi dosyası (.AT2/.csv/.txt)")
    ap.add_argument("--dt", type=float, default=None, help="Tek sütunlu veri için dt ipucu (s)")
    ap.add_argument("-u", "--units", default="g", help="İvme birimi ('g','m/s²','cm/s²','mm/s²')")
    ap.add_argument("-z", "--damping", default="5", help="Sönüm yüzdeleri, virgüllü liste (örn. 2,5,10)")
    ap.add_argument("--tmin", type=float, default=0.01)
    ap.add_argument("--tmax", type=float, default=10.0)
    ap.add_argument("-n", "--nperiods", type=int, default=500)
    ap.add_argument("--xaxis", choices=["period", "frequency"], default="period")
    ap.add_argument("--ytype", choices=["sa", "sv", "sd", "sa_abs", "sv_true", "sa_rel"], default="sa")
    ap.add_argument("--baseline", default="linear", choices=["none","demean","linear","poly2","poly3"])
    ap.add_argument("--dt_over_T", type=float, default=None, help="dt/T üst sınırı (örn. 0.05)")
    ap.add_argument("-o", "--outprefix", default=None, help="Çıktı öneki (klasör/isim)")
    args = ap.parse_args()

    # Kayıt oku
    time, accel, dt_auto, unit_guess = read_timeseries_auto(args.input, args.dt)
    accel_unit = args.units or unit_guess

    settings = SpectrumSettings(
        damping_list=[float(s) for s in args.damping.split(",")],
        Tmin=args.tmin, Tmax=args.tmax, nT=args.nperiods, logspace=True,
        accel_unit=accel_unit, baseline=args.baseline,
        enforce_dt_over_T=args.dt_over_T,
        compute_abs_acc=(args.ytype == "sa_abs"),
        compute_true_sv=True,
        compute_rel_acc=(args.ytype == "sa_rel"),
    )
    curves_by_z = compute_elastic_response_spectrum(time, accel, settings)

    # Dışa aktarım
    outprefix = args.outprefix or (pathlib.Path(args.input).with_suffix("").name + "_ERS")
    csv_path = export_spectra_to_csv(curves_by_z, outprefix + ".csv")
    png_path = plot_spectra(curves_by_z, ytype=args.ytype, xaxis=args.xaxis,
                            title=f"ERS ({args.ytype.upper()}) - {pathlib.Path(args.input).name}",
                            outfile=outprefix + f"_{args.ytype.upper()}.png")

    print(f"CSV: {csv_path}")
    if png_path:
        print(f"PNG: {png_path}")

if __name__ == "__main__":
    main_cli()
