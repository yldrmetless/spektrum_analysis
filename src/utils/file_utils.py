"""
Dosya işlemleri yardımcı modülü
"""

import os
import pandas as pd
from tkinter import filedialog, messagebox
from src.config.constants import (
    SUPPORTED_EXCEL_FORMATS, SUPPORTED_CSV_FORMATS, 
    SUPPORTED_IMAGE_FORMATS, SUPPORTED_EARTHQUAKE_FORMATS, DPI_SETTING
)

class FileUtils:
    """Dosya işlemleri yardımcı sınıfı"""
    
    @staticmethod
    def open_file_dialog(title="Dosya Seç", filetypes=None, multiple=False):
        """
        Dosya seçme dialogu açar
        
        Args:
            title (str): Dialog başlığı
            filetypes (list): Dosya türleri listesi
            multiple (bool): Çoklu dosya seçimi yapılacak mı
            
        Returns:
            str/list veya None: Seçilen dosya yolu(ları)
        """
        if filetypes is None:
            filetypes = SUPPORTED_EXCEL_FORMATS + SUPPORTED_CSV_FORMATS
        
        if multiple:
            return filedialog.askopenfilenames(title=title, filetypes=filetypes)
        else:
            return filedialog.askopenfilename(title=title, filetypes=filetypes)
    
    @staticmethod
    def open_earthquake_file_dialog(title="Deprem Kaydı Dosyası Seç", multiple=False):
        """
        Deprem kaydı dosya seçme dialogu açar
        
        Args:
            title (str): Dialog başlığı
            multiple (bool): Çoklu dosya seçimi yapılacak mı
            
        Returns:
            str/list veya None: Seçilen dosya yolu(ları)
        """
        if multiple:
            return filedialog.askopenfilenames(title=title, filetypes=SUPPORTED_EARTHQUAKE_FORMATS)
        else:
            return filedialog.askopenfilename(title=title, filetypes=SUPPORTED_EARTHQUAKE_FORMATS)
    
    @staticmethod
    def save_file_dialog(title="Dosyayı Kaydet", filetypes=None, default_extension=".png", parent=None):
        """
        Dosya kaydetme dialogu açar
        
        Args:
            title (str): Dialog başlığı
            filetypes (list): Dosya türleri listesi
            default_extension (str): Varsayılan dosya uzantısı
            
        Returns:
            str veya None: Seçilen dosya yolu
        """
        if filetypes is None:
            filetypes = SUPPORTED_IMAGE_FORMATS
        
        return filedialog.asksaveasfilename(
            title=title,
            filetypes=filetypes,
            defaultextension=default_extension,
            parent=parent
        )
    
    @staticmethod
    def select_directory(title="Klasör Seç", parent=None):
        """
        Klasör seçme dialogu açar
        
        Args:
            title (str): Dialog başlığı
            
        Returns:
            str veya None: Seçilen klasör yolu
        """
        return filedialog.askdirectory(title=title, parent=parent)
    
    @staticmethod
    def export_dataframe_to_excel(df, file_path=None, title="Excel'e Aktar"):
        """
        DataFrame'i Excel dosyasına aktarır
        
        Args:
            df (pd.DataFrame): Aktarılacak veri
            file_path (str, optional): Dosya yolu. None ise dialog açılır
            title (str): Dialog başlığı
            
        Returns:
            bool: İşlem başarılı mı
        """
        if file_path is None:
            file_path = FileUtils.save_file_dialog(
                title=title,
                filetypes=[("Excel Dosyası", "*.xlsx")],
                default_extension=".xlsx"
            )
        
        if not file_path:
            return False

        # DataFrame'i Excel'e yaz
        try:
            # openpyxl mevcutsa motoru belirt; değilse pandas varsayılanını dene
            try:
                import openpyxl  # noqa: F401
                engine = 'openpyxl'
            except Exception:
                engine = None

            if engine:
                df.to_excel(file_path, index=False, engine=engine)
            else:
                df.to_excel(file_path, index=False)

            messagebox.showinfo("Başarılı", f"Veriler başarıyla kaydedildi:\n{file_path}")
            return True
        except ImportError:
            messagebox.showerror("Kütüphane Eksik", "Excel'e aktarmak için 'openpyxl' gereklidir.")
            return False
        except Exception as e:
            messagebox.showerror("Hata", f"Excel kaydedilirken hata oluştu:\n{e}")
            return False

    @staticmethod
    def export_excel_sheets(sheets: dict, file_path: str = None, title: str = "Excel'e Aktar"):
        """
        Birden fazla DataFrame'i tek bir Excel dosyasında farklı sheet'lere yazar.

        Args:
            sheets (dict): {"Sheet Adı": DataFrame}
            file_path (str, optional): Hedef dosya yolu. None ise dialog açılır
            title (str): Dialog başlığı

        Returns:
            bool: İşlem başarılı mı
        """
        if not sheets or not isinstance(sheets, dict):
            messagebox.showerror("Hata", "Aktarılacak veri bulunamadı.")
            return False

        try:
            import pandas as pd
        except Exception:
            messagebox.showerror("Kütüphane Eksik", "Excel'e aktarmak için 'pandas' gereklidir.")
            return False

        # Yol seçimi
        if file_path is None:
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title=title,
                defaultextension=".xlsx",
                filetypes=[("Excel Dosyası", "*.xlsx"), ("Tüm Dosyalar", "*.*")]
            )

        if not file_path:
            return False

        try:
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                for sheet_name, df in sheets.items():
                    try:
                        safe_name = str(sheet_name)[:31]  # Excel sheet adı sınırı
                        df.to_excel(writer, sheet_name=safe_name, index=False)
                    except Exception as inner_err:
                        messagebox.showwarning("Uyarı", f"'{sheet_name}' sayfası yazılamadı: {inner_err}")
                        continue
            messagebox.showinfo("Başarılı", f"Veriler başarıyla kaydedildi:\n{file_path}")
            return True
        except ImportError:
            messagebox.showerror("Kütüphane Eksik", "Excel'e aktarmak için 'openpyxl' gereklidir.")
            return False
        except Exception as e:
            messagebox.showerror("Hata", f"Excel kaydedilirken hata oluştu:\n{e}")
            return False
        
        try:
            df.to_excel(file_path, index=False, engine='openpyxl')
            messagebox.showinfo("Başarılı", f"Veriler başarıyla kaydedildi:\n{file_path}")
            return True
        except ImportError:
            messagebox.showerror("Kütüphane Eksik", 
                               "Excel'e aktarmak için 'openpyxl' kütüphanesi gereklidir.\n"
                               "Lütfen 'pip install openpyxl' komutu ile kurun.")
            return False
        except Exception as e:
            messagebox.showerror("Hata", f"Dosya kaydedilirken hata oluştu:\n{e}")
            return False
    
    @staticmethod
    def copy_dataframe_to_clipboard(df):
        """
        DataFrame'i panoya kopyalar
        
        Args:
            df (pd.DataFrame): Kopyalanacak veri
            
        Returns:
            bool: İşlem başarılı mı
        """
        try:
            df.to_clipboard(index=False, excel=True, sep='\t')
            messagebox.showinfo("Başarılı", 
                               "Tüm veriler panoya kopyalandı.\nExcel'e yapıştırabilirsiniz.")
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Veriler kopyalanamadı:\n{e}")
            return False
    
    @staticmethod
    def save_figure(fig, file_path=None, dpi=DPI_SETTING, bbox_inches='tight'):
        """
        Matplotlib figure'ını dosyaya kaydeder
        
        Args:
            fig: Matplotlib figure nesnesi
            file_path (str, optional): Dosya yolu. None ise dialog açılır
            dpi (int): DPI ayarı
            bbox_inches (str): Bounding box ayarı
            
        Returns:
            bool: İşlem başarılı mı
        """
        if file_path is None:
            file_path = FileUtils.save_file_dialog(
                title="Grafiği Kaydet",
                filetypes=SUPPORTED_IMAGE_FORMATS
            )
        
        if not file_path:
            return False
        
        try:
            fig.savefig(file_path, dpi=dpi, bbox_inches=bbox_inches)
            messagebox.showinfo("Başarılı", f"Grafik başarıyla kaydedildi:\n{file_path}")
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Grafik kaydedilirken hata oluştu:\n{e}")
            return False
    
    @staticmethod
    def save_multiple_axes(fig, axes_dict, directory=None, base_name="spektrum"):
        """
        Birden fazla axes'i ayrı dosyalara kaydeder
        
        Args:
            fig: Matplotlib figure nesnesi
            axes_dict (dict): Axes sözlüğü {"isim": axes_object}
            directory (str, optional): Kayıt dizini. None ise dialog açılır
            base_name (str): Dosya ismi başlangıcı
            
        Returns:
            list: Kaydedilen dosya yolları
        """
        if directory is None:
            directory = FileUtils.select_directory("Grafikleri Kaydetmek İçin Klasör Seçin")
        
        if not directory:
            return []
        
        saved_files = []
        
        try:
            for graph_name, ax in axes_dict.items():
                # Axes'in bounding box'ını al
                bbox = ax.get_tightbbox(fig.canvas.get_renderer())
                bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())
                
                # Dosya adını oluştur
                file_name = f"{base_name}_{graph_name.lower().replace(' ', '_')}.png"
                full_path = os.path.join(directory, file_name)
                
                # Dosyayı kaydet
                fig.savefig(full_path, dpi=DPI_SETTING, bbox_inches=bbox_inches)
                saved_files.append(full_path)
            
            if saved_files:
                messagebox.showinfo("Başarılı", 
                                   f"Seçilen grafikler ayrı ayrı kaydedildi:\n" + 
                                   "\n".join(saved_files))
            
            return saved_files
            
        except Exception as e:
            messagebox.showerror("Hata", f"Grafikler kaydedilirken hata oluştu:\n{e}")
            return []
    
    @staticmethod
    def get_file_info(file_path):
        """
        Dosya hakkında bilgi döndürür
        
        Args:
            file_path (str): Dosya yolu
            
        Returns:
            dict: Dosya bilgileri
        """
        if not os.path.exists(file_path):
            return {"exists": False}
        
        stat = os.stat(file_path)
        
        return {
            "exists": True,
            "name": os.path.basename(file_path),
            "directory": os.path.dirname(file_path),
            "size": stat.st_size,
            "size_mb": stat.st_size / (1024 * 1024),
            "extension": os.path.splitext(file_path)[1].lower()
        }
    
    @staticmethod
    def validate_file_extension(file_path, allowed_extensions):
        """
        Dosya uzantısının geçerli olup olmadığını kontrol eder
        
        Args:
            file_path (str): Dosya yolu
            allowed_extensions (list): İzin verilen uzantılar
            
        Returns:
            bool: Uzantı geçerli mi
        """
        if not file_path:
            return False
        
        ext = os.path.splitext(file_path)[1].lower()
        return ext in allowed_extensions
    
    @staticmethod
    def ensure_directory_exists(directory):
        """
        Dizinin var olduğundan emin olur, yoksa oluşturur
        
        Args:
            directory (str): Dizin yolu
            
        Returns:
            bool: İşlem başarılı mı
        """
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
            return True
        except Exception as e:
            messagebox.showerror("Dizin Hatası", f"Dizin oluşturulamadı:\n{e}")
            return False 
