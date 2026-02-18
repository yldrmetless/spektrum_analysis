"""
TBDY-2018 3B Basit Ölçeklendirme Örneği
=======================================

Bu örnek, D04_TBDY_3B_Basit_Olceklendirme_Denetim.md belgesinde verilen
Python iskeletini çalışan hale getirir ve TBDY-2018 gereksinimlerini gösterir.
"""

import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple
import sys
import os

# Proje kök dizinini path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.scaling.tbdy_scaling import (
    scale_3d_simple_tbdy, validate_records_tbdy, 
    export_tbdy_results_csv, design_spectrum_tbdy
)
from src.scaling.scale_factor import calculate_srss_spectrum, normalize_weights_tbdy
from src.scaling.period_grid import build_period_grid
from src.scaling.weight_function import create_uniform_weights


def normalize_weights(T, w, T1):
    """
    Belgede verilen ağırlık normalizasyon fonksiyonu.
    0.2T1–1.5T1 dışını sıfırla, kalanları normalize et.
    """
    w2 = w.copy().astype(float)
    mask = (T >= 0.2*T1) & (T <= 1.5*T1)
    w2[~mask] = 0.0
    s = w2.sum()
    if s == 0:
        raise ValueError("Ağırlıklar aralıkta sıfırlandı")
    return w2 / s, mask


def scale_factor_closed_form(S, R, w):
    """
    Belgede verilen PEER kapalı form ölçek katsayısı.
    f* = sum(w*S*R) / sum(w*R^2)
    """
    num = np.sum(w * S * R)
    den = np.sum(w * R * R)
    if den <= 0:
        raise ValueError("Spektrumda sorun (denom<=0)")
    return num / den


def srss(sa_x, sa_y):
    """Belgede verilen SRSS hesaplama fonksiyonu."""
    return np.sqrt(sa_x**2 + sa_y**2)


def scale_3D_simple(T, S, T1, SAx_list, SAy_list, w=None):
    """
    Belgede verilen 3B basit ölçeklendirme iskelet fonksiyonu.
    
    Args:
        T: 301 log periyot
        S: tasarım SA(T)
        T1: birinci doğal periyot
        SAx_list, SAy_list: kayıt spektrumları
        w: ağırlık fonksiyonu
        
    Returns:
        f_list: ölçek katsayıları
        R_avg: ortalama ölçeklenmiş spektrum
        gamma: global düzeltme katsayısı
        min_ratio: minimum oran
    """
    n = len(SAx_list)
    if w is None:
        w = np.ones_like(T)
    wN, mask = normalize_weights(T, w, T1)

    f_list, R_scaled_list = [], []
    for SAx, SAy in zip(SAx_list, SAy_list):
        R = srss(SAx, SAy)
        f = scale_factor_closed_form(S, R, wN)
        f_list.append(f)
        R_scaled_list.append(f*R)

    R_avg = np.mean(R_scaled_list, axis=0)

    # 1.30 kontrolü ve global gamma
    ratio = R_avg[mask] / (1.30 * S[mask])
    gamma = 1.0
    if np.min(ratio) < 1.0:
        gamma = 1.0 / np.min(ratio)
        f_list = [gamma*f for f in f_list]
        R_scaled_list = [gamma*R for R in R_scaled_list]
        R_avg = gamma*R_avg

    return np.array(f_list), R_avg, gamma, np.min(R_avg[mask] / (1.30*S[mask]))


def generate_test_records(n_records: int = 12) -> List[Tuple]:
    """Test kayıtları oluştur."""
    np.random.seed(42)
    records = []
    
    # 3 farklı olay, her olay 4 kayıt
    n_events = 3
    records_per_event = n_records // n_events
    
    for event_id in range(n_events):
        for record_id in range(records_per_event):
            # 10 saniye, 0.01 dt
            dt = 0.01
            t = np.arange(0, 10, dt)
            
            # Gerçekçi deprem kaydı benzeri
            freq1 = 2.0 + event_id * 0.5
            freq2 = 8.0 + record_id * 2.0
            
            # X bileşeni
            ax = (0.3 * np.sin(2*np.pi*freq1*t) * np.exp(-t/4) + 
                  0.1 * np.sin(2*np.pi*freq2*t) * np.exp(-t/6) +
                  np.random.normal(0, 0.05, len(t)))
            
            # Y bileşeni (farklı frekans karakteristiği)
            ay = (0.25 * np.cos(2*np.pi*freq1*t) * np.exp(-t/5) + 
                  0.08 * np.cos(2*np.pi*freq2*t) * np.exp(-t/7) +
                  np.random.normal(0, 0.04, len(t)))
            
            meta = {
                "event_id": f"Event_{event_id+1}",
                "station": f"Station_{record_id+1}",
                "nga_number": f"NGA_{event_id*records_per_event + record_id + 1:04d}",
                "pair_name": f"Pair_{len(records)+1}"
            }
            
            records.append((ax, ay, dt, meta))
    
    return records


