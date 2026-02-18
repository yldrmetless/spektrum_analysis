"""
AFAD veri dosyalarını yükleme ve doğrulama işlemleri
"""

import pandas as pd
import numpy as np
import os
import json
import re
import time
from typing import Optional, Dict, Any, List, Tuple
from tkinter import messagebox
from ..config.constants import (
    AFAD_COLUMN_NAMES, REQUIRED_AFAD_COLUMNS, 
    SUPPORTED_EXCEL_FORMATS, SUPPORTED_CSV_FORMATS
)
from ..utils.afad_interpolation import interpolate_idw, equirectangular_distance_m
from ..utils.idw_interpolation import bilinear_interpolate

# ────────────────────────────────────────────────────────────────
# ────────────────────────────────────────────────────────────────

# GeoJSON cache sistemi - global cache
_GEOJSON_CACHE = {}
_CACHE_TIMESTAMPS = {}
_MAX_CACHE_AGE = 300  # 5 dakika cache süresi

class DataLoader:
    """AFAD veri dosyalarını yükleme ve doğrulama sınıfı"""
    
    def __init__(self):
        self.loaded_data = None
        self.file_path = None
    
    @staticmethod
    def _is_cache_valid(cache_key: str) -> bool:
        """Cache'in geçerli olup olmadığını kontrol eder"""
        if cache_key not in _CACHE_TIMESTAMPS:
            return False
        age = time.time() - _CACHE_TIMESTAMPS[cache_key]
        return age < _MAX_CACHE_AGE
    
    @staticmethod 
    def _get_cached_geojson(cache_key: str) -> Optional[Dict[str, Any]]:
        """Cache'den GeoJSON verisi alır"""
        if cache_key in _GEOJSON_CACHE and DataLoader._is_cache_valid(cache_key):
            print(f"⚡ Cache HIT: {cache_key} (süre: {time.time() - _CACHE_TIMESTAMPS[cache_key]:.1f}s)")
            return _GEOJSON_CACHE[cache_key]
        return None
    
    @staticmethod
    def _cache_geojson(cache_key: str, geojson_data: Dict[str, Any]) -> None:
        """GeoJSON verisini cache'ler"""
        _GEOJSON_CACHE[cache_key] = geojson_data
        _CACHE_TIMESTAMPS[cache_key] = time.time()
        print(f"💾 Cache SAVE: {cache_key} ({len(geojson_data.get('features', []))} poligon)")
    
    @staticmethod
    def clear_geojson_cache() -> None:
        """GeoJSON cache'ini temizler"""
        global _GEOJSON_CACHE, _CACHE_TIMESTAMPS
        _GEOJSON_CACHE.clear()
        _CACHE_TIMESTAMPS.clear()
        print("🧹 GeoJSON cache temizlendi")
        
    def load_file(self, file_path):
        """
        Dosyayı yükler ve doğrular
        
        Args:
            file_path (str): Yüklenecek dosyanın yolu
            
        Returns:
            pd.DataFrame veya None: Yüklenen ve doğrulanan veri
        """
        try:
            self.file_path = file_path
            print(f"📁 Dosya yükleniyor: {file_path}")
            
            # Dosya varlığını kontrol et
            if not os.path.exists(file_path):
                messagebox.showerror("Dosya Hatası", f"Dosya bulunamadı:\n{file_path}")
                return None
            
            # Dosya formatına göre okuma
            df = self._read_data_file(file_path, skiprows=3, header=None)
            if df is None:
                return None
            
            print(f"📊 Dosya okundu: {df.shape[0]} satır, {df.shape[1]} sütun")
            
            # Minimum sütun sayısı kontrolü (daha esnek)
            min_required_cols = 14  # En az SS ve S1 sütunları için gerekli
            if df.shape[1] < min_required_cols:
                messagebox.showerror("Dosya Formatı Hatası", 
                                   f"Veri setinde yeterli sütun bulunmuyor.\n"
                                   f"Gerekli: en az {min_required_cols} sütun\n"
                                   f"Bulunan: {df.shape[1]} sütun")
                return None
            
            # Sütun isimlerini ata (mevcut sütun sayısına göre)
            available_columns = min(len(df.columns), len(AFAD_COLUMN_NAMES))
            df.columns = AFAD_COLUMN_NAMES[:available_columns]
            
            print(f"📋 Sütun isimleri atandı: {list(df.columns[:6])}...")
            
            # Temel gerekli sütunları kontrol et (daha esnek)
            essential_cols = ['Boylam', 'Enlem', 'Ss_DD1', 'Ss_DD2', 'S1_DD1', 'S1_DD2']
            missing_cols = [col for col in essential_cols if col not in df.columns]
            
            if missing_cols:
                messagebox.showerror("Sütun Hatası", 
                                   f"Temel gerekli sütunlar bulunamadı: {missing_cols}\n"
                                   f"Mevcut sütunlar: {list(df.columns)}")
                return None
            
            # Mevcut sütunları kullan
            available_required_cols = [col for col in REQUIRED_AFAD_COLUMNS if col in df.columns]
            df_final = df[available_required_cols].copy()
            
            print(f"🔄 {len(available_required_cols)} sütun seçildi")
            
            # Sayisal degerleri temizle ve float'a cevir (virgul -> nokta)
            def _safe_to_float(val, idx, col_name):
                if pd.isna(val):
                    return np.nan
                try:
                    if isinstance(val, str):
                        cleaned = val.strip().replace(',', '.')
                        if cleaned == '':
                            return np.nan
                    else:
                        cleaned = val
                    return float(cleaned)
                except Exception as conv_err:
                    print(f"Donusum hatasi (satir={idx}, sutun={col_name}, deger={val!r}): {conv_err}")
                    return np.nan

            for col in available_required_cols:
                df_final[col] = pd.Series(
                    (_safe_to_float(value, idx, col) for idx, value in df_final[col].items()),
                    index=df_final.index
                )

            # Koordinat sütunlarındaki NaN'ları kontrol et
            coord_cols = ['Boylam', 'Enlem']
            coord_na_count = df_final[coord_cols].isna().sum().sum()
            
            if coord_na_count > 0:
                print(f"⚠️ Koordinat sütunlarında {coord_na_count} adet geçersiz değer bulundu")
            
            # Sadece koordinatları geçerli olan satırları al
            df_final = df_final.dropna(subset=coord_cols)
            
            if len(df_final) == 0:
                messagebox.showerror("Veri Hatası", 
                                   "Dosyada geçerli koordinat verisi bulunamadı.")
                return None
            
            print(f"✅ Veri yükleme başarılı: {len(df_final)} geçerli satır")
            
            self.loaded_data = df_final
            return df_final
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Dosya yükleme hatası: {error_msg}")
            
            # Daha detaylı hata mesajı
            if "No such file or directory" in error_msg:
                messagebox.showerror("Dosya Hatası", f"Dosya bulunamadı:\n{file_path}")
            elif "Excel file format cannot be determined" in error_msg:
                messagebox.showerror("Format Hatası", 
                                   "Excel dosyası okunamıyor. Dosyanın .xlsx formatında olduğundan emin olun.")
            elif "openpyxl" in error_msg.lower():
                messagebox.showerror("Kütüphane Eksik", 
                                   "Excel dosyalarını okumak için 'openpyxl' kütüphanesi gereklidir.\n"
                                   "Lütfen 'pip install openpyxl' komutunu çalıştırın.")
            else:
                messagebox.showerror("Dosya İşleme Hatası", 
                                   f"Veri seti işlenirken hata oluştu:\n\n{error_msg}\n\n"
                                   f"Dosya: {os.path.basename(file_path)}")
            return None
    


    def _read_data_file(self, file_path, **kwargs):
        """
        Dosya formatina gore veri okur.

        Args:
            file_path (str): Dosya yolu
            **kwargs: Pandas okuma parametreleri

        Returns:
            pd.DataFrame veya None: Okunan veri
        """
        try:
            if file_path.endswith('.csv'):
                print("CSV dosyasi okunuyor...")
                # Ondalik ayirac virgullu ve ayirac olarak noktal? virgullu CSV'ler icin
                # encoding ve ayirac denemeleri yap.
                base_kwargs = kwargs.copy()
                base_kwargs.setdefault('dtype', str)        # Degerleri string olarak tut, sonra temizle
                base_kwargs.setdefault('engine', 'python')  # sep=None icin gerekli
                base_kwargs.setdefault('sep', None)         # Otomatik ayirac algilama

                encodings = ['utf-8-sig', 'windows-1254', 'latin1']
                separators = [None, ';', ',']
                last_error = None

                for enc in encodings:
                    for sep in separators:
                        csv_kwargs = base_kwargs.copy()
                        csv_kwargs['encoding'] = enc
                        csv_kwargs['sep'] = sep
                        try:
                            df = pd.read_csv(file_path, **csv_kwargs)
                            print(f"CSV okundu (encoding='{enc}', sep='{sep or 'auto'}')")
                            return df
                        except Exception as csv_error:  # pragma: no cover - beklenmeyen okuma hatasi
                            last_error = csv_error
                            continue

                raise last_error if last_error else Exception('CSV okuma hatasi: bilinmeyen hata')

            elif file_path.endswith(('.xlsx', '.xls')):
                print('Excel dosyasi okunuyor...')
                try:
                    df = pd.read_excel(file_path, **kwargs)
                    print(f"Excel dosyasi basariyla okundu: {df.shape}")
                    return df
                except ImportError:
                    messagebox.showerror('Kutuphane Eksik',
                                       "Excel dosyalarini okumak icin 'openpyxl' kutuphanesi gereklidir.\n"
                                       "Lutfen 'pip install openpyxl' komutunu calistirin.")
                    return None
                except Exception as excel_error:
                    print(f"Excel okuma hatasi: {excel_error}")
                    raise excel_error
            else:
                messagebox.showerror('Dosya Formati Hatasi',
                                   f"Desteklenmeyen dosya formati: {os.path.splitext(file_path)[1]}\n"
                                   "Desteklenen formatlar: .xlsx, .xls, .csv")
                return None

        except Exception as e:
            print(f"_read_data_file hatasi: {e}")
            raise e

    def get_file_info(self):
        """
        Yüklenen dosya hakkında bilgi döndürür
        
        Returns:
            dict: Dosya bilgileri
        """
        if self.loaded_data is None or self.file_path is None:
            return {"status": "Veri yüklenmedi", "count": 0, "file": ""}
        
        return {
            "status": "Yüklendi",
            "count": len(self.loaded_data),
            "file": os.path.basename(self.file_path)
        }
    
    def is_data_loaded(self):
        """
        Veri yüklenmiş mi kontrolü
        
        Returns:
            bool: Veri durumu
        """
        return self.loaded_data is not None and len(self.loaded_data) > 0
    
    def get_pga_data_for_heatmap(self, dd_level):
        """
        Belirtilen DD seviyesi için PGA verilerini döndürür
        
        Args:
            dd_level (str): DD seviyesi (örn: "DD-2 (50 yılda aşılma olasılığı 10%)")
            
        Returns:
            list: [[lat, lon, pga_value], ...] formatında veri listesi
        """
        if self.loaded_data is None:
            return []
        
        try:
            # DD seviyesinden sütun adını oluştur
            dd_number = dd_level.split('-')[1].split(' ')[0]  # "DD-2" -> "2"
            pga_column = f'PGA_DD{dd_number}'
            
            # Gerekli sütunların varlığını kontrol et
            required_cols = ['Enlem', 'Boylam', pga_column]
            missing_cols = [col for col in required_cols if col not in self.loaded_data.columns]
            
            if missing_cols:
                print(f"⚠️ Heat map için gerekli sütunlar bulunamadı: {missing_cols}")
                return []
            
            # Verilen DD seviyesi için PGA verilerini al
            df = self.loaded_data[required_cols].copy()
            
            # NaN değerleri temizle
            df = df.dropna()
            
            # Liste formatında döndür: [[lat, lon, pga_value], ...]
            heat_data = []
            for _, row in df.iterrows():
                lat = float(row['Enlem'])
                lon = float(row['Boylam'])
                pga = float(row[pga_column])
                
                # Sadece pozitif PGA değerlerini al
                if pga > 0:
                    heat_data.append([lat, lon, pga])
            
            print(f"📊 Heat map verisi hazırlandı: {len(heat_data)} nokta ({dd_level})")
            return heat_data
            
        except Exception as e:
            print(f"❌ PGA veri hatası: {e}")
            return []
    
    def get_pga_dataframe_for_geojson(self, dd_level):
        """
        Belirtilen DD seviyesi için PGA verilerini DataFrame olarak döndürür
        
        Args:
            dd_level (str): DD seviyesi (örn: "DD-2 (50 yılda aşılma olasılığı 10%)")
            
        Returns:
            pd.DataFrame: ['lat', 'lon', 'pga'] sütunlarıyla DataFrame
        """
        if self.loaded_data is None:
            return pd.DataFrame()
        
        try:
            # DD seviyesinden sütun adını oluştur
            dd_number = dd_level.split('-')[1].split(' ')[0]  # "DD-2" -> "2"
            pga_column = f'PGA_DD{dd_number}'
            
            # Gerekli sütunların varlığını kontrol et
            required_cols = ['Enlem', 'Boylam', pga_column]
            missing_cols = [col for col in required_cols if col not in self.loaded_data.columns]
            
            if missing_cols:
                print(f"⚠️ GeoJSON için gerekli sütunlar bulunamadı: {missing_cols}")
                return pd.DataFrame()
            
            # DataFrame oluştur
            df = self.loaded_data[required_cols].copy()
            df = df.dropna()
            
            # Sütun isimlerini standartlaştır
            df = df.rename(columns={
                'Enlem': 'lat',
                'Boylam': 'lon', 
                pga_column: 'pga'
            })
            
            # Sadece pozitif PGA değerlerini al
            df = df[df['pga'] > 0]
            
            print(f"📊 GeoJSON DataFrame hazırlandı: {len(df)} nokta ({dd_level})")
            return df
            
        except Exception as e:
            print(f"❌ GeoJSON DataFrame hatası: {e}")
            return pd.DataFrame()
    
    # def create_geojson_grid(self, dd_level, cell_size=0.1):
    #     """
    #     PGA verilerinden GeoJSON grid oluşturur - sadece Türkiye sınırları içindeki gridler (CACHE)
        
    #     Args:
    #         dd_level (str): DD seviyesi
    #         cell_size (float): Grid hücre boyutu (derece cinsinden)
            
    #     Returns:
    #         dict: GeoJSON FeatureCollection
    #     """
    #     # Cache key oluştur
    #     cache_key = f"geojson_{dd_level}_{cell_size}_{hash(str(self.file_path))}"
        
    #     # ⚡ Cache kontrol et
    #     cached_result = self._get_cached_geojson(cache_key)
    #     if cached_result is not None:
    #         return cached_result
        
    #     # Cache miss - hesapla
    #     print(f"🔄 Cache MISS: GeoJSON grid hesaplanıyor ({dd_level})...")
    #     start_time = time.time()
        
    #     df = self.get_pga_dataframe_for_geojson(dd_level)
        
    #     if df.empty:
    #         empty_result = {"type": "FeatureCollection", "features": []}
    #         self._cache_geojson(cache_key, empty_result)
    #         return empty_result
        
    #     try:
    #         # MapUtils'i import et
    #         from ..utils.map_utils import MapUtils
            
    #         features = []
    #         filtered_count = 0
    #         total_count = len(df)
            
    #         print(f"🔍 Hızlı Türkiye sınır kontrolü başlatılıyor: {total_count} PGA verisi")
    #         print(f"⚡ Cache sistemi + akıllı sampling aktif")
            
    #         # Cache'i temizle (yeni session için)
    #         MapUtils.clear_boundary_cache()
            
    #         for _, row in df.iterrows():
    #             lat, lon, pga = row['lat'], row['lon'], row['pga']
                
    #             # Kare poligon koordinatları oluştur
    #             half_size = cell_size / 2
    #             coordinates = [[
    #                 [lon - half_size, lat - half_size],  # Sol alt
    #                 [lon + half_size, lat - half_size],  # Sağ alt  
    #                 [lon + half_size, lat + half_size],  # Sağ üst
    #                 [lon - half_size, lat + half_size],  # Sol üst
    #                 [lon - half_size, lat - half_size]   # Kapatma
    #             ]]
                
    #             # Akıllı Türkiye sınır kontrolü - İstanbul özel durumu dahil
                
    #             # Özel durum: İstanbul bölgesi için gevşek kontrol (sahil bölgeleri için)
    #             is_istanbul_area = (40.8 <= lat <= 41.3) and (28.6 <= lon <= 29.4)
                
    #             if is_istanbul_area:
    #                 # İstanbul bölgesinde daha gevşek kontrol - sadece bbox yeterli
    #                 is_in_turkey = MapUtils.is_in_turkey(lat, lon)
    #                 if not is_in_turkey:
    #                     filtered_count += 1
    #                     continue  # İstanbul bbox dışındaysa filtrele
    #             else:
    #                 # Normal Türkiye sınır kontrolü
    #                 # 1. Önce merkez noktayı kontrol et
    #                 is_center_in_turkey = MapUtils.is_point_in_turkey_boundaries(lat, lon)
                    
    #                 if is_center_in_turkey:
    #                     # Merkez Türkiye içindeyse, grid kabul edilebilir
    #                     pass  # Devam et
    #                 else:
    #                     # Merkez Türkiye dışındaysa, 2 köşe daha kontrol et (diagonal)
    #                     corner_checks = [
    #                         (lat - half_size, lon - half_size),  # Sol alt
    #                         (lat + half_size, lon + half_size),  # Sağ üst (diagonal)
    #                     ]
                        
    #                     found_turkey_point = False
    #                     for corner_lat, corner_lon in corner_checks:
    #                         if MapUtils.is_point_in_turkey_boundaries(corner_lat, corner_lon):
    #                             found_turkey_point = True
    #                             break  # İlk pozitif sonuçta dur
                        
    #                     if not found_turkey_point:
    #                         # Ne merkez ne de köşeler Türkiye içinde değil
    #                         filtered_count += 1
    #                         continue  # Bu gridi filtrele
                
    #             # GeoJSON feature oluştur
    #             feature = {
    #                 "type": "Feature",
    #                 "geometry": {
    #                     "type": "Polygon",
    #                     "coordinates": coordinates
    #                 },
    #                 "properties": {
    #                     "pga": float(pga),
    #                     "lat": float(lat),
    #                     "lon": float(lon),
    #                     "dd_level": dd_level
    #                 }
    #             }
    #             features.append(feature)
            
    #         geojson = {
    #             "type": "FeatureCollection", 
    #             "features": features
    #         }
            
    #         # Performans istatistikleri
    #         end_time = time.time()
    #         processing_time = end_time - start_time
            
    #         print(f"📐 GeoJSON grid oluşturuldu: {len(features)} kare poligon")
    #         print(f"🚫 Filtrelenen (hızlı kontrol): {filtered_count} kare poligon")
    #         print(f"📊 İşlenen: {total_count} → Kabul: {len(features)} (%{len(features)/total_count*100:.1f})")
    #         print(f"🏙️ İstanbul özel bölge koruması aktif (Zeytinburnu dahil)")
    #         print(f"⚡ İşlem süresi: {processing_time:.2f} saniye")
            
    #         # ⚡ Cache'e kaydet
    #         self._cache_geojson(cache_key, geojson)
            
    #         return geojson
            
    #     except Exception as e:
    #         print(f"❌ GeoJSON grid oluşturma hatası: {e}")
    #         import traceback
    #         traceback.print_exc()
    #         return {"type": "FeatureCollection", "features": []}
    
    
    def create_geojson_grid(self, dd_level, cell_size=0.1):
        import time
        import json
        import os
        from shapely.geometry import shape, mapping, box
        from shapely.ops import unary_union
        from shapely.prepared import prep
        
        cache_key = f"geojson_clipped_v2_{dd_level}_{cell_size}_{hash(str(self.file_path))}"
        cached_result = self._get_cached_geojson(cache_key)
        if cached_result is not None:
            return cached_result
        
        start_time = time.time()
        df = self.get_pga_dataframe_for_geojson(dd_level)
        if df.empty:
            return {"type": "FeatureCollection", "features": []}

        try:
            mask_path = os.path.join("data", "turkey_land.geojson")
            with open(mask_path, 'r', encoding='utf-8') as f:
                turkey_data = json.load(f)
            
            # 1. TÜM POLİGONLARI BİRLEŞTİR (En Garanti Yol)
            # Dosyadaki tüm feature'ları alıp tek bir 'land' objesi yapıyoruz
            polygons = [shape(f['geometry']) for f in turkey_data['features']]
            turkey_geom = unary_union(polygons) 
            prepared_turkey = prep(turkey_geom) # Hızlandırma
            
            features = []
            half_size = cell_size / 2
            
            for _, row in df.iterrows():
                lat, lon, pga = row['lat'], row['lon'], row['pga']
                
                # Kareyi oluştur
                grid_poly = box(lon - half_size, lat - half_size, lon + half_size, lat + half_size)
                
                # 2. HIZLI KONTROL VE KESME
                if not prepared_turkey.intersects(grid_poly):
                    continue # Tamamen denizdeyse atla
                    
                if prepared_turkey.contains(grid_poly):
                    final_geom = mapping(grid_poly) # Tamamı karadaysa olduğu gibi al
                else:
                    # Kıyıdaysa budama yap
                    clipped_poly = grid_poly.intersection(turkey_geom)
                    if clipped_poly.is_empty:
                        continue
                    final_geom = mapping(clipped_poly)

                features.append({
                    "type": "Feature",
                    "geometry": final_geom,
                    "properties": {
                        "pga": float(pga),
                        "lat": float(lat),
                        "lon": float(lon),
                        "dd_level": dd_level
                    }
                })
            
            geojson_result = {"type": "FeatureCollection", "features": features}
            self._cache_geojson(cache_key, geojson_result)
            
            print(f"✅ İşlem Tamam: {len(features)} poligon | Süre: {time.time() - start_time:.2f}s")
            return geojson_result
            
        except Exception as e:
            print(f"❌ Kritik Hata: {e}")
            return {"type": "FeatureCollection", "features": []}
    


    @staticmethod
    def _parse_dd_number(dd_level: str) -> str:
        """DD seviyesinden say?sal de?eri (1-4) ??kar?r."""
        m = re.search(r"DD-?([1-4])", str(dd_level))
        if not m:
            raise ValueError(f"Deprem d?zeyi anla??lamad?: {dd_level}")
        return m.group(1)

    def _build_interpolation_payload(
        self, dd_number: str, cols: List[str]
    ) -> Tuple[np.ndarray, Dict[str, np.ndarray], List[Tuple[str, str]]]:
        """IDW i?in koordinat ve de?er dizilerini haz?rlar."""
        coords = self.loaded_data[['Enlem', 'Boylam']].to_numpy(dtype=float)
        values_dict: Dict[str, np.ndarray] = {}
        requests: List[Tuple[str, str]] = []

        for col in cols:
            col_str = str(col)
            if "_DD" in col_str:
                base_key = col_str.split("_")[0]
                full_col = col_str
            else:
                base_key = col_str
                full_col = f"{col_str}_DD{dd_number}"
            requests.append((base_key, full_col))

        missing_cols = [full for _, full in requests if full not in self.loaded_data.columns]
        if missing_cols:
            raise ValueError(f"Gerekli AFAD s?tunlar? eksik: {missing_cols}")

        for base_key, full_col in requests:
            values_dict[base_key] = self.loaded_data[full_col].to_numpy(dtype=float)

        return coords, values_dict, requests

    def get_interpolated_values(
        self,
        target_lat: float,
        target_lon: float,
        dd_level: str,
        cols: Optional[List[str]] = None,
        k: int = 8,
        power: float = 2.0,
    ) -> Dict[str, Optional[float]]:
        """AFAD uyumlu IDW ile istenen parametreleri enterpole eder."""
        if self.loaded_data is None:
            return {}

        cols = cols or ["PGA"]

        try:
            dd_number = self._parse_dd_number(dd_level)
            coords, values_dict, requests = self._build_interpolation_payload(dd_number, cols)
        except Exception as exc:
            print(f"Enterpolasyon haz?rlama hatas?: {exc}")
            return {}

        results = interpolate_idw(
            target_lat,
            target_lon,
            coords,
            values_dict,
            k=k,
            power=power,
        )

        missing_for_bilinear = [full for base, full in requests if results.get(base) is None]
        if missing_for_bilinear:
            bilinear_vals = bilinear_interpolate(
                self.loaded_data,
                target_lat,
                target_lon,
                missing_for_bilinear,
                lat_col='Enlem',
                lon_col='Boylam'
            )
            for base, full in requests:
                if results.get(base) is None:
                    val = bilinear_vals.get(full)
                    if val is not None:
                        results[base] = float(val)

        distances_cache = None
        for base, _ in requests:
            if results.get(base) is not None:
                continue
            arr = values_dict.get(base)
            if arr is None:
                continue
            mask = np.isfinite(arr) & (arr > 0)
            if not np.any(mask):
                continue
            if distances_cache is None:
                distances_cache = equirectangular_distance_m(
                    target_lat,
                    target_lon,
                    coords[:, 0],
                    coords[:, 1]
                )
            valid_idx = np.where(mask)[0]
            nearest_idx = int(valid_idx[np.argmin(distances_cache[valid_idx])])
            results[base] = float(arr[nearest_idx])

        return results

    def get_closest_pga_value(self, target_lat, target_lon, dd_level):
        """Verilen koordinat i?in AFAD uyumlu PGA de?erini hesaplar."""
        results = self.get_interpolated_values(
            target_lat,
            target_lon,
            dd_level,
            cols=["PGA"],
            k=8,
            power=2.0,
        )
        pga_value = results.get("PGA")
        if pga_value is not None:
            print(f"IDW (k=8, p=2) AFAD PGA: {pga_value:.4f} g")
        else:
            print("PGA de?eri hesaplanamad? (IDW/bilinear ba?ar?s?z).")
        return pga_value
