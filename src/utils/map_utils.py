"""
Harita işlemleri yardımcı modülü
"""

import os
import socket
import tempfile
import webbrowser
import json
from tkinter import messagebox

try:
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Türkiye sınır verileri için global değişkenler
_TURKEY_BOUNDARIES = None
_BOUNDARY_CACHE = {}  # Nokta kontrol sonuçlarını cache'le

class MapUtils:
    """Harita işlemleri yardımcı sınıfı"""
    
    @staticmethod
    def is_folium_available():
        """
        Folium kütüphanesinin kullanılabilir olup olmadığını kontrol eder
        
        Returns:
            bool: Folium mevcut mu
        """
        return FOLIUM_AVAILABLE
    
    @staticmethod
    def check_internet_connection(timeout=5):
        """
        Internet bağlantısını kontrol eder
        
        Args:
            timeout (int): Bağlantı timeout süresi (saniye)
            
        Returns:
            bool: Internet bağlantısı var mı
        """
        try:
            # Google DNS sunucusuna bağlantı denemesi
            socket.create_connection(("8.8.8.8", 53), timeout=timeout)
            return True
        except (socket.timeout, socket.error, OSError):
            try:
                # Alternatif olarak Cloudflare DNS'e deneme
                socket.create_connection(("1.1.1.1", 53), timeout=timeout)
                return True
            except (socket.timeout, socket.error, OSError):
                return False
    
    @staticmethod
    def validate_coordinates(lat, lon):
        """
        Koordinatların geçerli olup olmadığını kontrol eder
        
        Args:
            lat (float): Enlem
            lon (float): Boylam
            
        Returns:
            tuple: (is_valid, message)
        """
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return False, "Koordinatlar sayısal değerler olmalıdır."
        
        if not (-90 <= lat <= 90):
            return False, f"Enlem -90 ile 90 arasında olmalıdır. Girilen: {lat}"
        
        if not (-180 <= lon <= 180):
            return False, f"Boylam -180 ile 180 arasında olmalıdır. Girilen: {lon}"
        
        return True, "Koordinatlar geçerli."
    
    @staticmethod
    def create_location_map(lat, lon, earthquake_level=None, soil_class=None, geojson_data=None, sds_value=None, afad_pga_value=None, zoom_start=12):
        """
        Belirtilen koordinatlarda harita oluşturur ve tarayıcıda açar
        """
        if not FOLIUM_AVAILABLE:
            raise ImportError("Harita özelliği için 'folium' kütüphanesini kurun: pip install folium")
        
        # Internet bağlantısını kontrol et
        if not MapUtils.check_internet_connection():
            messagebox.showwarning(
                "Internet Bağlantısı Yok", 
                "Harita özelliği çalışması için internet bağlantısı gereklidir.\n"
                "Lütfen internet bağlantınızı kontrol edin ve tekrar deneyin."
            )
            return False
        
        try:
            # Koordinatın Türkiye içinde olup olmadığını kontrol et
            is_in_turkey = MapUtils.is_in_turkey(lat, lon)
            
            if is_in_turkey:
                map_center = [lat, lon]
                zoom_level = zoom_start if zoom_start != 12 else 12
            else:
                map_center = list(MapUtils.get_turkey_center())
                zoom_level = 6
            
            # Harita oluştur
            m = folium.Map(location=map_center, zoom_start=zoom_level, tiles='OpenStreetMap', min_zoom=5)
            
            # Farklı harita katmanları ekle
            folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri',
                name='Uydu Görüntüsü',
                overlay=False,
                control=True
            ).add_to(m)
            
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
                attr='Google',
                name='Google Hybrid',
                overlay=False,
                control=True
            ).add_to(m)
            
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
                attr='Google',
                name='Google Terrain',
                overlay=False,
                control=True
            ).add_to(m)
            
            # Türkiye sınırlarını ayarla
            bounds = MapUtils.get_turkey_bounds()
            m.options.update({
                'maxBounds': [[bounds["min_lat"] - 1, bounds["min_lon"] - 1], 
                             [bounds["max_lat"] + 1, bounds["max_lon"] + 1]],
                'maxBoundsViscosity': 1.0
            })
            
            # GeoJSON PGA grid katmanı ekle (varsa)
            if geojson_data and geojson_data.get('features'):
                try:
                    print(f"🔄 GeoJSON katmanı ekleniyor: Başlangıçta {len(geojson_data['features'])} poligon")
                    
                    # -------------------------------------------------------------------------
                    # KRİTİK NOKTA: DENİZLERE VE KOMŞULARA TAŞAN ALANLARI JİLET GİBİ KESİYORUZ
                    # -------------------------------------------------------------------------
                    try:
                        from shapely.geometry import Point, shape, box
                        import requests
                        
                        print("🌍 Türkiye'nin gerçek sınırları indiriliyor...")
                        turkey_url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/TUR.geo.json"
                        res = requests.get(turkey_url, timeout=5)
                        turkey_geom = shape(res.json()['features'][0]['geometry'])
                        
                        # Marmara Denizi'ni ve İstanbul'u kapsayacak şekilde poligonu doldur
                        # box(min_lon, min_lat, max_lon, max_lat)
                        marmara_box = box(26.0, 40.0, 30.0, 41.5) 
                        turkey_geom = turkey_geom.union(marmara_box)
                        
                        # Kıyı şeritlerinde (İzmir, Antalya vs.) denize sıfır noktaların silinmemesi için
                        # ~5.5 km'lik bir tampon (buffer) ekliyoruz.
                        turkey_geom = turkey_geom.buffer(0.05)
                        
                        filtered_features = []
                        for feat in geojson_data['features']:
                            f_lat = feat['properties'].get('lat')
                            f_lon = feat['properties'].get('lon')
                            if f_lat is not None and f_lon is not None:
                                # Nokta, güncellenmiş Türkiye poligonunun içindeyse ekle
                                if turkey_geom.contains(Point(f_lon, f_lat)):
                                    filtered_features.append(feat)
                        
                        geojson_data['features'] = filtered_features
                        print(f"✂️ Sınır dışı alanlar JİLET GİBİ kesildi. Kalan poligon: {len(geojson_data['features'])}")
                        
                    except ImportError:
                        print("⚠️ Hassas kesim için 'shapely' kütüphanesi eksik.")
                    except Exception as e:
                        print(f"⚠️ Sınır kesme işlemi başarısız oldu, normal şekilde devam ediliyor: {e}")
                    # -------------------------------------------------------------------------

                    # Eğer filtrelemeden sonra elde poligon kaldıysa ekle
                    if geojson_data['features']:
                        from branca.colormap import LinearColormap
                        
                        # PGA değer aralığını bul
                        pga_values = [f['properties']['pga'] for f in geojson_data['features']]
                        pga_min, pga_max = min(pga_values), max(pga_values)
                        
                        # Renk skalası oluştur (AFAD TDTH tarzı)
                        try:
                            color_scale = LinearColormap(colors=['yellow', 'orange', 'red'], vmin=pga_min, vmax=pga_max)
                        except Exception:
                            color_scale = LinearColormap(['blue', 'green', 'yellow', 'red'], vmin=pga_min, vmax=pga_max)
                        
                        # GeoJSON katmanı oluştur
                        geojson_layer = folium.GeoJson(
                            geojson_data,
                            style_function=lambda feat: {
                                'fillColor': color_scale(feat['properties']['pga']),
                                'color': 'transparent', 
                                'weight': 0, 
                                'fillOpacity': 0.4, 
                                'opacity': 0 
                            },
                            highlight_function=lambda feat: {
                                'fillOpacity': 0.7, 
                                'weight': 1, 
                                'color': 'white', 
                                'opacity': 0.8
                            },
                            tooltip=folium.GeoJsonTooltip(
                                fields=['pga', 'lat', 'lon'],
                                aliases=['🌍 AFAD PGA (g):', '📍 Enlem:', '📍 Boylam:'],
                                localize=True, sticky=True, labels=True,
                                style="background-color: #fff3e0; border: 2px solid #ff9800; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); font-family: Arial, sans-serif; font-size: 12px; padding: 8px;"
                            ),
                            popup=folium.GeoJsonPopup(
                                fields=['pga', 'lat', 'lon', 'dd_level'],
                                aliases=['📊 AFAD PGA Değeri (g):', '📍 Koordinat - Enlem:', '📍 Koordinat - Boylam:', '🏗️ Deprem Düzeyi:'],
                                localize=True,
                                style="background-color: #fff3e0; border-radius: 5px; font-family: Arial, sans-serif;"
                            ),
                            popup_keep_highlighted=True
                        )
                        
                        # LayerControl için feature group
                        feature_group = folium.FeatureGroup(name=f"PGA Dağılımı ({earthquake_level})")
                        geojson_layer.add_to(feature_group)
                        feature_group.add_to(m)
                        
                        # Renk skalası legend'ini ekle
                        color_scale.caption = f'PGA Değerleri (g) - {earthquake_level}'
                        color_scale.add_to(m)
                        
                        # LayerControl ekle
                        folium.LayerControl(position='topright', collapsed=False).add_to(m)
                except Exception as e:
                    print(f"❌ GeoJSON katmanı ekleme hatası: {e}")
            
            # Popup metni oluştur - daha büyük ve stil sahibi
            popup_html = f"""
            <div style="width: 280px; font-family: Arial, sans-serif;">
                <h4 style="margin: 0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #e74c3c; padding-bottom: 5px;">
                    📍 Analiz Noktası
                </h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px; font-weight: bold; color: #34495e; width: 40%;">🌍 Enlem:</td>
                        <td style="padding: 5px; color: #2c3e50;">{lat:.6f}°</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; font-weight: bold; color: #34495e;">🌍 Boylam:</td>
                        <td style="padding: 5px; color: #2c3e50;">{lon:.6f}°</td>
                    </tr>"""
            
            if sds_value is not None:
                popup_html += f"<tr><td style='padding: 5px; font-weight: bold; color: #34495e;'>⚡ SDS (Tasarım):</td><td style='padding: 5px; color: #8e44ad; font-weight: bold;'>{sds_value:.4f} g</td></tr>"
            if afad_pga_value is not None:
                popup_html += f"<tr><td style='padding: 5px; font-weight: bold; color: #34495e;'>🌍 PGA (AFAD):</td><td style='padding: 5px; color: #ff6b35; font-weight: bold;'>{afad_pga_value:.4f} g</td></tr>"
            if earthquake_level:
                popup_html += f"<tr><td style='padding: 5px; font-weight: bold; color: #34495e;'>🏗️ Deprem Düzeyi:</td><td style='padding: 5px; color: #e74c3c; font-weight: bold;'>{earthquake_level}</td></tr>"
            if soil_class:
                popup_html += f"<tr><td style='padding: 5px; font-weight: bold; color: #34495e;'>🌱 Zemin Sınıfı:</td><td style='padding: 5px; color: #27ae60; font-weight: bold;'>{soil_class}</td></tr>"
            
            popup_html += "</table></div>"
            
            popup = folium.Popup(popup_html, max_width=300, min_width=280)
            
            folium.Marker(
                [lat, lon], 
                popup=popup, 
                tooltip="Analiz Noktası - Detaylar için tıklayın", 
                icon=folium.Icon(color='red', icon='info-sign', prefix='fa')
            ).add_to(m)
            
            # Geçici HTML dosyası oluştur