def demonstrate_tbdy_scaling():
    """TBDY-2018 3B basit ölçeklendirmeyi göster."""
    print("TBDY-2018 3B Basit Ölçeklendirme Örneği")
    print("=" * 50)
    
    # 1. Test kayıtları oluştur
    print("1. Test kayıtları oluşturuluyor...")
    records = generate_test_records(12)
    print(f"   ✓ {len(records)} kayıt oluşturuldu")
    
    # 2. Validasyon kontrolü
    print("2. TBDY validasyon kontrolü...")
    is_valid, msg = validate_records_tbdy(records)
    if is_valid:
        print(f"   ✓ {msg}")
    else:
        print(f"   ✗ {msg}")
        return
    
    # 3. TBDY parametreleri
    T1 = 1.0    # Birinci doğal periyot
    SDS = 0.8   # Kısa periyot tasarım spektral ivme katsayısı
    SD1 = 0.6   # 1 saniyelik tasarım spektral ivme katsayısı
    TL = 6.0    # Geçiş periyodu
    alpha = 1.3 # TBDY-2018 3B zorunlu çarpan
    
    print(f"3. TBDY parametreleri:")
    print(f"   T₁ = {T1} s")
    print(f"   SDS = {SDS} g")
    print(f"   SD₁ = {SD1} g")
    print(f"   TL = {TL} s")
    print(f"   α = {alpha} (3B zorunlu)")
    print(f"   Kontrol aralığı: [{0.2*T1:.1f}, {1.5*T1:.1f}] s")
    
    # 4. TBDY ölçeklendirme
    print("4. TBDY-2018 ölçeklendirme hesaplanıyor...")
    try:
        result = scale_3d_simple_tbdy(
            records=records,
            T1=T1,
            SDS=SDS,
            SD1=SD1,
            TL=TL,
            alpha=alpha,
            damping=5.0
        )
        print("   ✓ Hesaplama başarılı")
    except Exception as e:
        print(f"   ✗ Hata: {e}")
        return
    
    # 5. Sonuçları göster
    print("5. Sonuçlar:")
    print(f"   Kayıt sayısı: {result.n_records}")
    print(f"   TBDY koşulu: {'GEÇTİ' if result.pass_tbdy else 'KALDI'}")
    print(f"   Minimum oran: {result.min_ratio:.6f}")
    print(f"   Global gamma: {result.global_gamma:.6f}")
    print(f"   Gamma uygulandı: {'Evet' if result.gamma_applied else 'Hayır'}")
    print(f"   Aynı olay kontrolü: {'GEÇTİ' if result.same_event_check else 'KALDI'}")
    
    print(f"\n   Ölçek katsayıları (ilk 5):")
    for i, (f, mse) in enumerate(zip(result.f_list[:5], result.mse_list[:5])):
        print(f"     Kayıt {i+1}: f={f:.6f}, MSE={mse:.6f}")
    if len(result.f_list) > 5:
        print(f"     ... ve {len(result.f_list)-5} kayıt daha")
    
    # 6. Belgede verilen iskelet fonksiyonla karşılaştır
    print("\n6. Belgede verilen iskelet fonksiyonla karşılaştırma...")
    
    # Spektrumları hesapla (basitleştirilmiş)
    T_grid = result.T_grid
    S_design = design_spectrum_tbdy(T_grid, SDS, SD1, TL)
    
    # Kayıt spektrumları (SRSS için basit yaklaşım)
    SAx_list = []
    SAy_list = []
    
    for ax, ay, dt, meta in records:
        # Basit spektrum tahmini (gerçek hesaplama yerine)
        SA_x = np.ones_like(T_grid) * 0.2 * np.random.uniform(0.8, 1.2)
        SA_y = np.ones_like(T_grid) * 0.15 * np.random.uniform(0.8, 1.2)
        SAx_list.append(SA_x)
        SAy_list.append(SA_y)
    
    # Belgede verilen fonksiyonu çalıştır
    f_skeleton, R_avg_skeleton, gamma_skeleton, min_ratio_skeleton = scale_3D_simple(
        T_grid, alpha * S_design, T1, SAx_list, SAy_list
    )
    
    print(f"   İskelet fonksiyonu:")
    print(f"     Ortalama f: {np.mean(f_skeleton):.6f}")
    print(f"     Global γ: {gamma_skeleton:.6f}")
    print(f"     Min oran: {min_ratio_skeleton:.6f}")
    
    # 7. Grafik oluştur
    print("7. Grafik oluşturuluyor...")
    try:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        
        # Üst grafik: Spektrumlar
        ax1.loglog(result.T_grid, result.srss_avg, 'b-', linewidth=2, 
                   label='Ortalama SRSS (ölçekli)')
        ax1.loglog(result.T_grid, result.target_spectrum, 'r--', linewidth=2, 
                   label='1.30 × S_tasarım')
        ax1.axvspan(0.2*T1, 1.5*T1, alpha=0.2, color='green', 
                    label=f'Kontrol aralığı [{0.2*T1:.1f}, {1.5*T1:.1f}] s')
        ax1.set_xlabel('Periyot, T (s)')
        ax1.set_ylabel('Spektral İvme, Sa (g)')
        ax1.set_title('TBDY-2018 3B Basit Ölçeklendirme Sonuçları')
        ax1.grid(True, which='both', alpha=0.3)
        ax1.legend()
        
        # Alt grafik: Ölçek katsayıları
        ax2.bar(range(1, len(result.f_list)+1), result.f_list, 
                color='skyblue', alpha=0.7, edgecolor='navy')
        ax2.axhline(y=np.mean(result.f_list), color='red', linestyle='--', 
                    label=f'Ortalama f = {np.mean(result.f_list):.3f}')
        ax2.set_xlabel('Kayıt Numarası')
        ax2.set_ylabel('Ölçek Katsayısı, f')
        ax2.set_title('Kayıt Bazlı Ölçek Katsayıları')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.tight_layout()
        
        # Kaydet
        output_file = 'tbdy_3d_scaling_results.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"   ✓ Grafik kaydedildi: {output_file}")
        
        # Göster (etkileşimli ortamda)
        try:
            plt.show()
        except:
            pass
            
    except Exception as e:
        print(f"   ⚠ Grafik oluşturulamadı: {e}")
    
    # 8. CSV dışa aktarma
    print("8. CSV dışa aktarma...")
    try:
        records_meta = [
            {
                "event_id": meta.get("event_id", f"Event_{i+1}"),
                "station": meta.get("station", f"Station_{i+1}"),
                "nga_number": meta.get("nga_number", f"NGA_{i+1:04d}")
            }
            for i, (_, _, _, meta) in enumerate(records)
        ]
        
        csv_file = export_tbdy_results_csv(result, records_meta, "tbdy_3d_results.csv")
        print(f"   ✓ CSV dosyası oluşturuldu: {csv_file}")
        
        # CSV içeriğini göster
        import csv
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        print(f"   CSV içeriği (ilk 3 satır):")
        for i, row in enumerate(rows[:3]):
            print(f"     Kayıt {i+1}: f={row['f']}, pass_3D={row['pass_3D']}")
            
    except Exception as e:
        print(f"   ⚠ CSV dışa aktarma hatası: {e}")
    
    print("\n" + "=" * 50)
    print("TBDY-2018 3B Basit Ölçeklendirme örneği tamamlandı!")
    
    # Özet
    print(f"\nÖZET:")
    print(f"• Kayıt sayısı: {result.n_records} (≥11 ✓)")
    print(f"• Aynı olay kuralı: {'✓' if result.same_event_check else '✗'}")
    print(f"• TBDY koşulu (≥1.30): {'✓' if result.pass_tbdy else '✗'}")
    print(f"• Global düzeltme: {'Uygulandı' if result.gamma_applied else 'Gerekli değil'}")
    print(f"• Minimum oran: {result.min_ratio:.3f}")
    
    return result


if __name__ == "__main__":
    # Örneği çalıştır
    result = demonstrate_tbdy_scaling()
