"""
TBDY-2018 Spektrum Uygulaması Stil Ayarları
"""

# Ana Renkler
BG_COLOR = "#FFFFFF"
FRAME_COLOR = "#FFFFFF"
TEXT_COLOR = "#2C3E50"
ACCENT_COLOR = "#2E86AB"
BUTTON_BG = "#FFFFFF"
BUTTON_FG = "#2C3E50"

# Profesyonel Grafik Renk Paleti - Bilimsel ve Modern
CUSTOM_COLORS = {
    # Ana spektrum renkleri - daha profesyonel tonlar
    'yatay': '#1f77b4',      # Koyu mavi (matplotlib default blue)
    'dusey': '#9467bd',      # Profesyonel mor
    'yerdeğiştirme': '#ff7f0e',  # Turuncu (matplotlib default orange)
    'nokta': '#d62728',      # Kırmızı (matplotlib default red)
    
    # Zaman serisi grafik renkleri - daha belirgin ve okunabilir
    'acceleration': '#2E4057',    # Koyu lacivert - İvme
    'velocity': '#048A81',        # Teal yeşili - Hız  
    'displacement': '#C73E1D',    # Koyu kırmızı - Yerdeğiştirme
    
    # Yardımcı renkler
    'grid': '#E5E5E5',       # Daha yumuşak grid
    'text': '#2C3E50',       # Koyu gri metin
    'background': '#FAFAFA', # Çok açık gri arka plan
    'accent': '#3498DB',     # Vurgu rengi
    
    # Peak ve marker renkleri
    'peak_positive': '#E74C3C',   # Parlak kırmızı - pozitif peak
    'peak_negative': '#8E44AD',   # Mor - negatif peak
    'marker': '#F39C12',          # Turuncu - seçili nokta marker
    'selection': '#27AE60'        # Yeşil - seçim vurgusu
}

# Matplotlib Stil Ayarları
MPL_STYLE_CONFIG = {
    'figure.max_open_warning': 0,
    'font.family': 'DejaVu Sans',
    'font.size': 10,
    'axes.labelsize': 10,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9
}

# Seaborn Stil Ayarları
SEABORN_STYLE = "whitegrid"
SEABORN_CONTEXT = "notebook"
SEABORN_FONT_SCALE = 1.0

# Sayısal Format Fonksiyonları
def format_scientific_value(value, precision=4):
    """Bilimsel notasyonda sayısal değer formatlar"""
    if value == 0:
        return "0.0000"
    
    import math
    abs_val = abs(value)
    
    # Çok küçük veya çok büyük değerler için bilimsel notasyon
    if abs_val < 1e-3 or abs_val >= 1e4:
        return f"{value:.{precision}e}"
    # Normal değerler için sabit nokta
    elif abs_val >= 1:
        return f"{value:.{precision}f}"
    else:
        # Küçük değerler için daha fazla ondalık
        return f"{value:.{precision+2}f}"

def format_engineering_value(value, unit="", precision=4):
    """Mühendislik formatında değer formatlar (binlik ayırıcılar ile)"""
    if value == 0:
        return f"0.0000 {unit}".strip()
    
    import math
    abs_val = abs(value)
    
    # Çok küçük değerler
    if abs_val < 1e-6:
        return f"{value:.{precision}e} {unit}".strip()
    # Küçük değerler
    elif abs_val < 1e-3:
        return f"{value:.{precision+3}f} {unit}".strip()
    # Normal aralık
    elif abs_val < 1000:
        return f"{value:.{precision}f} {unit}".strip()
    # Büyük değerler - binlik ayırıcı ile
    else:
        return f"{value:,.{precision}f} {unit}".strip()

def format_table_value(value, data_type="general"):
    """Tablo için optimize edilmiş değer formatı"""
    if value == 0:
        return "0.0000"
    
    import math
    abs_val = abs(value)
    
    # Veri türüne göre özel formatlar
    if data_type == "time":
        # Zaman değerleri - genellikle saniye
        if abs_val < 0.001:
            return f"{value:.6f}"
        else:
            return f"{value:.4f}"
    elif data_type == "acceleration":
        # İvme değerleri - g cinsinden genellikle küçük
        if abs_val < 0.001:
            return f"{value:.6f}"
        else:
            return f"{value:.4f}"
    elif data_type == "velocity":
        # Hız değerleri - cm/s
        if abs_val < 0.01:
            return f"{value:.5f}"
        else:
            return f"{value:.3f}"
    elif data_type == "displacement":
        # Yerdeğiştirme - cm
        if abs_val < 0.01:
            return f"{value:.5f}"
        else:
            return f"{value:.3f}"
    else:
        # Genel format
        if abs_val < 1e-4:
            return f"{value:.6e}"
        elif abs_val < 0.001:
            return f"{value:.6f}"
        elif abs_val < 1:
            return f"{value:.5f}"
        elif abs_val < 1000:
            return f"{value:.4f}"
        else:
            return f"{value:.3e}"