# Geçici HTML dosyası oluştur
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
                temp_path = temp_file.name
            
            m.save(temp_path)
            
            # Türkiye sınır kilidi - Folium'da <body> olmadığı için </html> öncesine ekliyoruz
            bounds = MapUtils.get_turkey_bounds()
            lock_script = f"""
<script>
(function() {{
    function lockMap() {{
        var map = null;
        for (var key in window) {{
            try {{ if (window[key] instanceof L.Map) {{ map = window[key]; break; }} }} catch(e) {{}}
        }}
        if (!map) {{ setTimeout(lockMap, 300); return; }}
        var sw = L.latLng({bounds["min_lat"]}, {bounds["min_lon"]});
        var ne = L.latLng({bounds["max_lat"]}, {bounds["max_lon"]});
        var tb = L.latLngBounds(sw, ne);
        map.setMaxBounds(tb.pad(0.02));
        map.options.maxBoundsViscosity = 1.0;
        map.setMinZoom(6);
        map.on('drag', function() {{
            map.panInsideBounds(tb.pad(0.02), {{animate: false}});
        }});
    }}
    lockMap();
}})();
</script>
"""
            with open(temp_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            html_content = html_content.replace('</html>', lock_script + '\n</html>')
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            webbrowser.open(f'file://{os.path.abspath(temp_path)}')
                
            return True
            
        except Exception as e:
            messagebox.showerror("Harita Hatası", f"Harita oluşturulurken hata oluştu:\n{e}")
            return False
        
    @staticmethod
    def create_multi_point_map(points, zoom_start=10):
        """
        Birden fazla nokta için harita oluşturur
        
        Args:
            points (list): [(lat, lon, "label", earthquake_level, soil_class), ...] formatında nokta listesi
                          veya geriye uyumluluk için [(lat, lon, "label"), ...] 
            zoom_start (int): Başlangıç zoom seviyesi
            
        Returns:
            folium.Map veya None: Oluşturulan harita
        """
        if not FOLIUM_AVAILABLE:
            messagebox.showerror("Kütüphane Eksik", 
                               "Harita özelliği için 'folium' kütüphanesini kurun.")
            return None
        
        # Internet bağlantısını kontrol et
        if not MapUtils.check_internet_connection():
            messagebox.showwarning(
                "Internet Bağlantısı Yok", 
                "Harita özelliği çalışması için internet bağlantısı gereklidir.\n"
                "Lütfen internet bağlantınızı kontrol edin ve tekrar deneyin."
            )
            return None
        
        if not points:
            messagebox.showerror("Veri Hatası", "Gösterilecek nokta bulunamadı.")
            return None
        
        try:
            # İlk noktanın koordinatlarını kontrol et
            first_lat, first_lon = points[0][0], points[0][1]
            is_in_turkey = MapUtils.is_in_turkey(first_lat, first_lon)
            
            if is_in_turkey:
                # Türkiye içindeyse ilk noktaya odaklan
                map_center = [first_lat, first_lon]
                zoom_level = zoom_start if zoom_start != 10 else 10  # Default 10 kullan
            else:
                # Türkiye dışındaysa Türkiye merkezini kullan
                map_center = list(MapUtils.get_turkey_center())
                zoom_level = 6  # Türkiye genelini göster
            
            # Haritayı oluştur - ilk nokta odaklı
            m = folium.Map(location=map_center, zoom_start=zoom_level, tiles='OpenStreetMap')
            
            # Türkiye sınırlarını ayarla
            bounds = MapUtils.get_turkey_bounds()
            m.options.update({
                'maxBounds': [[bounds["min_lat"] - 1, bounds["min_lon"] - 1], 
                             [bounds["max_lat"] + 1, bounds["max_lon"] + 1]],
                'maxBoundsViscosity': 1.0
            })
            
            # Mini map eklentisi ekle
            try:
                from folium.plugins import MiniMap
                minimap = MiniMap(toggle_display=True, minimized=False, width=150, height=150)
                m.add_child(minimap)
            except ImportError:
                print("⚠️ MiniMap özelliği için folium sürümünü güncelleyin: pip install --upgrade folium")
                
            # MousePosition eklentisi ekle
            try:
                from folium.plugins import MousePosition
                mouse_position = MousePosition(
                    position='topright',
                    separator=' | ',
                    empty_string='Harita dışı',
                    lng_first=False,
                    num_digits=6,
                    prefix='Koordinatlar:',
                    lat_formatter="function(num) {return L.Util.formatNum(num, 6) + ' °N';}",
                    lng_formatter="function(num) {return L.Util.formatNum(num, 6) + ' °E';}"
                )
                m.add_child(mouse_position)
            except ImportError:
                print("⚠️ MousePosition özelliği için folium sürümünü güncelleyin: pip install --upgrade folium")
                
            # MeasureControl eklentisi ekle
            try:
                from folium.plugins import MeasureControl
                measure_control = MeasureControl(
                    position='topleft',
                    primary_length_unit='meters',
                    secondary_length_unit='kilometers',
                    primary_area_unit='sqmeters',
                    secondary_area_unit='hectares',
                    captured_options={
                        'color': '#e74c3c',
                        'weight': 3,
                        'opacity': 0.8
                    },
                    measure_options={
                        'color': '#3498db',
                        'weight': 2,
                        'opacity': 0.7
                    }
                )
                m.add_child(measure_control)
            except ImportError:
                print("⚠️ MeasureControl özelliği için folium sürümünü güncelleyin: pip install --upgrade folium")
            
            # Her noktayı haritaya ekle
            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 
                     'lightred', 'beige', 'darkblue', 'darkgreen']
            
            for i, point in enumerate(points):
                # Geriye uyumluluk için farklı tuple boyutlarını destekle
                if len(point) >= 5:
                    lat, lon, label, earthquake_level, soil_class = point[:5]
                elif len(point) >= 3:
                    lat, lon, label = point[:3]
                    earthquake_level = soil_class = None
                else:
                    continue  # Geçersiz veri formatı
                
                # Koordinatları doğrula
                is_valid, _ = MapUtils.validate_coordinates(lat, lon)
                if not is_valid:
                    continue
                
                color = colors[i % len(colors)]
                
                # Büyük ve stilize popup oluştur
                popup_html = f"""
                <div style="width: 280px; font-family: Arial, sans-serif;">
                    <h4 style="margin: 0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #{color}; padding-bottom: 5px;">
                        📍 {label}
                    </h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 5px; font-weight: bold; color: #34495e; width: 40%;">🌍 Enlem:</td>
                            <td style="padding: 5px; color: #2c3e50;">{lat:.6f}°</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold; color: #34495e;">🌍 Boylam:</td>
                            <td style="padding: 5px; color: #2c3e50;">{lon:.6f}°</td>
                        </tr>"""
                
                # Ek parametreler varsa popup'a ekle
                if earthquake_level:
                    popup_html += f"""
                        <tr>
                            <td style="padding: 5px; font-weight: bold; color: #34495e;">🏗️ Deprem Düzeyi:</td>
                            <td style="padding: 5px; color: #e74c3c; font-weight: bold;">{earthquake_level}</td>
                        </tr>"""
                if soil_class:
                    popup_html += f"""
                        <tr>
                            <td style="padding: 5px; font-weight: bold; color: #34495e;">🌱 Zemin Sınıfı:</td>
                            <td style="padding: 5px; color: #27ae60; font-weight: bold;">{soil_class}</td>
                        </tr>"""
                
                popup_html += """
                    </table>
                </div>
                """
                
                # Büyük popup ile marker ekle
                popup = folium.Popup(
                    popup_html,
                    max_width=300,
                    min_width=280
                )
                
                folium.Marker(
                    [lat, lon],
                    popup=popup,
                    tooltip=f"{label} - Detaylar için tıklayın",
                    icon=folium.Icon(color=color, icon='info-sign', prefix='fa')
                ).add_to(m)
            
            return m
            
        except Exception as e:
            messagebox.showerror("Harita Hatası", f"Çoklu nokta haritası oluşturulurken hata:\n{e}")
            return None
    
    @staticmethod
    def save_map_to_html(map_obj, file_path=None):
        """
        Haritayı HTML dosyası olarak kaydeder
        
        Args:
            map_obj (folium.Map): Kaydedilecek harita
            file_path (str, optional): Dosya yolu. None ise dialog açılır
            
        Returns:
            bool: İşlem başarılı mı
        """
        if map_obj is None:
            return False
        
        if file_path is None:
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="Haritayı HTML Olarak Kaydet",
                defaultextension=".html",
                filetypes=[("HTML Dosyası", "*.html")]
            )
        
        if not file_path:
            return False
        
        try:
            map_obj.save(file_path)
            messagebox.showinfo("Başarılı", f"Harita başarıyla kaydedildi:\n{file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Kayıt Hatası", f"Harita kaydedilirken hata oluştu:\n{e}")
            return False
    
    @staticmethod
    def get_turkey_bounds():
        """
        Türkiye'nin koordinat sınırlarını döndürür (daha sıkı karasal sınırlar)
        
        Returns:
            dict: {"min_lat", "max_lat", "min_lon", "max_lon"}
        """
        return {
            "min_lat": 35.85,   # En güney nokta (daha sıkı)
            "max_lat": 42.05,   # En kuzey nokta (daha sıkı)  
            "min_lon": 26.3,    # En batı nokta (daha sıkı)
            "max_lon": 44.7     # En doğu nokta (daha sıkı)
        }
    
    @staticmethod
    def is_in_turkey(lat, lon):
        """
        Verilen koordinatın Türkiye sınırları içinde olup olmadığını kontrol eder
        
        Args:
            lat (float): Enlem
            lon (float): Boylam
            
        Returns:
            bool: Türkiye içinde mi
        """
        bounds = MapUtils.get_turkey_bounds()
        return (bounds["min_lat"] <= lat <= bounds["max_lat"] and 
                bounds["min_lon"] <= lon <= bounds["max_lon"])
    
    @staticmethod
    def get_turkey_center():
        """
        Türkiye'nin merkez koordinatlarını döndürür
        
        Returns:
            tuple: (lat, lon) Türkiye'nin merkez koordinatları
        """
        bounds = MapUtils.get_turkey_bounds()
        center_lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
        center_lon = (bounds["min_lon"] + bounds["max_lon"]) / 2
        return center_lat, center_lon
    
    @staticmethod
    def setup_turkey_bounds(map_obj):
        """
        Haritayı Türkiye sınırlarıyla sınırlar
        
        Args:
            map_obj (folium.Map): Sınırlanacak harita objesi
        """
        bounds = MapUtils.get_turkey_bounds()
        
        # Haritayı Türkiye sınırlarına fit et
        southwest = [bounds["min_lat"], bounds["min_lon"]]
        northeast = [bounds["max_lat"], bounds["max_lon"]]
        map_obj.fit_bounds([southwest, northeast])
        
        # Max bounds ayarla - kullanıcının Türkiye dışına çıkmasını engeller
        map_obj.options.update({
            'maxBounds': [[bounds["min_lat"] - 1, bounds["min_lon"] - 1], 
                         [bounds["max_lat"] + 1, bounds["max_lon"] + 1]],
            'maxBoundsViscosity': 1.0
        })
    
    @staticmethod
    def _load_turkey_boundaries():
        """
        Türkiye sınır verilerini yükler
        
        Returns:
            dict: GeoJSON formatında Türkiye sınır verileri
        """
        global _TURKEY_BOUNDARIES
        
        if _TURKEY_BOUNDARIES is not None:
            return _TURKEY_BOUNDARIES
        
        try:
            # JSON dosyasının yolunu belirle
            current_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(current_dir, 'tr-cities-utf8.json')
            
            if not os.path.exists(json_path):
                print(f"❌ Türkiye sınır dosyası bulunamadı: {json_path}")
                return None
            
            # JSON dosyasını yükle
            with open(json_path, 'r', encoding='utf-8') as f:
                _TURKEY_BOUNDARIES = json.load(f)
            
            print(f"✅ Türkiye sınır verileri yüklendi: {len(_TURKEY_BOUNDARIES.get('features', []))} şehir")
            return _TURKEY_BOUNDARIES
            
        except Exception as e:
            print(f"❌ Türkiye sınır verileri yükleme hatası: {e}")
            return None
    
    @staticmethod
    def _point_in_polygon(point_lat, point_lon, polygon_coords):
        """
        Bir noktanın poligon içinde olup olmadığını kontrol eder (Ray Casting algoritması)
        
        Args:
            point_lat (float): Nokta enlemi
            point_lon (float): Nokta boylamı
            polygon_coords (list): Poligon koordinat listesi [[lon, lat], ...]
            
        Returns:
            bool: Nokta poligon içinde mi
        """
        if not polygon_coords or len(polygon_coords) < 3:
            return False
        
        x, y = point_lon, point_lat
        n = len(polygon_coords)
        inside = False
        
        p1x, p1y = polygon_coords[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon_coords[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    @staticmethod
    def _point_in_multipolygon(point_lat, point_lon, multipolygon_coords):
        """
        Bir noktanın MultiPolygon içinde olup olmadığını kontrol eder
        
        Args:
            point_lat (float): Nokta enlemi
            point_lon (float): Nokta boylamı
            multipolygon_coords (list): MultiPolygon koordinat listesi
            
        Returns:
            bool: Nokta MultiPolygon içinde mi
        """
        for polygon in multipolygon_coords:
            # Her poligonun ilk halka ana sınır, diğerleri delik
            if len(polygon) > 0:
                outer_ring = polygon[0]
                if MapUtils._point_in_polygon(point_lat, point_lon, outer_ring):
                    # Ana sınır içindeyse, delikleri kontrol et
                    in_hole = False
                    for hole in polygon[1:]:
                        if MapUtils._point_in_polygon(point_lat, point_lon, hole):
                            in_hole = True
                            break
                    
                    if not in_hole:
                        return True
        
        return False
    
    @staticmethod
    def is_point_in_turkey_boundaries(lat, lon):
        """
        Verilen koordinatın Türkiye şehir sınırları içinde olup olmadığını kontrol eder (Cache'li)
        
        Args:
            lat (float): Enlem
            lon (float): Boylam
            
        Returns:
            bool: Türkiye sınırları içinde mi
        """
        global _BOUNDARY_CACHE
        
        # Koordinatları cache için yuvarla (0.01 derece hassasiyet)
        cache_lat = round(lat, 2)
        cache_lon = round(lon, 2)
        cache_key = f"{cache_lat},{cache_lon}"
        
        # Cache'de var mı kontrol et
        if cache_key in _BOUNDARY_CACHE:
            return _BOUNDARY_CACHE[cache_key]
        
        # Önce basit bbox kontrolü yap - performans için
        if not MapUtils.is_in_turkey(lat, lon):
            _BOUNDARY_CACHE[cache_key] = False
            return False  # Basit sınırlar dışındaysa direkt false döndür
        
        boundaries = MapUtils._load_turkey_boundaries()
        if not boundaries or 'features' not in boundaries:
            result = MapUtils.is_in_turkey(lat, lon)  # Fallback
            _BOUNDARY_CACHE[cache_key] = result
            return result
        
        # Her şehrin sınırlarını kontrol et
        for feature in boundaries['features']:
            if 'geometry' not in feature:
                continue
                
            geometry = feature['geometry']
            geom_type = geometry.get('type')
            coordinates = geometry.get('coordinates', [])
            
            if geom_type == 'Polygon':
                # Poligonun ilk halka ana sınır, diğerleri delik
                if len(coordinates) > 0:
                    outer_ring = coordinates[0]
                    if MapUtils._point_in_polygon(lat, lon, outer_ring):
                        # Ana sınır içindeyse, delikleri kontrol et
                        in_hole = False
                        for hole in coordinates[1:]:
                            if MapUtils._point_in_polygon(lat, lon, hole):
                                in_hole = True
                                break
                        
                        if not in_hole:
                            _BOUNDARY_CACHE[cache_key] = True
                            return True
            
            elif geom_type == 'MultiPolygon':
                if MapUtils._point_in_multipolygon(lat, lon, coordinates):
                    _BOUNDARY_CACHE[cache_key] = True
                    return True
        
        _BOUNDARY_CACHE[cache_key] = False
        return False
    
    @staticmethod
    def clear_boundary_cache():
        """Boundary cache'ini temizle"""
        global _BOUNDARY_CACHE
        _BOUNDARY_CACHE.clear() 