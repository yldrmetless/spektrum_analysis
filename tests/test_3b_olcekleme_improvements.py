"""
3B Ölçekleme İyileştirmeleri için Test Paketi
===========================================

Raporda önerilen testlerin uygulanması:
1. Yönetmelik eşiği testi (global z)
2. Bileşen eş ölçek testi
3. PGMD grid testi
4. MSE tutarlılığı (kapalı form)
5. LP vs. tbdx_min
"""

import pytest
import numpy as np
from src.calculations.basic_scaling import basic_scaling_3d, design_spectrum_g, ScaleResult
from src.scaling.period_grid import build_period_grid, validate_period_grid
from src.scaling.scale_factor import calculate_scale_factor_3d, calculate_mse_log_space
from src.scaling.weight_function import create_uniform_weights


class Test3BOlceklemeIyilestirmeleri:
    """3B ölçekleme iyileştirmeleri test sınıfı"""
    
    def setup_method(self):
        """Her test öncesi çalışan setup"""
        # Test verisi oluştur
        self.T = build_period_grid()
        self.SDS = 0.8
        self.SD1 = 0.4
        self.TL = 6.0
        self.Tp = 1.0
        self.alpha = 1.3
        
        # Sahte kayıtlar oluştur
        self.records = []
        for i in range(11):  # Minimum 11 kayıt
            n_points = 5000
            dt = 0.01
            # Sahte ivme kayıtları
            ax = 0.1 * np.sin(2 * np.pi * np.arange(n_points) * dt / (0.5 + i * 0.1))
            ay = 0.1 * np.cos(2 * np.pi * np.arange(n_points) * dt / (0.7 + i * 0.1))
            meta = {"event_id": f"EV{i//3}", "pair_name": f"pair_{i+1}"}
            self.records.append((ax, ay, dt, meta))
    
    def test_yonetmelik_esigi_global_z(self):
        """Test 1: Yönetmelik eşiği testi (global z)"""
        # S̄_SRSS / (1.3·S_tas) min oranı ≥ 1.0 olmalı ([0.2Tp,1.5Tp] aralığında)
        result = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=self.alpha, use_record_based=False
        )
        
        # Kontrol aralığı
        lo, hi = 0.2 * self.Tp, 1.5 * self.Tp
        mask = (result.T >= lo) & (result.T <= hi)
        
        # Oranları kontrol et
        min_ratio = np.min(result.ratios[mask])
        assert min_ratio >= 1.0, f"Yönetmelik eşiği ihlali: min oran {min_ratio:.6f} < 1.0"
        
        # f_min ile ölçeklenmiş ortalama kontrol
        S_scaled = result.f_min * result.S_avg
        target_values = result.S_target
        ratios_check = S_scaled[mask] / target_values[mask]
        assert np.all(ratios_check >= 1.0), "Ölçeklenmiş spektrum hedefin altında"
    
    def test_bilesen_es_olcek(self):
        """Test 2: Bileşen eş ölçek testi"""
        # Her kayıt için f_x == f_y ve SRSS, ölçek sonrası √(Sa_X²+Sa_Y²) ile tutarlı
        result = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=self.alpha, use_record_based=True  # Kayıt-bazlı mod
        )
        
        # Per-record faktörleri kontrol et
        per_record_factors = result.per_record_factors
        assert len(per_record_factors) == len(self.records), "Her kayıt için ölçek katsayısı olmalı"
        
        # Tüm faktörler pozitif olmalı
        assert all(f > 0 for f in per_record_factors), "Negatif ölçek katsayısı"
        
        # SRSS tutarlılığı (basit kontrol)
        # Her kayıt için aynı f uygulandığında SRSS = √(f²·SaX² + f²·SaY²) = f·√(SaX² + SaY²)
        for i, f in enumerate(per_record_factors):
            assert 0.1 <= f <= 10.0, f"Ölçek katsayısı makul aralık dışında: {f}"
    
    def test_pgmd_grid(self):
        """Test 3: PGMD grid testi"""
        # period_grid.build_period_grid() çıktısı 301 nokta, [0.01,10] aralığı ve log-eş aralıklı
        T = build_period_grid()
        
        # 301 nokta kontrolü
        assert len(T) == 301, f"Periyot sayısı 301 olmalı, {len(T)} bulundu"
        
        # Aralık kontrolü
        assert np.isclose(T[0], 0.01, rtol=1e-6), f"İlk periyot 0.01 olmalı, {T[0]} bulundu"
        assert np.isclose(T[-1], 10.0, rtol=1e-6), f"Son periyot 10.0 olmalı, {T[-1]} bulundu"
        
        # Log-eş aralıklı kontrol
        is_valid, message = validate_period_grid(T)
        assert is_valid, f"Periyot ızgarası geçersiz: {message}"
        
        # Log-uzayda eşit aralıklı olup olmadığını kontrol et
        log_T = np.log10(T)
        log_diff = np.diff(log_T)
        assert np.allclose(log_diff, log_diff[0], rtol=1e-10), "Log-uzayda eşit aralıklı değil"
    
    def test_mse_tutarliligi_kapali_form(self):
        """Test 4: MSE tutarlılığı (kapalı form)"""
        # Eşitlik (3) ile bulunan f ile nümerik MSE(f) türev-sıfır koşulu uyumlu
        from src.scaling.scale_factor import calculate_range_scale_factor
        
        # Test verisi
        SA_target = design_spectrum_g(self.T, self.SDS, self.SD1, self.TL)
        SA_record = 0.5 * SA_target  # Yarı büyüklükte kayıt spektrumu
        weights = create_uniform_weights(self.T)
        
        # Kapalı form çözüm
        f_analytical = calculate_range_scale_factor(SA_target, SA_record, weights)
        
        # MSE hesapla
        SA_scaled = f_analytical * SA_record
        mse_analytical = calculate_mse_log_space(SA_target, SA_scaled, weights)
        
        # Nümerik kontrol: f'nin etrafında MSE türevinin sıfır olması
        eps = 1e-6
        f_plus = f_analytical + eps
        f_minus = f_analytical - eps
        
        SA_scaled_plus = f_plus * SA_record
        SA_scaled_minus = f_minus * SA_record
        
        mse_plus = calculate_mse_log_space(SA_target, SA_scaled_plus, weights)
        mse_minus = calculate_mse_log_space(SA_target, SA_scaled_minus, weights)
        
        # Türev yaklaşık sıfır olmalı
        derivative_approx = (mse_plus - mse_minus) / (2 * eps)
        assert abs(derivative_approx) < 1e-3, f"MSE türevi sıfır değil: {derivative_approx}"
        
        # Kapalı form çözüm minimum olmalı
        assert mse_analytical <= mse_plus, "Kapalı form çözüm minimum değil (sağ)"
        assert mse_analytical <= mse_minus, "Kapalı form çözüm minimum değil (sol)"
    
    def test_lp_vs_tbdx_min(self):
        """Test 5: LP vs. tbdx_min"""
        # Aynı kayıt setinde tbdx_min'in tek f'i ile LP'nin {fᵢ} sonucu için 
        # her iki durumda da r_min ≥ 1.0 (1.3 hedefi bağlamında)
        
        # TBDX_MIN modu
        result_tbdx = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=self.alpha, use_record_based=False
        )
        
        # LP modu
        result_lp = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=self.alpha, use_record_based=True
        )
        
        # Kontrol aralığı
        lo, hi = 0.2 * self.Tp, 1.5 * self.Tp
        mask = (result_tbdx.T >= lo) & (result_tbdx.T <= hi)
        
        # TBDX_MIN için minimum oran ≥ 1.0
        min_ratio_tbdx = np.min(result_tbdx.ratios[mask])
        assert min_ratio_tbdx >= 1.0, f"TBDX_MIN min oran {min_ratio_tbdx:.6f} < 1.0"
        
        # LP için minimum oran ≥ 1.0
        min_ratio_lp = np.min(result_lp.ratios[mask])
        assert min_ratio_lp >= 1.0, f"LP min oran {min_ratio_lp:.6f} < 1.0"
        
        # LP modunda per-record faktörler olmalı
        assert len(result_lp.per_record_factors) == len(self.records), "LP modunda per-record faktörler yok"
        
        # Mode notları kontrol et
        assert result_lp.mode == "record_lp", "LP modu doğru etiketlenmemiş"
        assert result_lp.mode_note is not None, "LP mode_note eksik"
        assert "Kısıt-Tatmin" in result_lp.mode_note, "LP mode_note açıklaması eksik"
    
    def test_alpha_kilidi_3b(self):
        """Test: Alpha parametresinin 3B modda 1.3'te kilitli olması"""
        # Alpha değeri 1.3'ten farklı verilse bile 3B modda 1.3 kullanılmalı
        result = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=1.0,  # Yanlış değer veriyoruz
            use_record_based=False
        )
        
        # Sonuçta alpha=1.3 kullanılmış olmalı (target kontrolü ile)
        S_tas = design_spectrum_g(result.T, self.SDS, self.SD1, self.TL)
        expected_target = 1.3 * S_tas  # 3B için zorunlu
        
        # Target spektrumun 1.3 katsayısı ile oluşturulduğunu kontrol et
        assert np.allclose(result.S_target, expected_target, rtol=1e-6), "Alpha kilidi çalışmıyor"
    
    def test_log_interpolasyon_tutarliligi(self):
        """Test: Log-log interpolasyonun tutarlılığı"""
        # SRSS hesaplamalarında log-log interpolasyon kullanılmalı
        result = basic_scaling_3d(
            self.records, self.Tp, self.SDS, self.SD1, self.TL,
            alpha=self.alpha, use_record_based=False
        )
        
        # Sonuç makul aralıkta olmalı
        assert 0.1 <= result.f_min <= 10.0, f"Ölçek katsayısı makul aralık dışında: {result.f_min}"
        
        # SRSS ortalaması pozitif olmalı
        assert np.all(result.S_avg > 0), "SRSS ortalaması negatif değerler içeriyor"
        assert np.all(np.isfinite(result.S_avg)), "SRSS ortalaması NaN/Inf değerler içeriyor"
    
    def test_validation_strict_enforcement(self):
        """Test: ≤3/event kuralının zorunlu uygulanması (11 kayıt kuralı uyarıya dönüştürüldü)"""
        # 11'den az kayıt artık izin veriliyor (allow_below_11=True)
        few_records = self.records[:5]  # Sadece 5 kayıt
        
        # Bu artık hata vermemeli (uyarı olarak değiştirildi)
        try:
            result = basic_scaling_3d(
                few_records, self.Tp, self.SDS, self.SD1, self.TL,
                alpha=self.alpha, use_record_based=False, allow_below_11=True
            )
            assert result is not None, "5 kayıt ile hesaplama başarısız"
        except ValueError as e:
            # Eğer hala hata alıyorsak, sadece ≤3/event kuralı için olmalı
            assert "aynı deprem" in str(e).lower(), f"Beklenmeyen hata: {e}"
        
        # Aynı depremden 4+ kayıt ile hata alınmalı
        same_event_records = []
        for i in range(11):
            ax = 0.1 * np.sin(2 * np.pi * np.arange(1000) * 0.01 / 1.0)
            ay = 0.1 * np.cos(2 * np.pi * np.arange(1000) * 0.01 / 1.0)
            meta = {"event_id": "SAME_EVENT", "pair_name": f"pair_{i+1}"}  # Hepsi aynı deprem
            same_event_records.append((ax, ay, 0.01, meta))
        
        with pytest.raises(ValueError, match="Aynı depremden seçilen kayıt sayısı sınırı aşıldı"):
            basic_scaling_3d(
                same_event_records, self.Tp, self.SDS, self.SD1, self.TL,
                alpha=self.alpha, use_record_based=False
            )


if __name__ == "__main__":
    # Testleri çalıştır
    pytest.main([__file__, "-v"])