# TTK Stil Ayarları
def configure_ttk_styles(style):
    """TTK stil ayarlarını uygular"""
    style.theme_use('clam')
    
    # Ana stil ayarları
    style.configure('.', 
                   background=BG_COLOR, 
                   foreground=TEXT_COLOR, 
                   font=('Segoe UI', 10))
    
    # Frame ayarları
    style.configure("TFrame", background=BG_COLOR)
    
    # LabelFrame ayarları
    style.configure("TLabelframe", 
                   background=BG_COLOR, 
                   bordercolor="#D0D0D0")
    style.configure("TLabelframe.Label", 
                   background=BG_COLOR, 
                   foreground=TEXT_COLOR, 
                   font=('Segoe UI', 11, 'bold'))
    
    # Notebook ayarları
    style.configure("TNotebook", 
                   background=BG_COLOR, 
                   borderwidth=0)
    style.configure("TNotebook.Tab", 
                   background="#DDE5E8", 
                   foreground=TEXT_COLOR, 
                   padding=[10, 5], 
                   font=('Segoe UI', 10))
    style.map("TNotebook.Tab", 
             background=[("selected", FRAME_COLOR)], 
             foreground=[("selected", ACCENT_COLOR)])
    
    # Button ayarları
    style.configure("TButton", 
                   background=BUTTON_BG, 
                   foreground=BUTTON_FG, 
                   font=('Segoe UI', 10), 
                   borderwidth=1, 
                   relief="raised")
    style.map("TButton", 
             background=[('active', '#E0E0E0')])
    
    # Accent Button ayarları
    style.configure("Accent.TButton", 
                   background=ACCENT_COLOR, 
                   foreground=FRAME_COLOR, 
                   font=('Segoe UI', 10, 'bold'))
    style.map("Accent.TButton", 
             background=[('active', '#256A8A')])
    
    # Entry ayarları
    style.configure("TEntry", fieldbackground=FRAME_COLOR)
    
    # Combobox ayarları
    style.configure("TCombobox", fieldbackground=FRAME_COLOR)
    
    # Treeview ayarları
    style.configure("Treeview", 
                   background=FRAME_COLOR, 
                   fieldbackground=FRAME_COLOR, 
                   rowheight=25)
    style.configure("Treeview.Heading", 
                   font=('Segoe UI', 10, 'bold'), 
                   background="#EAEAEA", 
                   relief="flat")
    style.map("Treeview.Heading", 
             background=[('active', '#D0D0D0')])

    # Grup başlıkları ve küçük/monospace label stilleri
    try:
        # LabelFrame başlık yazısı (Group)
        style.configure("Group.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        # Küçük, okunabilir label
        style.configure("Small.TLabel", font=("Segoe UI", 9))
        # Değerler için monospace stil (okunabilirlik)
        style.configure("Value.TLabel", font=("Consolas", 10))
    except Exception:
        pass

    # Başlık ve alt bilgi Label stilleri
    try:
        style.configure(
            "Title.TLabel",
            background=BG_COLOR,
            foreground=ACCENT_COLOR,
            font=FONTS['title']
        )
        style.configure(
            "Footer.TLabel",
            background=BG_COLOR,
            foreground='gray',
            font=FONTS['small']
        )
    except Exception:
        # Stil uygulanamazsa sessizce geç
        pass

# Font Ayarları
FONTS = {
    'title': ('Segoe UI', 24, 'bold'),
    'subtitle': ('Segoe UI', 12),
    'heading': ('Segoe UI', 11, 'bold'),
    'body': ('Segoe UI', 10),
    'small': ('Segoe UI', 9)
}

# Pencere Boyutları
WINDOW_SIZES = {
    'main': "1200x800",
    'menu': "600x400",
    'dialog': "400x320"
}

# Responsive boyutlandırma ayarları
RESPONSIVE_SETTINGS = {
    'min_window_width': 1200,
    'min_window_height': 700,
    'input_panel_min_width': 400,
    'input_panel_max_width': 500,
    'plot_panel_min_width': 600,
    'data_table_min_height': 400,
    'resize_threshold': {
        'small': (1200, 800),
        'medium': (1500, 900), 
        'large': (1920, 1080)
    }
}

# Responsive font boyutları
RESPONSIVE_FONTS = {
    'small_screen': {
        'title': ('Segoe UI', 10, 'bold'),
        'label': ('Segoe UI', 9),
        'entry': ('Segoe UI', 9),
        'button': ('Segoe UI', 9)
    },
    'medium_screen': {
        'title': ('Segoe UI', 11, 'bold'),
        'label': ('Segoe UI', 10),
        'entry': ('Segoe UI', 10),
        'button': ('Segoe UI', 10)
    },
    'large_screen': {
        'title': ('Segoe UI', 12, 'bold'),
        'label': ('Segoe UI', 11),
        'entry': ('Segoe UI', 11),
        'button': ('Segoe UI', 11)
    }
}

def get_screen_size_category(width, height):
    """Ekran boyutuna göre kategori döndürür"""
    if width < 1300 or height < 800:
        return 'small_screen'
    elif width < 1600 or height < 1000:
        return 'medium_screen'
    else:
        return 'large_screen'

def get_responsive_font(screen_category, element_type):
    """Responsive font ayarlarını döndürür"""
    return RESPONSIVE_FONTS.get(screen_category, RESPONSIVE_FONTS['medium_screen']).get(element_type, FONTS['label']) 
