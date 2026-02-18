""" 
TBDY - 2018 BÖLÜM 2 - SPEKTRUM HESAPLAMA Modülü
------------------------------------------------

1) Yatay Elastik Tasarım Spektrumu ile Düşey Elastik Tasarım Spektrumu'nun hesaplanması kapsar.

"""

import numpy as np  # Sayısal hesaplamalar için temel kütüphane
import pandas as pd  # Sonuçların DataFrame formatında tutulması için
import warnings  # Kullanıcıya sınır değer uyarıları vermek için
from typing import Any, Dict, Optional, Tuple, Union  # Tip ipuçları
from numpy.typing import ArrayLike  # ``numpy`` benzeri dizi tipini belirtmek için

# TL ve Yerçekimi İvmesi bilgilerinin Constants.py dosyasından çağırılması
# Modül doğrudan çalıştırıldığında da bu değerlere erişebilmek için import denemesi yapılır
try:
    from ..config.constants import DEFAULT_TL, GRAVITY_CM
except ImportError:
    import sys, os
    # Üst dizini ``sys.path``'e ekleyip constants dosyasını arar
    sys.path.append(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    from config.constants import DEFAULT_TL, GRAVITY_CM

# Spektrum formüllerinde kullanılan katsayılar
COEFF_HORIZ_INTERCEPT = 0.4      # Yatay spektrum başlangıç katsayısı
COEFF_HORIZ_SLOPE = 0.6          # Yatay spektrum başlangıç bölgesi eğimi
COEFF_VERT_INTERCEPT = 0.32      # Düşey spektrum başlangıç katsayısı
COEFF_VERT_SLOPE = 0.48          # Düşey spektrum başlangıç bölgesi eğimi
COEFF_VERT_PLATEAU = 0.8         # Düşey spektrum plato katsayısı
COEFF_VERT_SD1_RATIO = 0.5       # Düşey spektrum için SD1/SDS oranı


class SpectrumCalculator:

    """TBDY‑2018'e göre spektrum hesaplama sınıfı."""
    
    @staticmethod
    def validate_inputs(SDS: float, SD1: float, TL: float) -> None:
        """Spektrum hesaplama parametrelerini doğrular.

        Parametreler:
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float): Geçiş periyodu (saniye)

        Hatalar:
            ValueError: Geçersiz parametre değerleri için
        """
        # Parametrelerin fiziksel anlamlılık kontrolü
        if SDS < 0:
            raise ValueError(f"SDS negatif olamaz: {SDS}")  # Negatif ivme katsayısı

        if SD1 < 0:
            raise ValueError(f"SD1 negatif olamaz: {SD1}")  # 1 saniye ivme katsayısı 

        if TL <= 0:
            raise ValueError(f"TL pozitif olmalı: {TL}")  # Geçiş periyodu sıfırdan büyük olmalı

        # SDS=0 uyarısı
        if SDS == 0:
            warnings.warn("SDS=0: Spektral ivme değerleri sıfır olacak", UserWarning)

        # SD1=0 uyarısı
        if SD1 == 0:
            warnings.warn("SD1=0: Bazı bölgelerde spektral ivme sıfır olacak", UserWarning)

    def compute_corner_periods(
        self, SDS: float, SD1: float, TL: float
    ) -> Tuple[float, float, float, float, float]:
        """Köşe periyotlarını hesaplar.

        Parametreler:
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float): Geçiş periyodu (saniye)

        Döndürür:
            Tuple[float, float, float, float, float]: ``TA``, ``TB``, ``T_AD``,
            ``T_BD`` ve ``T_LD``
        """

        TA = 0.2 * SD1 / SDS if SDS > 0 else 0.0
        TB = SD1 / SDS if SDS > 0 else 0.0
        T_AD = TA / 3.0
        T_BD = TB / 3.0
        T_LD = TL / 2.0
        return TA, TB, T_AD, T_BD, T_LD

    def _sanitize_period_array(
        self, T: ArrayLike, eps: float = 1e-15, tiny: float = 1e-10
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Dönem dizisini ``numpy`` array'e çevirip sıfıra yakın değerleri güvenli hale getirir.

        Negatif periyot değerleri fiziksel olarak anlamsızdır ve kabul edilmez.

        Parametreler:
            T (ArrayLike): Girdi periyot dizisi
            eps (float): Sıfır kontrolü için tolerans
            tiny (float): Sıfır değerlerin yerine geçecek küçük sayı

        Döndürür:
            Tuple[np.ndarray, np.ndarray, np.ndarray]: ``T_np``, ``zero_mask`` ve ``T_safe``

        Hatalar:
            ValueError: ``T`` içinde negatif değer bulunduğunda
        """
        T_np = np.asarray(T, dtype=np.float64)  # Girdiyi ``numpy`` dizisine çevir
        if np.any(T_np < 0):
            warnings.warn(
                "Negatif periyot değerleri tespit edildi ve 0.0'a kırpıldı.",
                RuntimeWarning,
                stacklevel=2,
            )
            T_np = np.where(T_np < 0, 0.0, T_np)
        zero_mask = np.isclose(T_np, 0.0, atol=eps)  # Sıfıra yakın periyotlar için maske oluştur
        T_safe = np.where(zero_mask, tiny, T_np)  # Sıfıra eşit değerlere küçük sabit ata
        return T_np, zero_mask, T_safe  # Orijinal dizi, sıfır maskesi ve güvenli dizi geri döndür

    # ---------------------------------------------------------------------
    # 1)  YATAY ELASTİK TASARIM SPEKTRUMUNUN OLUŞTURULMASI
    # ---------------------------------------------------------------------

    def calculate_horizontal_spectrum(
        self,
        T: ArrayLike,
        SDS: float,
        SD1: float,
        TL: float = DEFAULT_TL,
        return_period_arrays: bool = False,
    ) -> Union[
        Tuple[np.ndarray, float, float],
        Tuple[np.ndarray, float, float, np.ndarray, np.ndarray, np.ndarray],
    ]:
        """Yatay elastik tasarım spektrumunu hesaplar.

        Parametreler:
            T (ArrayLike): Periyot dizisi
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float, opsiyonel): Geçiş periyodu (saniye). Varsayılan ``DEFAULT_TL``.

        Döndürür:
            Union[Tuple[np.ndarray, float, float], Tuple[np.ndarray, float, float, np.ndarray, np.ndarray, np.ndarray]]:
                Spektral ivme değerleri, TA ve TB köşe periyotları ve
                ``return_period_arrays=True`` ise ``T_np``, ``zero_mask`` ve ``T_safe``
                dizileri.
        """

        # Girdi parametrelerini doğrula
        self.validate_inputs(SDS, SD1, TL)

        # Köşe periyotlarının hesaplanması (Denklem 2.3)
        TA, TB, _, _, _ = self.compute_corner_periods(SDS, SD1, TL)

        # Periyot dizisini güvenli hale getir ve sıfıra eşitleri maskele
        T, zero_mask, T_safe = self._sanitize_period_array(T)

        # Bölme işlemlerini güvenli hata yönetimi ile yap
        with np.errstate(divide='ignore', invalid='ignore'):
            # T > TL bölgesi: SD1 * TL / T² (azalan bölge)
            sae_T = SD1 * TL / (T_safe ** 2)

            # T_B < T ≤ TL bölgesi: SD1 / T (1/T davranışı)
            mask_region3 = (T > TB) & (T <= TL)
            sae_T = np.where(mask_region3, SD1 / T_safe, sae_T)

        # TA < T ≤ TB bölgesi: SDS (sabite yakın plato)
        mask_region2 = (T > TA) & (T <= TB)
        sae_T = np.where(mask_region2, SDS, sae_T)

        # 0 ≤ T ≤ TA bölgesi: (COEFF_HORIZ_INTERCEPT + COEFF_HORIZ_SLOPE * T/TA) * SDS (doğrusal artış)
        mask_region1 = T <= TA
        if TA > 0:
            region1_values = (
                COEFF_HORIZ_INTERCEPT + COEFF_HORIZ_SLOPE * T / TA
            ) * SDS
        else:
            region1_values = SDS  # TA=0 durumu için fallback
        sae_T = np.where(mask_region1, region1_values, sae_T)

        # T≈0 özel durumu (Şekil 2.1'e göre)
        sae_T = np.where(zero_mask, COEFF_HORIZ_INTERCEPT * SDS, sae_T)

        # NaN/Inf değerleri temizle
        sae_T = np.where(np.isfinite(sae_T), sae_T, 0.0)

        if return_period_arrays:
            return sae_T, TA, TB, T, zero_mask, T_safe
        return sae_T, TA, TB  # Spektral ivme değerleri ve köşe periyotlar

    # ---------------------------------------------------------------------
    # 2)  DÜŞEY ELASTİK TASARIM SPEKTRUMUNUN OLUŞTURULMASI
    # ---------------------------------------------------------------------
    
    def calculate_vertical_spectrum(
        self,
        T: ArrayLike,
        SDS: float,
        SD1: Optional[float] = None,
        TL: float = DEFAULT_TL,
    ) -> Tuple[np.ndarray, float, float]:
        """Düşey elastik tasarım spektrumunu hesaplar.

        Parametreler:
            T (ArrayLike): Periyot dizisi
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (Optional[float]): 1 saniye periyot için tasarım spektral ivme katsayısı.
                ``None`` ise ``COEFF_VERT_SD1_RATIO * SDS`` alınır.
            TL (float, opsiyonel): Geçiş periyodu (saniye). Varsayılan ``DEFAULT_TL``.

        Döndürür:
            Tuple[np.ndarray, float, float]: Spektral ivme değerleri ve T_AD, T_BD köşe periyotları
        """

        if SD1 is None:
            SD1 = COEFF_VERT_SD1_RATIO * SDS  # Düşey spektrum için SD1 belirtilmediyse önerilen değer

        # Girdi parametrelerini doğrula
        self.validate_inputs(SDS, SD1, TL)

        # Yatay köşe periyotlarından düşey köşe periyotlarına geçiş
        _, _, T_AD, T_BD, T_LD = self.compute_corner_periods(SDS, SD1, TL)

        # Periyot dizisini güvenli hale getir
        T, zero_mask, T_safe = self._sanitize_period_array(T)

        # T > T_LD bölgesi: NaN (grafikte gösterilmez)
        saeD_T = np.full_like(T, np.nan)

        # Bölme işlemlerini güvenli hata yönetimi ile yap
        with np.errstate(divide='ignore', invalid='ignore'):
            # T_BD < T ≤ T_LD bölgesi: COEFF_VERT_PLATEAU * SDS * (T_BD / T)
            mask_region3 = (T > T_BD) & (T <= T_LD)
            saeD_T = np.where(
                mask_region3,
                COEFF_VERT_PLATEAU * SDS * (T_BD / T_safe),
                saeD_T,
            )

        # T_AD < T ≤ T_BD bölgesi: COEFF_VERT_PLATEAU * SDS (sabit plato)
        mask_region2 = (T > T_AD) & (T <= T_BD)
        saeD_T = np.where(mask_region2, COEFF_VERT_PLATEAU * SDS, saeD_T)

        # 0 ≤ T ≤ T_AD bölgesi: (COEFF_VERT_INTERCEPT + COEFF_VERT_SLOPE * T/T_AD) * SDS (doğrusal artış)
        mask_region1 = T <= T_AD
        if T_AD > 0:
            region1_values = (
                COEFF_VERT_INTERCEPT + COEFF_VERT_SLOPE * T / T_AD
            ) * SDS
        else:
            region1_values = COEFF_VERT_PLATEAU * SDS  # T_AD=0 durumu için fallback
        saeD_T = np.where(mask_region1, region1_values, saeD_T)

        # T≈0 özel durumu (Şekil 2.3'e göre)
        saeD_T = np.where(zero_mask, COEFF_VERT_INTERCEPT * SDS, saeD_T)

        # NaN olmayan değerleri temizle (sadece T > T_LD bölgesi NaN kalmalı)
        finite_mask = np.isfinite(saeD_T) | (T > T_LD)
        saeD_T = np.where(finite_mask, saeD_T, 0.0)
        
        return saeD_T, T_AD, T_BD  # Düşey spektral ivme ve köşe periyotları
    
    # ---------------------------------------------------------------------
    # 3)  YATAY ELASTİK TASARIM YERDEĞİŞTİRME SPEKTRUMUNUN OLUŞTURULMASI
    # ---------------------------------------------------------------------

    def calculate_displacement_spectrum(
        self, T: ArrayLike, SDS: float, SD1: float, TL: float = DEFAULT_TL
    ) -> Tuple[np.ndarray, float, float]:
        """Yatay elastik tasarım yerdeğiştirme spektrumunu hesaplar.

        Parametreler:
            T (ArrayLike): Periyot dizisi
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float, opsiyonel): Geçiş periyodu (saniye). Varsayılan ``DEFAULT_TL``.

        Döndürür:
            Tuple[np.ndarray, float, float]: Yerdeğiştirme değerleri ve TA, TB köşe periyotları
        """

        # Input validation (yatay spektrum çağrısında da yapılır ama güvenlik için)
        self.validate_inputs(SDS, SD1, TL)

        # Önce yatay spektrumu hesapla ve temizlenmiş periyot dizilerini al
        sae_T, TA, TB, T, zero_mask, T_safe = self.calculate_horizontal_spectrum(
            T, SDS, SD1, TL, return_period_arrays=True
        )

        # Denklem 2.4: Sde(T) = Sae(T) * g * (T/2π)²
        with np.errstate(divide='ignore', invalid='ignore'):
            sde_T = sae_T * GRAVITY_CM * (T_safe / (2 * np.pi)) ** 2

        # T≈0 durumunda yerdeğiştirme sıfır
        sde_T = np.where(zero_mask, 0.0, sde_T)

        # NaN/Inf değerleri temizle
        sde_T = np.where(np.isfinite(sde_T), sde_T, 0.0)
        
        return sde_T, TA, TB  # Yerdeğiştirme spektrumu ve yatay köşe periyotları

    # ---------------------------------------------------------------------
    # 4)  KÖŞE NOKTALARINI İÇEREN PERİYOT DİZİSİ
    # ---------------------------------------------------------------------

    def generate_period_array_optimized(
        self,
        SDS: float,
        SD1: float,
        TL: float = DEFAULT_TL,
        t_end: Optional[float] = None,
        use_geomspace: bool = True,
    ) -> np.ndarray:
        """Kritik köşe periyotlarını içeren optimize edilmiş periyot dizisi üretir.

        Parametreler:
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float): Geçiş periyodu (saniye)
            t_end (Optional[float]): Maksimum periyot değeri. ``None`` ise ``TL + 2.0``
            use_geomspace (bool): ``True`` ise 0–TA aralığı ``np.geomspace``
                ile logaritmik olarak örneklenir, ``False`` ise lineer ``np.linspace``
                kullanılır.

        Döndürür:
            np.ndarray: Optimize edilmiş periyot dizisi
        """
        
        if t_end is None:
            t_end = TL + 2.0  # Varsayılan olarak geçiş periyodunun biraz ötesine kadar örnekle

        # Köşe periyotları
        TA, TB, T_AD, T_BD, T_LD = self.compute_corner_periods(SDS, SD1, TL)

        # Bölgesel örnekleme stratejisi
        period_parts = []

        # Bölge 1: 0 ≤ T ≤ TA
        if TA > 0:
            if use_geomspace:
                start = max(TA / 1000, 1e-4)
                T_part1 = np.geomspace(start, TA, 1000, endpoint=False)
            else:
                T_part1 = np.linspace(0.0, TA, 1000, endpoint=False)
            period_parts.append(T_part1)

        # Bölge 2: TA < T ≤ TB (orta yoğunluk)
        if TB > TA:
            T_part2 = np.linspace(TA, TB, 600, endpoint=False)
            period_parts.append(T_part2)

        # Bölge 3: TB < T ≤ TL (yüksek yoğunluk, 1/T davranışı için)
        if TL > TB:
            T_part3 = np.linspace(TB, TL, 1500, endpoint=False)
            period_parts.append(T_part3)

        # Bölge 4: TL < T ≤ t_end (düşük yoğunluk, 1/T² davranışı)
        if t_end > TL:
            # Modal analiz için önemli periyotlar: 1-10s arası daha yoğun
            if t_end >= 10.0:
                T_part4a = np.linspace(TL, 10.0, 200, endpoint=False)
                T_part4b = np.linspace(10.0, t_end, 50, endpoint=True)
                T_part4 = np.concatenate((T_part4a, T_part4b))
            else:
                T_part4 = np.linspace(TL, t_end, 150, endpoint=True)
            period_parts.append(T_part4)

        # Tüm parçaları birleştir
        if period_parts:
            T_combined = np.concatenate(period_parts)
        else:
            T_combined = np.array([0.0])  # Hiçbir bölge oluşmadıysa sadece 0 periyodu

        # Kritik noktaları manuel ekle
        critical_points = [TA, TB, T_AD, T_BD, T_LD, 1.0, TL]
        # Modalanaliz için önemli periyotlar
        modal_points = [0.1, 0.2, 0.5, 2.0, 3.0, 5.0]

        all_critical = [p for p in critical_points + modal_points if 0 < p <= t_end]

        # Tüm noktaları birleştir ve sırala
        T_final = np.unique(np.concatenate((T_combined, all_critical, [0.0])))

        return T_final[T_final > 0]  # T=0 ve negatif değerleri filtrele (T=0 ayrıca eklenir)

    # ---------------------------------------------------------------------
    # 4-b)  TEKDÜZE LİNEER PERİYOT DİZİSİ (dT ile)
    # ---------------------------------------------------------------------
    def generate_period_array_linear(
        self,
        SDS: float,
        SD1: float,
        TL: float = DEFAULT_TL,
        t_end: Optional[float] = None,
        dT: float = 1e-4,
        snap_critical: bool = True,
        snap_mode: str = 'grid',
    ) -> np.ndarray:
        """0–``t_end`` aralığını tekdüze lineer adımlarla örnekler.

        Parametreler:
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float): Geçiş periyodu (saniye)
            t_end (Optional[float]): Maksimum periyot değeri. ``None`` ise ``TL + 2.0``
            dT (float): Lineer adım büyüklüğü
            snap_critical (bool): Köşe noktalarını en yakın ızgara noktasına oturt
            snap_mode (str): 'grid' veya 'exact'

        Döndürür:
            np.ndarray: Üretilen periyot dizisi
        """
        if t_end is None:
            t_end = TL + 2.0  # Varsayılan üst sınır
        if dT <= 0:
            raise ValueError("dT pozitif olmalı")  # Negatif veya sıfır adım olamaz

        T = np.arange(0.0, t_end + dT, dT, dtype=np.float64)  # Tekdüze adımlı periyot dizisi

        # Köşe noktaları
        TA, TB, T_AD, T_BD, T_LD = self.compute_corner_periods(SDS, SD1, TL)

        if snap_critical and snap_mode == 'exact':
            critical = [TA, TB, T_AD, T_BD, T_LD, 1.0, TL, 0.1, 0.2, 0.5, 2.0, 3.0, 5.0]
            nT = len(T)
            for p in critical:
                if 0.0 < p <= t_end:
                    j = int(round(p / dT))  # En yakın ızgara indeksine yuvarla
                    j = 0 if j < 0 else (nT - 1 if j >= nT else j)
                    T[j] = p  # Kritik noktayı dizide tam olarak temsil et
        # snap_mode='grid' ise ızgara bozulmaz

        T = np.clip(T, 0.0, t_end)
        T = np.unique(T)
        return T[T > 0]  # T=0 sonradan eklenecek

    # ---------------------------------------------------------------------
    # 5)  TÜM SPEKTRUMLARIN HESAPLANMASI
    # ---------------------------------------------------------------------
    def calculate_all_spectra(
        self,
        SDS: float,
        SD1: float,
        TL: float = DEFAULT_TL,
        include_horizontal: bool = True,
        include_vertical: bool = True,
        include_displacement: bool = False,
        t_end: Optional[float] = None,
        use_geomspace: bool = True,
        linear_step: Optional[float] = None,
        snap_critical: bool = True,
    ) -> Dict[str, Any]:
        """Yatay, düşey ve/veya yerdeğiştirme spektrumlarını döndürür.

        Parametreler:
            SDS (float): Kısa periyot tasarım spektral ivme katsayısı
            SD1 (float): 1 saniye periyot için tasarım spektral ivme katsayısı
            TL (float): Geçiş periyodu (saniye)
            include_horizontal (bool): Yatay spektrum dahil edilsin mi
            include_vertical (bool): Düşey spektrum dahil edilsin mi
            include_displacement (bool): Yerdeğiştirme spektrumu dahil edilsin mi
            t_end (Optional[float]): Maksimum periyot değeri. ``None`` ise ``TL + 2.0``
            use_geomspace (bool): Küçük periyotlarda logaritmik örnekleme kullan
            linear_step (Optional[float]): Tekdüze lineer adım (``generate_period_array_linear`` için)
            snap_critical (bool): Köşe noktaları ızgaraya oturtulsun mu

        Döndürür:
            Dict[str, Any]: DataFrame, periyot dizisi ve spektrum bilgilerini içeren sözlük
        """

        # Input validation
        self.validate_inputs(SDS, SD1, TL)

        # Tekdüze lineer dizi istenirse (dT verilmişse) onu kullan
        if linear_step is not None:
            T = self.generate_period_array_linear(SDS, SD1, TL, t_end, dT=linear_step, snap_critical=snap_critical)
        else:
            T = self.generate_period_array_optimized(SDS, SD1, TL, t_end, use_geomspace)
        T_full = np.insert(T, 0, 0.0)  # T = 0 dâhil

        df_dict, info, column_info, column_order = {}, {}, {}, []

        spectrum_specs = [
            {
                'include': include_horizontal,
                'key': 'horizontal',
                'column': 'Yatay Spektral İvme (g)',
                'unit': 'g',
                'description': 'Yatay elastik tasarım spektral ivmesi',
                'compute': lambda t: self.calculate_horizontal_spectrum(t, SDS, SD1, TL),
                'zero_value': COEFF_HORIZ_INTERCEPT * SDS,
                'meta': lambda ta, tb: {
                    'TA': ta,
                    'TB': tb,
                    'SDS': SDS,
                    'SD1': SD1,
                    'TL': TL,
                },
            },
            {
                'include': include_vertical,
                'key': 'vertical',
                'column': 'Düşey Spektral İvme (g)',
                'unit': 'g',
                'description': 'Düşey elastik tasarım spektral ivmesi',
                'compute': lambda t: self.calculate_vertical_spectrum(t, SDS, SD1, TL),
                'zero_value': COEFF_VERT_INTERCEPT * SDS,
                'meta': lambda t_ad, t_bd: {
                    'T_AD': t_ad,
                    'T_BD': t_bd,
                    'T_LD': TL / 2.0,
                    'SDS_eff': COEFF_VERT_PLATEAU * SDS,
                },
            },
            {
                'include': include_displacement,
                'key': 'displacement',
                'column': 'Yatay Spektral Yerdeğiştirme (cm)',
                'unit': 'cm',
                'description': 'Yatay elastik tasarım spektral yerdeğiştirmesi',
                'compute': lambda t: self.calculate_displacement_spectrum(t, SDS, SD1, TL),
                'zero_value': 0.0,
                'meta': lambda ta_d, tb_d: {
                    'TA': ta_d,
                    'TB': tb_d,
                    'SDS': SDS,
                    'TL': TL,
                    'is_displacement': True,
                },
            },
        ]

        for spec in spectrum_specs:
            if not spec['include']:
                continue
            values, c1, c2 = spec['compute'](T)
            full_values = np.insert(values, 0, spec['zero_value'])
            df_dict[spec['column']] = full_values
            info[spec['key']] = {'data': full_values, **spec['meta'](c1, c2)}
            column_info[spec['column']] = {
                'dtype': 'float64',
                'unit': spec['unit'],
                'description': spec['description'],
            }
            column_order.append(spec['column'])

        # DataFrame oluştur - Periyot (s)'i indeks olarak kullan
        if df_dict:
            df = pd.DataFrame(df_dict, index=T_full, columns=column_order)
            df.index.name = 'Periyot (s)'

            for col_name, col_data in column_info.items():
                df[col_name] = df[col_name].astype(col_data['dtype'])

            if 'Periyot (s)' not in df.columns:
                df.insert(0, 'Periyot (s)', df.index.values)
        else:
            df = pd.DataFrame(index=pd.Index(T_full, name='Periyot (s)'))

        info['column_metadata'] = column_info
        info['period_metadata'] = {'dtype': 'float64', 'unit': 's', 'description': 'Periyot değerleri'}

        return {
            'dataframe': df,
            'period_array': T_full,
            'spectrum_info': info,
        }
