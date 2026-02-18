"""
Gelişmiş export modülü - CSV, MATLAB .mat, JSON formatları
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
from tkinter import filedialog, messagebox
import os
from datetime import datetime

try:
    import scipy.io as sio
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

class AdvancedExporter:
    """Gelişmiş export sınıfı"""
    
    @staticmethod
    def export_to_csv(data: Dict[str, np.ndarray], 
                      metadata: Optional[Dict] = None,
                      file_path: Optional[str] = None) -> bool:
        """
        Verileri CSV formatına aktarır
        
        Args:
            data: Export edilecek veri dictionary'si
            metadata: Metadata bilgileri
            file_path: Kayıt yolu (None ise dialog açılır)
            
        Returns:
            bool: Başarı durumu
        """
        try:
            # Dosya yolu seçimi
            if not file_path:
                file_path = filedialog.asksaveasfilename(
                    title="CSV Olarak Kaydet",
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
                )
            
            if not file_path:
                return False
            
            # DataFrame oluştur
            df_data = {}
            
            # Veri uzunluklarını kontrol et
            max_length = 0
            for key, values in data.items():
                if isinstance(values, (list, np.ndarray)) and len(values) > max_length:
                    max_length = len(values)
            
            # Verileri DataFrame'e ekle
            for key, values in data.items():
                if isinstance(values, (list, np.ndarray)):
                    # Uzunlukları eşitle (kısa olanları NaN ile doldur)
                    if len(values) < max_length:
                        padded_values = np.full(max_length, np.nan)
                        padded_values[:len(values)] = values
                        df_data[key] = padded_values
                    else:
                        df_data[key] = values
                else:
                    # Skaler değerler için ilk satırda göster
                    scalar_column = np.full(max_length, np.nan)
                    scalar_column[0] = values
                    df_data[key] = scalar_column
            
            df = pd.DataFrame(df_data)
            
            # Metadata varsa başa ekle
            if metadata:
                # Metadata satırlarını oluştur
                metadata_lines = []
                metadata_lines.append("# Metadata")
                metadata_lines.append(f"# Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                for key, value in metadata.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            metadata_lines.append(f"# {key}.{sub_key}: {sub_value}")
                    else:
                        metadata_lines.append(f"# {key}: {value}")
                
                metadata_lines.append("# Data starts below")
                metadata_lines.append("")
                
                # Metadata'yı dosyaya yaz
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in metadata_lines:
                        f.write(line + '\n')
                
                # DataFrame'i append mode'da yaz
                df.to_csv(file_path, mode='a', index=False, float_format='%.12g')
            else:
                # Sadece DataFrame'i yaz
                df.to_csv(file_path, index=False, float_format='%.12g')
            
            print(f"📊 CSV export tamamlandı: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ CSV export hatası: {e}")
            messagebox.showerror("Export Hatası", f"CSV export başarısız:\n{str(e)}")
            return False
    
    @staticmethod
    def export_to_matlab(data: Dict[str, np.ndarray], 
                        metadata: Optional[Dict] = None,
                        file_path: Optional[str] = None) -> bool:
        """
        Verileri MATLAB .mat formatına aktarır
        
        Args:
            data: Export edilecek veri dictionary'si
            metadata: Metadata bilgileri
            file_path: Kayıt yolu (None ise dialog açılır)
            
        Returns:
            bool: Başarı durumu
        """
        if not SCIPY_AVAILABLE:
            messagebox.showerror("Hata", "MATLAB export için scipy kütüphanesi gerekli!")
            return False
        
        try:
            # Dosya yolu seçimi
            if not file_path:
                file_path = filedialog.asksaveasfilename(
                    title="MATLAB Dosyası Olarak Kaydet",
                    defaultextension=".mat",
                    filetypes=[("MATLAB files", "*.mat"), ("All files", "*.*")]
                )
            
            if not file_path:
                return False
            
            # MATLAB için veri hazırlığı
            mat_data = {}
            
            # Veri dizilerini ekle
            for key, values in data.items():
                if isinstance(values, (list, np.ndarray)):
                    # MATLAB column vector olarak kaydet
                    mat_data[key] = np.array(values).reshape(-1, 1)
                else:
                    # Skaler değerler
                    mat_data[key] = values
            
            # Metadata ekle
            if metadata:
                mat_data['metadata'] = {}
                for key, value in metadata.items():
                    if isinstance(value, dict):
                        # İç içe dictionary'leri flatten et
                        for sub_key, sub_value in value.items():
                            mat_data['metadata'][f"{key}_{sub_key}"] = str(sub_value)
                    else:
                        mat_data['metadata'][key] = str(value)
            
            # Export bilgilerini ekle
            mat_data['export_info'] = {
                'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'export_tool': 'TBDY Spektrum Analiz Araçları',
                'format_version': '1.0'
            }
            
            # MATLAB dosyasına kaydet
            sio.savemat(file_path, mat_data, format='5', long_field_names=True)
            
            print(f"📊 MATLAB export tamamlandı: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ MATLAB export hatası: {e}")
            messagebox.showerror("Export Hatası", f"MATLAB export başarısız:\n{str(e)}")
            return False
    
    @staticmethod
    def export_to_json(data: Dict[str, np.ndarray], 
                      metadata: Optional[Dict] = None,
                      file_path: Optional[str] = None,
                      indent: int = 2) -> bool:
        """
        Verileri JSON formatına aktarır
        
        Args:
            data: Export edilecek veri dictionary'si
            metadata: Metadata bilgileri
            file_path: Kayıt yolu (None ise dialog açılır)
            indent: JSON indent seviyesi
            
        Returns:
            bool: Başarı durumu
        """
        try:
            # Dosya yolu seçimi
            if not file_path:
                file_path = filedialog.asksaveasfilename(
                    title="JSON Olarak Kaydet",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
            
            if not file_path:
                return False
            
            # JSON için veri hazırlığı
            json_data = {
                "export_info": {
                    "export_date": datetime.now().isoformat(),
                    "export_tool": "TBDY Spektrum Analiz Araçları",
                    "format_version": "1.0"
                }
            }
            
            # Metadata ekle
            if metadata:
                json_data["metadata"] = {}
                for key, value in metadata.items():
                    if isinstance(value, dict):
                        json_data["metadata"][key] = value
                    elif isinstance(value, (np.ndarray, list)):
                        json_data["metadata"][key] = np.array(value).tolist()
                    elif isinstance(value, np.number):
                        json_data["metadata"][key] = float(value)
                    else:
                        json_data["metadata"][key] = value
            
            # Veri dizilerini ekle
            json_data["data"] = {}
            for key, values in data.items():
                if isinstance(values, (list, np.ndarray)):
                    # NumPy array'leri liste'ye çevir
                    json_data["data"][key] = np.array(values).tolist()
                elif isinstance(values, np.number):
                    # NumPy sayıları Python sayılarına çevir
                    json_data["data"][key] = float(values)
                else:
                    json_data["data"][key] = values
            
            # JSON dosyasına kaydet
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=indent, ensure_ascii=False)
            
            print(f"📊 JSON export tamamlandı: {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ JSON export hatası: {e}")
            messagebox.showerror("Export Hatası", f"JSON export başarısız:\n{str(e)}")
            return False
    
    @staticmethod
    def export_earthquake_data(time_data: np.ndarray,
                              acceleration: np.ndarray,
                              velocity: np.ndarray,
                              displacement: np.ndarray,
                              metadata: Optional[Dict] = None,
                              export_format: str = 'csv') -> bool:
        """
        Deprem verilerini belirtilen formata aktarır
        
        Args:
            time_data: Zaman serisi
            acceleration: İvme serisi
            velocity: Hız serisi
            displacement: Yerdeğiştirme serisi
            metadata: Metadata bilgileri
            export_format: Export formatı ('csv', 'matlab', 'json')
            
        Returns:
            bool: Başarı durumu
        """
        # Veri dictionary'si oluştur
        data = {
            'Time_s': time_data,
            'Acceleration': acceleration,
            'Velocity': velocity,
            'Displacement': displacement
        }
        
        # Birim bilgilerini metadata'ya ekle
        if not metadata:
            metadata = {}
        
        if 'units' not in metadata:
            metadata['units'] = {
                'time': 's',
                'acceleration': 'g',
                'velocity': 'cm/s',
                'displacement': 'cm'
            }
        
        # Format'a göre export
        if export_format.lower() == 'csv':
            return AdvancedExporter.export_to_csv(data, metadata)
        elif export_format.lower() in ['matlab', 'mat']:
            return AdvancedExporter.export_to_matlab(data, metadata)
        elif export_format.lower() == 'json':
            return AdvancedExporter.export_to_json(data, metadata)
        else:
            messagebox.showerror("Hata", f"Desteklenmeyen format: {export_format}")
            return False
    
    @staticmethod
    def show_export_dialog(time_data: np.ndarray,
                          acceleration: np.ndarray,
                          velocity: np.ndarray,
                          displacement: np.ndarray,
                          metadata: Optional[Dict] = None) -> None:
        """
        Export format seçim dialogu gösterir
        
        Args:
            time_data: Zaman serisi
            acceleration: İvme serisi
            velocity: Hız serisi
            displacement: Yerdeğiştirme serisi
            metadata: Metadata bilgileri
        """
        try:
            import tkinter as tk
            from tkinter import ttk
            
            # Dialog penceresi
            dialog = tk.Toplevel()
            dialog.title("Gelişmiş Export Seçenekleri")
            dialog.geometry("400x300")
            dialog.resizable(False, False)
            dialog.grab_set()  # Modal dialog
            
            # Ana frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill="both", expand=True)
            
            # Başlık
            title_label = ttk.Label(main_frame, text="📊 Export Formatı Seçin", 
                                   font=('Segoe UI', 12, 'bold'))
            title_label.pack(pady=(0, 20))
            
            # Format seçenekleri
            format_var = tk.StringVar(value="csv")
            
            # CSV seçeneği
            csv_frame = ttk.Frame(main_frame)
            csv_frame.pack(fill="x", pady=5)
            
            ttk.Radiobutton(csv_frame, text="📄 CSV Format", 
                           variable=format_var, value="csv").pack(side="left")
            ttk.Label(csv_frame, text="(Excel uyumlu, metadata ile)", 
                     font=('Segoe UI', 8), foreground='gray').pack(side="left", padx=(10, 0))
            
            # MATLAB seçeneği
            matlab_frame = ttk.Frame(main_frame)
            matlab_frame.pack(fill="x", pady=5)
            
            matlab_radio = ttk.Radiobutton(matlab_frame, text="🔬 MATLAB Format (.mat)", 
                                          variable=format_var, value="matlab")
            matlab_radio.pack(side="left")
            
            if not SCIPY_AVAILABLE:
                matlab_radio.configure(state="disabled")
                ttk.Label(matlab_frame, text="(scipy gerekli)", 
                         font=('Segoe UI', 8), foreground='red').pack(side="left", padx=(10, 0))
            else:
                ttk.Label(matlab_frame, text="(MATLAB/Octave uyumlu)", 
                         font=('Segoe UI', 8), foreground='gray').pack(side="left", padx=(10, 0))
            
            # JSON seçeneği
            json_frame = ttk.Frame(main_frame)
            json_frame.pack(fill="x", pady=5)
            
            ttk.Radiobutton(json_frame, text="🌐 JSON Format", 
                           variable=format_var, value="json").pack(side="left")
            ttk.Label(json_frame, text="(Web uyumlu, metadata ile)", 
                     font=('Segoe UI', 8), foreground='gray').pack(side="left", padx=(10, 0))
            
            # Veri bilgileri
            info_frame = ttk.LabelFrame(main_frame, text="📋 Veri Bilgileri", padding=10)
            info_frame.pack(fill="x", pady=(20, 10))
            
            ttk.Label(info_frame, text=f"Veri Noktası: {len(time_data):,}").pack(anchor="w")
            ttk.Label(info_frame, text=f"Süre: {time_data[-1]:.3f} saniye").pack(anchor="w")
            ttk.Label(info_frame, text="İçerik: Zaman, İvme, Hız, Yerdeğiştirme").pack(anchor="w")
            
            # Butonlar
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill="x", pady=(20, 0))
            
            def export_selected():
                selected_format = format_var.get()
                success = AdvancedExporter.export_earthquake_data(
                    time_data, acceleration, velocity, displacement,
                    metadata, selected_format
                )
                if success:
                    dialog.destroy()
            
            def cancel_export():
                dialog.destroy()
            
            ttk.Button(button_frame, text="📊 Export", 
                      command=export_selected).pack(side="right", padx=(5, 0))
            ttk.Button(button_frame, text="❌ İptal", 
                      command=cancel_export).pack(side="right")
            
            # Dialog'u ortala
            dialog.transient(dialog.master)
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
        except Exception as e:
            print(f"❌ Export dialog hatası: {e}")
            messagebox.showerror("Hata", f"Export dialog açılamadı:\n{str(e)}")
            
    @staticmethod
    def get_supported_formats() -> List[str]:
        """Desteklenen export formatlarını döndürür"""
        formats = ['csv', 'json']
        if SCIPY_AVAILABLE:
            formats.append('matlab')
        return formats