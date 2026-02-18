"""
Deprem kaydı istatistiksel analiz hesaplamaları
Peak Ground Acceleration (PGA), Peak Ground Velocity (PGV), Peak Ground Displacement (PGD)
ve diğer deprem mühendisliği parametreleri
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class PeakStats:
    """PGA/PGV/PGD gibi tepe değer istatistikleri."""

    peak_abs: float
    peak_pos: float
    peak_neg: float
    t_peak_abs: float
    t_peak_pos: float
    t_peak_neg: float
    idx_peak_abs: int
    idx_peak_pos: int
    idx_peak_neg: int
    unit: str
    valid_samples: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class RmsStats:
    """İvme, hız ve yerdeğiştirme için RMS değerleri."""

    acceleration: float
    velocity: float
    displacement: float
    accel_unit: str
    velocity_unit: str
    displacement_unit: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AriasIntensity:
    """Arias Intensity bilgilerini temsil eder."""

    arias_intensity: float
    unit: str
    valid_samples: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AriasAccelerationLevel:
    """Belirli bir yüzde için Arias tabanlı ivme eşiği (örn. A95)."""

    value: float
    percentile: float
    unit: str
    valid_samples: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class SignificantDuration:
    """Significant Duration ölçümleri."""

    duration: float
    start_time: float
    end_time: float
    start_percent: float
    end_percent: float
    valid_samples: int

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class DurationMeasures:
    """Arias tabanlı süre ölçütleri (Db, Du, Ds, De) ve yardımcı çıktılar.

    Bu kapsayıcı, arias_intensity_duration_spec.md şartnamesiyle uyumludur.
    """

    Db: float
    Du: float
    Ds: float
    De: float
    t_db: Optional[tuple]
    t_ds: Optional[tuple]
    t_de: Optional[tuple]
    AI_tot: float
    AI_cum: np.ndarray
    H: np.ndarray

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class Durations:
    """Spec uyumlu API: Db, Du, Ds, De ve yardımcı çıktılar (aynı alanlar)."""
    Db: float
    Du: float
    Ds: float
    De: float
    t_db: Optional[tuple]
    t_ds: Optional[tuple]
    t_de: Optional[tuple]
    AI_tot: float
    AI_cum: np.ndarray
    H: np.ndarray

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

@dataclass
class CavStats:
    """CAV veya CAVstd sonuçlarını saklar."""

    value: float
    value_si: float
    unit: str
    unit_si: str
    type: str
    threshold_g: Optional[float] = None
    window_size_s: Optional[float] = None
    damage_threshold_reference: Optional[float] = None
    damage_threshold_reference_si: Optional[float] = None
    valid_samples: int = 0

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class RecordInfo:
    """Kayıt hakkındaki temel bilgiler."""

    length: float
    data_points: int
    sampling_rate: float
    time_step: float

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class SamplingInfo:
    """Örnekleme bilgilerini içerir."""

    dt: float
    dt_source: str
    sampling_uniform: bool
    sampling_rate: float
    dt_median: Optional[float] = None
    dt_std: Optional[float] = None
    dt_min: Optional[float] = None
    dt_max: Optional[float] = None
    uniformity_ratio: Optional[float] = None
    uniformity_tolerance: Optional[float] = None
    total_duration: Optional[float] = None
    valid_time_samples: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    # Sözlük-benzeri erişim desteği (testlerde kullanılıyor)
    def __getitem__(self, key: str):
        return getattr(self, key)


@dataclass
class AllStats:
    """Tüm deprem istatistiklerini içerir."""

    pga: PeakStats
    pgv: PeakStats
    pgd: PeakStats
    rms: RmsStats
    arias_intensity: AriasIntensity
    arias_a95: AriasAccelerationLevel
    significant_duration_5_95: SignificantDuration
    significant_duration_5_75: SignificantDuration
    significant_duration_2_5_97_5: SignificantDuration
    cav: CavStats
    cavstd: CavStats
    record_info: RecordInfo
    sampling_info: SamplingInfo

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    # Testlerde sözlük benzeri erişim kullanıldığı için destekleyelim
    def __getitem__(self, key: str):
        return getattr(self, key)


class EarthquakeStats:
    """Deprem kaydı istatistik hesaplamaları sınıfı"""
    class _DictLikeView:
        """Dataclass sonuçlarını hem attribute hem de ['key'] ile erişilebilir kılan sarmalayıcı.

        alias_map: dış anahtarları gerçek dataclass alan adlarına eşler.
        """

        def __init__(self, obj: Any, alias_map: Optional[Dict[str, Any]] = None):
            self._obj = obj
            self._alias = alias_map or {}

        def __getitem__(self, key: str) -> Any:
            mapped = self._alias.get(key, key)
            if isinstance(mapped, str):
                return getattr(self._obj, mapped) if isinstance(mapped, str) else mapped(self._obj)

        def __getattr__(self, name: str) -> Any:
            return getattr(self._obj, name)

        def to_dict(self) -> Dict[str, Any]:
            return asdict(self._obj)

    @staticmethod
    def _wrap(obj: Any, alias_map: Optional[Dict[str, Any]] = None) -> Any:
        return EarthquakeStats._DictLikeView(obj, alias_map)

    @staticmethod
    def _peak_alias(prefix: str) -> Dict[str, str]:
        return {
            f"{prefix}_abs": "peak_abs",
            f"{prefix}_pos": "peak_pos",
            f"{prefix}_neg": "peak_neg",
            "t_peak_abs": "t_peak_abs",
            "t_peak_pos": "t_peak_pos",
            "t_peak_neg": "t_peak_neg",
            "idx_peak_abs": "idx_peak_abs",
            "idx_peak_pos": "idx_peak_pos",
            "idx_peak_neg": "idx_peak_neg",
            "unit": "unit",
            "valid_samples": "valid_samples",
        }
    
    # Diagnostics helper: SRSS vs Sum consistency notes
    @staticmethod
    def arias_quick_diagnostics(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g') -> Dict[str, Any]:
        """Quick diagnostics to flag common mistakes in two-horizontal Arias computations."""
        ax = np.asarray(ax, dtype=float)
        ay = np.asarray(ay, dtype=float)
        ia_sum = EarthquakeStats.arias_two_horizontal_sum(ax, ay, dt, unit)
        ia_srss = EarthquakeStats.arias_two_horizontal_srss(ax, ay, dt, unit)
        notes: list[str] = []
        if np.isfinite(ia_sum) and np.isfinite(ia_srss):
            if ia_srss < 0.95 * ia_sum:
                notes.append("RMS yerine SRSS kullanılıyor olabilir (√(ax²+ay²)/√2 ölçeği)")
            if not np.isclose(ia_sum, ia_srss, rtol=1e-4, atol=1e-6):
                notes.append("Sıra/normalizasyon hatası: karele→topla→entegre uygulanmalı")
        else:
            notes.append("Birim/dt/sinyal geçersiz: IA hesapları sonlu değil")
        return {
            "IA_sum": float(ia_sum),
            "IA_srss": float(ia_srss),
            "ok": bool(np.isclose(ia_sum, ia_srss, rtol=1e-4, atol=1e-6)),
            "notes": "; ".join(notes) if notes else "OK",
        }
    
    # Standart yerçekimi ivmesi (SI birimi)
    G_STANDARD = 9.80665  # m/s²  9.80665
    
    @staticmethod
    def _convert_acceleration_to_ms2(acceleration: np.ndarray, unit: str) -> np.ndarray:
        """
        İvmeyi m/s² birimine çevirir
        
        Args:
            acceleration: İvme zaman serisi
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²')
            
        Returns:
            np.ndarray: m/s² cinsinden ivme

        Raises:
            ValueError: Desteklenmeyen birim girildiğinde
        """
        factors = {
            'g': EarthquakeStats.G_STANDARD,
            'm/s²': 1.0,
            'cm/s²': 0.01,
            'mm/s²': 0.001,
        }
        try:
            factor = factors[unit]
        except KeyError as exc:
            raise ValueError(f"Unsupported acceleration unit: {unit}") from exc
        return acceleration * factor
    
    @staticmethod
    def _convert_acceleration_to_g(acceleration: np.ndarray, unit: str) -> np.ndarray:
        """
        İvmeyi g birimine çevirir
        
        Args:
            acceleration: İvme zaman serisi
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²')
            
        Returns:
            np.ndarray: g cinsinden ivme

        Raises:
            ValueError: Desteklenmeyen birim girildiğinde
        """
        factors = {
            'g': 1.0,
            'm/s²': 1.0 / EarthquakeStats.G_STANDARD,
            'cm/s²': 0.01 / EarthquakeStats.G_STANDARD,
            'mm/s²': 0.001 / EarthquakeStats.G_STANDARD,
        }
        try:
            factor = factors[unit]
        except KeyError as exc:
            raise ValueError(f"Unsupported acceleration unit: {unit}") from exc
        return acceleration * factor
    
    @staticmethod
    def _convert_ms2_to_unit(acceleration_ms2: np.ndarray, unit: str) -> np.ndarray:
        if unit is None:
            raise ValueError("Acceleration unit cannot be None")
        normalized = (
            unit.replace('^2', '²')
                .replace('�', '²')
                .strip()
        )
        factors = {
            'g': 1.0 / EarthquakeStats.G_STANDARD,
            'm/s²': 1.0,
            'cm/s²': 100.0,
            'mm/s²': 1000.0,
        }
        # Bazı eski parametreler kare işaretini içermeyebiliyor
        fallback = {
            'm/s': 1.0,
            'cm/s': 100.0,
            'mm/s': 1000.0,
        }
        factor = factors.get(normalized)
        if factor is None:
            factor = fallback.get(normalized)
        if factor is None:
            raise ValueError(f"Unsupported acceleration unit: {unit}")
        return acceleration_ms2 * factor
    
    @staticmethod
    def _convert_cav_to_si(cav_value: float, unit: str) -> float:
        """
        CAV değerini SI birimine (m/s) çevirir
        
        Args:
            cav_value: CAV değeri
            unit: İvme birimi
            
        Returns:
            float: m/s cinsinden CAV değeri

        Raises:
            ValueError: Desteklenmeyen birim girildiğinde
        """
        factors = {
            'g': EarthquakeStats.G_STANDARD,
            'm/s²': 1.0,
            'cm/s²': 0.01,
            'mm/s²': 0.001,
        }
        try:
            factor = factors[unit]
        except KeyError as exc:
            raise ValueError(f"Unsupported acceleration unit: {unit}") from exc
        return cav_value * factor

    @staticmethod
    def _calculate_peak_stats(data: np.ndarray, dt: float, unit: str) -> PeakStats:
        """Genel pik değerleri hesaplayıcı."""

        if dt <= 0:
            raise ValueError("dt must be positive")

        arr = np.asarray(data, dtype=float)
        finite_mask = np.isfinite(arr)

        if len(arr) == 0 or not np.any(finite_mask):
            return PeakStats(
                peak_abs=np.nan,
                peak_pos=np.nan,
                peak_neg=np.nan,
                t_peak_abs=np.nan,
                t_peak_pos=np.nan,
                t_peak_neg=np.nan,
                idx_peak_abs=-1,
                idx_peak_pos=-1,
                idx_peak_neg=-1,
                unit=unit,
                valid_samples=0,
            )

        time_array = np.arange(len(arr)) * dt
        clean_data = np.where(finite_mask, arr, np.nan)
        abs_data = np.abs(clean_data)

        idx_abs = np.nanargmax(abs_data)
        idx_pos = np.nanargmax(clean_data)
        idx_neg = np.nanargmin(clean_data)

        return PeakStats(
            peak_abs=abs_data[idx_abs],
            peak_pos=clean_data[idx_pos],
            peak_neg=clean_data[idx_neg],
            t_peak_abs=time_array[idx_abs],
            t_peak_pos=time_array[idx_pos],
            t_peak_neg=time_array[idx_neg],
            idx_peak_abs=idx_abs,
            idx_peak_pos=idx_pos,
            idx_peak_neg=idx_neg,
            unit=unit,
            valid_samples=int(np.sum(finite_mask)),
        )
    
    @staticmethod
    def calculate_pga(acceleration: np.ndarray, dt: float = 0.01, unit: str = 'g') -> Any:
        """
        Peak Ground Acceleration (PGA) hesaplar

        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²')

        Returns:
            Peak benzeri obje: ps.pga_abs veya ps['pga_abs'] ile erişilebilir
        """
        ps = EarthquakeStats._calculate_peak_stats(acceleration, dt, unit)
        return EarthquakeStats._wrap(ps, EarthquakeStats._peak_alias("pga"))
    
    @staticmethod
    def calculate_pgv(velocity: np.ndarray, dt: float = 0.01, unit: str = 'cm/s') -> Any:
        """
        Peak Ground Velocity (PGV) hesaplar

        Args:
            velocity: Hız zaman serisi
            dt: Zaman adımı (saniye)
            unit: Hız birimi ('m/s', 'cm/s', 'mm/s')

        Returns:
            Peak benzeri obje: ps.pgv_abs veya ps['pgv_abs'] ile erişilebilir
        """
        ps = EarthquakeStats._calculate_peak_stats(velocity, dt, unit)
        return EarthquakeStats._wrap(ps, EarthquakeStats._peak_alias("pgv"))
    
    @staticmethod
    def calculate_pgd(displacement: np.ndarray, dt: float = 0.01, unit: str = 'cm') -> Any:
        """
        Peak Ground Displacement (PGD) hesaplar

        Args:
            displacement: Yerdeğiştirme zaman serisi
            dt: Zaman adımı (saniye)
            unit: Yerdeğiştirme birimi ('m', 'cm', 'mm')

        Returns:
            Peak benzeri obje: ps.pgd_abs veya ps['pgd_abs'] ile erişilebilir
        """
        ps = EarthquakeStats._calculate_peak_stats(displacement, dt, unit)
        return EarthquakeStats._wrap(ps, EarthquakeStats._peak_alias("pgd"))
    
    @staticmethod
    def calculate_rms(data: np.ndarray) -> float:
        """
        Root Mean Square (RMS) hesaplar
        
        Args:
            data: Zaman serisi verisi
            
        Returns:
            float: RMS değeri
        """
        # Veriyi float diziye dönüştür ve NaN/Inf kontrolü yap
        clean_data = np.asarray(data, dtype=float)
        finite_mask = np.isfinite(clean_data)
        
        if len(clean_data) == 0 or not np.any(finite_mask):
            return np.nan
        
        # Sadece geçerli değerleri kullan
        valid_data = clean_data[finite_mask]
        return np.sqrt(np.mean(valid_data**2))
    
    @staticmethod
    def calculate_arias_intensity(acceleration: np.ndarray, dt: float, unit: str = 'g') -> Any:
        """Toplam Arias Intensity hesaplar.
        
        PEER/PGMD Formülü:
        I_A = (π/2g) * ∫[0,T] a²(t) dt
        
        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²')
            
        Returns:
            AriasIntensity: arias_intensity (m/s), unit, valid_samples
            
        References:
            Arias (1970), PEER/PGMD
        """
        # Veriyi float diziye dönüştür ve NaN/Inf kontrolü yap
        accel = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(accel)

        if len(accel) == 0 or not np.any(finite_mask):
            return EarthquakeStats._wrap(AriasIntensity(arias_intensity=np.nan, unit='m/s', valid_samples=0))
        
        # İvmeyi m/s² birimine çevir
        accel_ms2 = EarthquakeStats._convert_acceleration_to_ms2(accel, unit)
        
        # NaN değerleri sıfırla (trapz için)
        accel_ms2_clean = np.where(np.isfinite(accel_ms2), accel_ms2, 0.0)
        
        # Arias Intensity = (π/2g) * ∫ a²(t) dt
        integral = np.trapezoid(accel_ms2_clean**2, dx=dt)
        arias_intensity = (np.pi / (2 * EarthquakeStats.G_STANDARD)) * integral
        
        return EarthquakeStats._wrap(AriasIntensity(
            arias_intensity=arias_intensity,
            unit='m/s',
            valid_samples=int(np.sum(finite_mask)),
        ))

    @staticmethod
    def calculate_a95_level(acceleration: np.ndarray, unit: str = 'g', percentile: float = 95.0) -> Any:
        """Arias katkılarının %percentile'ini oluşturan ivme eşiğini döndürür."""
        if percentile <= 0 or percentile > 100:
            raise ValueError("percentile must be in the (0, 100] range")

        accel = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(accel)
        valid_samples = int(np.sum(finite_mask))

        if valid_samples == 0:
            out = AriasAccelerationLevel(
                value=np.nan,
                percentile=percentile,
                unit=unit,
                valid_samples=0,
            )
            return EarthquakeStats._wrap(out)

        accel_ms2 = EarthquakeStats._convert_acceleration_to_ms2(accel[finite_mask], unit)
        abs_acc = np.abs(accel_ms2)
        weights = abs_acc**2
        total_weight = float(np.sum(weights))

        if total_weight <= 0.0:
            threshold_ms2 = 0.0
        else:
            order = np.argsort(abs_acc)
            abs_sorted = abs_acc[order]
            weights_sorted = weights[order]
            cumulative = np.cumsum(weights_sorted)
            target = (percentile / 100.0) * total_weight
            idx = int(np.searchsorted(cumulative, target, side='left'))
            if idx >= len(abs_sorted):
                idx = len(abs_sorted) - 1
            threshold_ms2 = float(abs_sorted[idx])

        level_value = float(EarthquakeStats._convert_ms2_to_unit(threshold_ms2, unit))
        out = AriasAccelerationLevel(
            value=level_value,
            percentile=percentile,
            unit=unit,
            valid_samples=valid_samples,
        )
        return EarthquakeStats._wrap(out)

    # --- Two-horizontal Arias helpers (SRSS equivalence) ---
    @staticmethod
    def _arias_intensity_ms2(acc_ms2: np.ndarray, dt: float) -> float:
        """Internal: Arias intensity for an array already in m/s²."""
        if dt <= 0:
            raise ValueError("dt must be positive")
        a2 = acc_ms2.astype(float)**2
        integral = np.trapezoid(a2, dx=dt)
        return float((np.pi / (2 * EarthquakeStats.G_STANDARD)) * integral)

    @staticmethod
    def arias_two_horizontal_sum(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g') -> float:
        """IA_2H via component-wise sum: IA_x + IA_y (m/s)."""
        ax_ms2 = EarthquakeStats._convert_acceleration_to_ms2(np.asarray(ax, dtype=float), unit)
        ay_ms2 = EarthquakeStats._convert_acceleration_to_ms2(np.asarray(ay, dtype=float), unit)
        return EarthquakeStats._arias_intensity_ms2(ax_ms2, dt) + EarthquakeStats._arias_intensity_ms2(ay_ms2, dt)

    @staticmethod
    def arias_two_horizontal_srss(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g') -> float:
        """IA from SRSS time series: IA_SRSS = ∫(sqrt(ax²+ay²))² dt = ∫(ax²+ay²) dt (m/s)."""
        ax_ms2 = EarthquakeStats._convert_acceleration_to_ms2(np.asarray(ax, dtype=float), unit)
        ay_ms2 = EarthquakeStats._convert_acceleration_to_ms2(np.asarray(ay, dtype=float), unit)
        asrss = np.sqrt(ax_ms2**2 + ay_ms2**2)
        return EarthquakeStats._arias_intensity_ms2(asrss, dt)

    @staticmethod
    def arias_two_horizontal_check(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g', rtol: float = 1e-6, atol: float = 1e-6) -> float:
        """Assert IA_sum == IA_srss within tolerance; returns IA_total if OK."""
        ia_sum = EarthquakeStats.arias_two_horizontal_sum(ax, ay, dt, unit)
        ia_srss = EarthquakeStats.arias_two_horizontal_srss(ax, ay, dt, unit)
        if not np.isfinite(ia_sum) or not np.isfinite(ia_srss):
            raise AssertionError("IA_sum/IA_srss not finite; check units/dt/signal")
        if not np.isclose(ia_sum, ia_srss, rtol=rtol, atol=atol):
            raise AssertionError(f"SRSS vs sum mismatch: sum={ia_sum:.6g}, srss={ia_srss:.6g}")
        return ia_sum
    
    @staticmethod
    def calculate_arias_intensity_cumulative(
        acceleration: np.ndarray, 
        dt: float, 
        unit: str = 'g'
    ) -> Dict[str, Any]:
        """Kümülatif Arias Intensity hesaplar (PEER Algorithms §4 uyumlu).
        
        Zaman serisine göre I_A(t) değerlerini döndürür.
        Görselleştirme ve enerji birikimi analizi için kullanışlıdır.
        
        PEER Algorithms Formülü (§4, adım 3):
        I_A[0] = 0
        I_A[j] = Σ(i=0 to j-1) 0.5 * (a²[i] + a²[i+1]) * dt
        I_A(t) = (π/2g) * I_A[j]  (m/s² için)
        
        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi
            
        Returns:
            Dict: {
                'IA_cumulative': np.ndarray - Kümülatif I_A(t) dizisi (m/s),
                'IA_total': float - Toplam I_A (m/s),
                'E_normalized': np.ndarray - Normalize edilmiş E(t) = I_A(t)/I_A,tot,
                'time': np.ndarray - Zaman dizisi (saniye)
            }
            
        Examples:
            >>> result = EarthquakeStats.calculate_arias_intensity_cumulative(acc, dt, 'g')
            >>> plt.plot(result['time'], result['IA_cumulative'])
            >>> plt.axhline(result['IA_total'], label='Total')
            
        References:
            PEER Duration Algorithms §4
        """
        accel = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(accel)
        
        if len(accel) == 0 or not np.any(finite_mask):
            return {
                'IA_cumulative': np.array([np.nan]),
                'IA_total': np.nan,
                'E_normalized': np.array([np.nan]),
                'time': np.array([0.0])
            }
        
        # İvmeyi m/s² birimine çevir
        accel_ms2 = EarthquakeStats._convert_acceleration_to_ms2(accel, unit)
        
        # NaN değerleri sıfırla
        accel_ms2 = np.nan_to_num(accel_ms2, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Kümülatif trapezoid integral: E(t) = ∫[0,t] a²(τ) dτ
        e_squared = accel_ms2 ** 2
        E = EarthquakeStats._cumulative_trapezoid(e_squared, dt)
        
        # π/(2g) çarpanını uygula → I_A(t) (m/s)
        IA_cumulative = (np.pi / (2 * EarthquakeStats.G_STANDARD)) * E
        IA_total = float(IA_cumulative[-1])
        
        # Normalize edilmiş enerji: E(t) = I_A(t) / I_A,total
        if IA_total > 0:
            E_normalized = IA_cumulative / IA_total
        else:
            E_normalized = np.zeros_like(IA_cumulative)
        
        # Zaman dizisi
        time = np.arange(len(IA_cumulative)) * dt
        
        return {
            'IA_cumulative': IA_cumulative,
            'IA_total': IA_total,
            'E_normalized': E_normalized,
            'time': time,
            'unit': 'm/s',
            'valid_samples': int(np.sum(finite_mask))
        }

    # --- Arias Duration Measures (Bracketed, Uniform, Significant, Effective) ---
    @staticmethod
    def compute_duration_measures(
        acceleration: np.ndarray,
        dt: float,
        unit: str = 'g',
        *,
        threshold_mode: str = "relative_to_pga",  # 'relative_to_pga' | 'absolute' | 'absolute_g'
        k: float = 0.05,
        a0_abs: Optional[float] = None,
        percent_low: float = 0.05,
        percent_high: float = 0.95,
        AI_low_abs: Optional[float] = None,
        AI_high_abs: Optional[float] = None,
    ) -> Any:
        """Db, Du, Ds, De hesaplar ve AI(t), H(t) ile döndürür (spec uyumlu).

        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (s)
            unit: İvme birimi ('g','m/s²','cm/s²','mm/s²')
            threshold_mode: Bracketed/Uniform için eşik modu
            k: relative_to_pga için a0 = k * PGA (vars. 0.05)
            a0_abs: threshold_mode='absolute'/'absolute_g' için mutlak eşik
            percent_low/percent_high: Significant için [0,1] aralığında yüzdeler
            AI_low_abs/AI_high_abs: Effective için mutlak AI eşikleri (m/s)

        Returns:
            DurationMeasures sarmalayıcısı (wrap edilerek)
        """
        if dt <= 0:
            raise ValueError("dt must be positive")

        acc = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(acc)
        if acc.size == 0 or not np.any(finite_mask):
            empty = np.array([0.0])
            dm = DurationMeasures(Db=0.0, Du=0.0, Ds=0.0, De=0.0,
                                  t_db=None, t_ds=None, t_de=None,
                                  AI_tot=float('nan'), AI_cum=empty, H=empty)
            return EarthquakeStats._wrap(dm)

        # 1) SI'a çevir (m/s²) ve NaN temizle
        acc_ms2 = EarthquakeStats._convert_acceleration_to_ms2(acc, unit)
        acc_ms2 = np.nan_to_num(acc_ms2, nan=0.0, posinf=0.0, neginf=0.0)

        # 2) Kümülatif Arias ve Husid: mevcut güvenilir yordamı kullan
        ia_res = EarthquakeStats.calculate_arias_intensity_cumulative(acc, dt, unit)
        IA = np.asarray(ia_res.get('IA_cumulative', []), dtype=float)
        AI_tot = float(ia_res.get('IA_total', float('nan')))
        H = IA / AI_tot if (np.isfinite(AI_tot) and AI_tot > 0) else np.zeros_like(IA)
        t = np.arange(IA.size) * float(dt)

        # 3) Bracketed & Uniform eşik (m/s²)
        #    PGA m/s² cinsinden alınır
        pga_ms2 = float(np.max(np.abs(acc_ms2))) if acc_ms2.size else 0.0
        thr_mode = (threshold_mode or 'relative_to_pga').lower()
        if thr_mode in ("relative_to_pga", "relative"):
            a0_ms2 = k * pga_ms2
        elif thr_mode in ("absolute", "absolute_g"):
            if a0_abs is None:
                a0_ms2 = 0.05 * pga_ms2
            else:
                # a0_abs kullanıcının verdiği birimde olabilir → ms²'e çevir
                if thr_mode == "absolute_g":
                    a0_ms2 = float(a0_abs) * EarthquakeStats.G_STANDARD
                else:
                    # 'absolute' → a0_abs'ın 'unit' ile aynı birimde olduğu varsayımı
                    # unit'i kullanarak ms²'e çevir: ters yönde dönüştürücü yok, basit map kur
                    if unit == 'g':
                        a0_ms2 = float(a0_abs) * EarthquakeStats.G_STANDARD
                    elif unit == 'm/s²':
                        a0_ms2 = float(a0_abs)
                    elif unit == 'cm/s²':
                        a0_ms2 = float(a0_abs) * 0.01
                    elif unit == 'mm/s²':
                        a0_ms2 = float(a0_abs) * 0.001
                    else:
                        a0_ms2 = float(a0_abs)
        else:
            a0_ms2 = k * pga_ms2

        # 4) Bracketed (Db) ve Uniform (Du)
        mask = np.abs(acc_ms2) >= a0_ms2 if a0_ms2 > 0 else np.zeros_like(acc_ms2, dtype=bool)
        if mask.any():
            idx_first = int(np.argmax(mask))
            idx_last = int(mask.size - 1 - np.argmax(mask[::-1]))
            t1_db = float(idx_first * dt)
            t2_db = float(idx_last * dt)
            Db = float(max(0.0, t2_db - t1_db))
            t_db = (t1_db, t2_db)
            Du = float(mask.sum() * float(dt))
        else:
            Db, Du, t_db = 0.0, 0.0, None

        # 5) Significant (Ds) - percent_low/high [0,1]
        p1 = float(percent_low)
        p2 = float(percent_high)
        # Güvenli aralık ve mantık
        if not np.isfinite(AI_tot) or AI_tot <= 0 or not (0.0 <= p1 < p2 <= 1.0):
            Ds, t_ds = 0.0, None
        else:
            # EarthquakeStats.calculate_significant_duration 0-100 bekliyor
            d_obj = EarthquakeStats.calculate_significant_duration(acc, dt, p1*100.0, p2*100.0, unit)
            Ds = float(getattr(d_obj, 'duration', 0.0))
            try:
                t_ds = (float(getattr(d_obj, 'start_time', float('nan'))),
                        float(getattr(d_obj, 'end_time', float('nan'))))
            except Exception:
                t_ds = None

        # 6) Effective (De) - mutlak AI eşikleri (m/s)
        if not np.isfinite(AI_tot) or AI_tot <= 0:
            De, t_de = 0.0, None
        else:
            low = float(AI_low_abs) if (AI_low_abs is not None) else (p1 * AI_tot)
            high = float(AI_high_abs) if (AI_high_abs is not None) else (p2 * AI_tot)
            if low >= high:
                De, t_de = 0.0, None
            else:
                # İlk geçiş indeksleri (IA monoton değilse güvenlik için maksimum.accumulate uygulayalım)
                IA_mono = np.maximum.accumulate(IA)
                i1 = int(np.searchsorted(IA_mono, low, side='left'))
                i2 = int(np.searchsorted(IA_mono, high, side='left'))
                i1 = max(0, min(i1, IA_mono.size-1))
                i2 = max(0, min(i2, IA_mono.size-1))
                t1e = float(i1 * dt)
                t2e = float(i2 * dt)
                De = float(max(0.0, t2e - t1e))
                t_de = (t1e, t2e)

        dm = DurationMeasures(Db=Db, Du=Du, Ds=Ds, De=De,
                              t_db=t_db, t_ds=t_ds, t_de=t_de,
                              AI_tot=float(AI_tot), AI_cum=IA, H=H)
        return EarthquakeStats._wrap(dm)
    
    @staticmethod
    def _cumulative_trapezoid(e: np.ndarray, dt: float) -> np.ndarray:
        """
        PEER uyumlu kümülatif trapezoid integrali.
        
        E[0] = 0
        E[j] = Σ(i=0 to j-1) 0.5 * (e[i] + e[i+1]) * dt
        
        Args:
            e: Kare alınmış ivme dizisi (a²)
            dt: Zaman adımı
            
        Returns:
            np.ndarray: Kümülatif integral dizisi
        """
        if e.size < 2:
            return np.array([0.0])
        
        E = np.empty(e.size, dtype=float)
        E[0] = 0.0
        # Trapezoid kuralı: 0.5 * (e[i] + e[i+1]) * dt
        E[1:] = np.cumsum(0.5 * (e[:-1] + e[1:]) * dt)
        return E
    
    @staticmethod
    def _find_crossing_time(F: np.ndarray, dt: float, threshold: float) -> float:
        """
        PEER uyumlu eşik geçiş zamanı bulma (searchsorted + lineer interpolasyon).
        Sayısal kararlılığı artırmak için güçlendirilmiş versiyon.
        
        Args:
            F: Normalize kümülatif dizi [0, 1]
            dt: Zaman adımı
            threshold: Eşik değeri (örn. 0.05, 0.75, 0.95)
            
        Returns:
            float: Eşik geçiş zamanı (saniye)
        """
        # Binary search ile ilk geçiş indeksini bul
        idx = int(np.searchsorted(F, threshold, side="left"))
        
        # Sınır kontrolleri
        if idx == 0:
            return 0.0
        if idx >= F.size:
            return (F.size - 1) * dt
        
        # İnterpolasyon için noktaları ve zamanları al
        f_prev, f_curr = F[idx - 1], F[idx]
        t_prev = (idx - 1) * dt

        # Eşik tam olarak bir noktaya denk geliyorsa
        if f_curr == threshold:
            return idx * dt

        # Eşik tam olarak önceki noktaya denk geliyorsa
        if f_prev == threshold:
            return t_prev

        # Düz çizgi (plato) veya sayısal bir hatadan kaynaklanan
        # monoton olmama durumunu kontrol et
        if f_curr <= f_prev:
            return t_prev

        # Lineer interpolasyon: t = t1 + (y - y1) * (t2 - t1) / (y2 - y1)
        # Burada (t2 - t1) = dt
        t_interp = t_prev + (threshold - f_prev) * dt / (f_curr - f_prev)
        
        return float(t_interp)

    @staticmethod
    def calculate_significant_duration(
        acceleration: np.ndarray,
        dt: float,
        start_percent: float = 5.0,
        end_percent: float = 95.0,
        unit: str = 'g',
    ) -> Any:
        """PEER/PGMD uyumlu Significant Duration hesaplar (Arias Intensity bazlı).

        Bu fonksiyon PEER "Significant Duration" spesifikasyonuna tam uyumludur:
        - Cumulative trapezoid integrali (dikdörtgen yerine)
        - Monotonluk garantisi (np.maximum.accumulate)
        - Binary search (searchsorted) + lineer interpolasyon
        - Amplitüd değişmezliği (normalize edilmiş)

        Args:
            acceleration: İvme zaman serisi (tek bileşen: FN veya FP).
            dt: Zaman adımı (saniye).
            start_percent: Arias Intensity'nin başlangıç yüzdesi (varsayılan 5.0).
            end_percent: Arias Intensity'nin bitiş yüzdesi (varsayılan 95.0).
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²').

        Returns:
            SignificantDuration: Hesaplanan süre ve ilgili bilgiler.
            - duration: D = t_end - t_start (saniye)
            - start_time: t_start (saniye)
            - end_time: t_end (saniye)

        Raises:
            ValueError: start_percent >= end_percent olduğunda.

        Notes:
            - D5-75: start_percent=5.0, end_percent=75.0
            - D5-95: start_percent=5.0, end_percent=95.0
            - Süre amplitüd değişmezdir (10*a için aynı süre)
            - İki yatay bileşen için: Her bileşeni ayrı hesaplayın, 
              sonra MAX(D_FN, D_FP) veya MEAN(D_FN, D_FP) kullanın
            
        References:
            PEER/PGMD Significant Duration Specification v1.0
            
        Examples:
            >>> # Tek bileşen
            >>> result = EarthquakeStats.calculate_significant_duration(acc, dt, 5.0, 95.0, 'g')
            >>> print(f"D5-95: {result.duration:.3f} s")
            
            >>> # İki bileşen için özet
            >>> d_fn = EarthquakeStats.calculate_significant_duration(acc_fn, dt, 5.0, 95.0, 'g')
            >>> d_fp = EarthquakeStats.calculate_significant_duration(acc_fp, dt, 5.0, 95.0, 'g')
            >>> d_set = max(d_fn.duration, d_fp.duration)  # PEER önerisi: MAX
        """
        if start_percent >= end_percent:
            raise ValueError("start_percent must be less than end_percent")
        
        if dt <= 0:
            raise ValueError("dt must be positive")

        # Veriyi float diziye dönüştür ve NaN/Inf kontrolü yap
        accel = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(accel)
        
        if len(accel) == 0 or not np.any(finite_mask):
            return EarthquakeStats._wrap(SignificantDuration(
                duration=np.nan,
                start_time=np.nan,
                end_time=np.nan,
                start_percent=start_percent,
                end_percent=end_percent,
                valid_samples=0,
            ))
        
        # İvmeyi m/s² birimine çevir
        accel_ms2 = EarthquakeStats._convert_acceleration_to_ms2(accel, unit)
        
        # NaN değerleri sıfırla
        accel_ms2 = np.nan_to_num(accel_ms2, nan=0.0, posinf=0.0, neginf=0.0)
        
        # PEER uyumlu kümülatif trapezoid integral: E(t) = ∫[0,t] a²(τ) dτ
        e_squared = accel_ms2 ** 2
        E = EarthquakeStats._cumulative_trapezoid(e_squared, dt)
        
        # Toplam enerji
        E_total = float(E[-1])
        
        if not np.isfinite(E_total) or E_total <= 0.0:
            return EarthquakeStats._wrap(SignificantDuration(
                duration=np.nan,
                start_time=np.nan,
                end_time=np.nan,
                start_percent=start_percent,
                end_percent=end_percent,
                valid_samples=int(np.sum(finite_mask)),
            ))
        
        # Normalize: F(t) = E(t) / E(T_end) ∈ [0, 1]
        F = E / E_total
        
        # PEER gereksinimi: Monotonluğu garanti et (sayısal hatalar için)
        F = np.maximum.accumulate(F)
        
        # Eşik değerleri (yüzde → oran)
        p_start = start_percent / 100.0
        p_end = end_percent / 100.0
        
        # Geçiş zamanlarını bul (PEER searchsorted + interpolasyon)
        t_start = EarthquakeStats._find_crossing_time(F, dt, p_start)
        t_end = EarthquakeStats._find_crossing_time(F, dt, p_end)
        
        # Süre hesapla
        duration = t_end - t_start
        
        return EarthquakeStats._wrap(SignificantDuration(
            duration=duration,
            start_time=t_start,
            end_time=t_end,
            start_percent=start_percent,
            end_percent=end_percent,
            valid_samples=int(np.sum(finite_mask)),
        ))

    # --- Combined Husid and durations for two horizontals ---
    @staticmethod
    def husid_two_horizontal(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g', luf_hz: Optional[float] = None) -> Dict[str, Any]:
        """Return combined Husid H_2H(t) = [IAx(t)+IAy(t)] / [IAx(∞)+IAy(∞)].

        Args:
            ax: Birinci yatay ivme
            ay: İkinci yatay ivme
            dt: Zaman adımı (s)
            unit: İvme birimi
            luf_hz: Opsiyonel LUF kesim frekansı (Hz). Belirtilirse <LUF bileşenleri sıfırlanır.
        """
        ax = np.asarray(ax, dtype=float)
        ay = np.asarray(ay, dtype=float)
        ax_ms2 = EarthquakeStats._convert_acceleration_to_ms2(ax, unit)
        ay_ms2 = EarthquakeStats._convert_acceleration_to_ms2(ay, unit)
        # LUF yüksek geçiren filtre (FFT ile sert kesim)
        if luf_hz is not None and np.isfinite(luf_hz) and (luf_hz > 0.0) and dt > 0:
            def _apply_hpf(sig_ms2: np.ndarray) -> np.ndarray:
                n = sig_ms2.size
                if n == 0:
                    return sig_ms2
                freqs = np.fft.rfftfreq(n, d=dt)
                spec = np.fft.rfft(sig_ms2)
                mask = freqs >= float(luf_hz)
                spec = spec * mask
                return np.fft.irfft(spec, n=n)
            ax_ms2 = _apply_hpf(ax_ms2)
            ay_ms2 = _apply_hpf(ay_ms2)
        # cumulative E(t) with trapezoid, then scale by π/(2g)
        e_x = EarthquakeStats._cumulative_trapezoid(ax_ms2**2, dt)
        e_y = EarthquakeStats._cumulative_trapezoid(ay_ms2**2, dt)
        ia_x = (np.pi / (2 * EarthquakeStats.G_STANDARD)) * e_x
        ia_y = (np.pi / (2 * EarthquakeStats.G_STANDARD)) * e_y
        ia_sum = ia_x + ia_y
        ia_tot = float(ia_sum[-1]) if ia_sum.size > 0 else np.nan
        H = ia_sum / ia_tot if np.isfinite(ia_tot) and ia_tot > 0 else np.zeros_like(ia_sum)
        t = np.arange(len(H)) * dt
        return {"H": H, "time": t, "IA_total": ia_tot, "valid_samples": len(H)}

    @staticmethod
    def duration_two_horizontal(ax: np.ndarray, ay: np.ndarray, dt: float, start_percent: float = 5.0, end_percent: float = 95.0, unit: str = 'g', luf_hz: Optional[float] = None) -> Any:
        """Duration from combined Husid of two horizontals (returns SignificantDuration)."""
        res = EarthquakeStats.husid_two_horizontal(ax, ay, dt, unit, luf_hz)
        H = np.maximum.accumulate(np.asarray(res["H"], dtype=float))
        
        if len(H) == 0 or not np.any(np.isfinite(H)):
            return EarthquakeStats._wrap(SignificantDuration(
                duration=np.nan, start_time=np.nan, end_time=np.nan,
                start_percent=start_percent, end_percent=end_percent,
                valid_samples=0
            ))
            
        p_start = float(start_percent) / 100.0
        p_end = float(end_percent) / 100.0
        t_start = EarthquakeStats._find_crossing_time(H, dt, p_start)
        t_end = EarthquakeStats._find_crossing_time(H, dt, p_end)
        
        return EarthquakeStats._wrap(SignificantDuration(
            duration=float(t_end - t_start),
            start_time=float(t_start),
            end_time=float(t_end),
            start_percent=float(start_percent),
            end_percent=float(end_percent),
            valid_samples=int(res["valid_samples"]),
        ))

    # --- D5-95 detailed analysis helpers ---
    @staticmethod
    def d95_two_horizontal_srss(ax: np.ndarray, ay: np.ndarray, dt: float, unit: str = 'g') -> Any:
        """Return SignificantDuration for D5-95 using SRSS time-series path (equivalent)."""
        acc_vector = np.sqrt(np.asarray(ax, dtype=float)**2 + np.asarray(ay, dtype=float)**2)
        return EarthquakeStats.calculate_significant_duration(acc_vector, dt, 5.0, 95.0, unit)

    # --- PUBLIC-FACING PEER DURATION CALCULATION ---
    @staticmethod
    def calculate_d5_95_peer(acc_horizontal_1: np.ndarray, acc_horizontal_2: np.ndarray, dt: float, unit: str = 'g', luf_hz: Optional[float] = None) -> Any:
        """
        İki yatay bileşen için PEER standardına tam uyumlu D5-95 (Significant Duration) hesaplar.
        
        Bu metot, PEER tarafından önerilen ve _SearchResults.csv dosyasındaki değerlerle 
        tam uyumluluk sağlayan "birleşik Husid eğrisi" yöntemini kullanır. Yöntem şu adımları izler:
        1. Her iki yatay bileşen (örn. FN ve FP) için ayrı ayrı kümülatif Arias Intensity (IA)
           zaman serileri (IA_x(t) ve IA_y(t)) hesaplanır.
        2. Bu iki seri toplanarak birleşik bir kümülatif enerji serisi oluşturulur: IA_sum(t) = IA_x(t) + IA_y(t).
        3. Bu birleşik seri, toplam enerjiye (IA_sum(T_end)) normalize edilerek birleşik Husid
           eğrisi H(t) elde edilir.
        4. H(t) eğrisinin %5 ve %95 değerlerine ulaştığı zamanlar (t_start ve t_end) lineer
           interpolasyon ile bulunur.
        5. D5-95 süresi, D = t_end - t_start olarak hesaplanır.
        
        Bu yaklaşım, SRSS (vektör toplamı) zaman serisi üzerinden hesaplama ile matematiksel 
        olarak eşdeğerdir ancak PEER dokümantasyonundaki metodolojiyi doğrudan yansıtır.
        
        Args:
            acc_horizontal_1: Birinci yatay (örn. Fault-Normal) ivme zaman serisi.
            acc_horizontal_2: İkinci yatay (örn. Fault-Parallel) ivme zaman serisi.
            dt: Zaman adımı (saniye).
            unit: İvme birimi ('g', 'm/s²', 'cm/s²', 'mm/s²').
            
        Returns:
            SignificantDuration: Hesaplanan süre ve ilgili bilgiler.
        """
        # PEER standardını en doğru şekilde yansıtan birleşik Husid yöntemini çağır.
        return EarthquakeStats.duration_two_horizontal(
            acc_horizontal_1, acc_horizontal_2, dt, 5.0, 95.0, unit, luf_hz
        )

    @staticmethod
    def calculate_d5_75_peer(acc_horizontal_1: np.ndarray, acc_horizontal_2: np.ndarray, dt: float, unit: str = 'g', luf_hz: Optional[float] = None) -> Any:
        """PEER uyumlu D5-75 (iki yatay, birleşik Husid + opsiyonel LUF yüksek geçiren)."""
        return EarthquakeStats.duration_two_horizontal(
            acc_horizontal_1, acc_horizontal_2, dt, 5.0, 75.0, unit, luf_hz
        )
    
    @staticmethod
    def calculate_D5_75(acceleration: np.ndarray, dt: float, unit: str = 'g') -> Any:
        """
        PEER D5-75 (5%-75% significant duration) hesaplar.
        
        Kolaylık fonksiyonu: calculate_significant_duration(acc, dt, 5.0, 75.0, unit)
        
        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi
            
        Returns:
            SignificantDuration: duration, start_time, end_time
            
        Examples:
            >>> result = EarthquakeStats.calculate_D5_75(acc, dt, 'g')
            >>> print(f"D5-75: {result.duration:.3f} s")
        """
        return EarthquakeStats.calculate_significant_duration(acceleration, dt, 5.0, 75.0, unit)
    
    @staticmethod
    def calculate_D5_95(acceleration: np.ndarray, dt: float, unit: str = 'g') -> Any:
        """
        PEER D5-95 (5%-95% significant duration) hesaplar.
        
        Kolaylık fonksiyonu: calculate_significant_duration(acc, dt, 5.0, 95.0, unit)
        
        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi
            
        Returns:
            SignificantDuration: duration, start_time, end_time
            
        Examples:
            >>> result = EarthquakeStats.calculate_D5_95(acc, dt, 'g')
            >>> print(f"D5-95: {result.duration:.3f} s")
        """
        return EarthquakeStats.calculate_significant_duration(acceleration, dt, 5.0, 95.0, unit)
    
    @staticmethod
    def calculate_duration_two_components(
        acc_fn: np.ndarray, 
        acc_fp: np.ndarray, 
        dt: float,
        start_percent: float = 5.0,
        end_percent: float = 95.0,
        unit: str = 'g',
        summary_method: str = 'max'
    ) -> Dict[str, Any]:
        """
        İki yatay bileşen (FN & FP) için significant duration hesaplar.
        
        PEER önerisi: Her bileşen ayrı hesaplanır, özet için MAX kullanılır.
        
        Args:
            acc_fn: Fault-Normal ivme zaman serisi
            acc_fp: Fault-Parallel ivme zaman serisi
            dt: Zaman adımı (saniye)
            start_percent: Başlangıç yüzdesi (varsayılan 5.0)
            end_percent: Bitiş yüzdesi (varsayılan 95.0)
            unit: İvme birimi
            summary_method: 'max' (önerilen), 'mean', veya 'vector_sum' (PEER uyumlu)
            
        Returns:
            Dict: {
                'fn': SignificantDuration,
                'fp': SignificantDuration,
                'summary': float (özet süre),
                'method': str
            }
            
        Examples:
            >>> result = EarthquakeStats.calculate_duration_two_components(
            ...     acc_fn, acc_fp, dt, 5.0, 95.0, 'g', 'vector_sum'
            ... )
            >>> print(f"Set (PEER): {result['summary']:.3f} s")
        """
        # Her bileşen için ayrı hesapla
        d_fn = EarthquakeStats.calculate_significant_duration(
            acc_fn, dt, start_percent, end_percent, unit
        )
        d_fp = EarthquakeStats.calculate_significant_duration(
            acc_fp, dt, start_percent, end_percent, unit
        )
        
        # Özet hesapla
        if summary_method == 'max':
            # PEER önerisi: MAX(FN, FP)
            summary = max(d_fn.duration, d_fp.duration)
        elif summary_method == 'mean':
            # Alternatif: MEAN(FN, FP)
            summary = (d_fn.duration + d_fp.duration) / 2.0
        elif summary_method == 'vector_sum':
            # Vektör toplamı üzerinden (PEER uyumlu)
            d_vector = EarthquakeStats.duration_two_horizontal(
                acc_fn, acc_fp, dt, start_percent, end_percent, unit
            )
            summary = d_vector.duration
        else:
            raise ValueError(f"Geçersiz summary_method: {summary_method}. 'max', 'mean', veya 'vector_sum' kullanın.")
        
        return {
            'fn': d_fn,
            'fp': d_fp,
            'summary': summary,
            'method': summary_method
        }
    
    @staticmethod
    def calculate_cav(acceleration: np.ndarray, dt: float, unit: str = 'g',
                     standardize: bool = False, threshold_g: float = 0.025) -> Any:
        """Cumulative Absolute Velocity (CAV) hesaplar

        Args:
            acceleration: İvme zaman serisi
            dt: Zaman adımı (saniye)
            unit: İvme birimi
            standardize: CAVstd (CAV5) hesaplama modu (varsayılan False)
            threshold_g: CAVstd için eşik değeri (g cinsinden, varsayılan 0.025)

        Returns:
            CavStats: CAV değeri ve bilgileri

        Notes:
            - Standart CAV: ∫ |a(t)| dt
            - CAVstd (CAV5): 1-s pencerelerinde threshold_g eşiğini aşan kısımların toplamı
            - Hasar eşiği referansı: ~0.16 g·s (nükleer/altyapı uygulamaları)
        """
        # Veriyi float diziye dönüştür ve NaN/Inf kontrolü yap
        accel = np.asarray(acceleration, dtype=float)
        finite_mask = np.isfinite(accel)

        if dt <= 0:
            raise ValueError("dt must be positive")

        if len(accel) == 0 or not np.any(finite_mask):
            out = CavStats(
                value=np.nan,
                value_si=np.nan,
                unit=f'{unit}·s',
                unit_si='m/s',
                type='CAVstd' if standardize else 'CAV',
                valid_samples=0,
            )
            return EarthquakeStats._wrap(out, {"cav": "value", "cav_si": "value_si"})
        
        if not standardize:
            # Standart CAV = ∫ |a(t)| dt
            # NaN değerleri sıfırla (trapz için)
            accel_clean = np.where(np.isfinite(accel), accel, 0.0)
            cav_input_units = np.trapezoid(np.abs(accel_clean), dx=dt)
            
            # SI birimine çevir (m/s)
            cav_si = EarthquakeStats._convert_cav_to_si(cav_input_units, unit)
            
            out = CavStats(
                value=cav_input_units,
                value_si=cav_si,
                unit=f'{unit}·s',
                unit_si='m/s',
                type='CAV',
                valid_samples=int(np.sum(finite_mask)),
            )
            return EarthquakeStats._wrap(out, {"cav": "value", "cav_si": "value_si"})
        else:
            # CAVstd (CAV5) hesaplama
            # İvmeyi g birimine çevir (eşik karşılaştırması için)
            accel_g = EarthquakeStats._convert_acceleration_to_g(accel, unit)

            # NaN değerleri sıfırla
            accel_g_clean = np.where(np.isfinite(accel_g), accel_g, 0.0)
            accel_clean = np.where(np.isfinite(accel), accel, 0.0)

            # 1-saniyelik pencereleri vektörel olarak işleme
            window_size = max(1, int(1.0 / dt))  # 1 saniye = kaç örnek
            total_samples = len(accel_clean)
            pad = (-total_samples) % window_size

            if pad:
                accel_g_clean = np.pad(accel_g_clean, (0, pad), constant_values=0.0)
                accel_clean = np.pad(accel_clean, (0, pad), constant_values=0.0)

            windows_g = accel_g_clean.reshape(-1, window_size)
            windows_a = accel_clean.reshape(-1, window_size)

            max_abs = np.max(np.abs(windows_g), axis=1)
            window_cavs = np.trapezoid(np.abs(windows_a), dx=dt, axis=1)
            cavstd = window_cavs[max_abs >= threshold_g].sum()

            # CAVstd'yi SI birimine çevir (m/s)
            cavstd_si = EarthquakeStats._convert_cav_to_si(cavstd, unit)
            
            out = CavStats(
                value=cavstd,
                value_si=cavstd_si,
                unit=f'{unit}·s',
                unit_si='m/s',
                type='CAVstd',
                threshold_g=threshold_g,
                window_size_s=1.0,
                damage_threshold_reference=0.16,
                damage_threshold_reference_si=EarthquakeStats._convert_cav_to_si(0.16, 'g'),
                valid_samples=int(np.sum(finite_mask)),
            )
            return EarthquakeStats._wrap(out, {"cav": "value", "cav_si": "value_si"})
    
    # --- Kamusal dönüştürücü alias'ları (geriye dönük uyumlu) ---
    @staticmethod
    def convert_acceleration_to_ms2(acceleration: np.ndarray, unit: str) -> np.ndarray:
        """Kamusal alias: ivmeyi m/s² birimine çevirir (SI)."""
        return EarthquakeStats._convert_acceleration_to_ms2(acceleration, unit)
    
    @staticmethod
    def convert_acceleration_to_g(acceleration: np.ndarray, unit: str) -> np.ndarray:
        """Kamusal alias: ivmeyi g birimine çevirir."""
        return EarthquakeStats._convert_acceleration_to_g(acceleration, unit)
    
    @staticmethod
    def calculate_all_stats(time_data: np.ndarray, 
                          acceleration: np.ndarray, 
                          velocity: np.ndarray, 
                          displacement: np.ndarray,
                          accel_unit: str = 'g',
                          velocity_unit: str = 'cm/s',
                          displacement_unit: str = 'cm',
                          dt: Optional[float] = None) -> AllStats:
        """Tüm istatistikleri hesaplar.
        
        Args:
            time_data: Zaman serisi
            acceleration: İvme serisi
            velocity: Hız serisi
            displacement: Yerdeğiştirme serisi
            accel_unit: İvme birimi
            velocity_unit: Hız birimi
            displacement_unit: Yerdeğiştirme birimi
            dt: Zaman adımı (saniye). None ise time_data'dan hesaplanır.
            
        Returns:
            AllStats: Tüm istatistiksel sonuçlar
            
        Raises:
            ValueError: dt belirtilmemişse ve time_data geçersizse
        """
        # Zaman adımını belirle
        sampling_info: SamplingInfo
        
        if dt is not None:
            # Manuel dt verilmiş
            sampling_info = SamplingInfo(
                dt=dt,
                dt_source='manual',
                sampling_uniform=True,
                sampling_rate=1.0 / dt if dt > 0 else 0.0,
            )
        elif len(time_data) >= 2:
            # time_data'dan dt hesapla
            time_clean = np.asarray(time_data, dtype=float)
            finite_mask = np.isfinite(time_clean)
            
            if not np.any(finite_mask) or np.sum(finite_mask) < 2:
                raise ValueError("time_data geçersiz ve dt parametresi belirtilmemiş")
            
            valid_time = time_clean[finite_mask]
            if len(valid_time) < 2:
                raise ValueError("time_data'da yetersiz geçerli örnek ve dt parametresi belirtilmemiş")
            
            # Zaman farklarını hesapla
            time_diffs = np.diff(valid_time)
            dt_median = np.median(time_diffs)
            dt_std = np.std(time_diffs)
            
            # Tekdüzelik kontrolü (tolerans: median'ın %5'i)
            tolerance = abs(dt_median) * 0.05
            uniform_mask = np.abs(time_diffs - dt_median) <= tolerance
            uniformity_ratio = np.sum(uniform_mask) / len(time_diffs)
            is_uniform = uniformity_ratio >= 0.95  # %95 örnekleme tekdüzeliği
            
            dt = dt_median
            sampling_info = SamplingInfo(
                dt=dt,
                dt_source='calculated',
                sampling_uniform=is_uniform,
                sampling_rate=1.0 / dt if dt > 0 else 0.0,
                dt_median=dt_median,
                dt_std=dt_std,
                dt_min=float(np.min(time_diffs)),
                dt_max=float(np.max(time_diffs)),
                uniformity_ratio=uniformity_ratio,
                uniformity_tolerance=tolerance,
                total_duration=float(valid_time[-1] - valid_time[0]),
                valid_time_samples=len(valid_time),
            )
            
            if not is_uniform:
                print(f"⚠️ Örnekleme tekdüzeliği düşük: {uniformity_ratio:.1%} (dt_median={dt_median:.6f}s, std={dt_std:.6f}s)")
        else:
            raise ValueError("time_data yetersiz (< 2 örnek) ve dt parametresi belirtilmemiş")
        
        # Temel istatistikler (AllStats için dataclass versiyonları)
        pga_dc = EarthquakeStats._calculate_peak_stats(acceleration, dt, accel_unit)
        pgv_dc = EarthquakeStats._calculate_peak_stats(velocity, dt, velocity_unit)
        pgd_dc = EarthquakeStats._calculate_peak_stats(displacement, dt, displacement_unit)
        
        # RMS değerleri
        rms_accel = EarthquakeStats.calculate_rms(acceleration)
        rms_velocity = EarthquakeStats.calculate_rms(velocity)
        rms_displacement = EarthquakeStats.calculate_rms(displacement)
        rms_stats = RmsStats(
            acceleration=rms_accel,
            velocity=rms_velocity,
            displacement=rms_displacement,
            accel_unit=accel_unit,
            velocity_unit=velocity_unit,
            displacement_unit=displacement_unit,
        )
        
        # Gelişmiş istatistikler (dataclass'a dönüştür)
        arias_dict = EarthquakeStats.calculate_arias_intensity(acceleration, dt, accel_unit).to_dict()
        a95_dict = EarthquakeStats.calculate_a95_level(acceleration, unit=accel_unit).to_dict()
        duration_5_95_dict = EarthquakeStats.calculate_significant_duration(acceleration, dt, 5.0, 95.0, accel_unit).to_dict()
        duration_5_75_dict = EarthquakeStats.calculate_significant_duration(acceleration, dt, 5.0, 75.0, accel_unit).to_dict()
        duration_2_5_97_5_dict = EarthquakeStats.calculate_significant_duration(acceleration, dt, 2.5, 97.5, accel_unit).to_dict()
        cav_dict = EarthquakeStats.calculate_cav(acceleration, dt, accel_unit).to_dict()
        cavstd_dict = EarthquakeStats.calculate_cav(acceleration, dt, accel_unit, standardize=True).to_dict()
        
        # Kayıt bilgileri
        data_points = len(time_data)
        
        # Kayıt süresi: gerçek zaman aralığı (time[-1] - time[0])
        if sampling_info.total_duration is not None:
            record_length = sampling_info.total_duration
        else:
            time_clean = np.asarray(time_data, dtype=float)
            finite_mask = np.isfinite(time_clean)
            if np.any(finite_mask) and np.sum(finite_mask) >= 2:
                valid_time = time_clean[finite_mask]
                record_length = float(valid_time[-1] - valid_time[0])
            else:
                record_length = (data_points - 1) * dt if data_points > 1 else 0.0

        record_info = RecordInfo(
            length=record_length,
            data_points=data_points,
            sampling_rate=sampling_info.sampling_rate,
            time_step=dt,
        )

        return AllStats(
            pga=pga_dc,
            pgv=pgv_dc,
            pgd=pgd_dc,
            rms=rms_stats,
            arias_intensity=AriasIntensity(**arias_dict),
            arias_a95=AriasAccelerationLevel(**a95_dict),
            significant_duration_5_95=SignificantDuration(**duration_5_95_dict),
            significant_duration_5_75=SignificantDuration(**duration_5_75_dict),
            significant_duration_2_5_97_5=SignificantDuration(**duration_2_5_97_5_dict),
            cav=CavStats(**cav_dict),
            cavstd=CavStats(**cavstd_dict),
            record_info=record_info,
            sampling_info=sampling_info,
        )
