"""
TBDY‑2018 3B Basit Ölçeklendirme algoritması (SRSS, ortalama, tek ölçek katsayısı)

Girdi: Kayıt çiftleri listesi [(ax, ay, dt, meta), ...] ve tasarım spektrumu parametreleri.
Çıktı: f_min (tek küresel ölçek), ölçüt oranı eğrileri, doğrulama metrikleri.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union, Literal

import numpy as np
from ..config.constants import MIN_RECORD_COUNT, MAX_SAME_EVENT_PER_SET

# --- Yönetmelik doğrulamaları ---
def _validate_records(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    *,
    allow_below_11: bool = False,
    min_records: int = MIN_RECORD_COUNT,
    max_per_event: int = MAX_SAME_EVENT_PER_SET,
) -> None:
    """
    3B basit ölçeklendirme için kayıt listesi doğrulamaları.
    Varsayılan davranış (test uyumlu): <11 ise ValueError fırlatılır.
    allow_below_11=True → <11 durumunda hata yerine uyarı kabulü (GUI onayı ile).
    """
    n = len(records or [])
    if n <= 0:
        raise ValueError("En az bir kayıt çifti gereklidir.")
    if n < min_records and not allow_below_11:
        raise ValueError(f"Kayıt sayısı yetersiz: {n} < {min_records}.")

    # Zorunlu hata: Aynı depremden > max_per_event seçilemez
    counts: Dict[str, int] = {}
    for idx, rec in enumerate(records):
        try:
            _, _, dt, meta = rec
        except Exception:
            raise ValueError(f"Kayıt #{idx} beklenen (ax, ay, dt, meta) yapısında değil.")
        if not isinstance(dt, (int, float)) or float(dt) <= 0.0:
            raise ValueError(f"Kayıt #{idx} için zaman adımı (dt) geçersiz.")
        ev = None
        if isinstance(meta, dict):
            ev = meta.get("event_id") or meta.get("group_id") or meta.get("pair_name")
        ev = str(ev or f"EV{idx//3}")
        counts[ev] = counts.get(ev, 0) + 1
        if counts[ev] > max_per_event:
            raise ValueError(
                f"Aynı depremden seçilen kayıt sayısı sınırı aşıldı: '{ev}' için > {max_per_event}."
            )

    # allow_below_11=True ise burada hata üretmeyiz; GUI kullanıcı onayıyla devam edecektir.
    return None


from .response_spectrum import compute_elastic_response_spectrum, SpectrumSettings
from ..scaling.optimization import solve_lp_scaling
from ..calculations.spectrum import SpectrumCalculator
from ..scaling.scale_factor import calculate_scale_factor


@dataclass
class ScaleResult:
    f_min: float
    T: np.ndarray               # periyot ızgarası
    S_avg: np.ndarray           # ortalama SRSS spektrumu (g)
    S_target: np.ndarray        # hedef 1.3*S_tas(T)
    ratios: np.ndarray          # S_avg_scaled / (1.3*S_tas)
    per_record_factors: List[float]
    # Yeni alanlar (geri uyum için opsiyonel varsayılanlarla)
    mode: str = "tbdx_min"
    rmin: Optional[float] = None
    t_at_rmin: Optional[float] = None
    global_factor: Optional[float] = None
    peer_debug: Optional[Dict] = None
    # Suite istatistikleri (ölçeklenmiş): ortalama ve standart sapma
    S_suite_mean: Optional[np.ndarray] = None
    S_suite_std: Optional[np.ndarray] = None
    # Global zorlamanın tavan nedeniyle sınırlanıp sınırlanmadığı bilgisi
    global_capped: Optional[bool] = None
    # Mod açıklaması
    mode_note: Optional[str] = None


def design_spectrum_g(T: np.ndarray, SDS: float, SD1: float, TL: float = 6.0) -> np.ndarray:
    """TBDY 2.3.4’e göre tasarım Sae(T) [g] özet form.
    Not: `src/calculations/spectrum.py` içindeki formülle uyumlu tutuldu.
    """
    TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
    TB = SD1 / SDS if SDS > 0 else 0.0
    T = np.asarray(T, dtype=float)
    T_safe = np.where(T == 0.0, 1e-12, T)
    Sa = SD1 * TL / (T_safe ** 2)
    mask3 = (T > TB) & (T <= TL)
    Sa = np.where(mask3, SD1 / T_safe, Sa)
    mask2 = (T > TA) & (T <= TB)
    Sa = np.where(mask2, SDS, Sa)
    mask1 = (T <= TA)
    Sa = np.where(mask1, (0.4 + 0.6 * (T_safe / TA if TA > 0 else 0.0)) * SDS, Sa)
    Sa = np.where(T == 0.0, 0.4 * SDS, Sa)
    return np.where(np.isfinite(Sa), Sa, 0.0)


def compute_srss_average_g(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    T: np.ndarray,
    accel_unit: str = "g",
    damping_percent: float = 5.0,
) -> np.ndarray:
    """Her kayıt çifti için 5% sönümlü Sa(T) hesaplar, SRSS ile bileşkeyi alır, ortalamasını döndürür (g)."""
    settings = SpectrumSettings(
        damping_list=(damping_percent,),
        Tmin=float(T.min() if np.size(T) > 0 else 0.01),
        Tmax=float(T.max() if np.size(T) > 0 else 5.0),
        nT=int(len(T)),
        logspace=True,  # PGMD uyumlu log-yoğun örnekleme
        accel_unit=accel_unit,
        baseline="linear",
    )
    # SpectrumSettings nT ve Tmin/Tmax kullanıyor; T dizisini doğrudan kullanmak için küçük hack:
    # compute_elastic_response_spectrum logspace=False iken linspace üretir; burada hesaplama sonrası
    # T eksenini bizim T ile interpolate edeceğiz.

    srss_list: List[np.ndarray] = []
    for ax, ay, dt, meta in records:
        time = np.arange(len(ax), dtype=float) * float(dt)
        # X için spektrum
        sX = compute_elastic_response_spectrum(time, ax, settings)
        curvesX = next(iter(sX.values()))
        # Y için spektrum
        sY = compute_elastic_response_spectrum(time, ay, settings)
        curvesY = next(iter(sY.values()))

        # Log-log interpolasyon (PGMD uyumlu)
        def _interp_loglog(src_T: np.ndarray, src_Sa_g: np.ndarray, tgt_T: np.ndarray) -> np.ndarray:
            """Log(T)-ln(SA) uzayında interpolasyon, aralık dışı uçlarda düz sınırlar."""
            eps = 1e-15
            src_T = np.asarray(src_T, dtype=float)
            src_Sa_g = np.maximum(np.asarray(src_Sa_g, dtype=float), eps)
            tgt_T = np.maximum(np.asarray(tgt_T, dtype=float), eps)
            order = np.argsort(src_T)
            xlog = np.log(src_T[order])
            ylog = np.log(src_Sa_g[order])
            xi = np.log(tgt_T)
            yi = np.interp(xi, xlog, ylog, left=ylog[0], right=ylog[-1])
            return np.exp(yi)

        SaX = _interp_loglog(curvesX.T, curvesX.Sa_p_g, T)
        SaY = _interp_loglog(curvesY.T, curvesY.Sa_p_g, T)
        Scomp = np.sqrt(SaX**2 + SaY**2)
        srss_list.append(Scomp)

    if not srss_list:
        return np.zeros_like(T, dtype=float)
    S_avg = np.mean(np.vstack(srss_list), axis=0)
    return S_avg


def basic_scaling_3d(
    records: Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]],
    Tp: float,
    SDS: float,
    SD1: float,
    TL: float = 6.0,
    accel_unit: str = "g",
    T_override: Optional[np.ndarray] = None,
    damping_percent: float = 5.0,
    *,
    alpha: float = 1.3,
    use_record_based: bool = False,
    max_scale: Optional[float] = None,
    allow_below_11: bool = False,
    # PEER ek parametreleri
    scale_mode: str = "tbdx_min",                # "tbdx_min" | "peer"
    peer_points_per_decade: int = 100,
    peer_weighting: Union[Literal["uniform"], np.ndarray, Callable[[np.ndarray], np.ndarray]] = "uniform",
    peer_range: Optional[Tuple[float, float]] = None,
    enforce_tbdx: bool = True,
    max_global_scale: Optional[float] = None,
    peer_method: str = "min_mse",
    peer_period_knots: Optional[Sequence[float]] = None,
    peer_weight_knots: Optional[Sequence[float]] = None,
    peer_single_period: Optional[float] = None,
    peer_scale_limits: Optional[Tuple[Optional[float], Optional[float]]] = None,
    # Yeni: PEER Spectral Ordinate seçimi ("srss" | "gm") – PGMD/PEER için varsayılan: "gm"
    peer_spectral_ordinate: str = "gm",
) -> ScaleResult:
    """TBDY‑2018’e göre 3B Basit Ölçeklendirme.

    Varsayılan: Eski tek-küresel ölçek (f_min). Opsiyonel olarak kayıt-bazlı LP ölçekleme.

    Koşul: Ortalama SRSS, [0.2*Tp, 1.5*Tp] aralığında alpha*S_tas(T) değerini sağlamalı.
    """
    # Ön doğrulama (erken çıkış için hızlı kontrol)
    _validate_records(records, allow_below_11=allow_below_11)

    # Periyot ızgarası (raporlama/TBDY bağlamı)
    if T_override is not None:
        T = np.asarray(T_override, dtype=float)
    else:
        # SpektrumCalculator’ın optimize dizisini kullan (daha yoğun örnekleme)
        sc = SpectrumCalculator()
        T = sc.generate_period_array_optimized(SDS, SD1, TL, t_end=max(1.5*Tp, TL))
    # Alpha kilidi (TBDY 3B: 1.30 zorunlu). Kullanıcı farklı değer girse de enforce_tbdx True ise 1.30 kullan.
    alpha_requested = 1.3 if alpha is None else float(alpha)
    alpha_effective = 1.3 if (enforce_tbdx and not np.isclose(alpha_requested, 1.3, rtol=1e-6, atol=1e-9)) else alpha_requested

    # Tasarım hedefi (rapor ızgarasında)
    S_tas = design_spectrum_g(T, SDS, SD1, TL)
    target = float(alpha_effective) * S_tas
    eps = 1e-12
    lo, hi = 0.2 * Tp, 1.5 * Tp
    mask = (T >= lo) & (T <= hi)
    
    # SRSS hesabı (güvenli maskeleme dahil)
    S_avg = compute_srss_average_g(records, T, accel_unit, damping_percent)

    # ───────────────────────────────
    # PEER modu
    # ───────────────────────────────
    if str(scale_mode).lower() == "peer":
        EPS = 1e-15

        method_alias = (peer_method or "min_mse").strip().lower()
        if method_alias in {"no", "no scaling", "noscaling"}:
            method_alias = "no_scaling"
        elif method_alias in {"min", "minimize", "minimise", "minimize mse", "minimise mse", "range"}:
            method_alias = "min_mse"
        elif method_alias in {"single", "single period", "single_period"}:
            method_alias = "single_period"
        valid_methods = {"no_scaling", "min_mse", "single_period"}
        if method_alias not in valid_methods:
            raise ValueError(f"Bilinmeyen PEER ölçekleme yöntemi: {peer_method}")

        def _build_logT_grid(Tmin: float, Tmax: float, ppd: int = 100) -> np.ndarray:
            # PEER-uyumlu log ızgara: [0.01, 10.0] ve PPD=100 -> 301 nokta
            # Uç noktaları numerik olarak sabitle (tam 0.01 ve 10.0)
            Tmin = max(float(Tmin), 1e-3)
            Tmax = max(float(Tmax), Tmin * (10 ** (1 / max(ppd, 1))))
            eps_t = 1e-12
            is_strict = (abs(Tmin - 0.01) <= 1e-12) and (abs(Tmax - 10.0) <= 1e-12)
            if is_strict and ppd > 0:
                decades = 3.0  # log10(10) - log10(0.01)
                n = int(ppd * decades) + 1
                exponents = np.linspace(-2.0, 1.0, n, dtype=np.float64)
                grid = np.power(10.0, exponents, dtype=np.float64)
            else:
                decades = np.log10(Tmax) - np.log10(Tmin)
                n = max(int(np.ceil(decades * ppd)) + 1, 2)
                grid = np.logspace(np.log10(Tmin), np.log10(Tmax), n, dtype=np.float64)
            # Uç noktaları sabitle
            if grid.size >= 2:
                grid[0] = 0.01
                grid[-1] = 10.0
            return grid

        def _interp_safe(src_T: np.ndarray, src_S: np.ndarray, tgt_T: np.ndarray) -> np.ndarray:
            order = np.argsort(src_T)
            src_T = np.asarray(src_T)[order]
            src_S = np.asarray(src_S)[order]
            left = float(src_S[0])
            right = float(src_S[-1])
            return np.interp(tgt_T, src_T, src_S, left=left, right=right)

        def _interp_loglog(src_T: np.ndarray, src_S: np.ndarray, tgt_T: np.ndarray) -> np.ndarray:
            """Log(T)-ln(SA) uzayında interpolasyon, aralık dışı düz (flat) uç değerlerle."""
            src_T = np.asarray(src_T, dtype=float)
            src_S = np.maximum(np.asarray(src_S, dtype=float), EPS)
            tgt_T = np.maximum(np.asarray(tgt_T, dtype=float), EPS)
            order = np.argsort(src_T)
            x = src_T[order]
            y = src_S[order]
            xi = np.log(tgt_T)
            xlog = np.log(x)
            ylog = np.log(y)
            left = float(ylog[0])
            right = float(ylog[-1])
            yi = np.interp(xi, xlog, ylog, left=left, right=right)
            return np.exp(yi)

        def _record_spectra_on_grid(
            ax: np.ndarray,
            ay: np.ndarray,
            dt: float,
            T_grid: np.ndarray,
            *,
            return_srss: bool = False,
            spectral_ordinate: str = "srss",
        ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
            settings = SpectrumSettings(
                damping_list=(damping_percent,),
                Tmin=float(np.min(T_grid)),
                Tmax=float(np.max(T_grid)),
                nT=max(len(T_grid), 256),
                logspace=True,
                accel_unit=accel_unit,
                baseline="linear",
            )
            time = np.arange(len(ax), dtype=float) * float(dt)
            sX = compute_elastic_response_spectrum(time, ax, settings); cx = next(iter(sX.values()))
            sY = compute_elastic_response_spectrum(time, ay, settings); cy = next(iter(sY.values()))
            # ln-ln interpolasyon (PGMD uyumlu)
            SaX = _interp_loglog(cx.T, cx.Sa_p_g, T_grid)
            SaY = _interp_loglog(cy.T, cy.Sa_p_g, T_grid)
            SaX = np.maximum(SaX, EPS)
            SaY = np.maximum(SaY, EPS)
            # Spektral bileşke seçimi (SRSS varsayılan)
            ord_mode = (spectral_ordinate or "srss").strip().lower()
            if ord_mode == "gm":
                SA_MAIN = np.sqrt(SaX * SaY)
            else:
                SA_MAIN = np.sqrt(SaX**2 + SaY**2)
            SA_MAIN = np.asarray(SA_MAIN, dtype=np.float64)
            if return_srss:
                SA_SRSS = np.sqrt(SaX**2 + SaY**2)
                return np.asarray(SA_MAIN, dtype=np.float64), np.asarray(SA_SRSS, dtype=np.float64)
            return np.asarray(SA_MAIN, dtype=np.float64), None

        def _weighted_mse_log_kahan(S_t: np.ndarray, S_r: np.ndarray, w: np.ndarray) -> float:
            """Ağırlıklı MSE'yi ln-uzayda Kahan toplamayla hesaplar (float64)."""
            epsl = np.float64(1e-15)
            St = np.asarray(S_t, dtype=np.float64)
            Sr = np.asarray(S_r, dtype=np.float64)
            W  = np.asarray(w,   dtype=np.float64)
            St = np.maximum(St, epsl)
            Sr = np.maximum(Sr, epsl)
            diff = np.log(St) - np.log(Sr)
            term = W * (diff * diff)
            s = np.float64(0.0)
            c = np.float64(0.0)
            # Kahan summation
            for x in term:
                y = x - c
                t = s + y
                c = (t - s) - y
                s = t
            denom = np.float64(np.sum(W))
            if denom <= 0.0:
                return float('nan')
            return float(s / denom)

        def _build_weights_from_knots(T_peer: np.ndarray) -> np.ndarray:
            if peer_period_knots is None or peer_weight_knots is None:
                W = np.ones_like(T_peer, dtype=float)
                return W / np.sum(W)
            periods = np.asarray(peer_period_knots, dtype=float)
            weights = np.asarray(peer_weight_knots, dtype=float)
            if periods.size != weights.size or periods.size < 2:
                raise ValueError("Ağırlık düğümleri geçersiz: period ve weight listeleri aynı sayıda olmalı ve en az iki değer içermeli")
            if np.any(periods <= 0):
                raise ValueError("Ağırlık düğümlerinde pozitif olmayan periyot var")
            order = np.argsort(periods)
            periods = periods[order]
            weights = weights[order]
            log_peer = np.log(T_peer)
            log_knots = np.log(periods)
            interp = np.interp(log_peer, log_knots, weights, left=0.0, right=0.0)
            interp = np.maximum(interp, 0.0)
            total = np.sum(interp)
            if total <= 0:
                raise ValueError("Ağırlık fonksiyonu [0.01,10] s aralığında sıfıra indirgendi")
            return interp / total

        # Period penceresi yönteme göre belirlenir (No Scaling: kullanıcı ağırlık düğümleri veya varsayılan [0.01,10])
        Tmin, Tmax = peer_range if (peer_range is not None) else (0.01, 10.0)
        T_peer = _build_logT_grid(Tmin, Tmax, ppd=int(peer_points_per_decade))
        weights_peer = _build_weights_from_knots(T_peer)

        if isinstance(peer_weighting, np.ndarray) and peer_weight_knots is None:
            # Geriye dönük uyumluluk: doğrudan verilen ağırlık dizisini normalize et
            custom = np.asarray(peer_weighting, dtype=float)
            if custom.shape == T_peer.shape and np.sum(custom) > 0:
                weights_peer = custom / np.sum(custom)

        # Hedef PEER ızgarasında doğrudan analitik formülle hesaplanır (flat ekstrapolasyon hatasını önler)
        # Not: No Scaling sıralamasında α uygulanmaz; S_tas(T_peer) kullanılır
        S_target_peer = design_spectrum_g(T_peer, SDS, SD1, TL)

        main_ctx_list: List[np.ndarray] = []
        f_list: List[float] = []
        gm_preview: List[np.ndarray] = []

        if method_alias == "single_period":
            if peer_single_period is None:
                raise ValueError("Single Period yönteminde T_s değeri zorunlu")
            if not (Tmin <= float(peer_single_period) <= Tmax):
                raise ValueError("T_s değeri ağırlık periyot aralığı dışında")

        limits_tuple: Optional[Tuple[float, float]] = None
        if peer_scale_limits is not None:
            f_min, f_max = peer_scale_limits
            if f_min is not None or f_max is not None:
                f_min = float(f_min) if f_min is not None else -np.inf
                f_max = float(f_max) if f_max is not None else np.inf
                limits_tuple = (f_min, f_max)

        # PEER/PGMD: Varsayılan SRSS; kullanıcı seçimine göre güncellenebilir
        peer_spec_ord = (peer_spectral_ordinate or "srss").strip().lower()
        mse_list: List[float] = []
        for ax_rec, ay_rec, dt_rec, meta in records:
            SA_MAIN_peer, _ = _record_spectra_on_grid(
                ax_rec, ay_rec, dt_rec, T_peer, spectral_ordinate=peer_spec_ord
            )
            gm_preview.append(SA_MAIN_peer)

            # Kayıt-özel LUF maskesi: T > 1/LUF bölgelerinde w=0; yeniden normalize et
            weights_rec = np.asarray(weights_peer, dtype=float).copy()
            try:
                luf_hz = None
                if isinstance(meta, dict):
                    for key in (
                        "lowest_useable_frequency", "lowest_usable_frequency", "luf",
                        "low_useable_frequency", "low_usable_frequency", "min_freq", "fmin",
                    ):
                        if key in meta and meta[key] is not None:
                            luf_hz = float(meta[key])
                            break
                if (luf_hz is not None) and np.isfinite(luf_hz) and (luf_hz > 0.0):
                    T_max_use = float(1.0 / luf_hz)
                    weights_rec = np.where(T_peer <= T_max_use, weights_rec, 0.0)
            except Exception:
                pass
            # Yeniden normalize et (toplam tam 1.0 olsun)
            s_w = float(np.sum(weights_rec))
            if s_w > 0.0:
                weights_rec = weights_rec / s_w
                # epsilon düzeltmesi (tam 1.0)
                residual = 1.0 - float(np.sum(weights_rec))
                if abs(residual) > 0.0:
                    try:
                        idx_max = int(np.argmax(weights_rec))
                        weights_rec[idx_max] = float(weights_rec[idx_max] + residual)
                    except Exception:
                        pass
            else:
                weights_rec = np.asarray(weights_peer, dtype=float)

            if method_alias == "no_scaling":
                f_i = 1.0
            elif method_alias == "min_mse":
                f_i, _ = calculate_scale_factor(
                    S_target_peer,
                    SA_MAIN_peer,
                    weights_rec,
                    mode="range",
                    limits=limits_tuple,
                )
            else:  # single_period
                f_i, _ = calculate_scale_factor(
                    S_target_peer,
                    SA_MAIN_peer,
                    weights_rec,
                    mode="single",
                    T_s=float(peer_single_period),
                    T_grid=T_peer,
                    limits=limits_tuple,
                )

            f_list.append(float(f_i))
            scaled_peer = float(f_i) * SA_MAIN_peer
            main_ctx_list.append(np.asarray(scaled_peer, dtype=np.float64))
            # MSE'yi doğrudan T_peer üzerinde hesapla (Kahan, float64)
            try:
                mse_i = _weighted_mse_log_kahan(S_target_peer, scaled_peer, weights_rec)
            except Exception:
                mse_i = float('nan')
            mse_list.append(float(mse_i))

        if not main_ctx_list:
            S_avg_ctx = np.zeros_like(T_peer, dtype=float)
            S_std_ctx = np.zeros_like(T_peer, dtype=float)
        else:
            stack_scaled = np.vstack(main_ctx_list)
            S_avg_ctx = np.mean(stack_scaled, axis=0, dtype=np.float64)
            S_std_ctx = np.std(stack_scaled, axis=0, dtype=np.float64)

        # No Scaling modunda Tp bandı dayatması yok; tüm T_peer ekseninde değerlendirme yap
        lo_peer, hi_peer = 0.2 * Tp, 1.5 * Tp
        mask_peer = (T_peer >= lo_peer) & (T_peer <= hi_peer)
        mask_ctx = np.ones_like(T_peer, dtype=bool) if (method_alias == "no_scaling") else mask_peer
        # PEER Parity: No Scaling modunda global γ uygulanmaz
        if (method_alias != "no_scaling") and enforce_tbdx:
            with np.errstate(divide="ignore", invalid="ignore"):
                z_needed = float(np.max(np.where(mask_ctx, S_target_peer / np.maximum(S_avg_ctx, EPS), 0.0)))
            z_needed = max(z_needed, 1.0)
            if (max_global_scale is not None) and np.isfinite(max_global_scale):
                z = min(z_needed, float(max_global_scale))
                global_capped = bool(z_needed > float(max_global_scale))
            else:
                z = z_needed
                global_capped = False
        else:
            z = 1.0
            global_capped = False

        S_avg_star = np.asarray(z * S_avg_ctx, dtype=np.float64)
        S_std_star = np.asarray(z * S_std_ctx, dtype=np.float64)
        ratios = np.asarray(S_avg_star / np.maximum(S_target_peer, eps), dtype=np.float64)
        rmin = float(np.min(ratios[mask_ctx])) if np.any(mask_ctx) else float("nan")
        t_at_rmin = float(T_peer[mask_ctx][np.argmin(ratios[mask_ctx])]) if np.any(mask_ctx) else float("nan")

        if method_alias == "no_scaling":
            # No-Scaling: per-record f_i sabit 1.0; sadece suite düzeyinde γ uygulanır
            per_record_factors_star = [1.0 for _ in f_list]
            f_min_display = 1.0
            method_note = "PEER: No Scaling (f=1.0)"
        else:
            # Diğer PEER yöntemlerinde γ, per-record f_i üzerine uygulanabilir (raporlama amaçlı)
            per_record_factors_star = [float(z * fi) for fi in f_list]
            if per_record_factors_star:
                f_min_display = float(np.mean(per_record_factors_star))
            else:
                f_min_display = float(z)
            method_note = {
                "min_mse": "PEER: Minimize MSE",
                "single_period": f"PEER: Single Period (T_s={peer_single_period})",
            }.get(method_alias, "PEER")

        return ScaleResult(
            f_min=f_min_display,
            T=T_peer,
            S_avg=S_avg_star,
            S_target=S_target_peer,
            ratios=ratios,
            per_record_factors=per_record_factors_star,
            mode="peer",
            rmin=rmin,
            t_at_rmin=t_at_rmin,
            global_factor=z,
            peer_debug={
                "T_peer": T_peer,
                "weights_peer": weights_peer,
                "method": method_alias,
                "spectral_ordinate": peer_spec_ord,
                "gm_preview": gm_preview[: min(3, len(gm_preview))],
                # Görselleştirme için aralık bilgisi (No Scaling: ağırlık aralığı)
                "range": (float(T_peer[0]), float(T_peer[-1])) if (T_peer is not None and T_peer.size > 1) else (Tmin, Tmax),
                # Doğrudan hesaplanmış (T_peer) MSE listesi
                "mse_list": mse_list,
            },
            S_suite_mean=S_avg_star,
            S_suite_std=S_std_star,
            global_capped=global_capped,
            mode_note=method_note,
        )

    # ───────────────────────────────
    # Eski yollar (tbdx_min ve LP kayıt-bazlı)
    # ───────────────────────────────
    # Bireysel SRSS listesi ve ortalama (rapor ızgarasında)
    settings = SpectrumSettings(
        damping_list=(damping_percent,),
        Tmin=float(T.min() if np.size(T) > 0 else 0.01),
        Tmax=float(T.max() if np.size(T) > 0 else 5.0),
        nT=int(len(T)),
        logspace=True,  # PGMD uyumlu log-yoğun örnekleme
        accel_unit=accel_unit,
        baseline="linear",
    )
    srss_list: List[np.ndarray] = []
    for ax, ay, dt, meta in records:
        time = np.arange(len(ax), dtype=float) * float(dt)
        sX = compute_elastic_response_spectrum(time, ax, settings)
        curvesX = next(iter(sX.values()))
        sY = compute_elastic_response_spectrum(time, ay, settings)
        curvesY = next(iter(sY.values()))
        orderX = np.argsort(curvesX.T)
        orderY = np.argsort(curvesY.T)
        SaX = np.interp(T, curvesX.T[orderX], curvesX.Sa_p_g[orderX], left=curvesX.Sa_p_g[orderX][0], right=curvesX.Sa_p_g[orderX][-1])
        SaY = np.interp(T, curvesY.T[orderY], curvesY.Sa_p_g[orderY], left=curvesY.Sa_p_g[orderY][0], right=curvesY.Sa_p_g[orderY][-1])
        Scomp = np.sqrt(SaX**2 + SaY**2)
        srss_list.append(Scomp)
    if not srss_list:
        S_avg = np.zeros_like(T, dtype=float)
    else:
        S_avg = np.mean(np.vstack(srss_list), axis=0)

    # Hedef ve oranlar (tbdx_min/LP için)
    eps = 1e-12
    if use_record_based and len(srss_list) > 0:
        lp_max_scale = max_scale if max_scale is not None else 10.0
        f_vec = solve_lp_scaling(
            srss_list,
            S_tas,
            T,
            mask,
            alpha=float(alpha_effective),
            max_scale=lp_max_scale,
        )
        scaled_stack = np.vstack([f_vec[i] * srss_list[i] for i in range(len(srss_list))])
        mean_scaled = np.mean(scaled_stack, axis=0)
        std_scaled = np.std(scaled_stack, axis=0)
        if np.any(mask):
            deficit = float(np.max(target[mask] / np.maximum(mean_scaled[mask], eps)))
        else:
            deficit = 1.0
        if deficit > 1.0 + 1e-9:
            f_vec = f_vec * deficit
            scaled_stack = scaled_stack * deficit
            mean_scaled = mean_scaled * deficit
            std_scaled = std_scaled * deficit
        ratios = mean_scaled / np.maximum(target, eps)
        f_min_display = float(np.mean(f_vec)) if len(f_vec) > 0 else 1.0
        return ScaleResult(
            f_min=f_min_display,
            T=T,
            S_avg=S_avg,
            S_target=target,
            ratios=ratios,
            per_record_factors=[float(x) for x in f_vec],
            mode="record_lp",
            mode_note="LP: minimize sum(f_i) subject to mean≥α·S_target (Kısıt-Tatmin)",
            S_suite_mean=mean_scaled,
            S_suite_std=std_scaled,
        )
    else:
        with np.errstate(divide='ignore', invalid='ignore'):
            factors = target / np.maximum(S_avg, eps)
        if not np.any(mask):
            f_min = float(np.max(factors))
        else:
            f_min = float(np.max(factors[mask]))
        S_mean_scaled = f_min * S_avg
        if len(srss_list) > 0:
            scaled_stack = np.vstack([f_min * s for s in srss_list])
            S_std_scaled = np.std(scaled_stack, axis=0)
        else:
            S_std_scaled = np.zeros_like(T, dtype=float)
        ratios = S_mean_scaled / np.maximum(target, eps)
        rmin = float(np.min(ratios[mask])) if np.any(mask) else None
        t_at_rmin = float(T[mask][np.argmin(ratios[mask])]) if np.any(mask) else None
        return ScaleResult(
            f_min=f_min,
            T=T,
            S_avg=S_avg,
            S_target=target,
            ratios=ratios,
            per_record_factors=[f_min] * len(records),
            mode="tbdx_min",
            rmin=rmin,
            t_at_rmin=t_at_rmin,
            S_suite_mean=S_mean_scaled,
            S_suite_std=S_std_scaled,
        )
