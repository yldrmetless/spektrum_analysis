"""TBDY-2018 Zemin Katsayıları Hesaplama Modülü"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from config.constants import (
    FS_VALUES, F1_VALUES, SOIL_CLASSES,
)


logger = logging.getLogger(__name__)

class CoefficientCalculator:
    """Zemin katsayıları hesaplama sınıfı"""
    
    def __init__(self) -> None:
        """CoefficientCalculator başlatıcısı"""
        pass

    def calculate_site_coefficients(
        self, ss: float, s1: float, soil_class: str
    ) -> Tuple[float, float]:
        """TBDY-2018'e göre zemin katsayılarını hesaplar.

        Args:
            ss (float): Ss değeri
            s1 (float): S1 değeri
            soil_class (str): Zemin sınıfı (örn: "ZC")

        Returns:
            Tuple[float, float]: (fs, f1) katsayıları

        Raises:
            ValueError: Geçersiz zemin sınıfı, ZF durumu veya parametre aralık dışı
            Exception: Hesaplama sırasında beklenmeyen hatalar için
        """
        # Zemin sınıfını temizle (sadece ZC kısmını al)
        if " " in soil_class:
            soil_class = soil_class.split()[0]

        # ZF için özel durum kontrolü
        if soil_class == "ZF":
            logger.warning(
                "Zemin sınıfı ZF için özel zemin etüdü gereklidir.")
            raise ValueError(
                "Zemin sınıfı ZF için özel zemin etüdü gereklidir.")

        # Zemin sınıfının geçerliliğini kontrol et
        if soil_class not in FS_VALUES:
            logger.error("'%s' için zemin katsayıları bulunamadı.", soil_class)
            raise ValueError(
                f"'{soil_class}' için zemin katsayıları bulunamadı.")

        try:
            # Dinamik SS ve S1 aralıklarını al
            ss_points, s1_points = self._get_dynamic_parameter_ranges()

            ss_min, ss_max = ss_points[0], ss_points[-1]
            s1_min, s1_max = s1_points[0], s1_points[-1]

            # Tablo 2.1 ve 2.2'de ilk sutun "<=" degerini temsil eder.
            # Alt veya ust sinir disindaki Ss degerleri tablo sabitleriyle sinirlanir.
            ss_clamped = max(ss, ss_min)
            if ss < ss_min:
                logger.warning(
                    "Ss degeri %.3f alt sinir %.2f'in altinda; %.2f kullanilacak.",
                    ss,
                    ss_min,
                    ss_min,
                )

            if ss > ss_max:
                logger.warning(
                    "Ss degeri %.3f ust sinir %.2f'in ustunde; %.2f kullanilacak "
                    "(Ss>1.5 icin tablo sabiti).",
                    ss,
                    ss_max,
                    ss_max,
                )
                ss_clamped = ss_max

            s1_clamped = max(s1, s1_min)

            if s1 > s1_max:
                logger.error(
                    "S1 degeri aralik disinda: %.3f (gecerli aralik %.2f-%.2f)",
                    s1,
                    s1_min,
                    s1_max,
                )
                raise ValueError(
                    f"S1 degeri {s1:.3f} gecerli aralik disinda ({s1_min}-{s1_max})."
                )

            # Fs katsayisini hesapla (dogrusal interpolasyon)
            fs = np.interp(ss_clamped, ss_points, FS_VALUES[soil_class])

            # F1 katsayisini hesapla (dogrusal interpolasyon)
            f1 = np.interp(s1_clamped, s1_points, F1_VALUES[soil_class])

            logger.info("📊 Zemin katsayıları hesaplandı:")
            logger.info(
                "   SS=%.3f → Fs=%.3f (zemin: %s)", ss, fs, soil_class)
            logger.info(
                "   S1=%.3f → F1=%.3f (zemin: %s)", s1, f1, soil_class)

            return fs, f1

        except Exception as e:  # pragma: no cover - beklenmeyen hatalar
            logger.error("Zemin katsayıları hesaplanırken hata oluştu: %s", e)
            raise
    
    def calculate_design_parameters(
        self, ss: float, s1: float, fs: float, f1: float
    ) -> Tuple[float, float]:
        """
        Tasarım spektral ivme katsayılarını hesaplar
        
        Args:
            ss (float): Ss değeri
            s1 (float): S1 değeri
            fs (float): Fs zemin katsayısı
            f1 (float): F1 zemin katsayısı
            
        Returns:
            Tuple[float, float]: (SDS, SD1) tasarım katsayıları
        """
        SDS = ss * fs
        SD1 = s1 * f1
        return SDS, SD1
    
    def _get_dynamic_parameter_ranges(self) -> Tuple[List[float], List[float]]:
        """
        TBDY-2018 Tablo 2.1'e uygun SS ve S1 aralıklarını döndürür
        
        Returns:
            Tuple[List[float], List[float]]: (ss_points, s1_points) listeleri
        """
        # TBDY-2018 Tablo 2.1'e göre sabit SS aralıkları
        # Ss ≤ 0.25, Ss = 0.50, Ss = 0.75, Ss = 1.00, Ss = 1.25, Ss ≥ 1.50
        tbdy_ss_points = [0.25, 0.50, 0.75, 1.00, 1.25, 1.50]
        
        # TBDY-2018 Tablo 2.2'ye göre sabit S1 aralıkları
        # S1 ≤ 0.10, S1 = 0.20, S1 = 0.30, S1 = 0.40, S1 = 0.50, S1 ≥ 0.60
        tbdy_s1_points = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60]
        
        # TBDY-2018'e göre her iki parametre de sabit aralıklar kullanıyor
        logger.info("📊 TBDY-2018 standart parametre aralıkları kullanılıyor:")
        logger.info("   SS (Tablo 2.1): %s", tbdy_ss_points)
        logger.info("   S1 (Tablo 2.2): %s", tbdy_s1_points)
        
        return tbdy_ss_points, tbdy_s1_points
    
    def get_coefficient_table_info(
        self, soil_class: str, parameter_type: str = 'fs'
    ) -> Optional[Dict[str, Any]]:
        """
        Belirli bir zemin sınıfı için katsayı tablosu bilgilerini döndürür
        
        Args:
            soil_class (str): Zemin sınıfı
            parameter_type (str): 'fs' veya 'f1'
            
        Returns:
            Optional[Dict[str, Any]]: Tablo bilgileri
        """
        # Zemin sınıfını temizle
        if " " in soil_class:
            soil_class = soil_class.split()[0]
        
        if soil_class not in FS_VALUES:
            return None
        
        if parameter_type.lower() == 'fs':
            return {
                'soil_class': soil_class,
                'parameter': 'Fs',
                'ss_points': [0.25, 0.50, 0.75, 1.00, 1.25, 1.50],  # TBDY-2018 Tablo 2.1
                'values': FS_VALUES[soil_class],
                'description': 'Kısa periyot bölgesi için zemin katsayısı'
            }
        elif parameter_type.lower() == 'f1':
            return {
                'soil_class': soil_class,
                'parameter': 'F1',
                's1_points': [0.10, 0.20, 0.30, 0.40, 0.50, 0.60],  # TBDY-2018 Tablo 2.2
                'values': F1_VALUES[soil_class],
                'description': '1.0 saniye periyot için zemin katsayısı'
            }
        else:
            return None
    
    def validate_parameters(self, ss: float, s1: float) -> Tuple[bool, str]:
        """
        Ss ve S1 parametrelerinin geçerliliğini kontrol eder
        
        Args:
            ss (float): Ss değeri
            s1 (float): S1 değeri
            
        Returns:
            Tuple[bool, str]: (is_valid, message)
        """
        try:
            ss = float(ss)
            s1 = float(s1)
        except (ValueError, TypeError):
            return False, "Ss ve S1 değerleri sayısal olmalıdır."
        
        if ss < 0 or s1 < 0:
            return False, "Ss ve S1 değerleri pozitif olmalıdır."
        
        if ss > 2.5:
            return False, f"Ss değeri çok yüksek: {ss:.3f}. Normal aralık: 0.0-2.5"
        
        if s1 > 2.0:
            return False, f"S1 değeri çok yüksek: {s1:.3f}. Normal aralık: 0.0-2.0"
        
        return True, "Parametreler geçerli."
    
    def get_all_soil_class_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Tüm zemin sınıfları hakkında bilgi döndürür
        
        Returns:
            Dict[str, Dict[str, Any]]: Zemin sınıfı bilgileri
        """
        info: Dict[str, Dict[str, Any]] = {}

        for full_name in SOIL_CLASSES:
            code = full_name.split()[0]
            if code == 'ZF':
                continue

            fs_info = self.get_coefficient_table_info(code, 'fs')
            f1_info = self.get_coefficient_table_info(code, 'f1')

            info[code] = {
                'name': full_name,
                'fs_table': fs_info,
                'f1_table': f1_info
            }

        zf_full_name = next((s for s in SOIL_CLASSES if s.startswith('ZF')), 'ZF Sınıfı Zemin')
        info['ZF'] = {
            'name': zf_full_name,
            'description': 'Özel zemin etüdü gerektirir',
            'fs_table': None,
            'f1_table': None
        }

        return info
    
    def interpolate_coefficient(
        self, input_value: float, input_points: List[float], coefficient_values: List[float]
    ) -> float:
        """
        Verilen noktalara göre katsayı interpolasyonu yapar
        
        Args:
            input_value (float): Interpolasyon yapılacak değer
            input_points (list[float]): Referans noktaları
            coefficient_values (list[float]): Katsayı değerleri
            
        Returns:
            float: İnterpolasyon sonucu
        """
        return np.interp(input_value, input_points, coefficient_values)

    def calculate_complete_analysis(
        self, ss: float, s1: float, soil_class: str
    ) -> Dict[str, Any]:
        """
        Tam zemin analizi yapar ve tüm sonuçları döndürür
        
        Args:
            ss (float): Ss değeri
            s1 (float): S1 değeri
            soil_class (str): Zemin sınıfı
            
        Returns:
            Dict[str, Any]: Tam analiz sonuçları
        """
        # Parametreleri doğrula
        is_valid, message = self.validate_parameters(ss, s1)
        if not is_valid:
            return {"error": message}
        
        # Zemin katsayılarını hesapla
        try:
            fs, f1 = self.calculate_site_coefficients(ss, s1, soil_class)
        except Exception as e:
            logger.error("Zemin katsayıları hesaplanamadı: %s", e)
            return {"error": f"Zemin katsayıları hesaplanamadı: {e}"}
        
        # Tasarım parametrelerini hesapla
        SDS, SD1 = self.calculate_design_parameters(ss, s1, fs, f1)
        
        # Sonuçları döndür
        return {
            "input_parameters": {
                "ss": ss,
                "s1": s1,
                "soil_class": soil_class
            },
            "site_coefficients": {
                "fs": fs,
                "f1": f1
            },
            "design_parameters": {
                "SDS": SDS,
                "SD1": SD1
            },
            "coefficient_tables": {
                "fs_table": self.get_coefficient_table_info(soil_class, 'fs'),
                "f1_table": self.get_coefficient_table_info(soil_class, 'f1')
            }
        }
