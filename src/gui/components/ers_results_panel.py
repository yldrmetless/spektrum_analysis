"""
ERS Hesaplama Sonuçları paneli bileşeni
Hesaplama detayları ve sonuçları tabular formatta gösterir
"""

import tkinter as tk
from tkinter import ttk
import numpy as np
import pandas as pd

# Opsiyonel sabitler: yerçekimi için merkezi değerler
try:
    from src.config.constants import GRAVITY, GRAVITY_CM
except Exception:
    try:
        from config.constants import GRAVITY, GRAVITY_CM
    except Exception:
        GRAVITY = 9.80665
        GRAVITY_CM = 980.665
class ERSResultsPanel:
    """ERS hesaplama sonuçları paneli sınıfı"""
    
    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        self.current_results = None
        self.current_parameters = None
        
        # GUI bileşenleri
        self.main_frame = None
        self.parameters_tree = None
        self.results_tree = None
        self.summary_tree = None
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Widget'ları oluşturur"""
        # Ana çerçeve
        self.main_frame = ttk.Frame(self.parent_frame)
        self.main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Notebook oluştur (parametreler, sonuçlar, özet)
        self.results_notebook = ttk.Notebook(self.main_frame)
        self.results_notebook.pack(fill="both", expand=True)
        
        # Parametreler sekmesi
        self._create_parameters_tab()
        
        # Sonuçlar sekmesi  
        self._create_results_tab()
        
        # Özet sekmesi
        self._create_summary_tab()
    
    def _create_parameters_tab(self):
        """Hesaplama parametreleri sekmesi"""
        params_tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(params_tab, text="⚙️ Parametreler")
        
        # Parametreler tablosu
        params_frame = ttk.LabelFrame(params_tab, text="Hesaplama Parametreleri", padding=10)
        params_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # TreeView oluştur
        columns = ("Parametre", "Değer", "Açıklama")
        self.parameters_tree = ttk.Treeview(params_frame, columns=columns, show="headings", height=15)
        
        # Sütun başlıkları
        self.parameters_tree.heading("Parametre", text="Parametre")
        self.parameters_tree.heading("Değer", text="Değer")
        self.parameters_tree.heading("Açıklama", text="Açıklama")
        
        # Sütun genişlikleri
        self.parameters_tree.column("Parametre", width=200)
        self.parameters_tree.column("Değer", width=150)
        self.parameters_tree.column("Açıklama", width=400)
        
        # Scrollbar
        params_scrollbar = ttk.Scrollbar(params_frame, orient="vertical", command=self.parameters_tree.yview)
        self.parameters_tree.configure(yscrollcommand=params_scrollbar.set)
        
        # Pack
        self.parameters_tree.pack(side="left", fill="both", expand=True)
        params_scrollbar.pack(side="right", fill="y")
    
    def _create_results_tab(self):
        """Detaylı sonuçlar sekmesi"""
        results_tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(results_tab, text="📊 Detaylı Sonuçlar")
        
        # Sonuçlar tablosu
        self.results_frame = ttk.LabelFrame(results_tab, text="ERS Hesaplama Sonuçları", padding=10)
        self.results_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Başlangıçta boş bir ağaç; gerçek sütunlar sonuçlara göre oluşturulacak
        self.results_tree = ttk.Treeview(self.results_frame, columns=("Bilgi",), show="headings", height=20)
        self.results_tree.heading("Bilgi", text="Hesaplama sonrası sonuçlar burada gösterilecektir", anchor="center")
        self.results_tree.column("Bilgi", width=400, anchor="center")
        
        # Scrollbar
        self.results_scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=self.results_scrollbar.set)
        
        # Pack
        self.results_tree.pack(side="left", fill="both", expand=True)
        self.results_scrollbar.pack(side="right", fill="y")
        
        # Export butonu
        export_frame = ttk.Frame(results_tab)
        export_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Button(export_frame, text="📄 Sonuçları Excel'e Aktar", 
                  command=self._export_results).pack(side="left", padx=5)
    
    def _create_summary_tab(self):
        """Özet istatistikler sekmesi"""
        summary_tab = ttk.Frame(self.results_notebook)
        self.results_notebook.add(summary_tab, text="📈 Özet")
        
        # Özet tablosu
        summary_frame = ttk.LabelFrame(summary_tab, text="Özet İstatistikler", padding=10)
        summary_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # TreeView oluştur
        columns = ("Sönüm", "Max_Sd", "Max_Sv", "Max_Sa_g", "T_at_Max_Sa", "PGA_Ratio")
        self.summary_tree = ttk.Treeview(summary_frame, columns=columns, show="headings", height=10)
        
        # Sütun başlıkları (ortalanmış)
        self.summary_tree.heading("Sönüm", text="ζ (%)", anchor="center")
        self.summary_tree.heading("Max_Sd", text="Max Sd (m)", anchor="center")
        self.summary_tree.heading("Max_Sv", text="Max Sv (m/s)", anchor="center")
        self.summary_tree.heading("Max_Sa_g", text="Max Sa (g)", anchor="center")
        self.summary_tree.heading("T_at_Max_Sa", text="T @ Max Sa (s)", anchor="center")
        self.summary_tree.heading("PGA_Ratio", text="Sa/PGA", anchor="center")
        
        # Sütun genişlikleri ve içerik hizası (ortala)
        for col in columns:
            self.summary_tree.column(col, width=120, anchor="center")
        
        # Scrollbar
        summary_scrollbar = ttk.Scrollbar(summary_frame, orient="vertical", command=self.summary_tree.yview)
        self.summary_tree.configure(yscrollcommand=summary_scrollbar.set)
        
        # Pack
        self.summary_tree.pack(side="left", fill="both", expand=True)
        summary_scrollbar.pack(side="right", fill="y")
    
    def update_results(self, results_data, parameters_data, earthquake_data=None):
        """
        Sonuçları günceller
        
        Args:
            results_data: ERS hesaplama sonuçları
            parameters_data: Hesaplama parametreleri
            earthquake_data: Deprem kaydı verileri (opsiyonel)
        """
        self.current_results = results_data
        self.current_parameters = parameters_data
        
        # Parametreleri güncelle
        self._update_parameters(parameters_data, earthquake_data)
        
        # Sonuçları güncelle
        self._update_results(results_data)
        
        # Özeti güncelle
        self._update_summary(results_data, earthquake_data)
    
    def _update_parameters(self, parameters, earthquake_data):
        """Parametreler tablosunu günceller"""
        # Tabloyu temizle
        for item in self.parameters_tree.get_children():
            self.parameters_tree.delete(item)
        
        if not parameters:
            return
        
        # Parametreleri ekle
        param_list = [
            ("Sönüm Oranları (%)", 
             ", ".join([f"{z:.1f}" for z in parameters.get('damping_list', [])]),
             "Hesaplanan sönüm oranları"),
            
            ("Minimum Periyot (s)", 
             f"{parameters.get('Tmin', 0):.3f}",
             "Spektrum hesaplama alt sınırı"),
            
            ("Maksimum Periyot (s)", 
             f"{parameters.get('Tmax', 0):.3f}",
             "Spektrum hesaplama üst sınırı"),
            
            ("Periyot Sayısı", 
             str(parameters.get('nT', 0)),
             "Hesaplanan periyot noktası sayısı"),
            
            ("Periyot Dağılımı", 
             "Logaritmik" if parameters.get('logspace', True) else "Lineer",
             "Periyot noktalarının dağılım türü"),
            
            ("İvme Birimi", 
             parameters.get('accel_unit', 'g'),
             "Giriş ivme verisinin birimi"),
            
            ("dt/T Kontrolü", 
             f"{parameters.get('enforce_dt_over_T', 0):.3f}" if parameters.get('enforce_dt_over_T') else "Yok",
             "Zaman adımı/periyot oranı kontrolü")
        ]
        
        # Deprem kaydı bilgileri (varsa)
        if earthquake_data:
            time_data, acceleration, dt, accel_unit = earthquake_data
            param_list.extend([
                ("", "", ""),  # Boş satır
                ("=== Deprem Kaydı Bilgileri ===", "", ""),
                ("Zaman Adımı (s)", f"{dt:.6f}", "Orijinal kayıt zaman adımı"),
                ("Örneklem Sayısı", f"{len(acceleration)}", "Toplam veri noktası sayısı"),
                ("Toplam Süre (s)", f"{time_data[-1] - time_data[0]:.2f}", "Kayıt süresi"),
                ("Örnekleme Frekansı (Hz)", f"{1/dt:.2f}", "Saniyedeki örneklem sayısı"),
                ("PGA", f"{np.max(np.abs(acceleration)):.3f} {accel_unit}", "En büyük yer ivmesi")
            ])
        
        # Tabloya ekle
        for param, value, desc in param_list:
            if param.startswith("==="):
                # Başlık satırı
                self.parameters_tree.insert("", "end", values=(param, "", ""), tags=("header",))
            elif param == "":
                # Boş satır
                self.parameters_tree.insert("", "end", values=("", "", ""))
            else:
                self.parameters_tree.insert("", "end", values=(param, value, desc))
        
        # Başlık stilini ayarla
        self.parameters_tree.tag_configure("header", background="lightblue", font=("TkDefaultFont", 9, "bold"))
    
    def _update_results(self, results_data):
        """Sonuçlar tablosunu günceller"""
        # Eski ağacı kaldır ve yeni sütunları inşa et
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        if not results_data:
            # Boş ise yer tutucu göster
            self.results_tree = ttk.Treeview(self.results_frame, columns=("Bilgi",), show="headings", height=20)
            self.results_tree.heading("Bilgi", text="Sonuç bulunamadı", anchor="center")
            self.results_tree.column("Bilgi", width=300, anchor="center")
            self.results_tree.pack(side="left", fill="both", expand=True)
            self.results_scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.results_tree.yview)
            self.results_tree.configure(yscrollcommand=self.results_scrollbar.set)
            self.results_scrollbar.pack(side="right", fill="y")
            return

        # Sıralı sönüm listesi
        dampings = sorted(results_data.keys())
        # T referansı: ilk sönüm değerinden
        first_curves = results_data[dampings[0]]
        T_values = first_curves.T

        # Dinamik sütunlar: T (s) + her sönüm için 3 sütun
        dynamic_columns = ["T (s)"]
        for z in dampings:
            dynamic_columns.extend([
                f"Sd (m) ζ %{z:.1f}",
                f"Sv (m/s) ζ %{z:.1f}",
                f"Sa (g) ζ %{z:.1f}",
            ])

        self.results_tree = ttk.Treeview(self.results_frame, columns=dynamic_columns, show="headings", height=20)

        # Başlık ve genişlikler
        for col in dynamic_columns:
            self.results_tree.heading(col, text=col, anchor="center")
            base_width = 110 if col.startswith("T (s)") else 140
            self.results_tree.column(col, width=base_width, anchor="center")

        # Satırları doldur
        for i, T in enumerate(T_values):
            row_vals = [f"{T:.3f}"]
            for z in dampings:
                curves = results_data[z]
                row_vals.extend([
                    f"{curves.Sd[i]:.6f}",
                    f"{curves.Sv_p[i]:.3f}",
                    f"{curves.Sa_p_g[i]:.3f}",
                ])
            self.results_tree.insert("", "end", values=row_vals)

        # Scrollbar
        self.results_scrollbar = ttk.Scrollbar(self.results_frame, orient="vertical", command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=self.results_scrollbar.set)

        # Yerleşim
        self.results_tree.pack(side="left", fill="both", expand=True)
        self.results_scrollbar.pack(side="right", fill="y")
    
    def _update_summary(self, results_data, earthquake_data):
        """Özet tablosunu günceller"""
        # Tabloyu temizle
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)
        
        if not results_data:
            return
        
        # PGA hesapla (varsa) ve g'ye dönüştür
        pga = None
        if earthquake_data:
            _, acceleration, _, accel_unit = earthquake_data
            pga_val = np.max(np.abs(acceleration)) if acceleration is not None and len(acceleration) > 0 else None
            if pga_val is not None:
                pga = self._accel_value_to_g(pga_val, accel_unit)
        
        # Her sönüm oranı için özet istatistikler
        for z_pct, curves in results_data.items():
            # Maksimum değerler
            max_sd = np.max(curves.Sd)
            max_sv = np.max(curves.Sv_p)
            max_sa_g = np.max(curves.Sa_p_g)
            
            # Maksimum Sa'da periyot
            max_sa_idx = np.argmax(curves.Sa_p_g)
            t_at_max_sa = curves.T[max_sa_idx]
            
            # Sa/PGA oranı
            sa_pga_ratio = max_sa_g / pga if pga else 0
            
            self.summary_tree.insert("", "end", values=(
                f"{z_pct:.1f}",
                f"{max_sd:.6f}",
                f"{max_sv:.3f}",
                f"{max_sa_g:.3f}",
                f"{t_at_max_sa:.3f}",
                f"{sa_pga_ratio:.2f}" if pga else "N/A"
            ))

    def _accel_value_to_g(self, value: float, unit: str) -> float:
        """İvme değerini 'g' birimine dönüştürür (tek noktaya toplanmış yardımcı)."""
        try:
            if unit == 'g':
                return float(value)
            if unit == 'm/s²':
                return float(value) / GRAVITY
            if unit == 'cm/s²':
                return float(value) / GRAVITY_CM
            if unit == 'mm/s²':
                return float(value) / (GRAVITY_CM * 10.0)
        except Exception:
            pass
        # Bilinmeyen durumda değişmeden döndür
        return float(value)
    
    def _export_results(self):
        """Sonuçları Excel'e aktarır"""
        if not self.current_results:
            tk.messagebox.showerror("Hata", "Önce ERS hesaplama yapın!")
            return
        
        try:
            # 1) Parametreler sheet'i verisini hazırla
            params_data = []
            for child in self.parameters_tree.get_children():
                values = self.parameters_tree.item(child)['values']
                if len(values) >= 3:
                    params_data.append({'Parametre': values[0], 'Değer': values[1], 'Açıklama': values[2]})
            params_df = pd.DataFrame(params_data) if params_data else pd.DataFrame()

            # 2) Detaylı sonuçlar sheet'i
            results_rows = []
            cols_option = self.results_tree["columns"]
            if isinstance(cols_option, (list, tuple)):
                headers = list(cols_option)
            else:
                try:
                    headers = list(self.results_tree.tk.splitlist(cols_option))
                except Exception:
                    headers = []
            for child in self.results_tree.get_children():
                row_vals = self.results_tree.item(child)['values']
                row_dict = {}
                for h, v in zip(headers, row_vals):
                    try:
                        row_dict[h] = float(str(v).replace(',', '.'))
                    except Exception:
                        row_dict[h] = v
                results_rows.append(row_dict)
            results_df = pd.DataFrame(results_rows) if results_rows else pd.DataFrame()

            # 3) Özet sheet'i
            summary_data = []
            for child in self.summary_tree.get_children():
                values = self.summary_tree.item(child)['values']
                if len(values) >= 6:
                    summary_data.append({
                        'Sönüm (%)': float(values[0]),
                        'Max Sd (m)': float(values[1]),
                        'Max Sv (m/s)': float(values[2]),
                        'Max Sa (g)': float(values[3]),
                        'T @ Max Sa (s)': float(values[4]),
                        'Sa/PGA': values[5] if values[5] != 'N/A' else None
                    })
            summary_df = pd.DataFrame(summary_data) if summary_data else pd.DataFrame()

            # 4) FileUtils ile çok sayfalı export
            try:
                from src.utils.file_utils import FileUtils
            except Exception:
                try:
                    from utils.file_utils import FileUtils
                except Exception:
                    FileUtils = None
            if FileUtils is not None:
                sheets = {
                    'Parametreler': params_df,
                    'Detaylı Sonuçlar': results_df,
                    'Özet İstatistikler': summary_df
                }
                success = FileUtils.export_excel_sheets(sheets, file_path=None, title="ERS Sonuçları Kaydet")
                if success:
                    return

            # FileUtils yoksa fallback
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                title="ERS Sonuçları Kaydet",
                defaultextension=".xlsx",
                filetypes=[("Excel dosyaları", "*.xlsx"), ("Tüm dosyalar", "*.*")]
            )
            if not filename:
                return
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                if not params_df.empty:
                    params_df.to_excel(writer, sheet_name='Parametreler', index=False)
                if not results_df.empty:
                    results_df.to_excel(writer, sheet_name='Detaylı Sonuçlar', index=False)
                if not summary_df.empty:
                    summary_df.to_excel(writer, sheet_name='Özet İstatistikler', index=False)
            tk.messagebox.showinfo("Başarılı", f"ERS sonuçları kaydedildi:\n{filename}")
                
        except ImportError:
            tk.messagebox.showerror("Hata", "Excel dışa aktarma için pandas ve openpyxl gerekli.")
        except Exception as e:
            tk.messagebox.showerror("Hata", f"Dışa aktarma hatası:\n{str(e)}")
    
    def clear_results(self):
        """Tüm sonuçları temizler"""
        # Tabloları temizle
        for tree in [self.parameters_tree, self.results_tree, self.summary_tree]:
            if tree:
                for item in tree.get_children():
                    tree.delete(item)
        
        self.current_results = None
        self.current_parameters = None
