"""
Input File Parameters Dialog - Deprem kaydı dosya parametrelerini ayarlama dialogu
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import sys
import time
import json

# Bu dosya doğrudan çalıştırıldığında paket içi importların çalışabilmesi için
if __name__ == "__main__" or __package__ is None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(os.path.dirname(current_dir))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

from config.constants import SUPPORTED_EARTHQUAKE_FORMATS

class ToolTip:
    """
    Tooltip sınıfı - Widget'lara fare üzerine gelince açıklama gösterir
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
    
    def on_enter(self, event=None):
        self.show_tooltip()
    
    def on_leave(self, event=None):
        self.hide_tooltip()
    
    def show_tooltip(self):
        if self.tooltip_window or not self.text:
            return
        
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1,
                        font=("Segoe UI", "9", "normal"), wraplength=300)
        label.pack(ipadx=5, ipady=3)
    
    def hide_tooltip(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class InputFileParametersDialog:
    """Deprem kaydı dosya parametrelerini ayarlama dialogu"""
    
    def __init__(self, parent, file_path, current_params=None):
        """
        Args:
            parent: Ana pencere
            file_path: Dosya yolu
            current_params: Mevcut parametreler (düzenleme modunda)
        """
        self.parent = parent
        self.file_path = file_path
        self.current_params = current_params or {}
        self.result = None
        
        # Ek dosya yolları
        self.velocity_file_path = None
        self.displacement_file_path = None
        
        # Ortak buton genişliği (tüm ilgili butonlarda aynı görsel genişlik)
        self.common_button_width = max(len("Hız Kaydı Yükle"), len("Yerdeğiştirme Kaydı Yükle")) + 2
        
        # Dialog penceresi oluştur
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Deprem Kaydı Yükle")
        self.dialog.geometry("1600x1150")
        self.dialog.resizable(True, True)
        self.dialog.minsize(1600, 1150)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Pencereyi merkeze yerleştir
        self._center_window()
        
        # Varsayılan parametreler
        self._init_variables()
        
        # Arayüzü oluştur
        self._create_interface()
        # AT2↔VT2↔DT2 otomatik eşleme: ana dosyaya göre kardeşleri bul
        try:
            self._auto_find_sibling_records()
        except Exception as _ex:
            print(f"⚠️ Kardeş dosya otomatik eşleme hatası: {_ex}")
        
        # Dialog sonucu bekle
        self.dialog.wait_window()
    
    def _center_window(self):
        """Pencereyi ekranın merkezine yerleştirir"""
        self.dialog.update_idletasks()
        # Mevcut geometry bilgisini kullanarak merkezle (genişliğe/uzunluğa sabit değer yazma)
        try:
            current_geo = self.dialog.geometry()  # Örn: "700x900+100+100" veya "700x900"
            size_part = current_geo.split("+")[0]
            width_str, height_str = size_part.split("x")
            width = int(width_str)
            height = int(height_str)
        except Exception:
            # Okunamazsa, pencereden talep edilen boyutları kullan
            width = max(self.dialog.winfo_reqwidth(), 700)
            height = max(self.dialog.winfo_reqheight(), 600)

        screen_w = self.dialog.winfo_screenwidth()
        screen_h = self.dialog.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")
    
    def _init_variables(self):
        """Tkinter değişkenlerini başlatır"""
        # Mevcut parametreler + kullanıcı varsayılanları + program varsayılanları
        program_defaults = {
            'first_line': 5,
            'last_line': '',
            'time_step': 0.01,
            'scaling_factor': 1.0,
            'format': 'single_accel',
            'accel_column': 2,
            'time_column': 1,
            'frequency': 1,
            'initial_skip': 0,
            'accel_unit': 'g',
            'velocity_unit': 'cm/s',
            'displacement_unit': 'cm'
        }

        user_defaults = self._load_user_defaults()

        # Öncelik: program varsayılanı < kullanıcı varsayılanı < mevcut parametre (geçici/oturum)
        merged = {**program_defaults, **user_defaults, **self.current_params}

        # Dosya parametreleri
        self.first_line_var = tk.StringVar(value=str(merged.get('first_line')))
        self.last_line_var = tk.StringVar(value=str(merged.get('last_line')) if merged.get('last_line') is not None else '')
        self.time_step_var = tk.StringVar(value=str(merged.get('time_step')))
        self.scaling_factor_var = tk.StringVar(value=str(merged.get('scaling_factor')))

        # Format seçenekleri
        self.format_var = tk.StringVar(value=merged.get('format'))

        # Sütun ayarları
        self.accel_column_var = tk.StringVar(value=str(merged.get('accel_column')))
        self.time_column_var = tk.StringVar(value=str(merged.get('time_column')))
        self.frequency_var = tk.StringVar(value=str(merged.get('frequency')))
        self.initial_skip_var = tk.StringVar(value=str(merged.get('initial_skip')))

        # Birimler
        self.accel_unit_var = tk.StringVar(value=merged.get('accel_unit'))
        self.velocity_unit_var = tk.StringVar(value=merged.get('velocity_unit'))
        self.displacement_unit_var = tk.StringVar(value=merged.get('displacement_unit'))
        self._peer_format_auto_set = False

    def _get_defaults_file_path(self):
        """Kullanıcı varsayılanları dosya yolunu döndürür"""
        try:
            home_dir = os.path.expanduser("~")
            app_dir = os.path.join(home_dir, ".tbdyspektrum")
            if not os.path.exists(app_dir):
                os.makedirs(app_dir, exist_ok=True)
            return os.path.join(app_dir, "input_file_defaults.json")
        except Exception:
            # Fallback: çalışma dizini
            return os.path.join(os.getcwd(), "input_file_defaults.json")

    def _load_user_defaults(self):
        """JSON dosyasından kullanıcı varsayılanlarını yükler"""
        try:
            path = self._get_defaults_file_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"⚠️ Kullanıcı varsayılanları yüklenemedi: {e}")
        return {}

    def _save_user_defaults(self, data):
        """Kullanıcı varsayılanlarını JSON dosyasına kaydeder"""
        try:
            path = self._get_defaults_file_path()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ Varsayılanlar kaydedilemedi: {e}")
            return False
    
    def _create_interface(self):
        """Ana arayüzü oluşturur"""
        # Ana çerçeve
        main_frame = ttk.Frame(self.dialog, padding="15")
        main_frame.pack(fill="both", expand=True)
        
        # Dosya formatı bölümü (en üstte)
        format_top_frame = ttk.Frame(main_frame)
        format_top_frame.pack(fill="x", pady=(0, 10))
        self._create_format_options(format_top_frame)

        # Ayırıcı
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=(0, 15))

        # Ana içerik konteyneri: sol kontrol blokları + sağ önizleme
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True)

        # Sol blok (kontroller)
        left_column = ttk.Frame(content_frame)
        left_column.pack(side="left", fill="both", expand=False, padx=(0, 15))
        left_column.configure(width=520)

        # Deprem kaydı bilgileri ve birimler bölümü
        info_container = ttk.Frame(left_column)
        info_container.pack(fill="x", pady=(0, 10))

        file_info_frame = ttk.Frame(info_container)
        file_info_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self._create_file_parameters(file_info_frame)

        units_side_frame = ttk.Frame(info_container)
        units_side_frame.pack(side="left", fill="y")
        self._create_units_section(units_side_frame)

        # Ayırıcı
        ttk.Separator(left_column, orient="horizontal").pack(fill="x", pady=(0, 15))

        # Sütun ayarları bölümü
        column_settings_frame = ttk.Frame(left_column)
        column_settings_frame.pack(fill="x", pady=(0, 10))
        self._create_column_settings(column_settings_frame)

        # Ayırıcı
        ttk.Separator(left_column, orient="horizontal").pack(fill="x", pady=(0, 15))

        # Ek dosya ve işlem butonları bölümü
        actions_frame = ttk.Frame(left_column)
        actions_frame.pack(fill="x", pady=(0, 15))

        # Aksiyon bileşenleri
        self._create_additional_files_section(actions_frame)
        self._create_buttons(actions_frame)

        # Sağ blok (dosya önizlemeleri)
        preview_container = ttk.Frame(content_frame)
        preview_container.pack(side="left", fill="both", expand=True)

        # Tüm bileşenler oluşturulduktan sonra format değişikliğini uygula
        self._on_format_change()

        # Önizleme bileşenleri
        self._create_file_preview(preview_container)
    
    def _create_file_parameters(self, parent):
        """Dosya parametreleri bölümünü oluşturur"""
        params_frame = ttk.LabelFrame(parent, text="Deprem Kaydına Dair Bilgiler", padding=10)
        params_frame.pack(fill="x", pady=(0, 10))
        
        # İlk Satır
        first_line_frame = ttk.Frame(params_frame)
        first_line_frame.pack(fill="x", pady=2)
        ttk.Label(first_line_frame, text="İlk Satır:", width=16).pack(side="left")
        first_entry = ttk.Entry(first_line_frame, textvariable=self.first_line_var, width=10)
        first_entry.pack(side="left", padx=(5, 0))
        ToolTip(first_entry, "Veri okumaya başlanacak satır numarası.\n\nDosyanın başındaki başlık satırlarını atlamak için kullanılır.\n\nÖrnek: Dosyada 5 satır başlık varsa\nİlk Satır = 6 yazın.\n\nProgram otomatik tespit eder.")
        
        # Son Satır
        last_line_frame = ttk.Frame(params_frame)
        last_line_frame.pack(fill="x", pady=2)
        ttk.Label(last_line_frame, text="Son Satır:", width=16).pack(side="left")
        last_entry = ttk.Entry(last_line_frame, textvariable=self.last_line_var, width=10)
        last_entry.pack(side="left", padx=(5, 0))
        ToolTip(last_entry, "Veri okumanın duracağı satır numarası.\n\nDosyanın sonundaki ek bilgileri atlamak için kullanılır.\n\nBoş bırakılırsa dosyanın sonuna kadar okur.\n\nProgram otomatik tespit eder.")
        
        # Zaman Adımı
        time_step_frame = ttk.Frame(params_frame)
        time_step_frame.pack(fill="x", pady=2)
        ttk.Label(time_step_frame, text="Zaman Adımı dt:", width=16).pack(side="left")
        time_entry = ttk.Entry(time_step_frame, textvariable=self.time_step_var, width=10)
        time_entry.pack(side="left", padx=(5, 0))
        ToolTip(time_entry, "İvme kaydının örnekleme aralığı (saniye cinsinden).\n\nÖrnek:\n0.01 = 100 Hz örnekleme\n0.005 = 200 Hz örnekleme\n0.02 = 50 Hz örnekleme\n\nGenellikle 0.01 kullanılır.")
        
        # Ölçekleme Faktörü
        scaling_frame = ttk.Frame(params_frame)
        scaling_frame.pack(fill="x", pady=2)
        ttk.Label(scaling_frame, text="Ölçek Faktörü:", width=16).pack(side="left")
        scaling_entry = ttk.Entry(scaling_frame, textvariable=self.scaling_factor_var, width=10)
        scaling_entry.pack(side="left", padx=(5, 0))
        ToolTip(scaling_entry, "Dosyadaki değerleri ölçeklendirmek için çarpan.\n\n1.0 = Değişiklik yok\n9.81 = g değerlerini m/s²'ye çevir\n0.1 = Değerleri 10'da birine küçült\n\nGenellikle 1.0 kullanılır.")
    
    def _create_format_options(self, parent):
        """Format seçenekleri bölümünü oluşturur"""
        format_frame = ttk.LabelFrame(parent, text="Dosya Formatı", padding=10)
        format_frame.pack(fill="x", pady=(0, 10))
        
        # Format radio butonları - SeismoSignal sıralaması
        formats = [
            ("single_accel", "Her satırda tek ivme değeri"),
            ("time_accel", "Her satırda zaman ve ivme değeri"),
            ("multi_accel", "Her satırda birden fazla ivme değeri"),
            ("esm", "ESM Formatı"),
            ("peer_nga", "PEER NGA Formatı")
        ]

        format_tooltips = {
            "single_accel": "Her satır sadece tek bir ivme değeri içerir. Zaman adımı kutusuna girilen değer kullanılır.",
            "time_accel": "Satırlar hem zaman hem ivme sütunu içerir. Sütun numaralarını aşağıdaki bölümden belirleyin.",
            "multi_accel": "Satırlar birden fazla ivme sütunu içerir. Okuma frekansı ve başlangıç atlamasını ayarlayın.",
            "esm": "ESM kayıtları için otomatik çözümleme yapılır. Hız ve yerdeğiştirme kayıtlarını ayrıca yüklemeniz gerekir.",
            "peer_nga": "PEER NGA verileri için başlık bilgileri otomatik okunur. Hız ve yerdeğiştirme dosyalarını eşleştirin."
        }
        
        for value, text in formats:
            rb = ttk.Radiobutton(
                format_frame,
                text=text,
                variable=self.format_var,
                value=value,
                command=self._on_format_change
            )
            rb.pack(anchor="w", pady=1)
            ToolTip(rb, format_tooltips.get(value, ""))
    
    def _create_column_settings(self, parent):
        """Sütun ayarları bölümünü oluşturur - SeismoSignal standardı"""
        self.column_frame = ttk.LabelFrame(parent, text="Sütun Ayarları", padding=10)
        self.column_frame.pack(fill="x", pady=(0, 10))
        
        # İvme Sütunu (Single-value ve Time & Acceleration için)
        self.accel_col_frame = ttk.Frame(self.column_frame)
        self.accel_col_frame.pack(fill="x", pady=2)
        ttk.Label(self.accel_col_frame, text="İvme Sütunu:", width=18).pack(side="left")
        accel_entry = ttk.Entry(self.accel_col_frame, textvariable=self.accel_column_var, width=10)
        accel_entry.pack(side="left", padx=(5, 0))
        ToolTip(accel_entry, "İvme verilerinin bulunduğu sütun numarası.\n\nÖrnek: Dosyada 'Zaman İvme Hız' sütunları varsa\nİvme Sütunu = 2 yazın.\n\n'Her satırda birden fazla ivme değeri' formatında:\nHangi sütundan başlayarak veri okunacağını belirtir.")
        
        # Zaman Sütunu (Sadece Time & Acceleration için)
        self.time_col_frame = ttk.Frame(self.column_frame)
        self.time_col_frame.pack(fill="x", pady=2)
        ttk.Label(self.time_col_frame, text="Zaman Sütunu:", width=18).pack(side="left")
        time_entry = ttk.Entry(self.time_col_frame, textvariable=self.time_column_var, width=10)
        time_entry.pack(side="left", padx=(5, 0))
        ToolTip(time_entry, "Zaman verilerinin bulunduğu sütun numarası.\n\nSadece 'Her satırda zaman ve ivme değeri' formatında kullanılır.\n\nÖrnek: Dosyada 'Zaman İvme' sütunları varsa\nZaman Sütunu = 1 yazın.")
        
        # Okuma Frekansı (Sadece Multiple-value için)
        self.freq_frame = ttk.Frame(self.column_frame)
        self.freq_frame.pack(fill="x", pady=2)
        ttk.Label(self.freq_frame, text="Okuma Frekansı:", width=18).pack(side="left")
        freq_entry = ttk.Entry(self.freq_frame, textvariable=self.frequency_var, width=10)
        freq_entry.pack(side="left", padx=(5, 0))
        ToolTip(freq_entry, "Kaç değerde bir veri alınacağını belirtir.\n\n1 = Tüm değerleri oku\n2 = Her ikinci değeri oku (1, 3, 5, 7...)\n3 = Her üçüncü değeri oku (1, 4, 7, 10...)\n\nSadece 'Her satırda birden fazla ivme değeri'\nformatında kullanılır.")
        
        # Atlanan Başlangıç Değerleri (Sadece Multiple-value için)
        self.skip_frame = ttk.Frame(self.column_frame)
        self.skip_frame.pack(fill="x", pady=2)
        ttk.Label(self.skip_frame, text="Atlanan Başlangıç:", width=18).pack(side="left")
        skip_entry = ttk.Entry(self.skip_frame, textvariable=self.initial_skip_var, width=10)
        skip_entry.pack(side="left", padx=(5, 0))
        ToolTip(skip_entry, "Her satırın başından kaç değer atlanacağını belirtir.\n\n0 = Hiç değer atlama\n1 = İlk değeri atla, ikinciden başla\n2 = İlk iki değeri atla, üçüncüden başla\n\nSadece 'Her satırda birden fazla ivme değeri'\nformatında kullanılır.")
        
        # PEER NGA Format Bilgi Paneli (Sadece PEER NGA için)
        self.peer_nga_info_frame = ttk.Frame(self.column_frame)
        
        # PEER NGA bilgi metni - SeismoSignal stilinde
        peer_info_text = ttk.Label(
            self.peer_nga_info_frame, 
            text="Deprem adı otomatik tespit edilir.\nZaman adımı, birim bilgileri ve veri yapısı dosyadan alınır.\n⚠️ ZORUNLU: Hız ve Yerdeğiştirme kayıtlarını ayrı dosyalardan yükleyin.\nSadece İlk/Son Satır parametrelerini gerekirse değiştirin.",
            font=('Segoe UI', 9),
            justify='center',
            foreground='#555555'
        )
        peer_info_text.pack(pady=15)
        
        # ESM Format Bilgi Paneli (Sadece ESM için)
        self.esm_info_frame = ttk.Frame(self.column_frame)
        
        # ESM bilgi metni
        esm_info_text = ttk.Label(
            self.esm_info_frame, 
            text="Zaman adımı otomatik tespit edilir.\nBirim bilgileri ve veri yapısı dosyadan alınır.\n⚠️ ZORUNLU: Hız ve Yerdeğiştirme kayıtlarını ayrı dosyalardan yükleyin.\nParametreleri gerekirse değiştirebilirsiniz.",
            font=('Segoe UI', 9),
            justify='center',
            foreground='#555555'
        )
        esm_info_text.pack(pady=15)
        
        # İlk yüklemede format değişikliğini uygula (ek dosya bölümü oluşturulduktan sonra)
        # self._on_format_change() - Bu çağrı daha sonra yapılacak
    
    def _create_units_section(self, parent):
        """Birimler bölümünü oluşturur"""
        self.units_frame = ttk.LabelFrame(parent, text="Birimler", padding=10)
        self.units_frame.pack(fill="x", pady=(0, 10))
        
        # Birim etiketleri ve buton için ana çerçeve
        units_content_frame = ttk.Frame(self.units_frame)
        units_content_frame.pack(fill="x")

        # Sol taraf - birim etiketleri
        units_labels_frame = ttk.Frame(units_content_frame)
        units_labels_frame.pack(side="left", fill="both", expand=True)
        
        # Birim etiketleri - dinamik güncelleme için referans sakla
        self.accel_unit_label = ttk.Label(units_labels_frame, text="", font=('Segoe UI', 9))
        self.accel_unit_label.pack(anchor="w")
        
        self.velocity_unit_label = ttk.Label(units_labels_frame, text="", font=('Segoe UI', 9))
        self.velocity_unit_label.pack(anchor="w")
        
        self.displacement_unit_label = ttk.Label(units_labels_frame, text="", font=('Segoe UI', 9))
        self.displacement_unit_label.pack(anchor="w")
        
        # Sağ taraf - Birim Değiştir butonu
        button_frame = ttk.Frame(self.units_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(
            button_frame,
            text="Birim Değiştir",
            command=self._change_units,
            width=self.common_button_width
        ).pack()
        
        # İlk güncelleme
        self._update_units_display()
    
    def _create_additional_files_section(self, parent):
        """Ek dosya yükleme bölümünü oluşturur"""
        additional_frame = ttk.LabelFrame(parent, text="Ek Zaman Serileri", padding=10)
        additional_frame.pack(fill="x", pady=(0, 10))

        # Butonlar için ortak genişlik
        btn_text_velocity = "Hız Kaydı Yükle"
        btn_text_displacement = "Yerdeğiştirme Kaydı Yükle"
        button_width = self.common_button_width
        # Orta sütun (dosya adı göstergesi) için minimum piksel genişliği
        mid_col_min_px = 120
        
        # Açıklama metni
        self.additional_info_label = ttk.Label(additional_frame, 
                              text="Hız ve yerdeğiştirme kayıtlarını ayrı dosyalardan yükleyebilirsiniz:",
                              font=('Segoe UI', 8), foreground='blue', wraplength=420)
        self.additional_info_label.pack(anchor="w", pady=(0, 8))
        
        # Hız kaydı yükleme (grid yerleşimi)
        velocity_frame = ttk.Frame(additional_frame)
        velocity_frame.pack(fill="x", pady=3)

        ttk.Label(
            velocity_frame,
            text="Hız Kaydı:",
            anchor="w",
            font=('Segoe UI', 9)
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        # Dosya adı için orta kısım (esneyen sütun)
        self.velocity_file_var = tk.StringVar(value="Seçilmedi")
        velocity_label = ttk.Label(
            velocity_frame,
            textvariable=self.velocity_file_var,
            font=('Segoe UI', 8),
            foreground='gray'
        )
        velocity_label.grid(row=0, column=1, sticky="w")
        # Referans için widget'ı sakla
        self._velocity_label_widget = velocity_label

        ttk.Button(
            velocity_frame,
            text=btn_text_velocity,
            command=self._load_velocity_file,
            width=button_width,
        ).grid(row=0, column=2, sticky="e")

        velocity_frame.grid_columnconfigure(1, weight=1, minsize=mid_col_min_px)
        
        # Yerdeğiştirme kaydı yükleme (grid yerleşimi)
        displacement_frame = ttk.Frame(additional_frame)
        displacement_frame.pack(fill="x", pady=3)

        ttk.Label(
            displacement_frame,
            text="Yerdeğiştirme Kaydı:",
            anchor="w",
            font=('Segoe UI', 9)
        ).grid(row=0, column=0, sticky="w", padx=(0, 6))

        # Dosya adı için orta kısım (esneyen sütun)
        self.displacement_file_var = tk.StringVar(value="Seçilmedi")
        displacement_label = ttk.Label(
            displacement_frame,
            textvariable=self.displacement_file_var,
            font=('Segoe UI', 8),
            foreground='gray'
        )
        displacement_label.grid(row=0, column=1, sticky="w")
        # Referans için widget'ı sakla
        self._displacement_label_widget = displacement_label

        ttk.Button(
            displacement_frame,
            text=btn_text_displacement,
            command=self._load_displacement_file,
            width=button_width,
        ).grid(row=0, column=2, sticky="e")

        displacement_frame.grid_columnconfigure(1, weight=1, minsize=mid_col_min_px)
        
        # Temizleme butonu - ortalanmış
        button_frame = ttk.Frame(additional_frame)
        button_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(button_frame, text="Ek Dosyaları Temizle", 
                  command=self._clear_additional_files, width=25).pack()

    # ─────────────────────────────────────────────────────────────────────
    # AT2 ↔ VT2 ↔ DT2 Otomatik Eşleme ve Doğrulama
    # ─────────────────────────────────────────────────────────────────────
    def _get_main_base_and_dir(self):
        try:
            directory = os.path.dirname(self.file_path)
            base = os.path.splitext(os.path.basename(self.file_path))[0]
            return directory, base
        except Exception:
            return os.getcwd(), os.path.splitext(os.path.basename(self.file_path))[0]

    def _find_sibling_in_dir(self, target_ext_upper: str) -> str | None:
        try:
            directory, base = self._get_main_base_and_dir()
            for name in os.listdir(directory):
                try:
                    nbase, ext = os.path.splitext(name)
                    if nbase.upper() == base.upper() and ext.upper() == f".{target_ext_upper}".upper():
                        return os.path.join(directory, name)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _auto_find_sibling_records(self) -> None:
        """Ana dosya .AT2 ise aynı taban adlı .VT2 ve .DT2 dosyalarını otomatik bağlar."""
        try:
            _, base = self._get_main_base_and_dir()
            main_ext = os.path.splitext(self.file_path)[1].upper()
            if main_ext == ".AT2":
                vt2 = self._find_sibling_in_dir("VT2")
                dt2 = self._find_sibling_in_dir("DT2")
                if vt2:
                    self.velocity_file_path = vt2
                    if hasattr(self, 'velocity_file_var'):
                        self.velocity_file_var.set(os.path.basename(vt2))
                else:
                    # Eşleşen VT2 bulunamadıysa bilgi ver
                    try:
                        if hasattr(self, 'velocity_file_var'):
                            self.velocity_file_var.set(f"Hız (VT2) dosyası bulunamadı: {base}.VT2")
                    except Exception:
                        pass
                if dt2:
                    self.displacement_file_path = dt2
                    if hasattr(self, 'displacement_file_var'):
                        self.displacement_file_var.set(os.path.basename(dt2))
                else:
                    # Eşleşen DT2 bulunamadıysa bilgi ver
                    try:
                        if hasattr(self, 'displacement_file_var'):
                            self.displacement_file_var.set(f"Yerdeğiştirme (DT2) dosyası bulunamadı: {base}.DT2")
                    except Exception:
                        pass
                # Çoklu önizleme sekmelerini güncelle (format bağımsız)
                try:
                    if vt2 and hasattr(self, 'velocity_preview_text'):
                        self._load_file_content_to_tab_async("velocity", vt2)
                    if dt2 and hasattr(self, 'displacement_preview_text'):
                        self._load_file_content_to_tab_async("displacement", dt2)
                except Exception:
                    pass
        except Exception:
            pass

    def _validate_sibling_choice(self, selected_path: str, expected_ext_upper: str) -> bool:
        """Seçilen dosyanın ana base adıyla eşleştiğini doğrular."""
        try:
            main_dir, main_base = self._get_main_base_and_dir()
            if not selected_path:
                return False
            sel_base = os.path.splitext(os.path.basename(selected_path))[0]
            sel_ext = os.path.splitext(selected_path)[1].upper()
            if sel_base.upper() != main_base.upper() or sel_ext != f".{expected_ext_upper}".upper():
                messagebox.showwarning(
                    "Uygun Olmayan Dosya",
                    f"Seçilen dosya beklenen üçlü ile eşleşmiyor.\n\n"
                    f"Beklenen: {main_base}.{expected_ext_upper}\n"
                    f"Seçilen: {os.path.basename(selected_path)}"
                )
                return False
            return True
        except Exception:
            return True
    
    def _create_buttons(self, parent):
        """Butonları oluşturur"""
        # Ana butonlar çerçevesi
        main_buttons_frame = ttk.LabelFrame(parent, text="İşlemler", padding=10)
        main_buttons_frame.pack(fill="x", pady=(10, 0))
        
        # Üst butonlar
        # Üst butonlar - grid düzeni ile eşit dağılım
        top_button_frame = ttk.Frame(main_buttons_frame)
        top_button_frame.pack(fill="x", pady=(0, 12))

        btn_default = ttk.Button(top_button_frame, text="Varsayılan Değerler",
                                 command=self._program_defaults, width=22)
        btn_default.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        btn_save_default = ttk.Button(top_button_frame, text="Varsayılan Olarak Kaydet",
                                      command=self._set_as_default, width=22)
        btn_save_default.grid(row=0, column=1, sticky="ew", padx=(0, 0))

        # Alt butonlar - grid düzeni ile eşit dağılım
        bottom_button_frame = ttk.Frame(main_buttons_frame)
        bottom_button_frame.pack(fill="x")

        btn_help = ttk.Button(bottom_button_frame, text="Yardım",
                              command=self._help_clicked, width=22)
        btn_help.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        btn_ok = ttk.Button(bottom_button_frame, text="Tamam",
                            command=self._ok_clicked, width=20, style="Accent.TButton")
        btn_ok.grid(row=0, column=1, sticky="ew")

        # Grid sütunlarını eşit genişlikte olacak şekilde ayarla
        for frame in (top_button_frame, bottom_button_frame):
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_columnconfigure(1, weight=1)
    
    def _create_file_preview(self, parent):
        """Dosya önizlemesi bölümünü oluşturur - Format tipine göre tek veya çoklu önizleme"""
        self.preview_main_frame = ttk.Frame(parent)
        self.preview_main_frame.pack(fill="both", expand=True)
        
        # Sekmeli önizleme (tüm formatlar için hız/deplasman tab'larına hazır)
        self._create_multiple_preview()
        
        # Başlangıçta ivme önizlemesini göster ve içerikleri yükle
        self.preview_notebook.select(0)
        self.multiple_preview_frame.pack(fill="both", expand=True)
        self._load_multiple_file_contents()
    
    def _create_multiple_preview(self):
        """Çoklu dosya önizlemesi oluşturur (PEER NGA ve ESM için)"""
        self.multiple_preview_frame = ttk.LabelFrame(self.preview_main_frame, text="Dosya Önizlemeleri", padding=10)
        
        # Notebook için çoklu önizleme
        self.preview_notebook = ttk.Notebook(self.multiple_preview_frame)
        self.preview_notebook.pack(fill="both", expand=True)
        
        # İvme önizlemesi
        self._create_preview_tab("accel", "İvme Dosyası")
        
        # Hız önizlemesi
        self._create_preview_tab("velocity", "Hız Dosyası")
        
        # Yerdeğiştirme önizlemesi
        self._create_preview_tab("displacement", "Yerdeğiştirme Dosyası")
    
    def _create_preview_tab(self, tab_type, tab_title):
        """Önizleme sekmesi oluşturur"""
        tab_frame = ttk.Frame(self.preview_notebook)
        self.preview_notebook.add(tab_frame, text=tab_title)
        
        # İlerleme çubuğu alanı (başta gizli)
        progress_frame = ttk.Frame(tab_frame)
        progress_frame.pack(fill="x", pady=(0, 8))
        progress_label = ttk.Label(progress_frame, text="")
        progress_label.pack(side="left")
        progressbar = ttk.Progressbar(progress_frame, mode="determinate")
        progressbar.pack(side="right", fill="x", expand=True)
        progress_frame.pack_forget()

        # Text container
        text_container = ttk.Frame(tab_frame)
        text_container.pack(fill="both", expand=True)
        
        # Satır numaraları
        line_numbers = tk.Text(text_container, width=8, padx=3, takefocus=0,
                              border=0, state='disabled', wrap='none',
                              background='#f0f0f0', foreground='#666666')
        line_numbers.pack(side="left", fill="y")
        
        # Preview text
        preview_text = tk.Text(text_container, height=12, wrap='none')
        preview_text.pack(side="left", fill="both", expand=True)
        # Başlangıçta düzenlemeye kapalı
        try:
            preview_text.config(state='disabled')
        except Exception:
            pass
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(text_container, orient="vertical", 
                                   command=lambda *args: self._on_scroll_multi(tab_type, *args))
        v_scrollbar.pack(side="right", fill="y")
        
        h_scrollbar = ttk.Scrollbar(tab_frame, orient="horizontal", command=preview_text.xview)
        h_scrollbar.pack(side="bottom", fill="x")
        
        # Scrollbar bağlantıları
        preview_text.config(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        line_numbers.config(yscrollcommand=v_scrollbar.set)
        
        # Mouse wheel
        preview_text.bind("<MouseWheel>", lambda e: self._on_mousewheel_multi(tab_type, e))
        line_numbers.bind("<MouseWheel>", lambda e: self._on_mousewheel_multi(tab_type, e))
        
        # Widget'ları sakla
        setattr(self, f'{tab_type}_line_numbers', line_numbers)
        setattr(self, f'{tab_type}_preview_text', preview_text)
        setattr(self, f'{tab_type}_progress_frame', progress_frame)
        setattr(self, f'{tab_type}_progressbar', progressbar)
        setattr(self, f'{tab_type}_progress_label', progress_label)
    
    def _on_scroll_multi(self, tab_type, *args):
        """Çoklu önizleme için scroll fonksiyonu"""
        preview_text = getattr(self, f'{tab_type}_preview_text')
        line_numbers = getattr(self, f'{tab_type}_line_numbers')
        preview_text.yview(*args)
        line_numbers.yview(*args)
    
    def _on_mousewheel_multi(self, tab_type, event):
        """Çoklu önizleme için mouse wheel fonksiyonu"""
        preview_text = getattr(self, f'{tab_type}_preview_text')
        line_numbers = getattr(self, f'{tab_type}_line_numbers')
        preview_text.yview_scroll(int(-1*(event.delta/120)), "units")
        line_numbers.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break"

    def _on_format_change(self):
        """Format seçimi değiştiğinde sütun ayarlarını günceller - SeismoSignal standardı"""
        format_type = self.format_var.get()
        
        # Önce tüm frame'leri gizle
        self.accel_col_frame.pack_forget()
        self.time_col_frame.pack_forget() 
        self.freq_frame.pack_forget()
        self.skip_frame.pack_forget()
        self.peer_nga_info_frame.pack_forget()
        self.esm_info_frame.pack_forget()
        
        if format_type == "single_accel":
            # Single-value per line: Sadece İvme Sütunu gerekli
            self.accel_col_frame.pack(fill="x", pady=2)
            
        elif format_type == "time_accel":
            # Time & Acceleration: İvme ve Zaman Sütunları gerekli
            self.accel_col_frame.pack(fill="x", pady=2)
            self.time_col_frame.pack(fill="x", pady=2)
            
        elif format_type == "multi_accel":
            # Multiple-value per line: İvme Sütunu + Frekans + Atlanan Başlangıç
            self.accel_col_frame.pack(fill="x", pady=2)
            self.freq_frame.pack(fill="x", pady=2)
            self.skip_frame.pack(fill="x", pady=2)
            
        elif format_type == "esm":
            # ESM formatı: Bilgi paneli göster ve zorunlu dosya uyarısı ver
            self.esm_info_frame.pack(fill="x", pady=10)
            
        elif format_type == "peer_nga":
            # PEER NGA formatı: SeismoSignal'daki gibi özel bilgi paneli göster
            # Tüm parametreler otomatik tespit edilir
            self.peer_nga_info_frame.pack(fill="x", pady=10)
        
        # Ek dosya bilgi metnini güncelle
        self._update_additional_files_info()
        
        # Önizleme tipini güncelle
        self._update_preview_type(initial=True)
    
    def _update_additional_files_info(self):
        """Format tipine göre ek dosya bilgi metnini günceller"""
        # Ek dosya bölümü henüz oluşturulmamışsa çık
        if not hasattr(self, 'additional_info_label'):
            return
            
        format_type = self.format_var.get()
        
        if format_type in ['peer_nga', 'esm']:
            # Zorunlu dosya yükleme formatları
            info_text = f"⚠️ {format_type.upper()} formatı için ZORUNLU:\nHız ve yerdeğiştirme kayıtları ayrı dosyalardan yüklenmelidir."
            color = 'red'
        else:
            # İsteğe bağlı dosya yükleme formatları
            info_text = "Hız ve yerdeğiştirme kayıtlarını ayrı dosyalardan yükleyebilirsiniz:"
            color = 'blue'
        
        self.additional_info_label.config(text=info_text, foreground=color)
    
    def _update_preview_type(self, initial=False):
        """Format tipine göre önizleme tipini günceller"""
        # Önizleme frame'leri henüz oluşturulmamışsa çık
        if not hasattr(self, 'multiple_preview_frame') or not hasattr(self, 'preview_notebook'):
            return
            
        format_type = self.format_var.get()
        
        self.multiple_preview_frame.pack(fill="both", expand=True)
        if not initial:
            self._load_multiple_file_contents()
    
    def _load_multiple_file_contents(self):
        """Çoklu önizleme için dosya içeriklerini yükler"""
        # Çoklu önizleme widget'ları henüz oluşturulmamışsa çık
        if not hasattr(self, 'accel_preview_text'):
            return
            
        # Ana ivme dosyası
        self._load_file_content_to_tab_async("accel", self.file_path)
        
        # Hız dosyası
        velocity_file = getattr(self, 'velocity_file_path', None)
        if velocity_file:
            self._load_file_content_to_tab_async("velocity", velocity_file)
        else:
            self._clear_tab_content("velocity", "Hız dosyası seçilmedi")
        
        # Yerdeğiştirme dosyası
        displacement_file = getattr(self, 'displacement_file_path', None)
        if displacement_file:
            self._load_file_content_to_tab_async("displacement", displacement_file)
        else:
            self._clear_tab_content("displacement", "Yerdeğiştirme dosyası seçilmedi")
    
    def _load_file_content_to_tab_async(self, tab_type, file_path):
        """Belirli bir sekmeye dosya içeriğini parça parça ve arka planda yükler"""
        preview_text = getattr(self, f'{tab_type}_preview_text')
        line_numbers = getattr(self, f'{tab_type}_line_numbers')
        progress_frame = getattr(self, f'{tab_type}_progress_frame')
        progressbar = getattr(self, f'{tab_type}_progressbar')
        progress_label = getattr(self, f'{tab_type}_progress_label')

        # Başlangıç ayarları
        try:
            preview_text.config(state='normal')
            preview_text.delete("1.0", tk.END)
            preview_text.insert("1.0", "Yükleniyor...")
            preview_text.update_idletasks()
            preview_text.config(state='disabled')
            line_numbers.config(state='normal')
            line_numbers.delete("1.0", tk.END)
            line_numbers.config(state='disabled')
        except Exception:
            pass

        # İlerleme çubuğunu göster
        try:
            progress_frame.pack(fill="x", pady=(0, 8))
        except Exception:
            pass

        # Sayaçlar
        setattr(self, f'_{tab_type}_line_count', 0)

        def ui_append(lines_chunk):
            try:
                # İlk "Yükleniyor..." metnini temizle
                current_line_count = getattr(self, f'_{tab_type}_line_count', 0)
                if current_line_count == 0:
                    preview_text.config(state='normal')
                    preview_text.delete("1.0", tk.END)
                    preview_text.config(state='disabled')
                    line_numbers.config(state='normal')
                    line_numbers.delete("1.0", tk.END)
                    line_numbers.config(state='disabled')

                # Metni ekle
                preview_text.config(state='normal')
                preview_text.insert(tk.END, ''.join(lines_chunk))
                preview_text.config(state='disabled')

                # Satır numaralarını ekle
                start_index = current_line_count + 1
                end_index = current_line_count + len(lines_chunk)
                numbers_block = ''.join(f"{i:>4}\n" for i in range(start_index, end_index + 1))
                line_numbers.config(state='normal')
                line_numbers.insert(tk.END, numbers_block)
                line_numbers.config(state='disabled')
                current_line_count = end_index
                setattr(self, f'_{tab_type}_line_count', current_line_count)
            except Exception:
                pass

        def ui_progress(bytes_read, total_size):
            try:
                if total_size and total_size > 0:
                    progressbar.config(mode='determinate', maximum=total_size)
                    progressbar['value'] = bytes_read
                    percent = min(int(bytes_read * 100 / total_size), 100)
                    progress_label.config(text=f"%{percent}")
                else:
                    progressbar.config(mode='indeterminate')
                    progressbar.start(10)
                    progress_label.config(text="")
            except Exception:
                pass

        def ui_done():
            try:
                progressbar.stop()
            except Exception:
                pass
            try:
                progress_frame.pack_forget()
            except Exception:
                pass
            try:
                preview_text.config(state='disabled')
            except Exception:
                pass
            # Ana dosya için son satır numarasını otomatik ayarla
            if tab_type == 'accel':
                try:
                    total_lines = getattr(self, f'_{tab_type}_line_count', 0)
                    if total_lines > 0:
                        self.last_line_var.set(str(total_lines))
                except Exception:
                    pass

        def worker():
            try:
                total_size = 0
                try:
                    total_size = os.path.getsize(file_path)
                except Exception:
                    total_size = 0

                bytes_read = 0
                lines_buffer = []
                last_update = 0
                chunk_line_threshold = 500

                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line_checked = False
                    for line in f:
                        if tab_type == "accel" and not first_line_checked:
                            first_line_checked = True
                            self._auto_detect_peer_format(line)
                        bytes_read = 0
                        try:
                            bytes_read = f.tell()
                        except Exception:
                            pass

                        lines_buffer.append(line)
                        now = time.time()
                        if len(lines_buffer) >= chunk_line_threshold or (now - last_update) > 0.05:
                            chunk = lines_buffer
                            lines_buffer = []
                            last_update = now
                            self.dialog.after(0, ui_append, chunk)
                            self.dialog.after(0, ui_progress, bytes_read, total_size)

                if lines_buffer:
                    self.dialog.after(0, ui_append, lines_buffer)
                    self.dialog.after(0, ui_progress, total_size, total_size)
            except Exception as e:
                self.dialog.after(0, self._clear_tab_content, tab_type, f"Dosya okuma hatası: {str(e)}")
            finally:
                self.dialog.after(0, ui_done)

        threading.Thread(target=worker, daemon=True).start()
    
    def _clear_tab_content(self, tab_type, message):
        """Sekme içeriğini temizler ve mesaj gösterir"""
        preview_text = getattr(self, f'{tab_type}_preview_text')
        line_numbers = getattr(self, f'{tab_type}_line_numbers')
        
        preview_text.config(state='normal')
        preview_text.delete("1.0", tk.END)
        preview_text.insert("1.0", message)
        preview_text.config(state='disabled')
        
        line_numbers.config(state='normal')
        line_numbers.delete("1.0", tk.END)
        line_numbers.insert("1.0", "   1\n")
        line_numbers.config(state='disabled')
        
        # Satır sayacını sıfırla
        setattr(self, f'_{tab_type}_line_count', 0)
    
    def _auto_detect_peer_format(self, first_line: str) -> None:
        """Önizleme satırına göre PEER NGA formatını otomatik seçer."""
        if self._peer_format_auto_set:
            return
        if not first_line:
            return
        try:
            if "PEER NGA" in first_line.upper():
                self._peer_format_auto_set = True

                def _apply():
                    try:
                        if self.format_var.get() != "peer_nga":
                            self.format_var.set("peer_nga")
                            self._on_format_change()
                    finally:
                        self._peer_format_auto_set = True

                self.dialog.after(0, _apply)
        except Exception:
            self._peer_format_auto_set = True
    def _detect_first_data_line(self, lines):
        """Sayı ile başlayan ilk satırın numarasını otomatik tespit eder"""
        import re
        
        for i, line in enumerate(lines, 1):
            # Boş satırları atla
            if not line.strip():
                continue
                
            # Satırın başındaki boşlukları temizle
            cleaned_line = line.strip()
            
            # Sayı ile başlayan satırları kontrol et (pozitif/negatif sayılar, ondalık sayılar)
            # Örnek formatlar: "1.234", "-0.567", "0.001", "123.45", "-456.78"
            number_pattern = r'^[-+]?\d*\.?\d+([eE][-+]?\d+)?'
            
            if re.match(number_pattern, cleaned_line):
                # Eğer satır sadece bir sayı içeriyorsa veya sayılar içeriyorsa
                # Bu muhtemelen veri satırıdır
                parts = cleaned_line.split()
                try:
                    # İlk elemanın sayı olduğunu doğrula
                    float(parts[0])
                    return i
                except (ValueError, IndexError):
                    continue
        
        # Hiç sayı bulunamazsa varsayılan değeri döndür
        return 6

    def _detect_last_data_line(self, lines):
        """Veri içeren son satırın numarasını otomatik tespit eder"""
        import re
        
        # Sondan başa doğru kontrol et
        for i in range(len(lines), 0, -1):
            line = lines[i-1]  # 0-indexed olduğu için i-1
            
            # Boş satırları atla
            if not line.strip():
                continue
                
            # Satırın başındaki boşlukları temizle
            cleaned_line = line.strip()
            
            # Sayı ile başlayan satırları kontrol et
            number_pattern = r'^[-+]?\d*\.?\d+([eE][-+]?\d+)?'
            
            if re.match(number_pattern, cleaned_line):
                # Eğer satır sayı içeriyorsa bu veri satırıdır
                parts = cleaned_line.split()
                try:
                    # İlk elemanın sayı olduğunu doğrula
                    float(parts[0])
                    
                    # Ek kontroller: Çok kısa veya şüpheli satırları filtrele
                    if len(parts) >= 1:  # En az bir sayı olmalı
                        return i
                except (ValueError, IndexError):
                    continue
        
        # Hiç veri satırı bulunamazsa toplam satır sayısını döndür
        return len(lines)

    def _load_file_content(self):
        """Dosya içeriğini GUI'yi bloklamadan parça parça yükler ve satır numaralarını oluşturur"""
        # Metodu çoklu sekmeli yapı lehine devre dışı bırak
        return
    
    def _on_scroll(self, *args):
        """Scrollbar ile her iki text widget'ı da kaydır"""
        preview_text = getattr(self, 'accel_preview_text', None)
        line_numbers = getattr(self, 'accel_line_numbers', None)
        if preview_text and line_numbers:
            preview_text.yview(*args)
            line_numbers.yview(*args)
    
    def _on_mousewheel(self, event):
        """Mouse wheel ile scrolling'i sync et"""
        preview_text = getattr(self, 'accel_preview_text', None)
        line_numbers = getattr(self, 'accel_line_numbers', None)
        if preview_text and line_numbers:
            preview_text.yview_scroll(int(-1*(event.delta/120)), "units")
            line_numbers.yview_scroll(int(-1*(event.delta/120)), "units")
        return "break"
    
    def _change_units(self):
        """Birim değiştirme dialogunu açar"""
        try:
            # Birim değiştirme dialogu oluştur
            units_dialog = tk.Toplevel(self.dialog)
            units_dialog.title("Birim Ayarları")
            units_dialog.geometry("700x950")
            units_dialog.transient(self.dialog)
            units_dialog.grab_set()
            units_dialog.resizable(False, False)
            
            # Pencereyi merkeze yerleştir
            units_dialog.update_idletasks()
            x = (units_dialog.winfo_screenwidth() // 2) - (700 // 2)
            y = (units_dialog.winfo_screenheight() // 2) - (800 // 2)
            units_dialog.geometry(f"700x950+{x}+{y}")
            
            # Ana çerçeve
            main_frame = ttk.Frame(units_dialog, padding="30")
            main_frame.pack(fill="both", expand=True)
            
            # Başlık
            title_label = ttk.Label(main_frame, text="📏 Birim Ayarları", 
                                   font=('Segoe UI', 14, 'bold'))
            title_label.pack(pady=(0, 20))
            
            # Mevcut birimler için değişkenler
            new_accel_unit = tk.StringVar(value=self.accel_unit_var.get())
            new_velocity_unit = tk.StringVar(value=self.velocity_unit_var.get())
            new_displacement_unit = tk.StringVar(value=self.displacement_unit_var.get())
            
            # İvme birimi seçimi
            accel_frame = ttk.LabelFrame(main_frame, text="İvme Birimi", padding=20)
            accel_frame.pack(fill="x", pady=(0, 20))
            
            accel_options = [
                ("m/s² (metre/saniye²)", "m/s²"),
                ("g (yerçekimi ivmesi)", "g"),
                ("cm/s² (santimetre/saniye²)", "cm/s²"),
                ("mm/s² (milimetre/saniye²)", "mm/s²")
            ]
            
            for text, value in accel_options:
                rb = ttk.Radiobutton(accel_frame, text=text, variable=new_accel_unit, value=value)
                rb.pack(anchor="w", pady=5)
            
            # Hız birimi seçimi
            velocity_frame = ttk.LabelFrame(main_frame, text="Hız Birimi", padding=20)
            velocity_frame.pack(fill="x", pady=(0, 20))
            
            velocity_options = [
                ("m/s (metre/saniye)", "m/s"),
                ("cm/s (santimetre/saniye)", "cm/s"),
                ("mm/s (milimetre/saniye)", "mm/s"),
                ("km/h (kilometre/saat)", "km/h")
            ]
            
            for text, value in velocity_options:
                rb = ttk.Radiobutton(velocity_frame, text=text, variable=new_velocity_unit, value=value)
                rb.pack(anchor="w", pady=5)
            
            # Yerdeğiştirme birimi seçimi
            displacement_frame = ttk.LabelFrame(main_frame, text="Yerdeğiştirme Birimi", padding=20)
            displacement_frame.pack(fill="x", pady=(0, 20))
            
            displacement_options = [
                ("m (metre)", "m"),
                ("cm (santimetre)", "cm"),
                ("mm (milimetre)", "mm"),
                ("μm (mikrometre)", "μm")
            ]
            
            for i, (text, value) in enumerate(displacement_options):
                rb = ttk.Radiobutton(displacement_frame, text=text, variable=new_displacement_unit, value=value)
                rb.pack(anchor="w", pady=5)
            
            # Bilgi notu
            info_frame = ttk.Frame(main_frame)
            info_frame.pack(fill="x", pady=(20, 25))
            
            info_text = ("💡 Not: Birim değişikliği parametre görünümünü etkiler.\n"
                        "Grafik ve tablolardaki verilerin güncellenmesi için 'Tamam' butonuna basın.")
            info_label = ttk.Label(info_frame, text=info_text, 
                                  font=('Segoe UI', 10), foreground="blue",
                                  wraplength=600, justify="left")
            info_label.pack()
            
            # Butonlar
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill="x", pady=(25, 0))
            
            def apply_units():
                """Birim değişikliklerini uygula"""
                # Birim değişkenlerini güncelle
                self.accel_unit_var.set(new_accel_unit.get())
                self.velocity_unit_var.set(new_velocity_unit.get())
                self.displacement_unit_var.set(new_displacement_unit.get())
                
                # Ana dialogdaki birim etiketlerini güncelle (eğer mevcutsa)
                self._update_units_display()
                
                # Dialog'u kapat
                units_dialog.destroy()
                
                # Başarı mesajı
                messagebox.showinfo("Başarılı", 
                                  f"Birimler başarıyla güncellendi!\n\n"
                                  f"📊 İvme: {new_accel_unit.get()}\n"
                                  f"🚀 Hız: {new_velocity_unit.get()}\n"
                                  f"📍 Yerdeğiştirme: {new_displacement_unit.get()}")
            
            def reset_defaults():
                """Varsayılan birimlere sıfırla"""
                new_accel_unit.set("g")
                new_velocity_unit.set("cm/s")
                new_displacement_unit.set("cm")
            
            # Butonları yerleştir
            ttk.Button(button_frame, text="Varsayılana Sıfırla", 
                      command=reset_defaults).pack(side="left")
            
            ttk.Button(button_frame, text="İptal", 
                      command=units_dialog.destroy).pack(side="right", padx=(5, 0))
            
            ttk.Button(button_frame, text="Uygula", 
                      command=apply_units, 
                      style="Accent.TButton").pack(side="right", padx=(5, 0))
            
        except Exception as e:
            print(f"❌ Birim değiştirme dialogu hatası: {e}")
            messagebox.showerror("Hata", f"Birim ayarları açılırken hata:\n{str(e)}")
    
    def _update_units_display(self):
        """Ana dialogdaki birim gösterimini günceller"""
        try:
            # Güvenli import: önce mutlak, sonra relatif; başarısız olursa semboller kod olarak kalır
            try:
                from utils.unit_converter import UnitConverter as _UC
            except Exception:
                try:
                    from ...utils.unit_converter import UnitConverter as _UC
                except Exception:
                    _UC = None

            # Doğru birim simgelerini al
            accel_code = self.accel_unit_var.get()
            velocity_code = self.velocity_unit_var.get()
            disp_code = self.displacement_unit_var.get()
            
            # İvme birimi için symbol al
            if _UC is not None:
                accel_unit_info = _UC.get_unit_info('acceleration', accel_code)
                accel_symbol = accel_unit_info.get('symbol', accel_code)
            else:
                accel_symbol = accel_code
            
            # Hız birimi için (genellikle cm/s, m/s formatında)
            velocity_display = velocity_code  # Zaten doğru formatta olması gerekiyor
            
            # Yerdeğiştirme birimi için symbol al
            if _UC is not None:
                disp_unit_info = _UC.get_unit_info('displacement', disp_code)
                disp_symbol = disp_unit_info.get('symbol', disp_code)
            else:
                disp_symbol = disp_code
            
            # Units section'daki etiketleri güncelle (eğer widget'lar mevcutsa)
            # Bu kısım units section oluşturulduktan sonra çalışır
            self.accel_unit_label.config(text=f"İvme Birimi: {accel_symbol}")
            self.velocity_unit_label.config(text=f"Hız Birimi: {velocity_display}")
            self.displacement_unit_label.config(text=f"Yerdeğiştirme: {disp_symbol}")
        except Exception as e:
            print(f"⚠️ Birim görüntü güncelleme hatası: {e}")
    
    def _program_defaults(self):
        """Program varsayılanlarını yükler - SeismoSignal standardı"""
        self.first_line_var.set("5")  # SeismoSignal varsayılanı
        # Son satır değeri dosya yüklendiğinde otomatik tespit edilir
        if not self.last_line_var.get():
            self.last_line_var.set("5284")  # Örnek değer
        self.time_step_var.set("0.01")
        self.scaling_factor_var.set("1.0")
        self.format_var.set("single_accel")
        self.accel_column_var.set("2")  # SeismoSignal örneği
        self.time_column_var.set("1")
        self.frequency_var.set("1")     # Tüm değerleri oku
        self.initial_skip_var.set("0")  # Hiç değer atla
        
        # Format değişikliğini uygula
        self._on_format_change()
    
    def _set_as_default(self):
        """Mevcut ayarları varsayılan olarak kaydet"""
        try:
            data = {
                'first_line': int(self.first_line_var.get()) if self.first_line_var.get() else 5,
                'last_line': int(self.last_line_var.get()) if self.last_line_var.get() else '',
                'time_step': float(self.time_step_var.get()) if self.time_step_var.get() else 0.01,
                'scaling_factor': float(self.scaling_factor_var.get()) if self.scaling_factor_var.get() else 1.0,
                'format': self.format_var.get(),
                'accel_column': int(self.accel_column_var.get()) if self.accel_column_var.get() else 2,
                'time_column': int(self.time_column_var.get()) if self.time_column_var.get() else 1,
                'frequency': int(self.frequency_var.get()) if self.frequency_var.get() else 1,
                'initial_skip': int(self.initial_skip_var.get()) if self.initial_skip_var.get() else 0,
                'accel_unit': self.accel_unit_var.get(),
                'velocity_unit': self.velocity_unit_var.get(),
                'displacement_unit': self.displacement_unit_var.get()
            }

            if self._save_user_defaults(data):
                messagebox.showinfo("Başarılı", "Ayarlar varsayılan olarak kaydedildi.")
            else:
                messagebox.showerror("Hata", "Ayarlar kaydedilemedi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilirken hata oluştu:\n{e}")
    
    def _help_clicked(self):
        """Yardım dialogunu açar - SeismoSignal standardına uygun"""
        help_text = """
Dosya Giriş Parametreleri Yardımı (SeismoSignal Standardı):

TEMEL PARAMETRELER:
• İlk Satır (Varsayılan: 6): Dosyanın başından atlanacak satır sayısı. Çoğu accelerogram dosyası 
  başlık bilgileri içerir. Örneğin European Strong Motion Database dosyaları 31 satır başlık 
  içerir, bu durumda değer 32 olmalıdır.

• Son Satır: Program tarafından otomatik tespit edilir. Dosyada ivme verilerinden sonra hız/
  yerdeğiştirme verileri varsa, bu parametreyle sadece ivme bölümü okunabilir.

• Zaman Adımı dt: İvme kaydının zaman adımı (saniye). Maksimum 2^18 (262144) veri noktası 
  desteklenir. >10000 noktalı büyük dosyalar yavaş analize neden olabilir.

• Ölçek Faktörü: Verileri ölçeklendirmek için çarpan.

DOSYA FORMAT TÜRLERİ:

1) Her satırda tek ivme değeri: Sadece İvme Sütunu parametresi gerekir.

2) Her satırda zaman ve ivme değeri: İvme Sütunu ve Zaman Sütunu parametreleri gerekir.
   Bu format düzensiz zaman aralıklı veriler için kullanışlıdır.

3) Her satırda birden fazla ivme değeri: İvme Sütunu, Okuma Frekansı ve Atlanan Başlangıç 
   parametreleri gerekir. Frekans 1=tüm değerler, 2=her ikinci değer, 3=her üçüncü değer.

4) ESM/PEER NGA Formatları: Parametreler otomatik tespit edilir. İsteğe bağlı 
   olarak manuel ayarlama yapılabilir.

SÜTUN AYARLARI:
• İvme Sütunu: İvme değerlerinin bulunduğu sütun numarası
• Zaman Sütunu: Zaman değerlerinin bulunduğu sütun numarası  
• Okuma Frekansı: 1=tüm değerler, 2=her ikinci değer oku
• Atlanan Başlangıç: Satır başından atlanacak değer sayısı

BİRİMLER:
• İvme: g (yerçekimi ivmesi)
• Hız: cm/s (santimetre/saniye)  
• Yerdeğiştirme: cm (santimetre)

NOT: Unix ortamından gelen dosyalar düzgün okunmayabilir. Bu durumda dosyayı metin editöründe 
açıp ANSI/DOS formatında kaydedin.
        """
        
        help_dialog = tk.Toplevel(self.dialog)
        help_dialog.title("Yardım - SeismoSignal Standardı")
        help_dialog.geometry("700x600")
        help_dialog.transient(self.dialog)
        help_dialog.resizable(True, True)
        
        # Scrollable text widget
        text_frame = ttk.Frame(help_dialog)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget = tk.Text(text_frame, wrap="word", font=('Segoe UI', 9), padx=10, pady=10)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        text_widget.config(yscrollcommand=scrollbar.set)
        
        text_widget.insert("1.0", help_text)
        text_widget.config(state="disabled")
    
    def _ok_clicked(self):
        """OK butonuna tıklandığında çağrılır"""
        try:
            # Parametreleri validate et
            first_line = int(self.first_line_var.get())
            last_line = int(self.last_line_var.get())
            time_step = float(self.time_step_var.get())
            scaling_factor = float(self.scaling_factor_var.get())
            
            if first_line < 1:
                raise ValueError("İlk Satır 1'den küçük olamaz")
            if last_line < first_line:
                raise ValueError("Son Satır, İlk Satır'dan küçük olamaz")
            if time_step <= 0:
                raise ValueError("Zaman Adımı sıfırdan büyük olmalı")
            if last_line - first_line > 262144:
                raise ValueError("Maksimum 262144 veri noktası desteklenir (SeismoSignal limiti)")

            # Ek doğrulamalar
            accel_column = int(self.accel_column_var.get())
            time_column = int(self.time_column_var.get())
            frequency = int(self.frequency_var.get())
            initial_skip = int(self.initial_skip_var.get())

            if accel_column < 1:
                raise ValueError("İvme Sütunu 1 veya daha büyük olmalı")
            if time_column < 1:
                raise ValueError("Zaman Sütunu 1 veya daha büyük olmalı")
            if frequency <= 0:
                raise ValueError("Okuma Frekansı 0'dan büyük olmalı")
            if initial_skip < 0:
                raise ValueError("Atlanan Başlangıç 0 veya daha büyük olmalı")
            
            # PEER NGA ve ESM formatları için zorunlu dosya kontrolü
            format_type = self.format_var.get()
            if format_type in ['peer_nga', 'esm']:
                velocity_file = getattr(self, 'velocity_file_path', None)
                displacement_file = getattr(self, 'displacement_file_path', None)
                
                if not velocity_file:
                    raise ValueError(f"{format_type.upper()} formatı için hız kaydı yüklenmesi zorunludur.\n\n'Hız Kaydı Yükle' butonunu kullanarak hız dosyasını seçin.")
                
                if not displacement_file:
                    raise ValueError(f"{format_type.upper()} formatı için yerdeğiştirme kaydı yüklenmesi zorunludur.\n\n'Yerdeğiştirme Yükle' butonunu kullanarak yerdeğiştirme dosyasını seçin.")
                
            # Sonucu oluştur
            self.result = {
                'first_line': first_line,
                'last_line': last_line,
                'time_step': time_step,
                'scaling_factor': scaling_factor,
                'format': self.format_var.get(),
                'accel_column': accel_column,
                'time_column': time_column,
                'frequency': frequency,
                'initial_skip': initial_skip,
                'accel_unit': self.accel_unit_var.get(),
                'velocity_unit': self.velocity_unit_var.get(),
                'displacement_unit': self.displacement_unit_var.get(),
                'file_path': self.file_path,
                'velocity_file_path': getattr(self, 'velocity_file_path', None),
                'displacement_file_path': getattr(self, 'displacement_file_path', None)
            }
            
            self.dialog.destroy()
            
        except ValueError as e:
            messagebox.showerror("Hata", f"Geçersiz parametre: {str(e)}")
        except Exception as e:
            messagebox.showerror("Hata", f"Beklenmeyen hata: {str(e)}")
    
    def _cancel_clicked(self):
        """Cancel butonuna tıklandığında çağrılır"""
        self.result = None
        self.dialog.destroy()
    
    def _load_velocity_file(self):
        """Hız kaydı dosyası yükler"""
        from tkinter import filedialog
        
        # Beklenen klasör ve dosya adı (ana dosyaya göre)
        directory, base = self._get_main_base_and_dir()
        initialfile = f"{base}.VT2"
        file_path = filedialog.askopenfilename(
            title="Hız Kaydı Dosyası Seç",
            filetypes=[("VT2 Dosyaları (Hız)", "*.vt2"), ("Tüm Dosyalar", "*.*")],
            initialdir=directory,
            initialfile=initialfile
        )
        
        if file_path:
            import os
            file_name = os.path.basename(file_path)
            # Eşleme validasyonu: ana AT2 ile aynı base ada sahip VT2 olmalı
            if not self._validate_sibling_choice(file_path, "VT2"):
                return
            self.velocity_file_var.set(file_name)
            self.velocity_file_path = file_path
            print(f"📁 Hız kaydı yüklendi: {file_name}")
            
            # Önizlemeyi güncelle (format bağımsız)
            if hasattr(self, 'velocity_preview_text'):
                self._load_file_content_to_tab_async("velocity", file_path)
        else:
            print("❌ Hız kaydı yükleme iptal edildi")
    
    def _load_displacement_file(self):
        """Yerdeğiştirme kaydı dosyası yükler"""
        from tkinter import filedialog
        
        # Beklenen klasör ve dosya adı (ana dosyaya göre)
        directory, base = self._get_main_base_and_dir()
        initialfile = f"{base}.DT2"
        file_path = filedialog.askopenfilename(
            title="Yerdeğiştirme Kaydı Dosyası Seç",
            filetypes=[("DT2 Dosyaları (Yerdeğiştirme)", "*.dt2"), ("Tüm Dosyalar", "*.*")],
            initialdir=directory,
            initialfile=initialfile
        )
        
        if file_path:
            import os
            file_name = os.path.basename(file_path)
            if not self._validate_sibling_choice(file_path, "DT2"):
                return
            self.displacement_file_var.set(file_name)
            self.displacement_file_path = file_path
            print(f"📁 Yerdeğiştirme kaydı yüklendi: {file_name}")
            
            # Önizlemeyi güncelle (format bağımsız)
            if hasattr(self, 'displacement_preview_text'):
                self._load_file_content_to_tab_async("displacement", file_path)
        else:
            print("❌ Yerdeğiştirme kaydı yükleme iptal edildi")
    
    def _clear_additional_files(self):
        """Ek dosyaları temizler"""
        self.velocity_file_var.set("Seçilmedi")
        self.displacement_file_var.set("Seçilmedi")
        self.velocity_file_path = None
        self.displacement_file_path = None
        print("🧹 Ek dosyalar temizlendi")
        
        # Önizlemeyi temizle
        if hasattr(self, 'velocity_preview_text'):
            self._clear_tab_content("velocity", "Hız dosyası seçilmedi")
        if hasattr(self, 'displacement_preview_text'):
            self._clear_tab_content("displacement", "Yerdeğiştirme dosyası seçilmedi")