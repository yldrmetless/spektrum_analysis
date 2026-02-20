"""
Ana spektrum analiz penceresi - modüler yapıda yeniden tasarlandı
TBDY_GUI.py özellikleri entegre edildi
"""

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
import logging
import matplotlib
matplotlib.use('TkAgg')
from tkinter import PhotoImage
# Vektör çıktı boyutunu azaltmak için yol basitleştirmeyi aç
try:
    matplotlib.rcParams['path.simplify'] = True
except Exception:
    pass
from concurrent.futures import ThreadPoolExecutor
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
import time
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
import warnings
import re
from src.gui.components.input_panel import RoundedButton
# Modüler importlar
try:
    # Paket içinden (python -m src.main) çalışırken
    from ..config.styles import BG_COLOR, WINDOW_SIZES
    from ..data.loader import DataLoader
    from ..data.processor import DataProcessor
    from ..calculations.spectrum import SpectrumCalculator
    from ..calculations.coefficients import CoefficientCalculator
    from ..calculations.earthquake_stats import EarthquakeStats
    from ..utils.file_utils import FileUtils
    from ..utils.map_utils import MapUtils
    from ..utils.unit_converter import UnitConverter
    from ..utils.advanced_export import AdvancedExporter
    from ..utils.pdf_report_generator import PDFReportGenerator
    from ..gui.components.input_panel import InputPanel
    from ..models.design_params import DesignParamsModel
    from ..gui.components.plot_panel import PlotPanel
    from ..gui.components.data_table import DataTable
    from ..gui.components.interactive_plot import InteractivePlot
    from ..gui.components.stats_panel import StatsPanel
    from ..gui.components.basic_scaling_panel import BasicScalingPanel
    from ..gui.components.pair_manager import PairManager
    from ..gui.components.ers_panel import ERSPanel
    from ..gui.dialogs.save_dialog import SaveDialog, PeerExportDialog
    from ..gui.dialogs.input_file_params_dialog import InputFileParametersDialog
    from ..utils.responsive_manager import ResponsiveManager
    from ..utils.keyboard_manager import KeyboardManager
    from ..utils.enhanced_keyboard_manager import EnhancedKeyboardManager
except Exception:
    # Doğrudan dosya çalıştırma durumunda (python src/gui/main_window.py)
    # sys.path'e proje kökünü ekleyip mutlak importlara düş
    try:
        ROOT = Path(__file__).resolve().parents[2]
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
    except Exception:
        pass
    from src.config.styles import BG_COLOR, WINDOW_SIZES
    from src.data.loader import DataLoader
    from src.data.processor import DataProcessor
    from src.calculations.spectrum import SpectrumCalculator
    from src.calculations.coefficients import CoefficientCalculator
    from src.calculations.earthquake_stats import EarthquakeStats
    from src.utils.file_utils import FileUtils
    from src.utils.map_utils import MapUtils
    from src.utils.unit_converter import UnitConverter
    from src.utils.advanced_export import AdvancedExporter
    from src.utils.pdf_report_generator import PDFReportGenerator
    from src.gui.components.input_panel import InputPanel
    from src.models.design_params import DesignParamsModel
    from src.gui.components.plot_panel import PlotPanel
    from src.gui.components.data_table import DataTable
    from src.gui.components.interactive_plot import InteractivePlot
    from src.gui.components.stats_panel import StatsPanel
    from src.gui.components.basic_scaling_panel import BasicScalingPanel
    from src.gui.components.pair_manager import PairManager
    from src.gui.components.ers_panel import ERSPanel
    from src.gui.dialogs.save_dialog import SaveDialog, PeerExportDialog
    from src.gui.dialogs.input_file_params_dialog import InputFileParametersDialog
    from src.utils.responsive_manager import ResponsiveManager
    from src.utils.keyboard_manager import KeyboardManager
    from src.utils.enhanced_keyboard_manager import EnhancedKeyboardManager

# Matplotlib ayarları
plt.ioff()

class ScrollableFrame(ttk.Frame):
    """Dikey kaydırılabilir çerçeve (Canvas + Scrollbar)"""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # İçerik çerçevesi
        self.content = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.content, anchor="nw")

        # Scrollregion ve geniÅŸlik senkronu
        self.content.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))

        # Fare tekerleği – Windows/macOS/Linux
        def _on_wheel(event):
            if getattr(event, 'num', None) == 4:      # Linux up
                self.canvas.yview_scroll(-3, "units")
            elif getattr(event, 'num', None) == 5:    # Linux down
                self.canvas.yview_scroll(3, "units")
            else:
                delta = getattr(event, 'delta', 0)
                if sys.platform == "darwin":
                    self.canvas.yview_scroll(-int(delta), "units")
                else:
                    self.canvas.yview_scroll(-int(delta/120), "units")

        def _bind_mousewheel(_):
            self.canvas.bind_all("<MouseWheel>", _on_wheel)
            self.canvas.bind_all("<Button-4>", _on_wheel)
            self.canvas.bind_all("<Button-5>", _on_wheel)

        def _unbind_mousewheel(_):
            self.canvas.unbind_all("<MouseWheel>")
            self.canvas.unbind_all("<Button-4>")
            self.canvas.unbind_all("<Button-5>")

        self.content.bind("<Enter>", _bind_mousewheel)
        self.content.bind("<Leave>", _unbind_mousewheel)

class MainWindow:
    """Ana spektrum analiz penceresi"""
    
    def __init__(self, root):
        """
        Args:
            root: Tkinter pencere nesnesi
        """
        self.root = root
        self.logger = logging.getLogger(__name__)
        self.setup_window()
        

        
        # Veri ve hesaplama nesneleri
        self.data_loader = DataLoader()
        self.data_processor = DataProcessor()
        self.data_processor.data_loader = self.data_loader  # DataProcessor'a data_loader'ı bağla
        self.spectrum_calculator = SpectrumCalculator()
        self.coefficient_calculator = CoefficientCalculator()
        
        # Hesaplama sonuçları
        self.spectrum_data = {}
        
        # âš¡ Harita deÄŸer cache sistemi
        self._map_value_cache = {}
        self._last_calculated_params = None
        
        # Birim ayarları
        self.current_acceleration_unit = 'g'  # Varsayılan birim
        self.current_displacement_unit = 'cm'  # Varsayılan birim
        
        # GUI bileÅŸenleri
        self.input_panel = None
        self.plot_panel = None
        self.data_table = None
        
        # Responsive yönetici
        self.responsive_manager = ResponsiveManager(self.root)
        
        # Keyboard manager
        self.keyboard_manager = KeyboardManager(self.root)
        self._setup_keyboard_handlers()
        
        # Enhanced keyboard manager
        self.enhanced_keyboard_manager = EnhancedKeyboardManager(self.root)
        self._setup_enhanced_keyboard_shortcuts()

        # Arka plan işler için executor
        try:
            self._executor = ThreadPoolExecutor(max_workers=3)
        except Exception as ex:
            self._executor = None
            self.logger.debug(f"Executor başlatılamadı: {ex}")
        
        # Initialize variables
        self.loaded_earthquake_files = []
        self.selected_earthquake_var = tk.StringVar(value="Seçilen: Yok")
        self.processed_earthquake_data = {}  # Processed time series data
        self.paired_ia_var = None
        self.paired_components_var = None
        self.paired_results_frame = None
        self.earthquake_data_processor = DataProcessor()  # Data processor instance
        # Pair Manager
        self.pair_manager = PairManager(lambda: self.loaded_earthquake_files)
        self.earthquake_data_processor.data_loader = self.data_loader  # DataProcessor'a data_loader'ı bağla
        
        # İkonları yükle
        self._load_icons()
        
        # Ortak tasarım parametre modeli (SDS/SD1/TL için tek kaynak)
        try:
            self.design_params = DesignParamsModel.create(master=self.root, sds=0.8, sd1=0.4, tl=6.0)
        except Exception:
            self.design_params = None

        # Arayüzü oluştur
        self.create_interface()
    
    def _tk_dpi(self) -> float:
        """Tk scaling ile eşleşen DPI değerini döndürür (px/point → dpi)."""
        try:
            scaling = float(self.root.tk.call('tk', 'scaling'))  # px/point
            return 72.0 * scaling  # 72 point = 1 inch
        except Exception:
            return 100.0

    def _fit_mpl_to_widget(self, fig, widget, canvas) -> None:
        """Matplotlib figürünü verilen Tk widget boyutlarına sığdırır ve yeniden çizer."""
        try:
            widget.update_idletasks()
            width = max(widget.winfo_width(), 1)
            height = max(widget.winfo_height(), 1)
            dpi = fig.get_dpi() or 100.0
            fig.set_size_inches(width / dpi, height / dpi, forward=True)
            try:
                # Tight layout sırasında çıkan kenar uyarılarını bastır
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=UserWarning)
                    fig.tight_layout()
            except Exception:
                # Eğer kenar boşlukları yetmiyorsa minimal alt boşluk artışı deneyin
                try:
                    fig.subplots_adjust(left=0.08, right=0.99, bottom=0.12, top=0.96)
                except Exception:
                    pass
            canvas.draw_idle()
        except Exception:
            try:
                canvas.draw()
            except Exception:
                pass
    
    def _load_icons(self):
        """Sekme ikonlarını yükler"""        
        # Sağlam yol: proje kökü/icons
        try:
            base = Path(__file__).resolve().parents[2]
            icons_dir = base / "icons"
        except Exception:
            icons_dir = Path("icons")
        
        # Earthquake icon
        try:
            self.earthquake_icon = PhotoImage(file=str(icons_dir / "earthquake_01.png"))
            self.logger.debug(f"İkon başarıyla yüklendi: {icons_dir / 'earthquake_01.png'}")
        except Exception as e:
            self.logger.warning(f"Earthquake ikon yükleme hatası: {e}")
            self.earthquake_icon = None
        try:
            self.upload_icon = PhotoImage(file=str(icons_dir / "upload_02.png"))
            self.logger.debug(f"İkon başarıyla yüklendi: {icons_dir / 'upload_02.png'}")
        except Exception as e:
            self.logger.warning(f"Upload ikon yükleme hatası: {e}")
            self.upload_icon = None
        
        # Table icon
        try:
            self.table_icon = PhotoImage(file=str(icons_dir / "table_01.png"))
            self.logger.debug(f"İkon başarıyla yüklendi: {icons_dir / 'table_01.png'}")
        except Exception as e:
            self.logger.warning(f"Table ikon yükleme hatası: {e}")
            self.table_icon = None
        
        # Spectrum icon
        try:
            self.spectrum_icon = PhotoImage(file=str(icons_dir / "line_graph_01.png"))
            self.logger.debug(f"İkon başarıyla yüklendi: {icons_dir / 'line_graph_01.png'}")
        except Exception as e:
            self.logger.warning(f"Spectrum ikon yükleme hatası: {e}")
            self.spectrum_icon = None
    
    def setup_window(self) -> None:
        """Pencere ayarlarını yapar"""
        self.root.title("TBDY-2018 Deprem Yer Hareketleri")
        self.root.geometry(WINDOW_SIZES['main'])
        self.root.configure(bg=BG_COLOR)
        
        # Maksimizasyon görünürlük sonrası tetiklenecek (MenuWindow tarafından)
        # Ek güvence: pencere ekrana ilk kez map edildiğinde tek seferlik büyüt
        try:
            self.root.bind('<Map>', self._on_first_map, add='+')
        except Exception as e:
            self.logger.debug(f"<Map> olayına bağlanılamadı: {e}")
        
    
    def maximize_window(self) -> None:
        """Pencereyi tam ekran yapar - platform bağımsız"""
        try:
            # Windows için
            if self.root.tk.call('tk', 'windowingsystem') == 'win32':
                self.root.state('zoomed')
            else:
                # Linux/macOS için
                try:
                    self.root.attributes('-zoomed', True)
                except tk.TclError:
                    # Alternatif yöntem
                    self.root.wm_state('zoomed')
        except Exception:
            try:
                # Fallback - ekran boyutuna göre manuel ayarlama
                self.root.update_idletasks()
                width = self.root.winfo_screenwidth()
                height = self.root.winfo_screenheight()
                self.root.geometry(f"{width}x{height}+0+0")
            except Exception as e:
                self.logger.debug(f"Pencere maksimizasyon hatası (göz ardı edildi): {e}")

    def _on_first_map(self, event) -> None:
        """Pencere ilk kez görünür olduğunda (map) maksimizasyonu uygular ve bağlayı kaldırır."""
        try:
            # Tek seferlik çalışsın
            self.root.unbind('<Map>')
        except Exception as e:
            self.logger.debug(f"<Map> olayı unbind başarısız: {e}")
        try:
            # Bazı WM'lerde görünürlüğün tamamen sağlanması için kısa bir gecikme faydalı olabilir
            self.root.after(50, self.maximize_window)
        except Exception as e:
            self.logger.debug(f"after ile maksimizasyon planlanamadı: {e}")
            # DoÄŸrudan dene
            self.maximize_window()

    def _cancel_table_insertion(self):
        """Devam eden artımlı tablo doldurmayı iptal eder."""
        try:
            if getattr(self, '_table_insert_job', None):
                self.root.after_cancel(self._table_insert_job)
            self._table_insert_job = None
        except Exception:
            self._table_insert_job = None
    
    def create_interface(self) -> None:
        """Ana arayüzü oluşturur"""
        import tkinter as tk
        import tkinter.font as tkfont

        # Gizli tab stili (zaten _setup_spectrum_sub_notebook_style'da tanımlı ama
        # farklı isimle bir tane daha oluşturalım)
        style = ttk.Style()
        try:
            style.layout("MainHiddenTab.TNotebook", [
                ("MainHiddenTab.TNotebook.client", {"sticky": "nswe"})
            ])
            style.configure("MainHiddenTab.TNotebook", borderwidth=0)
            style.layout("MainHiddenTab.TNotebook.Tab", [])
            style.configure("MainHiddenTab.TNotebook.Tab", padding=0, borderwidth=0)
        except Exception:
            pass

        # Üst kısım: pill tab bar
        top_bar = ttk.Frame(self.root)
        top_bar.pack(anchor="w", padx=10, pady=(10, 0))

        self._main_tab_buttons = {}

        def _make_main_pill(parent, text, idx, icon=None):
            """Ana sekmeler için pill buton oluşturur"""
            from PIL import Image, ImageDraw, ImageTk
            try:
                fnt = tkfont.Font(family="Poppins", size=10, weight="bold")
            except Exception:
                fnt = tkfont.nametofont("TkDefaultFont").copy()
                fnt.configure(size=10, weight="bold")

            text_w = fnt.measure(text)
            pad_x, pad_y = 24, 8
            icon_space = 24 if icon else 0
            w = text_w + pad_x * 2 + icon_space
            h = fnt.metrics("linespace") + pad_y * 2
            r = 12

            parent_bg = style.lookup("TFrame", "background") or "#F0F0F0"
            cvs = tk.Canvas(parent, width=w, height=h, bg=parent_bg,
                        highlightthickness=0, cursor="hand2")
            cvs._pill_images = {}
            cvs._icon = icon

            def _make_pill_image(bg_hex):
                scale = 2
                sw, sh, sr = w * scale, h * scale, r * scale
                img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=bg_hex)
                img = img.resize((w, h), Image.LANCZOS)
                return img

            def _draw(bg, fg):
                cvs.delete("all")
                key = (bg, fg)
                if key not in cvs._pill_images:
                    pil_img = _make_pill_image(bg)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    cvs._pill_images[key] = tk_img
                else:
                    tk_img = cvs._pill_images[key]
                cvs.create_image(w // 2, h // 2, image=tk_img)
                
                text_x = w // 2 + (icon_space // 2 if icon else 0)
                if icon:
                    cvs.create_image(pad_x, h // 2, image=icon, anchor="w")
                cvs.create_text(text_x, h // 2, text=text, font=fnt, fill=fg)

            _draw("#D4D4D4", "#4B5563")

            def _on_click(e):
                self.notebook.select(idx)
                _refresh_main_tabs()

            cvs.bind("<Button-1>", _on_click)
            self._main_tab_buttons[idx] = (cvs, _draw)
            return cvs

        def _refresh_main_tabs():
            try:
                sel = self.notebook.index("current")
            except Exception:
                sel = 0
            for i, (cvs, draw_fn) in self._main_tab_buttons.items():
                if i == sel:
                    draw_fn("#255BD0", "#FFFFFF")
                else:
                    draw_fn("#D4D4D4", "#4B5563")

        # Pill tab'ları oluştur
        icon0 = self.spectrum_icon if hasattr(self, 'spectrum_icon') and self.spectrum_icon else None
        icon1 = self.earthquake_icon if hasattr(self, 'earthquake_icon') and self.earthquake_icon else None

        pill0 = _make_main_pill(top_bar, "Spektrum Oluşturma", 0, icon0)
        pill0.pack(side='left', padx=(0, 6))

        pill1 = _make_main_pill(top_bar, "Deprem Kayıtları", 1, icon1)
        pill1.pack(side='left', padx=(0, 6))

        # Gizli tab'lı Notebook
        self.notebook = ttk.Notebook(self.root, style="MainHiddenTab.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(6, 10))
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: _refresh_main_tabs())

        # Sekmeleri oluştur
        self.create_spectrum_tab()
        self.create_earthquake_records_tab()

        # İlk tab'ı seçili başlat
        _refresh_main_tabs()

        # Alt kısımda durum çubuğu
        try:
            status_frame = ttk.Frame(self.root)
            status_frame.pack(fill="x", side="bottom")
            self.status_var = tk.StringVar(value="Hazır")
            self.status_label = ttk.Label(status_frame, textvariable=self.status_var, font=('Poppins', 9))
            self.status_label.pack(anchor='w', padx=8, pady=2)
        except Exception:
            self.status_var = None
            self.status_label = None
    
    def _setup_spectrum_sub_notebook_style(self):
        """Notebook tab header'larını gizleyen stili oluşturur"""
        try:
            style = ttk.Style()
            # Notebook tab alanını tamamen gizle
            style.layout("HiddenTab.TNotebook", [
                ("HiddenTab.TNotebook.client", {"sticky": "nswe"})
            ])
            style.configure("HiddenTab.TNotebook", borderwidth=0)
            style.layout("HiddenTab.TNotebook.Tab", [])
            style.configure("HiddenTab.TNotebook.Tab", padding=0, borderwidth=0)
        except Exception:
            pass

    def create_spectrum_tab(self) -> None:
        """Spektrum analiz sekmesini oluşturur"""
        self.spektrum_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.spektrum_frame, text="Spektrum Oluşturma")

        
        # Sol panel – kaydırılabilir kapsayıcı (sabit genişlik)
        left_holder = ttk.Frame(self.spektrum_frame)
        left_holder.pack(side="left", fill="y", padx=10, pady=10)
        try:
            from ..config.constants import SIDEBAR_WIDTH_SPECTRUM as _TAB_WIDTH
        except Exception:
            try:
                from ..config.constants import APP_SIDEBAR_WIDTH as _TAB_WIDTH
            except Exception:
                _TAB_WIDTH = 220
        _fixed_left_width = int(_TAB_WIDTH)
        left_holder.configure(width=_fixed_left_width)
        left_holder.pack_propagate(False)

        self.input_scroll = ScrollableFrame(left_holder)
        self.input_scroll.pack(fill="y", expand=True)
        try:
            # Canvas başlangıç genişliğini de eşitle
            self.input_scroll.canvas.configure(width=_fixed_left_width)
        except Exception:
            pass

        # InputPanel'in ebeveyni artık scrollable içerik
        self.input_frame = self.input_scroll.content
        self.input_frame.configure(padding=15)

        # Sağ panel - içerik alanı (alt sekmeler barındırır)
        self.plot_frame = ttk.Frame(self.spektrum_frame, padding="10")
        self.plot_frame.pack(side="right", fill="both", expand=True)

        # Sağ panel içinde alt-sekmeler – gizli tab'lı Notebook + custom pill tab bar
        self._setup_spectrum_sub_notebook_style()

        # Custom pill tab bar
        import tkinter as tk
        import tkinter.font as tkfont

        tab_bar = ttk.Frame(self.plot_frame)
        tab_bar.pack(anchor="w", pady=(0, 6))

        self._spectrum_tab_buttons = {}

        def _make_pill_tab(parent, text, idx):
            """PIL ile anti-aliased yuvarlak köşeli pill buton oluşturur"""
            from PIL import Image, ImageDraw, ImageTk, ImageFont
            try:
                fnt = tkfont.Font(family="Poppins", size=10, weight="bold")
            except Exception:
                fnt = tkfont.nametofont("TkDefaultFont").copy()
                fnt.configure(size=10, weight="bold")
            text_w = fnt.measure(text)
            pad_x, pad_y = 24, 8
            w = text_w + pad_x * 2
            h = fnt.metrics("linespace") + pad_y * 2
            r = 12  # köşe yarıçapı

            parent_bg = ttk.Style().lookup("TFrame", "background") or "#F0F0F0"
            cvs = tk.Canvas(parent, width=w, height=h, bg=parent_bg,
                           highlightthickness=0, cursor="hand2")

            # PhotoImage referanslarını sakla (garbage collection engellenir)
            cvs._pill_images = {}

            def _make_pill_image(bg_hex, fg_hex):
                """PIL ile anti-aliased pill görsel oluşturur (2x supersampling)"""
                scale = 2  # supersampling faktörü
                sw, sh, sr = w * scale, h * scale, r * scale
                img = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.rounded_rectangle(
                    [0, 0, sw - 1, sh - 1],
                    radius=sr,
                    fill=bg_hex
                )
                # Küçült (anti-aliasing efekti)
                img = img.resize((w, h), Image.LANCZOS)
                return img

            def _draw(bg, fg):
                cvs.delete("all")
                key = (bg, fg)
                if key not in cvs._pill_images:
                    pil_img = _make_pill_image(bg, fg)
                    tk_img = ImageTk.PhotoImage(pil_img)
                    cvs._pill_images[key] = tk_img
                else:
                    tk_img = cvs._pill_images[key]
                cvs.create_image(w // 2, h // 2, image=tk_img)
                cvs.create_text(w // 2, h // 2, text=text, font=fnt, fill=fg)

            _draw("#F3F4F6", "#4B5563")

            def _on_click(e):
                self.spectrum_sub_notebook.select(idx)
                _refresh_all_tabs()

            cvs.bind("<Button-1>", _on_click)
            self._spectrum_tab_buttons[idx] = (cvs, _draw)
            return cvs

        def _refresh_all_tabs():
            try:
                sel = self.spectrum_sub_notebook.index("current")
            except Exception:
                sel = 0
            for i, (cvs, draw_fn) in self._spectrum_tab_buttons.items():
                if i == sel:
                    draw_fn("#255BD0", "#FFFFFF")
                else:
                    draw_fn("#D4D4D4", "#4B5563")

        tab_texts = ["Grafik", "Spektrum Veri Tablosu"]
        for i, txt in enumerate(tab_texts):
            pill = _make_pill_tab(tab_bar, txt, i)
            pill.pack(side='left', padx=(0, 6))

        # Notebook (tab'ları gizli)
        self.spectrum_sub_notebook = ttk.Notebook(self.plot_frame, style="HiddenTab.TNotebook")
        self.spectrum_sub_notebook.pack(fill="both", expand=True)

        # Notebook tab değiştiğinde pill'leri güncelle
        self.spectrum_sub_notebook.bind("<<NotebookTabChanged>>", lambda e: _refresh_all_tabs())

        # 1) Grafik sekmesi
        self.spectrum_graph_tab = ttk.Frame(self.spectrum_sub_notebook)
        self.spectrum_sub_notebook.add(self.spectrum_graph_tab, text="Grafik")

        # 2) Spektrum Veri Tablosu sekmesi
        self.spectrum_data_tab = ttk.Frame(self.spectrum_sub_notebook)
        self.spectrum_sub_notebook.add(self.spectrum_data_tab, text="Spektrum Veri Tablosu")

        # İlk tab'ı seçili olarak başlat
        _refresh_all_tabs()

        # Modüler bileşenleri oluştur
        self.input_panel = InputPanel(self.input_frame, self._on_data_loaded, design_params_model=getattr(self, 'design_params', None))
        self.input_panel.bind_load_command(self.load_data_file)
        self.input_panel.bind_calculation_command(self.run_calculation_and_plot)
        self.input_panel.bind_map_command(self.show_location_on_map)
        self.input_panel.bind_save_command(self.save_plot)
        self.input_panel.bind_report_command(self.generate_pdf_report)
        self.input_panel.bind_peer_export_command(self.export_peer_user_defined_spectrum)
        self.input_panel.bind_unit_change_callback(self._on_unit_change)  # Birim deÄŸiÅŸikliÄŸi callback'i
        
        # Kısayollar yardımı için küçük bir link/ikon
        try:
            shortcuts_frame = ttk.Frame(self.input_frame)
            shortcuts_frame.pack(fill="x", pady=(4, 0))
            help_link = ttk.Label(shortcuts_frame, text="? Kısayollar", foreground="#1E88E5", cursor="hand2")
            help_link.pack(anchor="e")
            def _open_shortcuts():
                try:
                    if hasattr(self.enhanced_keyboard_manager, 'show_shortcuts_help'):
                        self.enhanced_keyboard_manager.show_shortcuts_help()
                    elif hasattr(self.enhanced_keyboard_manager, 'show_shortcuts_dialog'):
                        self.enhanced_keyboard_manager.show_shortcuts_dialog()
                    elif hasattr(self.keyboard_manager, 'show_shortcuts'):
                        self.keyboard_manager.show_shortcuts()
                except Exception as ex:
                    self.logger.debug(f"Kısayollar penceresi açılamadı: {ex}")
            help_link.bind("<Button-1>", lambda e: _open_shortcuts())
        except Exception as ex:
            self.logger.debug(f"Kısayollar linki oluşturulamadı: {ex}")
        # Grafik sekmesinde grafik paneli
        self.plot_panel = PlotPanel(self.spectrum_graph_tab)

        # Veri sekmesinde veri tablosu
        self.data_table = DataTable(self.spectrum_data_tab)
        
        # Responsive yöneticiye kaydet
        self.responsive_manager.register_component(self.input_panel, 'input_panel')
        self.responsive_manager.register_component(self.plot_panel, 'plot_panel')
        self.responsive_manager.register_component(self.data_table, 'data_table')
        
        # Komutları bağla
        self.bind_input_panel_commands()
    
    
    def create_earthquake_records_tab(self) -> None:
        """Deprem kayıtları sekmesini oluşturur"""
        earthquake_tab = ttk.Frame(self.notebook)
        self.notebook.add(earthquake_tab, text="Deprem Kayıtları")

        
        # Sol panel - Dosya yükleme ve liste (sabit genişlik)
        left_panel = ttk.Frame(earthquake_tab)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        try:
            from ..config.constants import SIDEBAR_WIDTH_RECORDS as _REC_TAB_WIDTH
        except Exception:
            try:
                from ..config.constants import APP_SIDEBAR_WIDTH as _REC_TAB_WIDTH
            except Exception:
                _REC_TAB_WIDTH = 220
        left_panel.config(width=int(_REC_TAB_WIDTH))
        try:
            left_panel.pack_propagate(False)
        except Exception:
            pass
        
        # Deprem kaydı yükleme bölümü
        # file_frame = ttk.LabelFrame(left_panel, text="Deprem Kaydı Dosyası", padding=10)
        # file_frame.pack(fill="x", pady=(0, 10))
        
        # # Çoklu dosya yükleme butonu
        # self.load_earthquake_records_button = ttk.Button(
        #     file_frame, 
        #     text="📁 Deprem Kayıtları Yükle",
        #     command=self.load_multiple_earthquake_records
        # )
        # self.load_earthquake_records_button.pack(pady=5)
        
        # # Durum etiketi
        # self.earthquake_file_status_var = tk.StringVar(value="Henüz dosya yüklenmedi")
        # self.earthquake_file_status_label = ttk.Label(file_frame, textvariable=self.earthquake_file_status_var, 
        #                                              foreground="gray", font=('Segoe UI', 9))
        # self.earthquake_file_status_label.pack(pady=5)
        
        # Deprem kaydı yükleme bölümü (TASARIM REVİZE + RoundedButton)


        # ttk içinde modern görünüm için tk container kullanıyoruz
        FILE_BG = "#FFFFFF"
        BORDER = "#D6DBE3"
        TEXT_GRAY = "#7A8699"

        file_wrap = tk.Frame(left_panel, bg=FILE_BG)
        file_wrap.pack(fill="x", pady=(0, 10))

        # Başlık (LabelFrame başlığı yerine)
        title_font = tkfont.nametofont("TkDefaultFont").copy()
        title_font.configure(size=int(title_font.cget("size")) + 1, weight="bold")

        tk.Label(
            file_wrap,
            text="Deprem Kaydı Dosyası",
            bg=FILE_BG,
            fg="#8A94A6",     # açık gri başlık (2. görsel gibi)
            font=title_font
        ).pack(anchor="w", padx=2, pady=(0, 6))

        # İç beyaz alan (eski inner yerine)
        inner = tk.Frame(file_wrap, bg=FILE_BG)
        inner.pack(fill="x")

        # dashed kutu alanı
        dashed = tk.Canvas(
            inner,
            height=120,
            bg=FILE_BG,
            highlightthickness=0,
            bd=0
        )
        dashed.pack(fill="x", padx=2, pady=2)

        def _draw_dashed_box(e=None):
            dashed.delete("border")
            w = dashed.winfo_width()
            h = dashed.winfo_height()
            if w <= 5 or h <= 5:
                return
            # Basit dashed rectangle (rounded istersen ayrıca ekleriz)
            dashed.create_rectangle(
                4, 4, w - 4, h - 4,
                outline=BORDER,
                width=2,
                dash=(6, 4),
                tags="border"
            )

        dashed.bind("<Configure>", _draw_dashed_box)

        # Butonu ortalamak için container (Canvas içine window olarak)
        btn_host = tk.Frame(dashed, bg=FILE_BG)
        status_host = tk.Frame(dashed, bg=FILE_BG)

        # Canvas üzerine yerleştir
        btn_win = dashed.create_window(0, 0, window=btn_host, anchor="n")
        status_win = dashed.create_window(0, 0, window=status_host, anchor="n")

        def _place_content(e=None):
            w = dashed.winfo_width()
            h = dashed.winfo_height()
            if w <= 5 or h <= 5:
                return

            pad = 10

            # window'ları ortala
            dashed.coords(btn_win, w // 2, 22)
            dashed.coords(status_win, w // 2, 78)

            # content genişliği (2. görsel gibi geniş)
            content_w = max(160, int((w - 2 * pad) * 0.88))

            # window genişliğini set et (kritik: kırpılmayı engeller)
            dashed.itemconfigure(btn_win, width=content_w)
            dashed.itemconfigure(status_win, width=content_w)

            # RoundedButton kendi Canvas olduğu için width ver
            try:
                self.load_earthquake_records_button.configure(width=content_w)
            except Exception:
                pass

        dashed.bind("<Configure>", _place_content, add="+")
        _draw_dashed_box()
        _place_content()
        
        base_font = tkfont.nametofont("TkDefaultFont")
        btn_font = base_font.copy()

        # +2 istersen 2, +1 istersen 1 yap
        btn_font.configure(size=int(base_font.cget("size")) + 2)

        # ✅ RoundedButton burada kullanılıyor
        self.load_earthquake_records_button = RoundedButton(
            btn_host,
            text="Deprem Kayıtlarını Yükle",
            on_click=self.load_multiple_earthquake_records,
            height=52,
            radius=12,
            btn_bg="#2F6FED",
            hover_bg="#255BD0",
            fg="white",
            canvas_bg=FILE_BG,
            image=self.upload_icon,
            font=btn_font 
        )
        self.load_earthquake_records_button.pack(fill="x")

        # Durum etiketi
        self.earthquake_file_status_var = tk.StringVar(value="Henüz dosya yüklenmedi")
        self.earthquake_file_status_label = tk.Label(
            status_host,
            textvariable=self.earthquake_file_status_var,
            bg=FILE_BG,
            fg=TEXT_GRAY,
            font=("Segoe UI", 10)
        )
        self.earthquake_file_status_label.pack()
        
        # Yüklenen depremler listesi
        list_frame = ttk.LabelFrame(left_panel, text="Yüklenen Depremler", padding=10)
        list_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Listbox ve scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill="both", expand=True)
        
        self.earthquake_listbox = tk.Listbox(
            listbox_frame,
            height=10,
            exportselection=False  # keep selection when other widgets (e.g. combos) get focus
        )
        self.earthquake_listbox.pack(side="left", fill="both", expand=True)
        self.earthquake_listbox.bind('<<ListboxSelect>>', self._on_earthquake_select)
        
        # Sağ tık menüsü (platform uyumlu)
        self.earthquake_listbox.bind('<Button-3>', self._show_earthquake_context_menu)          # Windows/Linux
        self.earthquake_listbox.bind('<Button-2>', self._show_earthquake_context_menu)          # macOS
        self.earthquake_listbox.bind('<Control-Button-1>', self._show_earthquake_context_menu)  # macOS Ctrl+Click
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.earthquake_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.earthquake_listbox.config(yscrollcommand=scrollbar.set)
        
        # Seçili deprem durumu
        ttk.Label(list_frame, textvariable=self.selected_earthquake_var, 
                 font=('Segoe UI', 9, 'bold')).pack(pady=(10, 0))
        
        # Deprem kaydı istatistikleri paneli (yakınlaştırılmış boşluklar)
        stats_frame = ttk.LabelFrame(left_panel, text="Seçili Deprem İstatistikleri", padding=6)
        stats_frame.pack(fill="both", expand=True, pady=(4, 0))
        
        # İstatistik panelini buraya taşı
        self.stats_panel = StatsPanel(stats_frame, main_window=self)
        
        # SaÄŸ panel - Alt sekmeler
        right_panel = ttk.Frame(earthquake_tab)
        right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        
        # Alt sekmeler için notebook oluştur
        self.earthquake_sub_notebook = ttk.Notebook(right_panel)
        self.earthquake_sub_notebook.pack(fill="both", expand=True)
        
        # Time Series sekmesi (mevcut grafikler)
        self._create_time_series_tab()

        # Deprem Kaydı Ölçekleme sekmesi
        self._create_basic_scaling_tab()

    def _create_time_series_tab(self):
        """Time Series alt sekmesini oluÅŸturur"""
        # Standart Time Series sekmesi
        time_series_tab = ttk.Frame(self.earthquake_sub_notebook)
        self.earthquake_sub_notebook.add(time_series_tab, text="Zaman Serisi")
        
        self._create_time_series_plots(time_series_tab)

        # Kayıt Grafikleri sekmesi (alt sekmelerle)
        interactive_tab = ttk.Frame(self.earthquake_sub_notebook)
        self.earthquake_sub_notebook.add(interactive_tab, text="Kayıt Grafikleri")

        # Alt-notebook oluÅŸtur
        self.interactive_notebook = ttk.Notebook(interactive_tab)
        self.interactive_notebook.pack(fill="both", expand=True)

        # Arias ÅŞiddeti alt-sekmesi (Süre)
        arias_tab = ttk.Frame(self.interactive_notebook)
        self.interactive_notebook.add(arias_tab, text="Süre")

        # Arias ÅŞiddeti (%) alt-sekmesi (grafik + tablo)
        arias_percent_tab = ttk.Frame(self.interactive_notebook)
        self.interactive_notebook.add(arias_percent_tab, text="Arias ÅŞiddeti")
        self._create_arias_percent_tab(arias_percent_tab)
        # Arias sekmesi: yalnız grafik alanı (kapsayıcı → canvas)

        # Ana konteyner: solda bilgi paneli, sağda grafik alanı
        arias_container = ttk.Frame(arias_tab)
        arias_container.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        # Sol panel üst: Hesaplama Parametreleri
        params_frame = ttk.LabelFrame(arias_container, text="Hesaplama Parametreleri", padding=8)
        params_frame.pack(side="left", fill="y", padx=(0, 8))

        # Süre Tipi seçimi (Radiobuttons)
        ttk.Label(params_frame, text="Süre Tipi:").pack(anchor="w")
        self.var_duration_type = tk.StringVar(value="Significant Duration")
        for _text in ("Bracketed Duration", "Uniform Duration", "Significant Duration", "Effective Duration"):
            _rb = ttk.Radiobutton(
                params_frame,
                text=_text,
                variable=self.var_duration_type,
                value=_text,
                command=self._set_duration_type,
            )
            _rb.pack(anchor="w", pady=(2, 0))

        # Duration parametre alanları
        try:
            sep = ttk.Separator(params_frame, orient='horizontal')
            sep.pack(fill='x', pady=(6, 6))
        except Exception:
            pass

        # Bracketed & Uniform: a0 eşiği (g) — bu alanı "Hesapla" üstündeki divider'ın hemen üzerine yerleştireceğiz
        # Not: Frame ve giriş bileşenleri divider eklenmeden az önce oluşturulacak

        # Significant: baÅŸlangıç/bitiÅŸ yüzdeleri (% Arias ÅŞiddeti)
        self.sig_frame = ttk.Frame(params_frame)
        self.sig_start_percent_var = tk.StringVar(value="5.0")
        self.sig_end_percent_var = tk.StringVar(value="95.0")
        ttk.Label(self.sig_frame, text="Başlangıç (%):").pack(anchor='w')
        ttk.Entry(self.sig_frame, textvariable=self.sig_start_percent_var, width=8).pack(anchor='w', pady=(2,0))
        ttk.Label(self.sig_frame, text="BitiÅŸ (%):").pack(anchor='w', pady=(6,0))
        ttk.Entry(self.sig_frame, textvariable=self.sig_end_percent_var, width=8).pack(anchor='w', pady=(2,0))
        ttk.Label(self.sig_frame, text="% Arias ÅŞiddeti").pack(anchor='w', pady=(4,0))

        # Effective: mutlak AI (m/s)
        self.eff_frame = ttk.Frame(params_frame)
        self.eff_start_ai_var = tk.StringVar(value="0.08")
        self.eff_end_ai_var = tk.StringVar(value="1.48")
        ttk.Label(self.eff_frame, text="Başlangıç AI (m/s):").pack(anchor='w')
        ttk.Entry(self.eff_frame, textvariable=self.eff_start_ai_var, width=12).pack(anchor='w', pady=(2,0))
        ttk.Label(self.eff_frame, text="BitiÅŸ AI (m/s):").pack(anchor='w', pady=(6,0))
        ttk.Entry(self.eff_frame, textvariable=self.eff_end_ai_var, width=12).pack(anchor='w', pady=(2,0))

        # A0 alanı ve hemen ardından divider (başlangıçta dinamik; pack işlemi görünürlük fonksiyonunda)
        # a0 alanı (divider'ın üstünde)
        self.brk_uni_frame = ttk.Frame(params_frame)
        self.uniform_a0_label = ttk.Label(self.brk_uni_frame, text="İvme Eşiği, a₀ (g):")
        self.uniform_a0_label.pack(anchor='w')
        self.uniform_a0_var = tk.StringVar(value="0.01")
        ent_a0 = ttk.Entry(self.brk_uni_frame, textvariable=self.uniform_a0_var, width=12)
        ent_a0.pack(anchor='w', pady=(2,0))
        try:
            ent_a0.bind('<Return>', lambda e: self._refresh_arias_plot())
            ent_a0.bind('<FocusOut>', lambda e: self._refresh_arias_plot())
        except Exception:
            pass

        self._a0_divider = ttk.Separator(params_frame, orient='horizontal')
        # pack işlemi _update_duration_param_visibility içinde yapılacak
        try:
            self.arias_compute_button = ttk.Button(params_frame, text="Hesapla", command=self._on_compute_a_squared)
            # pack işlemi alt divider'dan sonra yapılacak
        except Exception:
            pass

        # Hesapla düğmesinin altına divider ve süre sonucu
        try:
            self._compute_result_divider = ttk.Separator(params_frame, orient='horizontal')
            self._compute_result_divider.pack(fill='x', pady=(6, 6))
        except Exception:
            pass
        try:
            # Alt blok: Hesapla butonu ve Hesaplanan Süre her zaman en altta
            self.arias_compute_button.pack(anchor='w', pady=(8, 0))
            ttk.Label(params_frame, text="Hesaplanan Süre:").pack(anchor='w', pady=(8, 0))
            self.duration_result_var = tk.StringVar(value="")
            self.duration_result_entry = ttk.Entry(params_frame, textvariable=self.duration_result_var, width=36, state='readonly')
            self.duration_result_entry.pack(anchor='w')
            # Bracketed Duration açıklaması için alt divider ve metin (başlangıçta gizli)
            self._bd_info_divider = ttk.Separator(params_frame, orient="horizontal")
            self.bracketed_info_label = ttk.Label(
                params_frame,
                text=(
                    "Db (bracketed duration) olarak adlandırılan süre, yer ivmesinin seçilmiş bir eşik değeri (a₀) ilk kez aştığı an ile son kez aştığı an arasında geçen toplam zamandır."
                    " Bu tanımın sorunu, depremin asıl \"etkili\" bölümünün ayrıntılarını dikkate almaması; yalnızca baştaki ilk ve sondaki son eşik aşımalarını saymasıdır."
                    " Bu yüzden, ana sarsıntı geçtikten sonra kaydın sonunda eşiği kısa süreli de olsa aşan küçük alt olaylar varsa, hesaplanan süre gereğinden uzun çıkabilir."
                    " Ayrıca eşik değeri ne kadar düşük seçilirse, bu süre o kadar değişken olur; eşiği biraz düşürmek bile hesaplanan süreyi belirgin biçimde uzatabilir."
                ),
                wraplength=340,
                justify="left"
            )
            # Uniform Duration açıklaması (başlangıçta gizli)
            self._ud_info_divider = ttk.Separator(params_frame, orient='horizontal')
            self.uniform_info_label = ttk.Label(
                params_frame,
                text=(
                    "Du (uniform duration) olarak adlandırılan süre, ivmenin belirlenen bir eşik değeri (a₀) üzerinde kaldığı tüm zaman aralıklarının toplamıdır."
                    " Yani, eşiğin ilk ve son aşıldığı anlar arasındaki tek ve kesintisiz bir süreyi ölçmek yerine, ivmenin bu eşiği geçtiği her bir kısa bölümün süreleri toplanarak hesaplanır."
                ),
                wraplength=340,
                justify='left'
            )
            # Significant Duration açıklaması (başlangıçta gizli)
            self._sd_info_divider = ttk.Separator(params_frame, orient='horizontal')
            self.significant_info_label = ttk.Label(
                params_frame,
                text=(
                    "Ds (significant duration), kayıttaki enerji birikimine göre tanımlanan süredir. Buradaki enerji, yer hareketinin ivme zaman serisinin karesinin zamana göre integraliyle temsil edilir."
                    " Kısaca, depremin enerjisinin büyük kısmının biriktiği zamanı hedefler; böylece tek tek eşik aşımlarına bakmak yerine toplam enerjiye odaklanır ve sarsıntının etkili bölümünü tanımlamaya çalışır."
                ),
                wraplength=340,
                justify='left'
            )
            # Effective Duration açıklaması (başlangıçta gizli)
            self._ed_info_divider = ttk.Separator(params_frame, orient='horizontal')
            self.effective_info_label = ttk.Label(
                params_frame,
                text=(
                    "Effective duration (De), kümülatif Arias şiddetinin mutlak iki eşik değeri arasında geçen süre olarak tanımlanır."
                ),
                wraplength=340,
                justify='left'
            )
        except Exception:
            pass

        # Başlangıçta parametre görünürlüğünü ayarla
        try:
            self._update_duration_param_visibility()
        except Exception:
            pass

        # Sol bilgi paneli (kaldırıldı)

        # Yalnız grafiğe ayrılmış kapsayıcı frame (sağ)
        arias_plot_frame = ttk.Frame(arias_container)
        arias_plot_frame.pack(side="right", fill="both", expand=True)

        # Figure: tight_layout çağrısını _fit_mpl_to_widget içinde yapacağız (erken uyarıyı önlemek için)
        # Not: constrained_layout kullanılmaz, tek mekanik tight_layout
        self.arias_figure = Figure(figsize=(8, 5), dpi=self._tk_dpi())
        self.arias_ax = self.arias_figure.add_subplot(111)
        self.arias_ax.set_xlabel("Zaman (s)", fontsize=9)
        self.arias_ax.set_ylabel("Arias ÅŞiddeti (m/s)", fontsize=9)
        self.arias_ax.grid(True, linestyle='--', alpha=0.3)
        self.arias_ax.tick_params(labelsize=8)

        # Canvas'ın master'ı kapsayıcı frame
        self.arias_canvas = FigureCanvasTkAgg(self.arias_figure, master=arias_plot_frame)
        arias_canvas_widget = self.arias_canvas.get_tk_widget()
        # Tk default kenarlık/çıkıntıları kaldır
        try:
            arias_canvas_widget.configure(highlightthickness=0, borderwidth=0, bg='white')
        except Exception:
            pass
        # Canvas'ı kapsayıcı içine pack ile yerleştir
        arias_canvas_widget.pack(side="top", fill="both", expand=True)

        # Widget görünür olduğunda ilk sığdırmayı yap (Map + after_idle)
        def _arias_initial_layout_fix():
            try:
                self._fit_mpl_to_widget(self.arias_figure, arias_canvas_widget, self.arias_canvas)
            except Exception:
                pass

        try:
            arias_canvas_widget.bind('<Map>', lambda e: _arias_initial_layout_fix(), add='+')
        except Exception:
            pass
        try:
            self.root.after_idle(_arias_initial_layout_fix)
        except Exception:
            pass

        # Yeniden boyutlanmada sığdır: kapsayıcı frame ve canvas widget
        try:
            arias_plot_frame.bind('<Configure>', lambda e: self._fit_mpl_to_widget(self.arias_figure, arias_canvas_widget, self.arias_canvas), add='+')
        except Exception:
            pass
        try:
            arias_canvas_widget.bind('<Configure>', lambda e: self._fit_mpl_to_widget(self.arias_figure, arias_canvas_widget, self.arias_canvas), add='+')
        except Exception:
            pass

        # Sekme ilk görünür olduğunda güvence: Notebook sekme değişiminde sığdır
        try:
            self.interactive_notebook.bind('<<NotebookTabChanged>>',
                                           lambda e: (self._fit_mpl_to_widget(self.arias_figure, arias_canvas_widget, self.arias_canvas)
                                                      if self.interactive_notebook.select() == str(arias_tab) else None),
                                           add='+')
        except Exception:
            pass

        # Canvas widget referansını sakla
        self.arias_canvas_widget = arias_canvas_widget
        
        # tight_layout sayesinde otomatik yerleşim sağlanıyor
        # --------------------------------------------------------------------------
        
        # Elastic Response Spectrum sekmesi
        self._create_ers_tab()

    def _create_ers_tab(self):
        """Elastic Response Spectrum alt sekmesini oluÅŸturur"""
        ers_main_tab = ttk.Frame(self.earthquake_sub_notebook)
        self.earthquake_sub_notebook.add(ers_main_tab, text="Tepki Spektrumu")
        
        # ERS için alt-notebook oluştur
        self.ers_notebook = ttk.Notebook(ers_main_tab)
        self.ers_notebook.pack(fill="both", expand=True)
        
        # Grafik sekmesi
        ers_graph_tab = ttk.Frame(self.ers_notebook)
        self.ers_notebook.add(ers_graph_tab, text="Pseudo Spectrum")
        
        # ERS panelini oluÅŸtur (grafik sekmesinde)
        self.ers_panel = ERSPanel(ers_graph_tab, spectrum_mode="pseudo")
        
        # Ana window referansını ver
        self.ers_panel.set_main_window(self)

        # Gerçek spektrum sekmesi
        ers_real_tab = ttk.Frame(self.ers_notebook)
        self.ers_notebook.add(ers_real_tab, text="Gerçek Tepki Spektrumu")
        self.real_ers_panel = ERSPanel(ers_real_tab, spectrum_mode="real")
        self.real_ers_panel.set_main_window(self)
        
        # Sonuçlar sekmeleri (Pseudo ve Gerçek ayrı ayrı)
        from ..gui.components.ers_results_panel import ERSResultsPanel
        ers_pseudo_results_tab = ttk.Frame(self.ers_notebook)
        self.ers_notebook.add(ers_pseudo_results_tab, text="Pseudo Sonuçları")
        self.ers_pseudo_results_panel = ERSResultsPanel(ers_pseudo_results_tab)
        
        ers_real_results_tab = ttk.Frame(self.ers_notebook)
        self.ers_notebook.add(ers_real_results_tab, text="Gerçek Sonuçları")
        self.ers_real_results_panel = ERSResultsPanel(ers_real_results_tab)
        
        # ERS panellerini ilgili sonuç panellerine bağla
        self.ers_panel.set_results_panel(self.ers_pseudo_results_panel)
        self.real_ers_panel.set_results_panel(self.ers_real_results_panel)
        
        # Responsive yöneticiye kaydet
        if hasattr(self, 'responsive_manager'):
            self.responsive_manager.register_component(self.ers_panel, 'ers_panel')
            self.responsive_manager.register_component(self.real_ers_panel, 'real_ers_panel')
            self.responsive_manager.register_component(self.ers_pseudo_results_panel, 'ers_results_panel_pseudo')
            self.responsive_manager.register_component(self.ers_real_results_panel, 'ers_results_panel_real')

    def _create_arias_percent_tab(self, parent):
        """Arias ÅŞiddeti (%) - Zaman grafiÄŸi ve tablo sekmesi"""
        # PanedWindow ile iki bölmeli, yeniden boyutlandırılabilir yapı
        container = ttk.PanedWindow(parent, orient='horizontal')
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # Sol: tablo (paned child)
        table_frame = ttk.Frame(container)
        container.add(table_frame, weight=1)

        controls_frame = ttk.Frame(table_frame)
        controls_frame.pack(fill="x", padx=0, pady=(0, 6))

        def _open_pair_dialog():
            panel = getattr(self, "stats_panel", None)
            if panel is None:
                messagebox.showerror("Hata", "İstatistik paneli hazır değil.", parent=self.root)
                return
            try:
                panel.open_pair_selection_dialog()
            except Exception as exc:
                try:
                    self.logger.exception("Deprem çifti diyalogu açılamadı: %s", exc)
                except Exception:
                    pass
                messagebox.showerror("Hata", f"Deprem çifti diyalogu açılamadı:\n{exc}", parent=self.root)

        ttk.Button(
            controls_frame,
            text="Deprem Çifti Belirle",
            command=_open_pair_dialog
        ).pack(anchor="w")

        self.paired_ia_var = tk.StringVar(value="")
        self.paired_components_var = tk.StringVar(value="")
        self.paired_results_frame = ttk.Frame(controls_frame, padding=(0, 4))
        try:
            self.paired_results_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass

        ttk.Label(
            self.paired_results_frame,
            text="Toplam Yatay Arias ÅŞiddeti (m/s):"
        ).grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(
            self.paired_results_frame,
            textvariable=self.paired_ia_var,
            state="readonly",
            width=28
        ).grid(row=0, column=1, padx=5, pady=2, sticky="w")

        ttk.Label(
            self.paired_results_frame,
            text="Seçilen Bileşenler:"
        ).grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(
            self.paired_results_frame,
            textvariable=self.paired_components_var,
            state="readonly",
            width=28
        ).grid(row=1, column=1, padx=5, pady=2, sticky="w")

        try:
            self.paired_results_frame.pack_forget()
        except Exception:
            pass

        table_body = ttk.Frame(table_frame)
        table_body.pack(fill="both", expand=True)

        columns = ("time", "acc", "ia", "ia_pct")
        self.arias_table = ttk.Treeview(table_body, columns=columns, show="headings", height=20)
        self.arias_table.heading("time", text="Zaman (s)")
        self.arias_table.heading("acc", text="İvme (g)")
        self.arias_table.heading("ia", text="Arias ÅŞiddeti (m/s)")
        self.arias_table.heading("ia_pct", text="Arias ÅŞiddeti (%)")
        # Sütun içeriklerini ortala
        self.arias_table.column("time", width=90, anchor="center")
        self.arias_table.column("acc", width=90, anchor="center")
        self.arias_table.column("ia", width=120, anchor="center")
        self.arias_table.column("ia_pct", width=120, anchor="center")
        scrollbar = ttk.Scrollbar(table_body, orient="vertical", command=self.arias_table.yview)
        self.arias_table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.arias_table.pack(side="left", fill="both", expand=True)

        # SaÄŸ: grafik (paned child)
        plot_frame = ttk.Frame(container)
        container.add(plot_frame, weight=2)

        plot_paned = ttk.PanedWindow(plot_frame, orient='vertical')
        plot_paned.pack(fill="both", expand=True)

        pct_graph_frame = ttk.Frame(plot_paned)
        ms_graph_frame = ttk.Frame(plot_paned)
        plot_paned.add(pct_graph_frame, weight=1)
        plot_paned.add(ms_graph_frame, weight=1)

        self.arias_pct_figure = Figure(figsize=(6, 3), dpi=self._tk_dpi())
        self.arias_pct_ax = self.arias_pct_figure.add_subplot(111)
        self.arias_pct_ax.set_xlabel("Zaman (s)", fontsize=9)
        self.arias_pct_ax.set_ylabel("Arias ÅŞiddeti (%)", fontsize=9)
        self.arias_pct_ax.grid(True, linestyle='--', alpha=0.3)

        self.arias_pct_canvas = FigureCanvasTkAgg(self.arias_pct_figure, master=pct_graph_frame)
        pct_canvas_widget = self.arias_pct_canvas.get_tk_widget()
        pct_canvas_widget.pack(fill="both", expand=True)

        self.arias_ms_figure = Figure(figsize=(6, 3), dpi=self._tk_dpi())
        self.arias_ms_ax = self.arias_ms_figure.add_subplot(111)
        self.arias_ms_ax.set_xlabel("Zaman (s)", fontsize=9)
        self.arias_ms_ax.set_ylabel("Arias ÅŞiddeti (m/s)", fontsize=9)
        self.arias_ms_ax.grid(True, linestyle='--', alpha=0.3)

        self.arias_ms_canvas = FigureCanvasTkAgg(self.arias_ms_figure, master=ms_graph_frame)
        ms_canvas_widget = self.arias_ms_canvas.get_tk_widget()
        ms_canvas_widget.pack(fill="both", expand=True)

        # Grafikleri çerçevelerine göre otomatik sığdır
        def _bind_fit(targets, figure, widget, canvas):
            def _fit(event=None):
                try:
                    self._fit_mpl_to_widget(figure, widget, canvas)
                except Exception:
                    pass
            for tgt in targets:
                try:
                    tgt.bind('<Map>', _fit, add='+')
                    tgt.bind('<Configure>', _fit, add='+')
                except Exception:
                    pass

        _bind_fit((pct_canvas_widget, pct_graph_frame), self.arias_pct_figure, pct_canvas_widget, self.arias_pct_canvas)
        _bind_fit((ms_canvas_widget, ms_graph_frame), self.arias_ms_figure, ms_canvas_widget, self.arias_ms_canvas)

        # Başlangıçta sonuç alanını gizle
        self.clear_paired_arias_display()

        # Veri yükleme/güncelleme yardımcıları
        self._refresh_arias_percent_tab()

    def update_paired_arias_display(self, total_ia: float, comp1_name: str, comp2_name: str) -> None:
        """Arias ÅŞiddeti sekmesinde çift sonuçlarını gösterir."""
        try:
            if self.paired_ia_var is None or self.paired_components_var is None:
                return
            self.paired_ia_var.set(f"{float(total_ia):.4f}")
            self.paired_components_var.set(f"{comp1_name} + {comp2_name}")
            if self.paired_results_frame is not None and not self.paired_results_frame.winfo_manager():
                self.paired_results_frame.pack(fill="x", pady=(4, 0))
        except Exception as exc:
            try:
                self.logger.warning(f"Arias sonuçları gösterilemedi: {exc}")
            except Exception:
                pass

    def clear_paired_arias_display(self) -> None:
        """Arias ÅŞiddeti sekmesindeki çift sonuçlarını temizler."""
        try:
            if self.paired_ia_var is not None:
                self.paired_ia_var.set("")
            if self.paired_components_var is not None:
                self.paired_components_var.set("")
            if self.paired_results_frame is not None and self.paired_results_frame.winfo_manager():
                self.paired_results_frame.pack_forget()
        except Exception:
            pass

    def _refresh_arias_percent_tab(self):
        """Aktif kayıt üzerinden Arias% grafiği ve tabloyu günceller."""
        try:
            # Seçili kayıt adını bul
            sel = self.earthquake_listbox.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx >= len(self.loaded_earthquake_files):
                return
            name = self.loaded_earthquake_files[idx]['name']
            data = self.processed_earthquake_data.get(name, {})
            time_data = data.get('time', [])
            acc = data.get('acceleration', [])
            dt = data.get('dt', data.get('params', {}).get('time_step', None))
            acc_unit = data.get('accel_unit', 'g')
            if dt is None and len(time_data) > 1:
                import numpy as _np
                t = _np.asarray(time_data, dtype=float)
                diffs = _np.diff(t)
                diffs = diffs[_np.isfinite(diffs) & (diffs > 0)]
                dt = float(_np.median(diffs)) if diffs.size else None
            if dt is None or len(time_data) == 0 or len(acc) == 0:
                return

            # Hesapla
            from ..calculations.earthquake_stats import EarthquakeStats
            import numpy as _np
            acc_arr = _np.asarray(acc, dtype=float)
            res = EarthquakeStats.calculate_arias_intensity_cumulative(acc_arr, float(dt), acc_unit)
            ia = _np.asarray(res.get('IA_cumulative', []), dtype=float)
            t = _np.asarray(res.get('time', []), dtype=float)
            ia_tot = float(res.get('IA_total', ia[-1] if ia.size else 0.0))
            pct = (ia / ia_tot * 100.0) if (ia_tot > 0 and ia.size) else _np.zeros_like(ia)

            # Tabloyu doldur
            try:
                self.arias_table.delete(*self.arias_table.get_children())
            except Exception:
                pass
            for i in range(min(len(t), len(acc_arr), len(ia))):
                self.arias_table.insert("", "end", values=(f"{t[i]:.4f}", f"{acc_arr[i]:.5f}", f"{ia[i]:.6f}", f"{pct[i]:.2f}"))

            # Grafiği çiz
            self.arias_pct_ax.clear()
            self.arias_pct_ax.set_xlabel("Zaman (s)", fontsize=9)
            self.arias_pct_ax.set_ylabel("Arias ÅŞiddeti (%)", fontsize=9)
            self.arias_pct_ax.grid(True, linestyle='--', alpha=0.3)
            self.arias_pct_ax.plot(t, pct, color="#2E86AB", linewidth=1.2)
            self.arias_pct_canvas.draw_idle()
            if hasattr(self, "arias_ms_ax"):
                self.arias_ms_ax.clear()
                self.arias_ms_ax.set_xlabel("Zaman (s)", fontsize=9)
                self.arias_ms_ax.set_ylabel("Arias ÅŞiddeti (m/s)", fontsize=9)
                self.arias_ms_ax.grid(True, linestyle='--', alpha=0.3)
                self.arias_ms_ax.plot(t, ia, color="#E67E22", linewidth=1.2)
                self.arias_ms_canvas.draw_idle()
        except Exception as e:
            try:
                self.logger.debug(f"Arias% sekmesi güncellenemedi: {e}")
            except Exception:
                print(f"Arias% sekmesi güncellenemedi: {e}")


    def _update_arias_plot(self, earthquake_data: Dict[str, Any], record_name: Optional[str] = None) -> None:
        """Arias ÅŞiddeti kümülatif eÄŸrisini çizer.

        X: Zaman (s), Y: Arias ÅŞiddeti (m/s)
        """
        if not hasattr(self, 'arias_ax') or not hasattr(self, 'arias_canvas'):
            return

        try:
            time_data = earthquake_data.get('time', [])
            acceleration = earthquake_data.get('acceleration', [])
            # dt öncelik sırası: explicit dt -> params.time_step -> zaman dizisinden kestirim
            dt = earthquake_data.get('dt', None)
            if dt is None:
                dt = (earthquake_data.get('params', {}) or {}).get('time_step', None)
            if dt is None and isinstance(time_data, (list, tuple)) and len(time_data) > 1:
                try:
                    import numpy as _np
                    diffs = _np.diff(_np.asarray(time_data, dtype=float))
                    # Pozitif ve sonlu farklardan medyan al
                    diffs = diffs[_np.isfinite(diffs) & (diffs > 0)]
                    if diffs.size > 0:
                        dt = float(_np.median(diffs))
                except Exception:
                    dt = None
            # Birim öncelik sırası: explicit accel_unit -> units.acceleration -> kayıt parametreleri
            accel_unit = earthquake_data.get('accel_unit', None)
            if accel_unit is None:
                accel_unit = (earthquake_data.get('units', {}) or {}).get('acceleration', None)
            if accel_unit is None and record_name:
                try:
                    # loaded_earthquake_files içinden parametreleri bul
                    for rec in getattr(self, 'loaded_earthquake_files', []):
                        if rec.get('name') == record_name:
                            accel_unit = rec.get('parameters', {}).get('accel_unit', 'g')
                            break
                except Exception:
                    accel_unit = 'g'
            if accel_unit is None:
                accel_unit = 'g'

            if dt is None or len(time_data) == 0 or len(acceleration) == 0:
                self._clear_arias_plot()
                return

            import numpy as _np
            time_arr = _np.asarray(time_data, dtype=float)
            acc_arr = _np.asarray(acceleration, dtype=float)

            # Kümülatif Arias hesapla
            result = EarthquakeStats.calculate_arias_intensity_cumulative(acc_arr, float(dt), accel_unit)
            ia_t = result.get('IA_cumulative', None)
            t = result.get('time', None)
            # Toplam AI (son deÄŸer)
            try:
                ai_total = float(result.get('arias_intensity', None)) if result.get('arias_intensity', None) is not None else None
            except Exception:
                ai_total = None

            # Güvenlik: boyut ve değer kontrolü
            if ia_t is None or t is None or len(ia_t) == 0:
                self._clear_arias_plot()
                return

            # Çizim
            self.arias_ax.clear()
            self.arias_ax.plot(t, ia_t, color="#1f77b4", linewidth=1.5)
            self.arias_ax.set_xlabel("Zaman (s)", fontsize=9)
            self.arias_ax.set_ylabel("Arias ÅŞiddeti (m/s)", fontsize=9)
            title = f"Arias ÅŞiddeti" + (f" - {record_name}" if record_name else "")
            self.arias_ax.set_title(title, fontsize=10, pad=8)
            self.arias_ax.grid(True, linestyle='--', alpha=0.3)
            self.arias_ax.tick_params(labelsize=8)
            
            # Eksen limitlerini ayarla
            try:
                import numpy as _np
                if _np.size(t) > 1:
                    t_min, t_max = float(_np.min(t)), float(_np.max(t))
                    self.arias_ax.set_xlim(t_min, t_max)
                
                if _np.size(ia_t) > 0:
                    y_min = float(_np.nanmin(ia_t))
                    y_max = float(_np.nanmax(ia_t))
                    
                    # Geçerli değerleri kontrol et
                    if not _np.isfinite(y_min):
                        y_min = 0.0
                    if not _np.isfinite(y_max) or y_max <= y_min:
                        y_max = max(y_min + 1.0, 1.0)
                    
                    # Y ekseni için %10 padding
                    y_range = y_max - y_min
                    padding = 0.1 * y_range
                    self.arias_ax.set_ylim(y_min - padding, y_max + padding)
                
                # Tick locator ayarla
                self.arias_ax.yaxis.set_major_locator(MaxNLocator(nbins=6, prune='both'))
                self.arias_ax.xaxis.set_major_locator(MaxNLocator(nbins=8, prune='both'))
            except Exception as e:
                self.logger.debug(f"Arias grafik limit ayarı hatası: {e}")

            # Süre hesapları ve overlay (seçime duyarlı)
            try:
                from src.calculations.earthquake_stats import EarthquakeStats as _EQS
                duration_type = self.var_duration_type.get() if hasattr(self, 'var_duration_type') else 'Significant Duration'
                dm = None
                duration_val = 0.0

                # Parametre okuma
                # Bracketed/Uniform: a0 her zaman mutlak g
                if duration_type in ('Bracketed Duration', 'Uniform Duration'):
                    try:
                        a0_value = float(getattr(self, 'uniform_a0_var', tk.StringVar(value='0.01')).get())
                    except Exception:
                        a0_value = 0.01
                    dm = _EQS.compute_duration_measures(
                        acc_arr, float(dt), accel_unit,
                        threshold_mode='absolute_g', a0_abs=a0_value
                    )
                else:
                    # Significant yüzdeleri
                    try:
                        sig_low_percent = float(getattr(self, 'sig_start_percent_var', tk.StringVar(value='5.0')).get())
                    except Exception:
                        sig_low_percent = 5.0
                    try:
                        sig_high_percent = float(getattr(self, 'sig_end_percent_var', tk.StringVar(value='95.0')).get())
                    except Exception:
                        sig_high_percent = 95.0
                    # Effective mutlak AI (opsiyonel)
                    try:
                        ai_low_txt = getattr(self, 'eff_start_ai_var', tk.StringVar(value='')).get().strip()
                        ai_high_txt = getattr(self, 'eff_end_ai_var', tk.StringVar(value='')).get().strip()
                        AI_low_abs = float(ai_low_txt) if ai_low_txt else None
                        AI_high_abs = float(ai_high_txt) if ai_high_txt else None
                    except Exception:
                        AI_low_abs, AI_high_abs = None, None

                    dm = _EQS.compute_duration_measures(
                        acc_arr, float(dt), accel_unit,
                        percent_low=sig_low_percent / 100.0,
                        percent_high=sig_high_percent / 100.0,
                        AI_low_abs=AI_low_abs, AI_high_abs=AI_high_abs,
                    )

                # Overlay çizimi
                if duration_type == 'Bracketed Duration':
                    duration_val = float(getattr(dm, 'Db', 0.0))
                    t_db = getattr(dm, 't_db', None)
                    if t_db:
                        y_base = float(self.arias_ax.get_ylim()[0])
                        self.arias_ax.hlines(y=y_base, xmin=float(t_db[0]), xmax=float(t_db[1]), colors='red', linewidth=3, zorder=10)
                elif duration_type == 'Uniform Duration':
                    duration_val = float(getattr(dm, 'Du', 0.0))
                    import numpy as _np
                    # Eşiği g biriminde al ve ivmeyi güvenilir şekilde g'ye dönüştür
                    try:
                        a0_value_g = float(getattr(self, 'uniform_a0_var', tk.StringVar(value='0.01')).get())
                    except Exception:
                        a0_value_g = 0.01
                    try:
                        accel_g = _EQS.convert_acceleration_to_g(acc_arr.astype(float), str(accel_unit))
                    except Exception:
                        # Fallback: birim bilinmiyorsa g varsay
                        accel_g = acc_arr.astype(float)
                    above = _np.abs(accel_g) >= float(a0_value_g)
                    if _np.any(above):
                        starts = _np.where(_np.diff(_np.r_[0, above.astype(int)]) == 1)[0]
                        ends = _np.where(_np.diff(_np.r_[above.astype(int), 0]) == -1)[0]
                        y_base = float(self.arias_ax.get_ylim()[0])
                        for s, e in zip(starts, ends):
                            self.arias_ax.hlines(y=y_base, xmin=float(t[s]), xmax=float(t[e]), colors='red', linewidth=2, zorder=10)
                elif duration_type == 'Significant Duration':
                    duration_val = float(getattr(dm, 'Ds', 0.0))
                    t_ds = getattr(dm, 't_ds', None)
                    if t_ds:
                        import numpy as _np
                        mask = (_np.asarray(t) >= float(t_ds[0])) & (_np.asarray(t) <= float(t_ds[1]))
                        self.arias_ax.plot(_np.asarray(t)[mask], _np.asarray(ia_t)[mask], color='red', linewidth=2.5, zorder=10)
                elif duration_type == 'Effective Duration':
                    duration_val = float(getattr(dm, 'De', 0.0))
                    t_de = getattr(dm, 't_de', None)
                    if t_de:
                        import numpy as _np
                        mask = (_np.asarray(t) >= float(t_de[0])) & (_np.asarray(t) <= float(t_de[1]))
                        self.arias_ax.plot(_np.asarray(t)[mask], _np.asarray(ia_t)[mask], color='red', linewidth=2.5, zorder=10)

                # Sonuç alanını güncelle
                try:
                    if hasattr(self, 'duration_result_var'):
                        self.duration_result_var.set(f"{duration_type}: {duration_val:.2f} sec")
                except Exception:
                    pass
            except Exception as _e:
                try:
                    self.logger.debug(f"Duration calculation/plotting error: {_e}")
                except Exception:
                    pass
                try:
                    if hasattr(self, 'duration_result_var'):
                        self.duration_result_var.set("Hesaplama Hatası")
                except Exception:
                    pass

            # D5-95 overlay: alt çizgi ve eğri üzerinde kırmızı vurgulama
            try:
                if getattr(self, 'show_d595_overlay_var', None) and self.show_d595_overlay_var.get():
                    d95_obj = EarthquakeStats.calculate_significant_duration(acc_arr, float(dt), 5.0, 95.0, unit=accel_unit)
                    t_start = float(getattr(d95_obj, 'start_time', float('nan')))
                    t_end = float(getattr(d95_obj, 'end_time', float('nan')))
                    if _np.isfinite(t_start) and _np.isfinite(t_end) and t_end > t_start:
                        # Alt çizgi
                        self.arias_ax.hlines(y=_np.min(self.arias_ax.get_ylim()), xmin=t_start, xmax=t_end, colors='red', linewidth=3)
                        # Eğri üzerinde kırmızı vurgulama
                        try:
                            # IA yüzdesi üzerinden eşiklere karşılık gelen zaman aralığını işaretle
                            # Bizde IA(t) mutlak; yüzdesel aralık için normalizasyon yapalım
                            ia_norm = _np.asarray(ia_t, dtype=float)
                            if ia_norm.size > 0:
                                ia_norm = ia_norm / _np.nanmax(ia_norm)
                                mask = (t >= t_start) & (t <= t_end)
                                self.arias_ax.plot(t[mask], (ia_norm[mask] * (self.arias_ax.get_ylim()[1]-self.arias_ax.get_ylim()[0]) + self.arias_ax.get_ylim()[0]),
                                                   color='red', linewidth=2, alpha=0.85)
                        except Exception:
                            pass
            except Exception:
                pass

            # Uniform Duration overlay (eski): devre dışı bırakıldı (yeni parametreli sürüm yukarıda)
            try:
                if getattr(self, 'var_duration_type', None) and self.var_duration_type.get() == 'Uniform Duration' and False:
                    # EÅŸik: %PGA
                    try:
                        a0_percent = float(getattr(self, 'uniform_a0_percent_var', tk.StringVar(value='5.0')).get())
                    except Exception:
                        a0_percent = 5.0
                    # PGA (mutlak ivme maksimumu)
                    pga = float(_np.nanmax(_np.abs(acc_arr))) if acc_arr.size else 0.0
                    threshold = (a0_percent / 100.0) * pga
                    if pga > 0 and threshold >= 0:
                        # Eşik üstündeki aralıkları bul
                        above = _np.abs(acc_arr) > threshold
                        # Ardışık True segmentlerini zamana çevir
                        if above.any():
                            # Geçiş indeksleri
                            idx = _np.flatnonzero(_np.diff(above.astype(int)))
                            # Segment başlangıç/bitiş indeksleri
                            starts = [0] + (idx + 1).tolist() if above[0] else (idx + 1).tolist()
                            ends = idx.tolist() + [above.size - 1] if above[-1] else idx.tolist()
                            # Düzeltme: baş ve son için koşullu
                            if above[0]:
                                starts = [0] + (idx + 1).tolist()
                            else:
                                starts = (idx + 1).tolist()
                            if above[-1]:
                                ends = idx.tolist() + [above.size - 1]
                            else:
                                ends = idx.tolist()
                            # Çizim: her segmentte alt kırmızı çizgi
                            y_base = _np.min(self.arias_ax.get_ylim())
                            for s, e in zip(starts, ends):
                                if e >= s:
                                    self.arias_ax.hlines(y=y_base, xmin=t[s], xmax=t[e], colors='red', linewidth=2)
                            # Toplam süreyi info panelinde göstermek isterseniz burada hesaplanır
                            total_duration = float(_np.sum(( _np.asarray(ends) - _np.asarray(starts) + 1 )) * float(dt)) if len(starts) and len(ends) else 0.0
                            try:
                                self.arias_d575_var.set(f"{total_duration:.3f}")
                            except Exception:
                                pass
            except Exception:
                pass

            # Bracketed Duration overlay: ilk ve son eşik aşımı arasında alt çizgi
            try:
                if getattr(self, 'var_duration_type', None) and self.var_duration_type.get() == 'Bracketed Duration':
                    try:
                        a0_percent = float(getattr(self, 'uniform_a0_percent_var', tk.StringVar(value='5.0')).get())
                    except Exception:
                        a0_percent = 5.0
                    dm = EarthquakeStats.compute_duration_measures(
                        acc_arr, float(dt), accel_unit,
                        threshold_mode='relative_to_pga', k=a0_percent/100.0
                    )
                    t_db = getattr(dm, 't_db', None)
                    if t_db and _np.isfinite(t_db[0]) and _np.isfinite(t_db[1]) and (t_db[1] > t_db[0]):
                        y_base = _np.min(self.arias_ax.get_ylim())
                        self.arias_ax.hlines(y=y_base, xmin=float(t_db[0]), xmax=float(t_db[1]), colors='red', linewidth=3)
            except Exception:
                pass

            # Effective Duration overlay: mutlak AI eşiklerine göre alt çizgi (vars: %5–%95 AI_tot)
            try:
                if getattr(self, 'var_duration_type', None) and self.var_duration_type.get() == 'Effective Duration':
                    dm = EarthquakeStats.compute_duration_measures(
                        acc_arr, float(dt), accel_unit,
                        threshold_mode='relative_to_pga',  # a0 yalnız Uniform/Bracketed için; burada önemli değil
                        k=0.05,
                        percent_low=0.05, percent_high=0.95,
                        AI_low_abs=None, AI_high_abs=None
                    )
                    t_de = getattr(dm, 't_de', None)
                    if t_de and _np.isfinite(t_de[0]) and _np.isfinite(t_de[1]) and (t_de[1] > t_de[0]):
                        y_base = _np.min(self.arias_ax.get_ylim())
                        self.arias_ax.hlines(y=y_base, xmin=float(t_de[0]), xmax=float(t_de[1]), colors='red', linewidth=3)
            except Exception:
                pass
            
            # Sol panel değerlerini güncelle
            try:
                # AI
                if ai_total is None and ia_t is not None and len(ia_t) > 0:
                    ai_total = float(ia_t[-1])
                if ai_total is not None and _np.isfinite(ai_total):
                    self.arias_ai_var.set(f"{ai_total:.3f}")
                else:
                    self.arias_ai_var.set("--")

                # D5-95 ve D5-75
                try:
                    d95 = EarthquakeStats.calculate_significant_duration(acc_arr, float(dt), 5.0, 95.0, unit=accel_unit)
                    self.arias_d595_var.set(f"{float(getattr(d95, 'duration', float('nan'))):.3f}")
                except Exception:
                    self.arias_d595_var.set("--")
                try:
                    d75 = EarthquakeStats.calculate_significant_duration(acc_arr, float(dt), 5.0, 75.0, unit=accel_unit)
                    self.arias_d575_var.set(f"{float(getattr(d75, 'duration', float('nan'))):.3f}")
                except Exception:
                    self.arias_d575_var.set("--")
            except Exception:
                pass

            self.arias_canvas.draw_idle()
        except Exception as e:
            self.logger.debug(f"Arias çizimi hatası: {e}")
            try:
                self._clear_arias_plot()
            except Exception:
                pass


    def _clear_arias_plot(self) -> None:
        """Arias grafiğini temizler ve eksenleri sıfırlar."""
        if not hasattr(self, 'arias_ax') or not hasattr(self, 'arias_canvas'):
            return
        self.arias_ax.clear()
        self.arias_ax.set_xlabel("Zaman (s)", fontsize=9)
        self.arias_ax.set_ylabel("Arias ÅŞiddeti (m/s)", fontsize=9)
        self.arias_ax.set_title("Arias ÅŞiddeti", fontsize=10, pad=8)
        self.arias_ax.grid(True, linestyle='--', alpha=0.3)
        self.arias_ax.tick_params(labelsize=8)
        self.arias_canvas.draw_idle()

    def _refresh_arias_plot(self) -> None:
        """Seçili deprem kaydı üzerinden Arias grafiğini yeniden çizer (overlay güncellemeleri için)."""
        try:
            # a(t)^2 hesap çizimini korumak için geçici bastırma bayrağı
            if getattr(self, '_suppress_arias_refresh', False):
                return
            if not hasattr(self, 'loaded_earthquake_files') or not self.loaded_earthquake_files:
                return
            # Basit seçim: listedeki ilk kayıt (veya seçili kayıt varsa onu kullan)
            record_name = None
            earthquake_data = None
            try:
                current_selection = getattr(self, 'earthquake_listbox', None)
                if current_selection and hasattr(current_selection, 'curselection'):
                    sel = current_selection.curselection()
                    if sel:
                        index = sel[0]
                        if index < len(self.loaded_earthquake_files):
                            record_name = self.loaded_earthquake_files[index].get('name')
                            earthquake_data = self.loaded_earthquake_files[index].get('data')
            except Exception:
                pass
            if earthquake_data is None:
                # Fallback: önceki hesaplanmış veri
                earthquake_data = getattr(self, 'current_earthquake_data', None) or {}
            if earthquake_data:
                self._update_arias_plot(earthquake_data, record_name)
        except Exception:
            pass

    def _on_compute_a_squared(self) -> None:
        """Seçili deprem kaydı için a(t)^2 grafiğini çizer (X: Zaman, Y: İvme²).
        Sağlam veri erişimi ve görünür hata bildirimi ile güncellenmiş sürüm."""
        from tkinter import messagebox
        import numpy as _np
        from src.calculations.earthquake_stats import EarthquakeStats as _EQS

        self.logger.debug("a(t)² hesaplama başlatıldı...")

        # 1) Seçili kayıt
        record_name = None
        earthquake_data = None
        try:
            current_selection = getattr(self, 'earthquake_listbox', None)
            if current_selection and hasattr(current_selection, 'curselection'):
                sel = current_selection.curselection()
                if sel and hasattr(self, 'loaded_earthquake_files') and self.loaded_earthquake_files:
                    index = sel[0]
                    if index < len(self.loaded_earthquake_files):
                        record = self.loaded_earthquake_files[index]
                        record_name = record.get('name')
                        # Tercihen iÅŸlenmiÅŸ veri
                        earthquake_data = record.get('processed_data') or record.get('data')
                        self.logger.debug(f"Seçili kayıt: {record_name}")
        except Exception as e:
            self.logger.error(f"Seçili deprem verisi alınırken hata: {e}")
            try:
                messagebox.showerror("Veri Hatası", "Seçili deprem verisi okunurken bir hata oluştu.", parent=self.root)
            except Exception:
                pass
            return

        if not earthquake_data:
            self.logger.warning("a(t)² için seçili deprem kaydı bulunamadı")
            try:
                messagebox.showwarning("Seçim Yapılmadı", "Lütfen listeden bir deprem kaydı seçin.", parent=self.root)
            except Exception:
                pass
            return

        # Arias otomatik yenilemeyi bastır
        self._suppress_arias_refresh = True
        try:
            time_data = earthquake_data.get('time', [])
            acceleration = earthquake_data.get('acceleration', [])
            dt = earthquake_data.get('dt')

            if (time_data is None) or (acceleration is None) \
               or (_np.size(time_data) == 0) or (_np.size(acceleration) == 0):
                self.logger.warning("İvme/zaman verisi eksik")
                try:
                    messagebox.showerror("Veri Hatası", "Seçili kaydın ivme veya zaman verisi bulunamıyor.", parent=self.root)
                except Exception:
                    pass
                return

            t = _np.asarray(time_data, dtype=float)
            a = _np.asarray(acceleration, dtype=float)

            # Çizim: seçilen süre tipine göre Husid veya a^2
            if not hasattr(self, 'arias_ax') or not hasattr(self, 'arias_canvas'):
                return
            self.arias_ax.clear()

            sel = self.var_duration_type.get() if hasattr(self, 'var_duration_type') else 'Significant Duration'
            accel_unit = earthquake_data.get('accel_unit', 'g') if isinstance(earthquake_data, dict) else 'g'

            if sel == 'Significant Duration':
                # Husid grafiÄŸi
                try:
                    p1 = float(getattr(self, 'sig_start_percent_var', tk.StringVar(value='5.0')).get()) / 100.0
                    p2 = float(getattr(self, 'sig_end_percent_var', tk.StringVar(value='95.0')).get()) / 100.0
                except Exception:
                    p1, p2 = 0.05, 0.95
                # dt yoksa time vektöründen güvenle tahmin et
                _dt = float(dt) if (dt is not None and float(dt) > 0) else (float(_np.median(_np.diff(t))) if t.size >= 2 else 0.0)
                dm_h = _EQS.compute_duration_measures(a, _dt, accel_unit,
                                                      percent_low=p1, percent_high=p2)
                H = _np.asarray(getattr(dm_h, 'H', _np.zeros_like(t)), dtype=float)
                t_ds = getattr(dm_h, 't_ds', None)
                if H.size != t.size:
                    H = _np.interp(t, _np.linspace(t[0], t[-1], H.size), H) if H.size > 0 else _np.zeros_like(t)
                self.arias_ax.plot(t, H * 100.0, color='black', linewidth=1.5)
                if t_ds and _np.isfinite(t_ds[0]) and _np.isfinite(t_ds[1]):
                    t_start, t_end = float(t_ds[0]), float(t_ds[1])
                    mask = (t >= t_start) & (t <= t_end)
                    self.arias_ax.plot(t[mask], (H*100.0)[mask], color='red', linewidth=2.5, zorder=10)
                    self.arias_ax.axvline(x=t_start, color='gray', linestyle='--', linewidth=1)
                    self.arias_ax.axvline(x=t_end, color='gray', linestyle='--', linewidth=1)
                    self.arias_ax.axhline(y=p1*100.0, color='gray', linestyle='--', linewidth=1)
                    self.arias_ax.axhline(y=p2*100.0, color='gray', linestyle='--', linewidth=1)
                self.arias_ax.set_xlabel('Zaman (s)', fontsize=9)
                self.arias_ax.set_ylabel('Arias ÅŞiddeti (%)', fontsize=9)
                title = f'Husid GrafiÄŸi' + (f' - {record_name}' if record_name else '')
                self.arias_ax.set_title(title, fontsize=10, pad=8)
                self.arias_ax.set_ylim(-5, 105)
                if t.size > 1:
                    self.arias_ax.set_xlim(float(_np.min(t)), float(_np.max(t)))
                self.arias_ax.grid(True, linestyle='--', alpha=0.3)
                self.arias_ax.tick_params(labelsize=8)
                from matplotlib.ticker import MaxNLocator as _MaxNLocator
                self.arias_ax.yaxis.set_major_locator(_MaxNLocator(nbins=6, prune='both'))
                self.arias_ax.xaxis.set_major_locator(_MaxNLocator(nbins=8, prune='both'))
                self.arias_canvas.draw_idle()
            elif sel == 'Effective Duration':
                # Kümülatif Arias (m/s) grafiği
                try:
                    ai_low_str = getattr(self, 'eff_start_ai_var', tk.StringVar(value='')).get().strip()
                    ai_high_str = getattr(self, 'eff_end_ai_var', tk.StringVar(value='')).get().strip()
                    AI_low_abs = float(ai_low_str) if ai_low_str else None
                    AI_high_abs = float(ai_high_str) if ai_high_str else None
                except Exception:
                    AI_low_abs = None; AI_high_abs = None
                _dt = float(dt) if (dt is not None and float(dt) > 0) else (float(_np.median(_np.diff(t))) if t.size >= 2 else 0.0)
                dm_e = _EQS.compute_duration_measures(
                    a, _dt, accel_unit,
                    AI_low_abs=AI_low_abs, AI_high_abs=AI_high_abs
                )
                IA = _np.asarray(getattr(dm_e, 'AI_cum', _np.zeros_like(t)), dtype=float)
                t_de = getattr(dm_e, 't_de', None)
                if IA.size != t.size and IA.size > 0:
                    IA = _np.interp(t, _np.linspace(t[0], t[-1], IA.size), IA)
                self.arias_ax.plot(t, IA, color='black', linewidth=1.5)
                if t_de and _np.isfinite(t_de[0]) and _np.isfinite(t_de[1]):
                    ts, te = float(t_de[0]), float(t_de[1])
                    mask = (t >= ts) & (t <= te)
                    self.arias_ax.plot(t[mask], IA[mask], color='red', linewidth=2.5, zorder=10)
                    self.arias_ax.axvline(x=ts, color='gray', linestyle='--', linewidth=1)
                    self.arias_ax.axvline(x=te, color='gray', linestyle='--', linewidth=1)
                    if AI_low_abs is not None:
                        self.arias_ax.axhline(y=float(AI_low_abs), color='gray', linestyle='--', linewidth=1)
                    if AI_high_abs is not None:
                        self.arias_ax.axhline(y=float(AI_high_abs), color='gray', linestyle='--', linewidth=1)
                self.arias_ax.set_xlabel('Zaman (s)', fontsize=9)
                self.arias_ax.set_ylabel('Kümülatif Arias ÅŞiddeti (m/s)', fontsize=9)
                title = f'Kümülatif Arias ÅŞiddeti' + (f' - {record_name}' if record_name else '')
                self.arias_ax.set_title(title, fontsize=10, pad=8)
                if t.size > 1:
                    self.arias_ax.set_xlim(float(_np.min(t)), float(_np.max(t)))
                self.arias_ax.grid(True, linestyle='--', alpha=0.3)
                self.arias_ax.tick_params(labelsize=8)
                from matplotlib.ticker import MaxNLocator as _MaxNLocator
                self.arias_ax.yaxis.set_major_locator(_MaxNLocator(nbins=6, prune='both'))
                self.arias_ax.xaxis.set_major_locator(_MaxNLocator(nbins=8, prune='both'))
                self.arias_canvas.draw_idle()
            else:
                # a(t)^2 grafiÄŸi
                a2 = _np.square(a)
                self.arias_ax.plot(t, a2, color='black', linewidth=1.0)
                # eşik çizgisi
                try:
                    a0_g = float(getattr(self, 'uniform_a0_var', tk.StringVar(value='0.01')).get())
                    a0_squared = float(a0_g ** 2)
                    self.arias_ax.axhline(y=a0_squared, color='red', linestyle='--', linewidth=1.2)
                except Exception:
                    a0_squared = None
                if sel == 'Uniform Duration' and a0_squared is not None and t.size == a2.size:
                    mask = _np.asarray(a2, dtype=float) >= a0_squared
                    if _np.any(mask):
                        self.arias_ax.fill_between(t, a0_squared, a2, where=mask, color='red', alpha=0.5, interpolate=True, zorder=5)
                self.arias_ax.set_xlabel('Zaman (s)', fontsize=9)
                self.arias_ax.set_ylabel('İvme²', fontsize=9)
                title = f'İvme Karesi (a²)' + (f' - {record_name}' if record_name else '')
                self.arias_ax.set_title(title, fontsize=10, pad=8)
                if t.size > 1:
                    self.arias_ax.set_xlim(float(_np.min(t)), float(_np.max(t)))
                if a2.size > 0:
                    y_min = float(_np.nanmin(a2)); y_max = float(_np.nanmax(a2))
                    if _np.isfinite(y_min) and _np.isfinite(y_max) and y_max > y_min:
                        padding = 0.1 * (y_max - y_min)
                        self.arias_ax.set_ylim(y_min - padding, y_max + padding)
                self.arias_ax.grid(True, linestyle='--', alpha=0.3)
                self.arias_ax.tick_params(labelsize=8)
                from matplotlib.ticker import MaxNLocator as _MaxNLocator
                self.arias_ax.yaxis.set_major_locator(_MaxNLocator(nbins=6, prune='both'))
                self.arias_ax.xaxis.set_major_locator(_MaxNLocator(nbins=8, prune='both'))
                self.arias_canvas.draw_idle()

            # Seçime göre süreyi de hesaplayıp göster
            try:
                sel = self.var_duration_type.get() if hasattr(self, 'var_duration_type') else 'Significant Duration'
                accel_unit = 'g'
                try:
                    for rec in getattr(self, 'loaded_earthquake_files', []):
                        if rec.get('name') == record_name:
                            accel_unit = rec.get('parameters', {}).get('accel_unit', 'g')
                            break
                except Exception:
                    pass
                if isinstance(earthquake_data, dict):
                    accel_unit = earthquake_data.get('accel_unit', accel_unit)

                if sel in ('Bracketed Duration', 'Uniform Duration'):
                    try:
                        a0_value = float(getattr(self, 'uniform_a0_var', tk.StringVar(value='0.01')).get())
                    except Exception:
                        a0_value = 0.01
                    dm = _EQS.compute_duration_measures(
                        a, float(_np.median(_np.diff(t))) if t.size >= 2 else float(dt or 0.0),
                        accel_unit,
                        threshold_mode='absolute_g', a0_abs=a0_value
                    )
                    if hasattr(self, 'duration_result_var'):
                        if sel == 'Bracketed Duration':
                            self.duration_result_var.set(f"Bracketed Duration: {float(getattr(dm, 'Db', 0.0)):.2f} sec")
                        else:
                            self.duration_result_var.set(f"Uniform Duration: {float(getattr(dm, 'Du', 0.0)):.2f} sec")
                elif sel == 'Significant Duration':
                    try:
                        p1 = float(getattr(self, 'sig_start_percent_var', tk.StringVar(value='5.0')).get()) / 100.0
                        p2 = float(getattr(self, 'sig_end_percent_var', tk.StringVar(value='95.0')).get()) / 100.0
                    except Exception:
                        p1, p2 = 0.05, 0.95
                    dm = _EQS.compute_duration_measures(
                        a, float(_np.median(_np.diff(t))) if t.size >= 2 else float(dt or 0.0),
                        accel_unit,
                        percent_low=p1, percent_high=p2
                    )
                    if hasattr(self, 'duration_result_var'):
                        self.duration_result_var.set(f"Significant Duration: {float(getattr(dm, 'Ds', 0.0)):.2f} sec")
                elif sel == 'Effective Duration':
                    try:
                        ai_low = getattr(self, 'eff_start_ai_var', tk.StringVar(value='')).get().strip()
                        ai_high = getattr(self, 'eff_end_ai_var', tk.StringVar(value='')).get().strip()
                        AI_low_abs = float(ai_low) if ai_low else None
                        AI_high_abs = float(ai_high) if ai_high else None
                    except Exception:
                        AI_low_abs = None; AI_high_abs = None
                    dm = _EQS.compute_duration_measures(
                        a, float(_np.median(_np.diff(t))) if t.size >= 2 else float(dt or 0.0),
                        accel_unit,
                        AI_low_abs=AI_low_abs, AI_high_abs=AI_high_abs
                    )
                    if hasattr(self, 'duration_result_var'):
                        self.duration_result_var.set(f"Effective Duration: {float(getattr(dm, 'De', 0.0)):.2f} sec")
            except Exception as e:
                self.logger.debug(f"Süre hesap gösterim hatası: {e}")
        except Exception as e:
            self.logger.exception(f"a(t)² çizim hatası: {e}")
            try:
                messagebox.showerror("Grafik Hatası", f"Grafik çizilirken bir hata oluştu:\n{e}", parent=self.root)
            except Exception:
                pass
        finally:
            self._suppress_arias_refresh = False

    def _set_duration_type(self) -> None:
        """Süre tipi seçimi değiştiğinde arayüzü ve grafiği günceller."""
        try:
            self.logger.debug(f"Süre tipi değiştirildi: {self.var_duration_type.get()}")
            self._update_duration_param_visibility()
            self._refresh_arias_plot()
        except Exception as e:
            try:
                self.logger.error(f"Süre tipi değiştirilirken hata: {e}")
            except Exception:
                pass

    def _update_duration_param_visibility(self) -> None:
        """Seçilen süre tipine göre parametre çerçevelerinin ve ayırıcıların görünürlüğünü yönetir."""
        try:
            selected = self.var_duration_type.get() if hasattr(self, 'var_duration_type') else "Significant Duration"

            # 1) Tüm dinamik elemanları gizle
            for w in (
                getattr(self, 'brk_uni_frame', None),
                getattr(self, 'sig_frame', None),
                getattr(self, 'eff_frame', None),
                getattr(self, '_a0_divider', None),
                getattr(self, '_compute_result_divider', None),
                getattr(self, '_bd_info_divider', None),
                getattr(self, 'bracketed_info_label', None),
                getattr(self, '_ud_info_divider', None),
                getattr(self, 'uniform_info_label', None),
                getattr(self, '_sd_info_divider', None),
                getattr(self, 'significant_info_label', None),
                getattr(self, '_ed_info_divider', None),
                getattr(self, 'effective_info_label', None),
            ):
                try:
                    if w is not None:
                        w.pack_forget()
                except Exception:
                    pass

            # 2) Dinamik bloğu Hesapla butonunun hemen öncesine yerleştir
            target_before = getattr(self, 'arias_compute_button', None)

            frame_to_show = None
            if selected in ("Bracketed Duration", "Uniform Duration"):
                frame_to_show = getattr(self, 'brk_uni_frame', None)
            elif selected == "Significant Duration":
                frame_to_show = getattr(self, 'sig_frame', None)
            elif selected == "Effective Duration":
                frame_to_show = getattr(self, 'eff_frame', None)

            if target_before is not None and frame_to_show is not None:
                try:
                    if hasattr(self, 'uniform_a0_label') and selected in ("Bracketed Duration", "Uniform Duration"):
                        self.uniform_a0_label.configure(text="İvme Eşiği, a₀ (g):")
                except Exception:
                    pass
                try:
                    self._a0_divider.pack(fill='x', pady=(8, 6), before=target_before)
                except Exception:
                    pass
                try:
                    frame_to_show.pack(fill='x', pady=(0, 6), before=target_before)
                except Exception:
                    pass
                try:
                    self._compute_result_divider.pack(fill='x', pady=(6, 6), before=target_before)
                except Exception:
                    pass
                # Açıklama metinlerini seçime göre göster
                try:
                    if selected == "Bracketed Duration" and getattr(self, 'bracketed_info_label', None) is not None:
                        self._bd_info_divider.pack(fill='x', pady=(6, 6))
                        self.bracketed_info_label.pack(fill='x', pady=(0, 0))
                    elif selected == "Uniform Duration" and getattr(self, 'uniform_info_label', None) is not None:
                        self._ud_info_divider.pack(fill='x', pady=(6, 6))
                        self.uniform_info_label.pack(fill='x', pady=(0, 0))
                    elif selected == "Significant Duration" and getattr(self, 'significant_info_label', None) is not None:
                        self._sd_info_divider.pack(fill='x', pady=(6, 6))
                        self.significant_info_label.pack(fill='x', pady=(0, 0))
                    elif selected == "Effective Duration" and getattr(self, 'effective_info_label', None) is not None:
                        self._ed_info_divider.pack(fill='x', pady=(6, 6))
                        self.effective_info_label.pack(fill='x', pady=(0, 0))
                except Exception:
                    pass
        except Exception as e:
            try:
                self.logger.debug(f"Parametre görünürlüğü güncellenirken hata: {e}")
            except Exception:
                pass

    def _create_time_series_plots(self, parent):
        """SeismoSignal benzeri üç grafik paneli ve veri tabloları oluşturur"""
        # Ana konteyner
        main_container = ttk.Frame(parent)
        main_container.pack(fill="both", expand=True)
        
        # Toolbar (üstte)
        toolbar_frame = ttk.Frame(main_container)
        toolbar_frame.pack(fill="x", padx=5, pady=5)
        
        # Birim göstergeleri (SeismoSignal benzeri)
        units_frame = ttk.Frame(toolbar_frame)
        units_frame.pack(side="right")
        
        # Dinamik birim göstergeleri için label referansları sakla
        self.accel_unit_label = ttk.Label(units_frame, text="İvme: g", font=('Segoe UI', 8))
        self.accel_unit_label.pack(side="left", padx=5)
        
        self.velocity_unit_label = ttk.Label(units_frame, text="Hız: cm/s", font=('Segoe UI', 8))
        self.velocity_unit_label.pack(side="left", padx=5)
        
        self.displacement_unit_label = ttk.Label(units_frame, text="Yerdeğiştirme: cm", font=('Segoe UI', 8))
        self.displacement_unit_label.pack(side="left", padx=5)
        
        # Ana içerik alanı (tabloları ve grafikleri içerir)
        content_container = ttk.Frame(main_container)
        content_container.pack(fill="both", expand=True, padx=5)
        
        # Sol panel - Veri tabloları
        tables_panel = ttk.Frame(content_container)
        tables_panel.pack(side="left", fill="both", padx=(0, 10))
        tables_panel.pack_propagate(False)
        tables_panel.config(width=350)
        
        # Sağ panel - Grafikler
        plots_panel = ttk.Frame(content_container)
        plots_panel.pack(side="right", fill="both", expand=True)
        
        # Veri tablolarını oluştur
        self._create_data_tables(tables_panel)
        
        # Grafikleri oluÅŸtur
        self._create_plots_panel(plots_panel)

    def _create_data_tables(self, parent):
        """Zaman serisi veri tablolarını oluşturur"""
        # Acceleration tablosu
        accel_frame = ttk.LabelFrame(parent, text="İvme Verileri (g)", padding=5)
        accel_frame.pack(fill="both", expand=True, pady=(0, 5))
        
        # Acceleration Treeview
        accel_tree_frame = ttk.Frame(accel_frame)
        accel_tree_frame.pack(fill="both", expand=True)
        
        self.accel_tree = ttk.Treeview(accel_tree_frame, columns=("time", "acceleration"), 
                                      show="headings", height=8)
        self.accel_tree.heading("time", text="Zaman (s)")
        self.accel_tree.heading("acceleration", text="İvme (g)")
        self.accel_tree.column("time", width=80, anchor="center")
        self.accel_tree.column("acceleration", width=90, anchor="center")
        
        accel_scrollbar = ttk.Scrollbar(accel_tree_frame, orient="vertical", 
                                       command=self.accel_tree.yview)
        self.accel_tree.config(yscrollcommand=accel_scrollbar.set)
        
        self.accel_tree.pack(side="left", fill="both", expand=True)
        accel_scrollbar.pack(side="right", fill="y")
        
        # CTRL+A ve kopyalama özelliklerini ekle
        self._bind_table_shortcuts(self.accel_tree, "İvme")
        
        # Velocity tablosu
        velocity_frame = ttk.LabelFrame(parent, text="Hız Verileri (cm/s)", padding=5)
        velocity_frame.pack(fill="both", expand=True, pady=5)
        
        # Velocity Treeview
        velocity_tree_frame = ttk.Frame(velocity_frame)
        velocity_tree_frame.pack(fill="both", expand=True)
        
        self.velocity_tree = ttk.Treeview(velocity_tree_frame, columns=("time", "velocity"), 
                                         show="headings", height=8)
        self.velocity_tree.heading("time", text="Zaman (s)")
        self.velocity_tree.heading("velocity", text="Hız (cm/s)")
        self.velocity_tree.column("time", width=80, anchor="center")
        self.velocity_tree.column("velocity", width=90, anchor="center")
        
        velocity_scrollbar = ttk.Scrollbar(velocity_tree_frame, orient="vertical", 
                                          command=self.velocity_tree.yview)
        self.velocity_tree.config(yscrollcommand=velocity_scrollbar.set)
        
        self.velocity_tree.pack(side="left", fill="both", expand=True)
        velocity_scrollbar.pack(side="right", fill="y")
        
        # CTRL+A ve kopyalama özelliklerini ekle
        self._bind_table_shortcuts(self.velocity_tree, "Hız")
        
        # Displacement tablosu
        displacement_frame = ttk.LabelFrame(parent, text="Yerdeğiştirme Verileri (cm)", padding=5)
        displacement_frame.pack(fill="both", expand=True, pady=(5, 0))
        
        # Displacement Treeview
        displacement_tree_frame = ttk.Frame(displacement_frame)
        displacement_tree_frame.pack(fill="both", expand=True)
        
        self.displacement_tree = ttk.Treeview(displacement_tree_frame, columns=("time", "displacement"), 
                                             show="headings", height=8)
        self.displacement_tree.heading("time", text="Zaman (s)")
        self.displacement_tree.heading("displacement", text="Yerdeğiştirme (cm)")
        self.displacement_tree.column("time", width=80, anchor="center")
        self.displacement_tree.column("displacement", width=90, anchor="center")
        
        displacement_scrollbar = ttk.Scrollbar(displacement_tree_frame, orient="vertical", 
                                              command=self.displacement_tree.yview)
        self.displacement_tree.config(yscrollcommand=displacement_scrollbar.set)
        
        self.displacement_tree.pack(side="left", fill="both", expand=True)
        displacement_scrollbar.pack(side="right", fill="y")
        
        # CTRL+A ve kopyalama özelliklerini ekle
        self._bind_table_shortcuts(self.displacement_tree, "Yerdeğiştirme")
        
        # Ham zaman değer haritaları (float parsesi riskini önlemek için)
        self._accel_time_map = {}
        self._velocity_time_map = {}
        self._displacement_time_map = {}

    def _create_plots_panel(self, parent):
        """Grafik panelini olu?turur"""
        # Zaman Serisi sekmesi i?in de InteractivePlot bile?eni kullan
        self.time_series_plot = InteractivePlot(parent)
        self.time_series_figure, axes = self.time_series_plot.create_interactive_figure(
            nrows=3,
            ncols=1,
            figsize=(12, 8)
        )

        # Eskiden kullan?lan referans isimlerini koru (di?er fonksiyonlar bunlara ba?l?)
        self.accel_ax = axes[0] if len(axes) > 0 else None
        self.velocity_ax = axes[1] if len(axes) > 1 else None
        self.displacement_ax = axes[2] if len(axes) > 2 else None
        self.time_series_canvas = self.time_series_plot.canvas

        # Sa? t?k men?s?n? yeni canvas ?zerine ba?la
        try:
            canvas_widget = self.time_series_canvas.get_tk_widget()
            canvas_widget.bind('<Button-3>', self._show_plot_context_menu)
            canvas_widget.bind('<Button-2>', self._show_plot_context_menu)
            canvas_widget.bind('<Control-Button-1>', self._show_plot_context_menu)
        except Exception:
            pass

        # Ba?lang?? ayarlar? ve bo? grafik mesaj?
        self._configure_time_series_plots()
        self._show_empty_plots()

    def _configure_time_series_plots(self):
        """Grafik ayarlar?n? yap?land?r?r - SeismoSignal stili"""
        accel_ax = getattr(self, 'accel_ax', None)
        velocity_ax = getattr(self, 'velocity_ax', None)
        displacement_ax = getattr(self, 'displacement_ax', None)
        if not (accel_ax and velocity_ax and displacement_ax):
            return

        # Toolbar birim g?stergelerini g?ncelle
        self._update_unit_display()

        # Varsay?lan birimler
        accel_unit = "g"
        velocity_unit = "cm/s"
        displacement_unit = "cm"

        # E?er y?klenmi? deprem kayd? varsa, o kayd?n birimlerini kullan
        if hasattr(self, 'loaded_earthquake_files') and self.loaded_earthquake_files:
            current_selection = getattr(self, 'earthquake_listbox', None)
            if current_selection and hasattr(current_selection, 'curselection'):
                selection = current_selection.curselection()
                if selection:
                    index = selection[0]
                    if index < len(self.loaded_earthquake_files):
                        params = self.loaded_earthquake_files[index]['parameters']
                        accel_unit = params.get('accel_unit', accel_unit)
                        velocity_unit = params.get('velocity_unit', velocity_unit)
                        displacement_unit = params.get('displacement_unit', displacement_unit)

        # İvme grafiği
        accel_ax.set_ylabel(f'İvme ({accel_unit})', fontsize=10)
        accel_ax.grid(True, alpha=0.3)
        accel_ax.set_title('İvme Zaman Grafiği', fontsize=11, fontweight='bold', loc='center', pad=6)
        # Hız grafiği
        velocity_ax.set_ylabel(f'Hız ({velocity_unit})', fontsize=10)
        velocity_ax.grid(True, alpha=0.3)
        velocity_ax.set_title('Hız Zaman Grafiği', fontsize=11, fontweight='bold', loc='center', pad=6)
        # Yerdeğiştirme grafiği
        displacement_ax.set_ylabel(f'Yerdeğiştirme ({displacement_unit})', fontsize=10)
        displacement_ax.set_xlabel('Zaman (saniye)', fontsize=10)
        displacement_ax.grid(True, alpha=0.3)
        displacement_ax.set_title('Yerdeğiştirme Zaman Grafiği', fontsize=11, fontweight='bold', loc='center', pad=6)

        # Bo? g?r?n?mde ta?may? ?nle: anlaml? x-limit ve margin/locator ayarla
        axes = (accel_ax, velocity_ax, displacement_ax)
        x_limits = (0.0, 1.0)
        y_limits = ((-0.2, 0.2), (-1.0, 1.0), (-1.0, 1.0))

        from contextlib import suppress
        for ax, ylim in zip(axes, y_limits):
            with suppress(Exception):
                ax.set_xlim(*x_limits)
                ax.set_ylim(*ylim)
                ax.margins(x=0.01, y=0.10)
                try:
                    from matplotlib.ticker import MaxNLocator
                    ax.xaxis.set_major_locator(MaxNLocator(nbins=4, prune='both'))
                    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, prune='both'))
                except Exception:
                    pass

    def _show_empty_plots(self):
        """Bo? grafikler ve tablolar? g?sterir"""
        # ?nce grafik i?aretlerini temizle
        self._clear_plot_markers()
        
        # Toolbar birim g?stergelerini varsay?lan de?erlere g?ncelle
        self._update_unit_display()
        
        # Grafikleri temizle (varsa InteractivePlot ?zerinden)
        ts_plot = getattr(self, 'time_series_plot', None)
        if ts_plot is not None:
            try:
                ts_plot.clear_plot()
            except Exception:
                pass
        else:
            for ax in (getattr(self, 'accel_ax', None), getattr(self, 'velocity_ax', None), getattr(self, 'displacement_ax', None)):
                if ax is not None:
                    ax.clear()
        
        # Tablolar? temizle
        self._clear_data_tables()
        
        # Ayarlar? yeniden uygula
        self._configure_time_series_plots()
        
        # Boş mesajları ekle
        for ax in (getattr(self, 'accel_ax', None), getattr(self, 'velocity_ax', None), getattr(self, 'displacement_ax', None)):
            if ax is None:
                continue
            ax.text(0.5, 0.5, 'Deprem kaydı seçilmedi',
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=12, color='gray', style='italic')
        
        # Canvas'? g?ncelle
        canvas = getattr(self, 'time_series_canvas', None)
        if canvas is not None:
            try:
                canvas.draw_idle()
            except Exception:
                pass

        # Canvas'ı güncelle
        self.time_series_canvas.draw_idle()

    def _run_in_executor(self, func, on_success=None, on_error=None):
        """Fonksiyonu arka planda çalıştır ve sonucu ana threade aktar."""
        if not getattr(self, '_executor', None):
            # Executor yoksa eşzamanlı çalıştır
            try:
                result = func()
                if on_success:
                    on_success(result)
            except Exception as e:
                if on_error:
                    on_error(e)
            return
        def _wrap():
            try:
                result = func()
                if on_success:
                    self.root.after(0, lambda: on_success(result))
            except Exception as e:
                if on_error:
                    self.root.after(0, lambda: on_error(e))
        try:
            self._executor.submit(_wrap)
        except Exception as ex:
            self.logger.debug(f"Arka plan işi başlatılamadı: {ex}")
            try:
                result = func()
                if on_success:
                    on_success(result)
            except Exception as e:
                if on_error:
                    on_error(e)

    def _minmax_decimate(self, x_data, y_data, max_points: int):
        """Min/Max decimation: veriyi dilimlere bölerek her dilimde min ve max noktaları korur.

        Args:
            x_data (Sequence[float]): X ekseni (zaman) verisi
            y_data (Sequence[float]): Y ekseni verisi
            max_points (int): Çıktı için hedef nokta sayısı (yaklaşık)

        Returns:
            (x_dec, y_dec): Azaltılmış veri dizileri
        """
        try:
            n = len(x_data)
            if n <= max_points or max_points <= 0:
                return x_data, y_data
            import math
            bucket_size = max(1, math.floor(n / max_points))
            x_out = []
            y_out = []
            for i in range(0, n, bucket_size):
                j = min(n, i + bucket_size)
                # Dilim
                xs = x_data[i:j]
                ys = y_data[i:j]
                if not xs:
                    continue
                # Min/Max bul
                ymin = min(ys)
                ymax = max(ys)
                imin = ys.index(ymin)
                imax = ys.index(ymax)
                # Zaman sırasını koruyarak ekle
                idxs = sorted([imin, imax])
                for k in idxs:
                    if 0 <= k < len(xs):
                        x_out.append(xs[k])
                        y_out.append(ys[k])
            return x_out, y_out
        except Exception:
            return x_data, y_data
    def _plot_time_series(self, earthquake_data: Dict[str, Any]) -> None:
        """Zaman serilerini ?izer ve tablolar? art?ml? doldurur (UI bloklanmaz)."""
        if not earthquake_data:
            self._show_empty_plots()
            return

        try:
            # K?sa s?reli busy imleci
            self.root.config(cursor="watch")
            self.root.update_idletasks()

            import time as _t
            t0 = _t.time()

            # ?nceki i?aretleri kald?r ve toolbar birim g?stergelerini g?ncelle
            self._clear_plot_markers()
            self._update_unit_display()

            # Ham veriler
            time_data = list(earthquake_data['time'])
            accel_data = list(earthquake_data['acceleration'])
            velocity_data = list(earthquake_data['velocity'])
            displacement_data = list(earthquake_data['displacement'])

            # Birimler (dosya parametrelerinden)
            accel_unit = "g"
            velocity_unit = "cm/s"
            displacement_unit = "cm"
            try:
                sel = self.earthquake_listbox.curselection()
                if sel:
                    i = sel[0]
                    if i < len(self.loaded_earthquake_files):
                        p = self.loaded_earthquake_files[i]['parameters']
                        accel_unit = p.get('accel_unit', accel_unit)
                        velocity_unit = p.get('velocity_unit', velocity_unit)
                        displacement_unit = p.get('displacement_unit', displacement_unit)
            except Exception:
                pass

            ts_plot = getattr(self, 'time_series_plot', None)
            if ts_plot is not None:
                ts_plot.plot_time_series(
                    time_data=time_data,
                    accel_data=accel_data,
                    velocity_data=velocity_data,
                    displacement_data=displacement_data,
                    accel_unit=accel_unit,
                    velocity_unit=velocity_unit,
                    displacement_unit=displacement_unit
                )
            else:
                # Fallback: klasik Matplotlib ?izimini kullan
                accel_ax = getattr(self, 'accel_ax', None)
                velocity_ax = getattr(self, 'velocity_ax', None)
                displacement_ax = getattr(self, 'displacement_ax', None)
                axes_ready = all(ax is not None for ax in (accel_ax, velocity_ax, displacement_ax))
                if axes_ready:
                    accel_ax.clear()
                    velocity_ax.clear()
                    displacement_ax.clear()

                    max_points = 5000
                    if len(time_data) > 10000:
                        t_a, y_a = self._minmax_decimate(time_data, accel_data, max_points)
                        t_v, y_v = self._minmax_decimate(time_data, velocity_data, max_points)
                        t_d, y_d = self._minmax_decimate(time_data, displacement_data, max_points)
                    else:
                        t_a, y_a = time_data, accel_data
                        t_v, y_v = time_data, velocity_data
                        t_d, y_d = time_data, displacement_data

                    try:
                        from ..config.styles import CUSTOM_COLORS
                        color_a = CUSTOM_COLORS['acceleration']
                        color_v = CUSTOM_COLORS['velocity']
                        color_d = CUSTOM_COLORS['displacement']
                        grid_c = CUSTOM_COLORS['grid']
                        text_c = CUSTOM_COLORS['text']
                    except Exception:
                        color_a = "#2E86AB"
                        color_v = "#6C757D"
                        color_d = "#2CA02C"
                        grid_c = "#D0D0D0"
                        text_c = "#111"

                    accel_ax.plot(t_a, y_a, linewidth=1.2, alpha=0.9, color=color_a, rasterized=True, clip_on=True)
                    accel_ax.set_ylabel(f'İvme ({accel_unit})', fontsize=10, color=text_c)
                    accel_ax.set_title('İvme Zaman Grafiği', fontsize=11, fontweight='bold', color=text_c, loc='center', pad=6)
                    accel_ax.grid(True, alpha=0.3, color=grid_c)

                    velocity_ax.plot(t_v, y_v, linewidth=1.2, alpha=0.9, color=color_v, rasterized=True, clip_on=True)
                    velocity_ax.set_ylabel(f'Hız ({velocity_unit})', fontsize=10, color=text_c)
                    velocity_ax.set_title('Hız Zaman Grafiği', fontsize=11, fontweight='bold', color=text_c, loc='center', pad=6)
                    velocity_ax.grid(True, alpha=0.3, color=grid_c)

                    displacement_ax.plot(t_d, y_d, linewidth=1.2, alpha=0.9, color=color_d, rasterized=True, clip_on=True)
                    displacement_ax.set_ylabel(f'Yerdeğiştirme ({displacement_unit})', fontsize=10, color=text_c)
                    displacement_ax.set_xlabel('Zaman (s)', fontsize=10, color=text_c)
                    displacement_ax.set_title('Yerdeğiştirme Zaman Grafiği', fontsize=11, fontweight='bold', color=text_c, loc='center', pad=6)
                    displacement_ax.grid(True, alpha=0.3, color=grid_c)

                    for ax in (accel_ax, velocity_ax, displacement_ax):
                        try:
                            ax.relim()
                            ax.margins(x=0.01, y=0.12)
                            ax.autoscale_view()
                        except Exception:
                            pass
                    if len(time_data) > 1:
                        accel_ax.set_xlim(time_data[0], time_data[-1])

                    canvas = getattr(self, 'time_series_canvas', None)
                    if canvas is not None:
                        canvas.draw_idle()

            # Tablolar? art?ml? doldur
            self._populate_data_tables(time_data, accel_data, velocity_data, displacement_data)

            self.logger.info(f"Zaman serisi ?izildi (toplam { _t.time() - t0:.3f} s)")

        except Exception as e:
            self.logger.exception(f"Grafik ?izimi hatas?: {e}")
            self._show_empty_plots()
        finally:
            try:
                self.root.config(cursor="")
                self.root.update_idletasks()
            except Exception:
                pass

    def parse_afad_acc_asc(self, path: str):
        """
        AFAD .asc ivme kaydı:
        - İlk satırlar KEY: VALUE header
        - İlk saf sayısal satırdan itibaren tek kolon ivme değerleri
        """
        _NUM_LINE = re.compile(r'^\s*[+-]?\d+(\.\d+)?([eE][+-]?\d+)?\s*$')
        header = {}
        data = []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()

        # 1) Header parse (KEY: VALUE olanlar)
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                header[k.strip()] = v.strip()

        # 2) İlk numeric satırı bul
        start_idx = None
        for i, line in enumerate(lines):
            if _NUM_LINE.match(line):
                start_idx = i
                break

        if start_idx is None:
            raise ValueError("Dosyada sayısal veri başlangıcı bulunamadı.")

        # 3) Sadece numeric satırları al (arada boş/garip satır varsa da dayanıklı)
        for line in lines[start_idx:]:
            line = line.strip()
            if not line:
                continue
            if _NUM_LINE.match(line):
                data.append(float(line))
            # numeric değilse sessizce geç (istersen loglayabilirsin)

        if not data:
            raise ValueError("Sayısal veri okunamadı (data boş).")

        return header, data
    
    
    def load_multiple_earthquake_records(self) -> None:
        """Birden fazla deprem kaydı dosyasını yükler (tüm desteklenen formatlar)"""
        try:
            # Çoklu dosya seçim dialogu
            file_paths = FileUtils.open_earthquake_file_dialog(
                title="Birden Fazla Deprem Kaydı Dosyası Seç",
                multiple=True
            )
            
            if file_paths and len(file_paths) > 0:
                successful_loads = 0
                failed_loads = 0
                duplicate_files = []
                result = True  # Varsayılan olarak duplicate dosyaları yükle
                
                # Önce duplicate kontrolü yap
                import os
                for file_path in file_paths:
                    file_name = file_path.split('/')[-1]
                    if self._is_file_already_loaded(file_name):
                        duplicate_files.append(file_name)
                
                # Duplicate varsa uyarı göster
                if duplicate_files:
                    import tkinter.messagebox as msgbox
                    duplicate_names = '\n'.join(duplicate_files)
                    result = msgbox.askyesno(
                        "Aynı İsimli Dosyalar Bulundu",
                        f"Aşağıdaki dosyalar zaten yüklü:\n\n{duplicate_names}\n\n"
                        f"Bu dosyaları tekrar yüklemek istiyor musunuz?\n\n"
                        f"• EVET: Aynı dosyalar tekrar yüklenecek\n"
                        f"• HAYIR: Sadece yeni dosyalar yüklenecek",
                        icon='warning'
                    )
                    
                    if not result:
                        # Sadece yeni dosyaları yükle
                        file_paths = [fp for fp in file_paths 
                                    if not self._is_file_already_loaded(os.path.basename(fp))]
                    self.logger.info(f"Duplicate dosyalar atlandı. {len(file_paths)} yeni dosya yüklenecek.")
                
                # Arka planda yükleme
                def _do_load(paths):
                    succ = 0
                    fail = 0
                    for p in paths:
                        try:
                            file_name_inner = os.path.basename(p)
                            if self._add_earthquake_to_list(file_name_inner, p):
                                succ += 1
                            else:
                                fail += 1
                        except Exception as ferr:
                            fail += 1
                            self.logger.exception(f"Dosya yükleme hatası ({p}): {ferr}")
                    return succ, fail

                def _on_done(result):
                    succ, fail = result
                    # Durum mesajını güncelle
                    if fail == 0:
                        duplicate_info = f" ({len(duplicate_files)} duplicate atlandı)" if duplicate_files and not result else ""
                        self.earthquake_file_status_var.set(
                            f"✅ {succ} dosya başarıyla yüklendi!{duplicate_info}"
                        )
                        if getattr(self, 'earthquake_file_status_label', None) and self._widget_exists(self.earthquake_file_status_label):
                            self.earthquake_file_status_label.config(foreground="green")
                    else:
                        duplicate_info = f" ({len(duplicate_files)} duplicate)" if duplicate_files else ""
                        self.earthquake_file_status_var.set(
                            f"⚠️ {succ} başarılı, {fail} başarısız{duplicate_info}"
                        )
                        if getattr(self, 'earthquake_file_status_label', None) and self._widget_exists(self.earthquake_file_status_label):
                            self.earthquake_file_status_label.config(foreground="orange")
                    self.logger.info(f"Çoklu yükleme tamamlandı: {succ} başarılı, {fail} başarısız")

                self._run_in_executor(lambda: _do_load(file_paths), _on_done, lambda e: self.logger.exception(e))
                
                # Durum mesajını güncelle
                if failed_loads == 0:
                    # Tüm dosyalar başarılı
                    duplicate_info = f" ({len(duplicate_files)} duplicate atlandı)" if duplicate_files and not result else ""
                    self.earthquake_file_status_var.set(
                        f"✅ {successful_loads} dosya başarıyla yüklendi!{duplicate_info}"
                    )
                    if getattr(self, 'earthquake_file_status_label', None) and self._widget_exists(self.earthquake_file_status_label):
                        self.earthquake_file_status_label.config(foreground="green")
                else:
                    # Karışık sonuç
                    duplicate_info = f" ({len(duplicate_files)} duplicate)" if duplicate_files else ""
                    self.earthquake_file_status_var.set(
                        f"⚠️ {successful_loads} başarılı, {failed_loads} başarısız{duplicate_info}"
                    )
                    if getattr(self, 'earthquake_file_status_label', None) and self._widget_exists(self.earthquake_file_status_label):
                        self.earthquake_file_status_label.config(foreground="orange")
                
                self.logger.info(f"Çoklu yükleme tamamlandı: {successful_loads} başarılı, {failed_loads} başarısız")
                
            else:
                self.logger.info("Dosya seçimi iptal edildi veya dosya seçilmedi")
                
        except Exception as e:
            # Genel hata durumu
            error_msg = f"Çoklu dosya yüklenirken hata oluştu: {str(e)}"
            self.earthquake_file_status_var.set(f"❌ {error_msg}")
            self.earthquake_file_status_label.config(foreground="red")
            self.logger.exception(f"Çoklu deprem kaydı yükleme hatası: {e}")
    
    def _is_file_already_loaded(self, file_name: str) -> bool:
        """Dosyanın zaten yüklenip yüklenmediğini kontrol eder"""
        return any(file_info['name'] == file_name for file_info in self.loaded_earthquake_files)
    
    def _generate_unique_name(self, base_name: str) -> str:
        """Verilen ada göre benzersiz bir görüntü adı üretir.

        Aynı isimde bir kayıt varsa sonuna artan sayaç ekler.
        Uzantı varsa, sayaç uzantıdan önce eklenir.
        """
        try:
            existing_names = set(
                [rec.get('name') for rec in getattr(self, 'loaded_earthquake_files', [])]
            ) | set(getattr(self, 'processed_earthquake_data', {}).keys())

            if base_name not in existing_names:
                return base_name

            # Uzantıyı ayır
            name_part = base_name
            ext_part = ''
            if '.' in base_name:
                try:
                    name_part, ext_part = base_name.rsplit('.', 1)
                except Exception:
                    name_part, ext_part = base_name, ''

            counter = 2
            while True:
                candidate = f"{name_part} ({counter})"
                if ext_part:
                    candidate = f"{candidate}.{ext_part}"
                if candidate not in existing_names:
                    return candidate
                counter += 1
        except Exception:
            return base_name

    def _add_earthquake_to_list(self, file_name: str, file_path: str) -> bool:
        """Yüklenen deprem kaydını listeye ekler ve işler"""
        try:
            # Input File Parameters dialogunu aç
            dialog = InputFileParametersDialog(self.root, file_path)

            # Kullanıcı Cancel'a basarsa dosyayı yükleme
            if dialog.result is None:
                self.logger.info(f"Dosya parametreleri ayarlanmadı, dosya yüklenmedi: {file_name}")
                return False

            self.logger.info(f"Deprem kaydı işleniyor: {file_name}")

            # === BURASI ÖNEMLİ KISIM ===
            # AFAD .asc dosyası ise kendi parser’ını kullan
            if file_path.lower().endswith(".asc"):
                header, acc_cm = self.parse_afad_acc_asc(file_path)

                # dt: AFAD header
                dt = float(header.get("SAMPLING_INTERVAL_S", "0.01"))
                n = len(acc_cm)
                time = [i * dt for i in range(n)]

                # acceleration: cm/s^2 -> g
                acc_g = [a / 981.0 for a in acc_cm]

                # velocity (cm/s) & displacement (cm): trapezoidal integration
                vel = [0.0] * n
                disp = [0.0] * n
                for i in range(1, n):
                    vel[i] = vel[i-1] + 0.5 * (acc_cm[i] + acc_cm[i-1]) * dt      # cm/s
                    disp[i] = disp[i-1] + 0.5 * (vel[i] + vel[i-1]) * dt         # cm

                processed_data = {
                    "format_type": "AFAD_ASC",
                    "time": time,
                    "acceleration": acc_g,     # grafik bunu istiyor (g)
                    "velocity": vel,           # cm/s
                    "displacement": disp,      # cm
                    "dt": dt,
                    "npts": n,
                    "afad_header": header,
                }

            else:
                processed_data = self.earthquake_data_processor.process_earthquake_record(
                    file_path, dialog.result
                )
            # === BURASI ÖNEMLİ KISIM SONU ===


            # PEER NGA formatından gelen deprem adını kullan
            display_name = file_name
            if processed_data.get('earthquake_name') and processed_data.get('format_type') in ['AT2', 'VT2', 'DT2']:
                earthquake_name = processed_data['earthquake_name']
                self.logger.debug(f"PEER NGA formatından deprem adı alındı: {earthquake_name}")
                display_name = earthquake_name

            # İsim çakışmalarını önle
            display_name = self._generate_unique_name(display_name)

            # Dosya bilgileri ile birlikte kaydet
            earthquake_record = {
                'name': display_name,
                'original_filename': file_name,
                'path': file_path,
                'parameters': dialog.result,
                'processed_data': processed_data
            }

            self.loaded_earthquake_files.append(earthquake_record)
            self.processed_earthquake_data[display_name] = earthquake_record['processed_data']

            # Listbox'a ekle
            numbered_display_name = f"{len(self.loaded_earthquake_files)}. {display_name}"
            self.earthquake_listbox.insert(tk.END, numbered_display_name)

            # İlk yüklenen dosyayı otomatik seç
            if len(self.loaded_earthquake_files) == 1:
                self.earthquake_listbox.selection_set(0)
                self._on_earthquake_select(None)

            self.logger.info(f"Deprem kaydı başarıyla işlendi: {file_name}")
            return True

        except Exception as e:
            self.logger.exception(f"Dosya işleme hatası ({file_name}): {e}")
            messagebox.showerror(
                "Veri İşleme Hatası",
                f"'{file_name}' dosyası işlenirken hata oluştu:\n\n{str(e)}",
                parent=self.root
            )
            return False
    def _on_earthquake_select(self, event):
        """Deprem kaydı seçildiğinde çağrılır ve grafikleri günceller"""
        try:
            import time
            start_time = time.time()
            self.logger.debug("Deprem seçimi başlatıldı...")
            # Devam eden tablo doldurmayı iptal et (yeni seçim)
            try:
                self._cancel_table_insertion()
            except Exception:
                pass
            
            # Seçili indeksi al
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                selected_file = self.loaded_earthquake_files[index]
                selected_name = selected_file['name']
                
                # Seçili deprem bilgisini güncelle
                self.selected_earthquake_var.set(f"Seçilen: {selected_name}")
                
                # Seçilen deprem kaydının verilerini al ve grafikle
                if selected_name in self.processed_earthquake_data:
                    earthquake_data = self.processed_earthquake_data[selected_name]
                    data_size = len(earthquake_data.get('time', []))
                    self.logger.info(f"Veri boyutu: {data_size:,} nokta")
                    
                    # Grafikleri ve tabloları güncelle
                    plot_start = time.time()
                    # Eksik seriler için güvenli doldurma: sadece mevcut olanları çiz, boşları atla
                    try:
                        if isinstance(earthquake_data.get('acceleration'), (list, tuple)) and len(earthquake_data.get('acceleration', [])) == 0:
                            # acceleration tamamen yoksa, ancak velocity/displacement varsa yine de çizim/tablolar yapılabilsin
                            pass
                    except Exception:
                        pass
                    self._plot_time_series(earthquake_data)
                    # Arias grafiğini güncelle
                    try:
                        self._update_arias_plot(earthquake_data, selected_name)
                        # Arias% sekmesini de tazele
                        try:
                            self._refresh_arias_percent_tab()
                        except Exception as _e2:
                            self.logger.debug(f"Arias% sekmesi yenileme hatası: {_e2}")
                    except Exception as _e:
                        self.logger.debug(f"Arias grafiği güncellenemedi: {_e}")
                    plot_time = time.time() - plot_start
                    self.logger.debug(f"Grafik çizimi tamamlandı: {plot_time:.2f} s")
                    
                    # İstatistikleri hesapla ve göster (konsol için)
                    stats_start = time.time()
                    stats = self.earthquake_data_processor.get_time_series_stats(earthquake_data)
                    self._show_earthquake_stats(selected_name, stats)
                    stats_time = time.time() - stats_start
                    self.logger.debug(f"İstatistik hesaplama tamamlandı: {stats_time:.2f} s")
                    
                    # İstatistik panelini güncelle
                    if hasattr(self, 'stats_panel'):
                        try:
                            # Sparkline'lar için ham serileri aktar
                            try:
                                time_data = earthquake_data.get('time', [])
                                acceleration = earthquake_data.get('acceleration', [])
                                velocity = earthquake_data.get('velocity', [])
                                displacement = earthquake_data.get('displacement', [])
                                self.stats_panel.update_series(time=time_data,
                                                               acceleration=acceleration,
                                                               velocity=velocity,
                                                               displacement=displacement)
                            except Exception:
                                pass
                            self.stats_panel.update_stats(stats)
                            self.logger.debug("İstatistik paneli güncellendi")
                        except Exception as e:
                            self.logger.warning(f"İstatistik paneli güncelleme hatası: {e}")
                    
                    # ERS panelini güncelle
                    if hasattr(self, 'ers_panel') or hasattr(self, 'real_ers_panel'):
                        try:
                            time_data = earthquake_data.get('time', [])
                            acceleration = earthquake_data.get('acceleration', [])
                            dt = earthquake_data.get('dt', 0.01)
                            accel_unit = earthquake_data.get('accel_unit', 'g')
                            
                            if len(time_data) > 0 and len(acceleration) > 0:
                                for panel_attr in ("ers_panel", "real_ers_panel"):
                                    panel = getattr(self, panel_attr, None)
                                    if not panel:
                                        continue
                                    panel.update_data(
                                        time_data=time_data,
                                        acceleration=acceleration,
                                        dt=dt,
                                        accel_unit=accel_unit,
                                        record_name=selected_name
                                    )
                                self.logger.debug("ERS panelleri güncellendi")
                        except Exception as e:
                            self.logger.warning(f"ERS paneli güncelleme hatası: {e}")
                    
                    # İnteraktif grafikleri güncelle
                    if hasattr(self, 'interactive_plot'):
                        try:
                            time_data = earthquake_data.get('time', [])
                            acceleration = earthquake_data.get('acceleration', [])
                            velocity = earthquake_data.get('velocity', [])
                            displacement = earthquake_data.get('displacement', [])
                            
                            # Birim bilgilerini al
                            sel = self.earthquake_listbox.curselection()
                            if sel:
                                idx = sel[0]
                                if idx < len(self.loaded_earthquake_files):
                                    params = self.loaded_earthquake_files[idx]['parameters']
                                    accel_unit = params.get('accel_unit', 'g')
                                    velocity_unit = params.get('velocity_unit', 'cm/s')
                                    displacement_unit = params.get('displacement_unit', 'cm')
                                else:
                                    accel_unit = 'g'
                                    velocity_unit = 'cm/s'
                                    displacement_unit = 'cm'
                            else:
                                accel_unit = 'g'
                                velocity_unit = 'cm/s'
                                displacement_unit = 'cm'
                            
                            # Mevcut serilerle çiz (en azından ivme + zaman varsa; yoksa hız/yerdeğiştirme mevcutsa yine çiz)
                            if len(time_data) > 0 and (len(acceleration) > 0 or len(velocity) > 0 or len(displacement) > 0):
                                # Eksik olanlar için sıfır dizileri kullanma; plot fonksiyonu hepsini bekliyor
                                import numpy as _np
                                acc_plot = _np.asarray(acceleration) if len(acceleration) > 0 else _np.zeros(len(time_data))
                                vel_plot = _np.asarray(velocity) if len(velocity) > 0 else _np.zeros(len(time_data))
                                disp_plot = _np.asarray(displacement) if len(displacement) > 0 else _np.zeros(len(time_data))
                                self.interactive_plot.plot_time_series(
                                    time_data=time_data,
                                    accel_data=acc_plot,
                                    velocity_data=vel_plot,
                                    displacement_data=disp_plot,
                                    accel_unit=accel_unit,
                                    velocity_unit=velocity_unit,
                                    displacement_unit=displacement_unit
                                )
                                self.logger.debug("İnteraktif grafikler güncellendi (mevcut seriler ile)")
                        except Exception as e:
                            self.logger.warning(f"İnteraktif grafik güncelleme hatası: {e}")
                    
                    # Baseline correction kaldırıldı - bu kodlar artık gerekli değil
                    
                    # Baseline correction kaldırıldı - durum güncellemesi gerekli değil
                    
                    total_time = time.time() - start_time
                    self.logger.info(f"Deprem seçimi tamamlandı: {selected_name} ({total_time:.2f} s)")
                else:
                    self.logger.warning(f"Veri bulunamadı: {selected_name}")
                    self._show_empty_plots()
                
            else:
                self.selected_earthquake_var.set("Seçilen: Yok")
                self._show_empty_plots()
                if hasattr(self, 'stats_panel'):
                    self.stats_panel.clear_stats()
                # İnteraktif grafikleri de temizle
                if hasattr(self, 'interactive_plot'):
                    try:
                        self.interactive_plot.clear_plot()
                    except Exception as e:
                        self.logger.debug(f"İnteraktif grafik temizleme hatası: {e}")
                # Arias grafiÄŸini temizle
                try:
                    self._clear_arias_plot()
                except Exception as _e:
                    self.logger.debug(f"Arias grafik temizleme hatası: {_e}")
                
        except IndexError:
            self.selected_earthquake_var.set("Seçilen: Hata - geçersiz seçim")
            self._show_empty_plots()
            if hasattr(self, 'stats_panel'):
                self.stats_panel.clear_stats()
            # İnteraktif grafikleri de temizle
            if hasattr(self, 'interactive_plot'):
                try:
                    self.interactive_plot.clear_plot()
                except Exception as e:
                    self.logger.debug(f"İnteraktif grafik temizleme hatası: {e}")
            # Arias grafiÄŸini temizle
            try:
                self._clear_arias_plot()
            except Exception as _e:
                self.logger.debug(f"Arias grafik temizleme hatası: {_e}")
        except Exception as e:
            self.logger.exception(f"Deprem seçimi hatası: {e}")
            import traceback
            traceback.print_exc()
            self._show_empty_plots()
            if hasattr(self, 'stats_panel'):
                self.stats_panel.clear_stats()
            # İnteraktif grafikleri de temizle
            if hasattr(self, 'interactive_plot'):
                try:
                    self.interactive_plot.clear_plot()
                except Exception as e:
                    self.logger.debug(f"İnteraktif grafik temizleme hatası: {e}")
    
    def get_selected_earthquake_file(self) -> Optional[str]:
        """Seçili deprem kaydının dosya yolunu döndürür"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                return self.loaded_earthquake_files[index]['path']
            return None
        except:
            return None
    
    def bind_input_panel_commands(self) -> None:
        """Girdi paneli komutlarını bağlar"""
        self.input_panel.bind_load_command(self.load_data_file)
        self.input_panel.bind_calculation_command(self.run_calculation_and_plot)
        self.input_panel.bind_map_command(self.show_location_on_map)
        self.input_panel.bind_save_command(self.save_plot)
    
    def load_data_file(self) -> None:
        """AFAD veri dosyasını yükler"""
        # Reentrancy guard: dialogun iki kez açılmasını önle
        if getattr(self, '_open_dialog_running', False):
            return
        self._open_dialog_running = True
        try:
            self.logger.debug("Dosya seçme dialogu açılıyor...")
            
            # Dosya yükleme işlemi
            file_path = FileUtils.open_file_dialog(
                title="AFAD TDTH Veri Setini Seç",
                filetypes=[
                    ("Excel dosyaları", "*.xlsx"),
                    ("CSV dosyaları", "*.csv"),
                    ("Tüm dosyalar", "*.*")
                ]
            )
            
            if file_path:
                self.logger.info(f"Seçilen dosya: {file_path}")
                
                # Dosya varlığını kontrol et
                if not os.path.exists(file_path):
                    messagebox.showerror("Dosya Hatası", f"Seçilen dosya bulunamadı:\n{file_path}", parent=self.root)
                    self.input_panel.update_file_status("❌ Dosya bulunamadı.", "red")
                    return
                
                # Dosya boyutunu kontrol et
                try:
                    file_size = os.path.getsize(file_path)
                    self.logger.debug(f"Dosya boyutu: {file_size / (1024*1024):.2f} MB")
                except Exception as size_error:
                    self.logger.debug(f"Dosya boyutu okunamadı: {size_error}")
                
                # Veriyi yükle
                self.logger.info("Veri yükleme işlemi başlatılıyor...")
                loaded_df = self.data_loader.load_file(file_path)
                
                if loaded_df is not None:
                    # Başarılı yükleme
                    file_name = os.path.basename(file_path)
                    row_count = len(loaded_df)
                    col_count = len(loaded_df.columns)
                    
                    self.logger.info(f"Veri yükleme başarılı: {row_count} satır, {col_count} sütun")
                    
                    self.input_panel.update_file_status(
                        f"✅ Dosya başarıyla yüklendi: {file_name} ({row_count:,} veri noktası)", 
                        "green"
                    )
                    
                    # Hesaplama butonunu etkinleÅŸtir
                    self.input_panel.enable_calculation_button()
                    
                    # Data loaded callback'i çağır
                    if hasattr(self, '_on_data_loaded'):
                        self._on_data_loaded()
                        
                    self.logger.info("Dosya yükleme işlemi tamamlandı")
                        
                else:
                    # Yükleme hatası - DataLoader'dan None döndü
                    self.logger.warning("DataLoader None döndü")
                    self.input_panel.update_file_status(
                        "❌ Dosya formatı uygun değil veya bozuk.", 
                        "red"
                    )
            else:
                self.logger.info("Dosya seçimi iptal edildi")
            
        except Exception as e:
            error_msg = str(e)
            self.logger.exception(f"load_data_file hatası: {error_msg}")
            
            # Detaylı hata mesajı
            if "FileNotFoundError" in error_msg:
                messagebox.showerror("Dosya Hatası", f"Dosya bulunamadı:\n{error_msg}", parent=self.root)
            elif "PermissionError" in error_msg:
                messagebox.showerror("İzin Hatası", f"Dosyaya erişim izni yok:\n{error_msg}", parent=self.root)
            else:
                messagebox.showerror("Dosya Yükleme Hatası", 
                                   f"Dosya yüklenirken beklenmeyen hata oluştu:\n\n{error_msg}", parent=self.root)
            
            self.input_panel.update_file_status("❌ Dosya yükleme hatası.", "red")
        finally:
            try:
                self._open_dialog_running = False
            except Exception:
                pass
    
    def run_calculation_and_plot(self) -> None:
        """Hesaplama yapar ve grafik çizer"""
        try:
            self.logger.info("Spektrum hesaplama başlatılıyor...")
            
            # Yeni hesaplama başladı - harita ve rapor tuşlarını devre dışı bırak
            try:
                self.input_panel.disable_map_button()
                self.input_panel.disable_report_button()
            except Exception as e:
                self.logger.debug(f"Tuş devre dışı bırakma hatası: {e}")
            
            # Girdi parametrelerini al
            params = self.input_panel.get_input_parameters()
            self.logger.debug(f"Girdi parametreleri alındı: {params}")
            
            lat = float(params["lat"])
            lon = float(params["lon"])
            dd = params["earthquake_level"]
            zemin = params["soil_class"]
            
            self.logger.info(f"Koordinatlar: {lat}, {lon}, DD: {dd}, Zemin: {zemin}")
            
        except ValueError as e:
            self.logger.warning(f"Girdi hatası: {e}")
            messagebox.showerror("Geçersiz Girdi", 
                               "Lütfen enlem ve boylam için sayısal değerler girin.", parent=self.root)
            return
        except Exception as e:
            self.logger.warning(f"Parametre okuma hatası: {e}")
            messagebox.showerror("Parametre Hatası", f"Parametreler okunurken hata: {str(e)}", parent=self.root)
            return
        
        try:
            # AFAD parametrelerini al
            self.logger.info("AFAD verileri sorgulanıyor...")
            ss, s1 = self.data_processor.get_parameters_for_location(lat, lon, dd)
            if ss is None:
                self.logger.error("AFAD verileri alınamadı")
                messagebox.showerror("Veri Hatası", "AFAD verileri alınamadı. Lütfen veri dosyasının yüklendiğinden emin olun.", parent=self.root)
                return
            
            self.logger.info(f"AFAD parametreleri: SS={ss}, S1={s1}")
            
        except Exception as e:
            self.logger.exception(f"AFAD veri hatası: {e}")
            messagebox.showerror("AFAD Veri Hatası", f"AFAD verileri alınırken hata: {str(e)}", parent=self.root)
            return
        
        try:
            # Zemin katsayılarını hesapla
            self.logger.info("Zemin katsayıları hesaplanıyor...")
            fs, f1 = self.coefficient_calculator.calculate_site_coefficients(ss, s1, zemin)
            if fs is None:
                self.logger.error("Zemin katsayıları hesaplanamadı")
                return
            
            self.logger.info(f"Zemin katsayıları: Fs={fs}, F1={f1}")
            
        except Exception as e:
            self.logger.exception(f"Zemin katsayısı hatası: {e}")
            messagebox.showerror("Hesaplama Hatası", f"Zemin katsayıları hesaplanırken hata: {str(e)}", parent=self.root)
            return
        
        try:
            # Tasarım parametrelerini hesapla
            self.logger.info("Tasarım parametreleri hesaplanıyor...")
            SDS, SD1 = self.coefficient_calculator.calculate_design_parameters(ss, s1, fs, f1)
            self.logger.info(f"Tasarım parametreleri: SDS={SDS}, SD1={SD1}")
            
            # Sonuçları girdi paneline yaz
            results = {
                "ss": ss, "s1": s1, "fs": fs, "f1": f1,
                "SDS": SDS, "SD1": SD1
            }
            self.input_panel.set_results(results)
            self.logger.debug("Sonuçlar girdi paneline yazıldı")
            
        except Exception as e:
            self.logger.exception(f"Tasarım parametreleri hatası: {e}")
            messagebox.showerror("Hesaplama Hatası", f"Tasarım parametreleri hesaplanırken hata: {str(e)}", parent=self.root)
            return
        
        try:
            # Spektrum seçeneklerini al
            spectrum_options = self.input_panel.get_spectrum_options()
            self.logger.debug(f"Spektrum seçenekleri: {spectrum_options}")
            
            # Birim ayarlarını al
            unit_settings = self.input_panel.get_unit_settings()
            target_acc_unit = unit_settings["acceleration_unit"]
            target_disp_unit = unit_settings["displacement_unit"]
            self.logger.debug(f"Birim ayarları: İvme={target_acc_unit}, Yerdeğiştirme={target_disp_unit}")
            
        except Exception as e:
            self.logger.exception(f"Ayarlar okuma hatası: {e}")
            messagebox.showerror("Ayar Hatası", f"Spektrum ayarları okunurken hata: {str(e)}", parent=self.root)
            return
        
        try:
            # Spektrumları hesapla (arka planda)
            self.logger.info("Spektrumlar arka planda hesaplanıyor...")
            def _calc():
                return self.spectrum_calculator.calculate_all_spectra(
                    SDS, SD1,
                    include_horizontal=spectrum_options["horizontal"],
                    include_vertical=spectrum_options["vertical"],
                    include_displacement=spectrum_options["displacement"]
                )
            def _on_calc_done(spectrum_result):
                try:
                    self.logger.info("Spektrum hesaplaması tamamlandı")
                    self.logger.debug(f"DataFrame shape: {spectrum_result['dataframe'].shape}")
                    self.logger.debug(f"Spektrum türleri: {list(spectrum_result['spectrum_info'].keys())}")
                    # Devam: veri işleme ve çizim aynı akışla
                    self._on_spectrum_calculated(spectrum_result, target_acc_unit, target_disp_unit, spectrum_options, ss, s1, fs, f1, SDS, SD1, lat, lon, zemin, dd)
                except Exception as ie:
                    self.logger.exception(f"Hesaplama sonrası hata: {ie}")
            def _on_calc_err(err):
                self.logger.exception(f"Spektrum hesaplama hatası: {err}")
                messagebox.showerror("Spektrum Hatası", f"Spektrumlar hesaplanırken hata: {str(err)}", parent=self.root)
            self._run_in_executor(_calc, _on_calc_done, _on_calc_err)
            return
        
        except Exception as e:
            self.logger.exception(f"Spektrum hesaplama hatası: {e}")
            messagebox.showerror("Spektrum Hatası", f"Spektrumlar hesaplanırken hata: {str(e)}", parent=self.root)
            return

    def _on_spectrum_calculated(
        self,
        spectrum_result,
        target_acc_unit: str,
        target_disp_unit: str,
        spectrum_options: Dict[str, Any],
        ss: float,
        s1: float,
        fs: float,
        f1: float,
        SDS: float,
        SD1: float,
        lat: float,
        lon: float,
        zemin: str,
        dd: str,
    ) -> None:
        """Arka plan spektrum hesaplaması tamamlandığında UI güncellemelerini yapar."""
        try:
            # Orijinal sonucu koru ve periyot dizisini merkezî kaynak olarak sakla
            original_result = spectrum_result
            self._last_period_array = original_result['period_array']

            # Birim dönüştürme gerekiyorsa orijinal sonuç üzerinden uygula
            if target_acc_unit != 'g' or target_disp_unit != 'cm':
                self.logger.info("Birim dönüştürme uygulanıyor...")
                spectrum_result = self._apply_unit_conversion(original_result, target_acc_unit, target_disp_unit)
                self.logger.info("Birim dönüştürme tamamlandı")

            # Sonuçları sakla: all_data/spectrum_info (gerekirse dönüştürülmüş),
            # original_* ise daima orijinal (g/cm) sonuçtan
            self.spectrum_data = {
                'all_data': spectrum_result['dataframe'],
                'spectrum_info': spectrum_result['spectrum_info'],
                'original_data': original_result['dataframe'].copy(),
                'original_spectrum_info': original_result['spectrum_info'].copy()
            }
            self.logger.debug("Spektrum verileri saklandı")

        except Exception as e:
            self.logger.exception(f"Veri işleme hatası: {e}")
            messagebox.showerror("Veri İşleme Hatası", f"Veriler işlenirken hata: {str(e)}", parent=self.root)
            return

        try:
            # Grafik çiz
            self.logger.info("Grafikler çiziliyor...")
            if not hasattr(self, 'plot_panel') or self.plot_panel is None:
                self.logger.error("Plot panel bulunamadı!")
                messagebox.showerror("Grafik Hatası", "Grafik paneli bulunamadı!", parent=self.root)
                return

            self.plot_panel.plot_spectra(spectrum_result, spectrum_options)
            self.logger.info("Grafikler başarıyla çizildi")

        except Exception as e:
            self.logger.exception(f"Grafik çizme hatası: {e}")
            messagebox.showerror("Grafik Hatası", f"Grafikler çizilirken hata: {str(e)}", parent=self.root)
            # Grafik hatası olsa bile veri tablosunu güncellemeye devam et

        try:
            # Veri tablolarını güncelle
            self.logger.info("Veri tabloları güncelleniyor...")
            if hasattr(self, 'data_table') and self.data_table is not None:
                self.data_table.set_dataframe(spectrum_result['dataframe'])
                self.logger.info("Veri tabloları güncellendi")
                # PEER aktarım butonunu aktif et
                try:
                    self.input_panel.enable_peer_export_button()
                except Exception:
                    pass
            else:
                self.logger.warning("Veri tablosu bulunamadı")

        except Exception as e:
            self.logger.exception(f"Tablo güncelleme hatası: {e}")
            messagebox.showerror("Tablo Hatası", f"Veri tabloları güncellenirken hata: {str(e)}", parent=self.root)

        self.logger.info("Spektrum hesaplama işlemi tamamlandı!")

        # Hesaplama sonuçlarını sakla (PDF raporu için gerekli)
        self.calculation_results = {
            'Ss': ss,
            'S1': s1,
            'Fs': fs,
            'F1': f1,
            'SDS': SDS,
            'SD1': SD1,
            'soil_class': zemin,
            'earthquake_level': dd,
            'latitude': lat,
            'longitude': lon,
            'spectrum_data': spectrum_result,
            'calculation_timestamp': time.time()
        }
        self.logger.info("Hesaplama sonuçları saklandı (PDF raporu için hazır)")

        # Spektrum hesaplama tamamlandı - harita, rapor ve grafik kaydet tuşlarını aktif et
        try:
            self.input_panel.enable_map_button()
            self.input_panel.enable_report_button()
            self.input_panel.enable_save_button()
        except Exception as e:
            self.logger.debug(f"Tuş aktifleştirme hatası: {e}")
        
        try:
            # Grafik çiz
            self.logger.info("Grafikler çiziliyor...")
            if not hasattr(self, 'plot_panel') or self.plot_panel is None:
                self.logger.error("Plot panel bulunamadı!")
                messagebox.showerror("Grafik Hatası", "Grafik paneli bulunamadı!", parent=self.root)
                return
                
            self.plot_panel.plot_spectra(spectrum_result, spectrum_options)
            self.logger.info("Grafikler başarıyla çizildi")
            
        except Exception as e:
            self.logger.exception(f"Grafik çizme hatası: {e}")
            messagebox.showerror("Grafik Hatası", f"Grafikler çizilirken hata: {str(e)}", parent=self.root)
            # Grafik hatası olsa bile veri tablosunu güncellemeye devam et
        
        try:
            # Veri tablolarını güncelle
            self.logger.info("Veri tabloları güncelleniyor...")
            if hasattr(self, 'data_table') and self.data_table is not None:
                self.data_table.set_dataframe(spectrum_result['dataframe'])
                self.logger.info("Veri tabloları güncellendi")
                # PEER aktarım butonunu aktif et
                try:
                    self.input_panel.enable_peer_export_button()
                except Exception:
                    pass
            else:
                self.logger.warning("Veri tablosu bulunamadı")
                
        except Exception as e:
            self.logger.exception(f"Tablo güncelleme hatası: {e}")
            messagebox.showerror("Tablo Hatası", f"Veri tabloları güncellenirken hata: {str(e)}")
        
        self.logger.info("Spektrum hesaplama işlemi tamamlandı!")
        
        # Hesaplama sonuçlarını sakla (PDF raporu için gerekli)
        self.calculation_results = {
            'Ss': ss,
            'S1': s1,
            'Fs': fs,
            'F1': f1,
            'SDS': SDS,
            'SD1': SD1,
            'soil_class': zemin,
            'earthquake_level': dd,
            'latitude': lat,
            'longitude': lon,
            'spectrum_data': spectrum_result,
            'calculation_timestamp': time.time()
        }
        self.logger.info("Hesaplama sonuçları saklandı (PDF raporu için hazır)")
        
        # Spektrum hesaplama tamamlandı - harita, rapor ve grafik kaydet tuşlarını aktif et
        try:
            self.input_panel.enable_map_button()
            self.input_panel.enable_report_button()
            self.input_panel.enable_save_button()
        except Exception as e:
            self.logger.debug(f"Tuş aktifleştirme hatası: {e}")

    # def export_peer_user_defined_spectrum(self) -> None:
    #     """
    #     Spektrum verilerini kullanıcıdan alınan bir çarpan katsayısı ile
    #     çarparak PEER CSV formatında dışa aktarır.
    #     """
    #     try:
    #         from tkinter import messagebox
    #         from src.utils.file_utils import FileUtils
    #         # Daha önce oluşturduğumuz modern diyalog sınıfını import ediyoruz
    #         # (Aynı dosyadaysa import'a gerek yok)

    #         # 1. VERİ KONTROLÜ
    #         if not hasattr(self, 'spectrum_data') or not self.spectrum_data:
    #             messagebox.showwarning("Veri Yok", "Önce spektrumları hesaplayın.", parent=self.root)
    #             return

    #         # 2. MODERN DİALOGU AÇ (Kullanıcıdan Çarpan Katsayısını Al)
    #         dialog = PeerExportDialog(self.root)
    #         multiplier = dialog.get_result()

    #         # Kullanıcı "İptal"e bastıysa işlemi durdur
    #         if multiplier is None:
    #             return

    #         # 3. VERİLERİ HAZIRLA
    #         spectrum_info = self.spectrum_data.get('spectrum_info', {})
    #         horizontal_info = spectrum_info.get('horizontal') if isinstance(spectrum_info, dict) else None
            
    #         if not horizontal_info or 'data' not in horizontal_info:
    #             messagebox.showwarning("Veri Yok", "Yatay spektral ivme verisi bulunamadı.", parent=self.root)
    #             return

    #         period_values = getattr(self, '_last_period_array', None)
    #         acceleration_values = horizontal_info.get('data')
    #         acc_unit = horizontal_info.get('unit', 'g')

    #         # Periyot değerleri yoksa DataFrame'den çekmeyi dene
    #         if period_values is None:
    #             df = self.spectrum_data.get('all_data')
    #             if df is not None:
    #                 period_values = df.index.values

    #         if period_values is None or len(acceleration_values) == 0:
    #             messagebox.showwarning("Hata", "Dışa aktarılacak veri seti eksik.", parent=self.root)
    #             return

    #         # Uzunluk eşitleme
    #         n = min(len(period_values), len(acceleration_values))
    #         period_values = period_values[:n]
    #         acceleration_values = acceleration_values[:n]

    #         # 4. KAYDETME DİALOGU (Dosya Yolu Seçimi)
    #         file_path = FileUtils.save_file_dialog(
    #             title="PEER Kullanıcı Tanımlı Spektrumu Kaydet",
    #             filetypes=[("CSV dosyası", "*.csv")],
    #             default_extension=".csv",
    #             parent=self.root
    #         )
            
    #         if not file_path:
    #             return

    #         # 5. CSV YAZMA (Çarpan Katsayısını Burada Uyguluyoruz)
    #         lines = [
    #             "User Defined Spectrum,",
    #             f"Multiplier Factor: {multiplier},", # Hangi katsayıyla çarpıldığını not düşüyoruz
    #             f"T (s),Sa ({acc_unit})"
    #         ]

    #         for t, sa in zip(period_values, acceleration_values):
    #             # ÖNEMLİ: İvme değerini (Sa) kullanıcının girdiği çarpanla çarpıyoruz
    #             scaled_sa = sa * multiplier
    #             lines.append(f"{t:.6g},{scaled_sa:.6g}")

    #         with open(file_path, 'w', encoding='utf-8') as f:
    #             for line in lines:
    #                 f.write(line + '\n')

    #         messagebox.showinfo("Başarılı", f"Spektrum {multiplier} katsayısı ile çarpılarak kaydedildi.", parent=self.root)

    #     except Exception as e:
    #         messagebox.showerror("Aktarım Hatası", f"Hata oluştu: {str(e)}", parent=self.root)
    #         if hasattr(self, 'logger'):
    #             self.logger.exception(f"PEER export error: {e}")
    
    
    def export_peer_user_defined_spectrum(self) -> None:
        """
        Spektrum verilerini kullanıcıdan alınan bir çarpan katsayısı ile
        Y eksenini (Sa) çarparak PEER CSV formatında dışa aktarır.
        """
        try:
            from tkinter import messagebox
            from src.utils.file_utils import FileUtils

            # 1. VERİ KONTROLÜ
            if not hasattr(self, 'spectrum_data') or not self.spectrum_data:
                messagebox.showwarning("Veri Yok", "Önce spektrumları hesaplayın.", parent=self.root)
                return

            # 2. POP-UP DİALOGU AÇ
            dialog = PeerExportDialog(self.root)
            multiplier = dialog.get_result()

            # İptal basıldıysa multiplier None döner, işlemi durdur
            if multiplier is None:
                return

            # 3. VERİLERİ HAZIRLA
            spectrum_info = self.spectrum_data.get('spectrum_info', {})
            horizontal_info = spectrum_info.get('horizontal') if isinstance(spectrum_info, dict) else None
            
            if not horizontal_info or 'data' not in horizontal_info:
                messagebox.showwarning("Veri Yok", "Yatay spektral ivme verisi bulunamadı.", parent=self.root)
                return

            period_values = getattr(self, '_last_period_array', None)
            acceleration_values = horizontal_info.get('data') # Y EKSENİ KAYNAĞI
            acc_unit = horizontal_info.get('unit', 'g')

            if period_values is None:
                df = self.spectrum_data.get('all_data')
                if df is not None:
                    period_values = df.index.values

            if period_values is None or len(acceleration_values) == 0:
                messagebox.showwarning("Hata", "Dışa aktarılacak veri seti eksik.", parent=self.root)
                return

            # Uzunluk eşitleme
            n = min(len(period_values), len(acceleration_values))
            period_values = period_values[:n]
            acceleration_values = acceleration_values[:n]

            # 4. KAYDETME DİALOGU
            file_path = FileUtils.save_file_dialog(
                title="PEER Kullanıcı Tanımlı Spektrumu Kaydet",
                filetypes=[("CSV dosyası", "*.csv")],
                default_extension=".csv",
                parent=self.root
            )
            
            if not file_path:
                return

            # 5. CSV YAZMA
            lines = [
                "User Defined Spectrum,",
                f"T (s),Sa ({acc_unit})" # Başlığa multiplier eklemiyoruz, PEER formatı temiz kalsın
            ]

            # X ekseni (t) sabit kalıyor, Y ekseni (sa) multiplier ile çarpılıyor
            for t, sa in zip(period_values, acceleration_values):
                scaled_sa = sa * multiplier 
                lines.append(f"{t:.6g},{scaled_sa:.6g}")

            with open(file_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    f.write(line + '\n')

            messagebox.showinfo("Başarılı", f"Spektrum CSV olarak kaydedildi. (Çarpan: {multiplier})", parent=self.root)

        except Exception as e:
            messagebox.showerror("Aktarım Hatası", f"Hata oluştu: {str(e)}", parent=self.root)
            if hasattr(self, 'logger'):
                self.logger.exception(f"PEER export error: {e}")
    
    def _apply_unit_conversion(self, spectrum_result: Dict[str, Any], target_acc_unit: str, target_disp_unit: str) -> Dict[str, Any]:
        """Spektrum sonuçlarına birim dönüştürme uygular"""
        # DataFrame'i dönüştür
        converted_df = UnitConverter.convert_spectrum_dataframe(
            spectrum_result['dataframe'], 
            target_acc_unit, 
            target_disp_unit
        )
        
        # Spectrum info verilerini de dönüştür
        converted_spectrum_info = {}
        
        for spectrum_type, info in spectrum_result['spectrum_info'].items():
            converted_info = info.copy()
            
            # Birim bilgisini güncelle
            if spectrum_type in ['horizontal', 'vertical']:
                converted_info['unit'] = target_acc_unit
            elif spectrum_type == 'displacement':
                converted_info['unit'] = target_disp_unit
            
            # İvme spektrumları için dönüştürme
            if spectrum_type in ['horizontal', 'vertical'] and target_acc_unit != 'g':
                converted_data = UnitConverter.convert_acceleration(
                    info['data'], 'g', target_acc_unit
                )
                converted_info['data'] = converted_data
                
                # SDS değerini de dönüştür
                if 'SDS' in converted_info:
                    converted_info['SDS'] = UnitConverter.convert_acceleration(
                        converted_info['SDS'], 'g', target_acc_unit
                    )
                
                # Vertical spektrum için SDS_eff değerini de dönüştür
                if 'SDS_eff' in converted_info:
                    converted_info['SDS_eff'] = UnitConverter.convert_acceleration(
                        converted_info['SDS_eff'], 'g', target_acc_unit
                    )
                
                # SD1 değerini de dönüştür (yatay spektrum için)
                if spectrum_type == 'horizontal' and 'SD1' in converted_info:
                    converted_info['SD1'] = UnitConverter.convert_acceleration(
                        converted_info['SD1'], 'g', target_acc_unit
                    )
            
            # Yerdeğiştirme spektrumu için dönüştürme
            elif spectrum_type == 'displacement' and target_disp_unit != 'cm':
                converted_data = UnitConverter.convert_displacement(
                    info['data'], 'cm', target_disp_unit
                )
                converted_info['data'] = converted_data
            
            converted_spectrum_info[spectrum_type] = converted_info
        
        return {
            'dataframe': converted_df,
            'period_array': spectrum_result['period_array'],
            'spectrum_info': converted_spectrum_info
        }
    
    def show_location_on_map(self) -> None:
        """Konumu haritada gösterir (HIZLI CACHE sistemi)"""
        try:
            self.logger.info("Hızlı harita yükleme başlatılıyor...")
            map_start_time = time.time()
            
            # Girdi parametrelerini al
            params = self.input_panel.get_input_parameters()
            lat = float(params["lat"])
            lon = float(params["lon"])
            earthquake_level = params["earthquake_level"]
            soil_class = params["soil_class"]
            
            # Cache key oluÅŸtur
            cache_key = f"map_{lat}_{lon}_{earthquake_level}_{soil_class}"
            current_params = (lat, lon, earthquake_level, soil_class)
            
            # âš¡ Cache'den deÄŸerleri al veya hesapla
            sds_value = None
            afad_pga_value = None
            
            if (cache_key in self._map_value_cache and 
                self._last_calculated_params == current_params and 
                hasattr(self, 'spectrum_data') and self.spectrum_data):
                
                # Cache hit - deÄŸerleri direkt al
                cached_values = self._map_value_cache[cache_key]
                sds_value = cached_values.get('sds_value')
                afad_pga_value = cached_values.get('afad_pga_value')
                self.logger.debug(f"DeÄŸer cache HIT: SDS={sds_value:.4f}g, PGA={afad_pga_value:.4f}g")
                
            else:
                # Cache miss - deÄŸerleri hesapla
                self.logger.debug("Değer cache MISS - hesaplanıyor...")
                
                # SDS değerini spektrum sonuçlarından al
                try:
                    if hasattr(self, 'spectrum_data') and self.spectrum_data:
                        spectrum_info = self.spectrum_data.get('spectrum_info', {})
                        horizontal_info = spectrum_info.get('horizontal', {})
                        if 'SDS' in horizontal_info:
                            sds_value = horizontal_info['SDS']
                            self.logger.debug(f"SDS deÄŸeri bulundu: {sds_value:.4f} g")
                        
                except Exception as e:
                    self.logger.exception(f"SDS değeri alma hatası: {e}")
                    sds_value = None
            
                # AFAD PGA deÄŸer alma (sadece cache miss durumunda)
                try:
                    if (hasattr(self, 'data_processor') and self.data_processor and
                        hasattr(self.data_processor, 'data_loader') and 
                        self.data_processor.data_loader and 
                        self.data_processor.data_loader.is_data_loaded()):
                        
                        afad_pga_value = self.data_processor.data_loader.get_closest_pga_value(
                            lat, lon, earthquake_level
                        )
                        if afad_pga_value is not None:
                            self.logger.debug(f"AFAD PGA deÄŸeri bulundu: {afad_pga_value:.4f} g")
                        
                except Exception as e:
                    self.logger.exception(f"AFAD PGA değeri alma hatası: {e}")
                    afad_pga_value = None
                
                # âš¡ DeÄŸerleri cache'e kaydet
                self._map_value_cache[cache_key] = {
                    'sds_value': sds_value,
                    'afad_pga_value': afad_pga_value
                }
                self._last_calculated_params = current_params
                self.logger.debug("DeÄŸerler cache'e kaydedildi")
            
            # Koordinatın Türkiye sınırları içinde olup olmadığını kontrol et
            if not MapUtils.is_in_turkey(lat, lon):
                bounds = MapUtils.get_turkey_bounds()
                messagebox.showwarning(
                    "Koordinat Uyarısı", 
                    f"Girilen koordinat Türkiye sınırları dışında!\n\n"
                    f"Türkiye koordinat sınırları:\n"
                    f"• Enlem: {bounds['min_lat']}° - {bounds['max_lat']}°\n"
                    f"• Boylam: {bounds['min_lon']}° - {bounds['max_lon']}°\n\n"
                    f"Harita yine de gösterilecek, ancak Türkiye odaklı olacak.",
                    parent=self.root
                )
            
            # PGA GeoJSON grid verilerini al
            geojson_data = None
            try:
                if hasattr(self, 'data_processor') and self.data_processor:
                    # DataProcessor'daki data_loader'dan GeoJSON grid verilerini al
                    if (hasattr(self.data_processor, 'data_loader') and 
                        self.data_processor.data_loader and 
                        self.data_processor.data_loader.is_data_loaded()):
                        
                        geojson_data = self.data_processor.data_loader.create_geojson_grid(
                            earthquake_level, 
                            cell_size=0.1  # Grid hücre boyutu (derece)
                        )
                        if geojson_data and geojson_data.get('features'):
                            self.logger.debug(f"GeoJSON grid verisi hazır: {len(geojson_data['features'])} poligon ({earthquake_level})")
                        else:
                            self.logger.warning("GeoJSON grid verisi bulunamadı veya yüklenemedi")
                    else:
                        self.logger.warning("AFAD veri seti yüklenmemiş - PGA grid katmanı eklenmeyecek")
                else:
                    self.logger.warning("Data processor bulunamadı - PGA grid katmanı eklenmeyecek")
            except Exception as e:
                self.logger.exception(f"GeoJSON grid veri hazırlama hatası: {e}")
                geojson_data = None
            
            # Folium kontrolü
            if not MapUtils.is_folium_available():
                messagebox.showerror("Kütüphane Eksik", 
                                   "Harita özelliği için 'folium' kütüphanesini kurun.\n"
                                   "Kurulum: pip install folium", parent=self.root)
                return
            
            # Harita oluştur ve göster (arka planda)
            def _mkmap():
                return MapUtils.create_location_map(lat, lon, earthquake_level, soil_class, geojson_data, sds_value, afad_pga_value)
            def _on_map_done(success):
                total_time = time.time() - map_start_time
                if success:
                    grid_info = f" + {len(geojson_data['features'])} PGA poligonu" if geojson_data and geojson_data.get('features') else ""
                    self.logger.info(f"Harita gösterildi: {lat}, {lon} - {earthquake_level}, {soil_class}{grid_info}")
                    self.logger.info(f"Toplam harita yükleme süresi: {total_time:.2f} s")
                else:
                    messagebox.showwarning("Uyarı", "Harita oluşturulamadı.", parent=self.root)
            self._run_in_executor(_mkmap, _on_map_done, lambda e: self.logger.exception(e))
            return
                
        except ValueError:
            messagebox.showerror("Geçersiz Koordinat", "Lütfen geçerli enlem ve boylam değerleri girin.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Harita Hatası", f"Harita oluşturulurken hata: {str(e)}", parent=self.root)
            self.logger.exception(f"Harita hatası: {e}")
    
    def clear_map_cache(self) -> None:
        """Harita deÄŸer cache'ini temizler"""
        self._map_value_cache.clear()
        self._last_calculated_params = None
        self.logger.info("Harita deÄŸer cache'i temizlendi")
    
    def save_plot(self) -> None:
        """Grafikleri dosya olarak kaydeder.

        Ağır savefig çağrılarının UI'yı kilitlememesi için dosya yazma işlemlerini
        arka plana taşır. UI dialogları ve bbox hesaplarını ana threade bırakır.
        """
        try:
            plotted_axes = self.plot_panel.get_plotted_axes()
            if not plotted_axes:
                messagebox.showwarning("Grafik Yok", "Kaydedilecek bir grafik oluşturulmadı.", parent=self.root)
                return

            figure = self.plot_panel.get_figure()
            if figure is None:
                messagebox.showerror("Grafik Hatası", "Kaydedilecek grafik bulunamadı.", parent=self.root)
                return

            available_graphs = list(plotted_axes.keys())
            dialog = SaveDialog(self.root, available_graphs)
            result = dialog.result
            if not result:
                return

            def _set_status(text: str):
                try:
                    if hasattr(self, "status_var") and self.status_var:
                        self.status_var.set(text)
                except Exception:
                    pass

            if result["mode"] == "birlikte":
                save_options = self._ask_quick_save_options(default_format='png', default_dpi=300)
                if not save_options:
                    return
                filetypes = [(save_options['format'].upper() + " dosyası", f"*.{save_options['format']}")]
                file_path = FileUtils.save_file_dialog(
                    title="Tüm Grafikleri Birlikte Kaydet",
                    filetypes=filetypes,
                    default_extension=f".{save_options['format']}",
                    parent=self.root
                )
                if not file_path:
                    return

                def _do_save_all():
                    figure.savefig(
                        file_path,
                        dpi=save_options['dpi'],
                        bbox_inches='tight',
                        facecolor='white',
                        edgecolor='none'
                    )
                    return file_path

                def _on_all_saved(_):
                    try:
                        messagebox.showinfo("Başarılı", f"Grafik başarıyla kaydedildi:\n{file_path}", parent=self.root)
                    except Exception:
                        pass
                    self.logger.info(f"Tüm grafikler kaydedildi: {file_path}")
                    _set_status(f"Grafikler kaydedildi: {os.path.basename(file_path)}")

                def _on_all_error(err):
                    messagebox.showerror("Kaydetme Hatası", f"Grafik kaydedilirken hata: {err}", parent=self.root)
                    self.logger.exception(f"Grafik kaydetme hatası: {err}")
                    _set_status("Grafik kaydedilemedi")

                _set_status("Grafikler kaydediliyor...")
                executor = getattr(self, "_executor", None)
                if executor:
                    future = executor.submit(_do_save_all)
                    def _poll_all():
                        if future.done():
                            try:
                                res = future.result()
                            except Exception as exc:
                                _on_all_error(exc)
                            else:
                                _on_all_saved(res)
                        else:
                            try:
                                self.root.after(80, _poll_all)
                            except Exception:
                                pass
                    try:
                        self.root.after(60, _poll_all)
                    except Exception:
                        pass
                else:
                    try:
                        _on_all_saved(_do_save_all())
                    except Exception as exc:
                        _on_all_error(exc)

            elif result["mode"] == "ayri":
                dir_path = FileUtils.select_directory(
                    title="Grafikleri Kaydetmek İçin Klasör Seçin",
                    parent=self.root
                )
                if not dir_path:
                    return

                selected_graphs = result.get("graphs") or []
                if not selected_graphs:
                    messagebox.showwarning("Uyarı", "Kaydedilecek grafik seçilmedi.", parent=self.root)
                    return

                save_options = self._ask_quick_save_options(default_format='png', default_dpi=300)
                if not save_options:
                    return

                try:
                    figure.canvas.draw()
                    renderer = figure.canvas.get_renderer()
                except Exception:
                    renderer = None

                bbox_map = {}
                for graph_name in selected_graphs:
                    ax = plotted_axes.get(graph_name)
                    if not ax:
                        continue
                    try:
                        bbox = ax.get_tightbbox(renderer) if renderer is not None else None
                        bbox_inches = bbox.transformed(figure.dpi_scale_trans.inverted()) if bbox else 'tight'
                        bbox_map[graph_name] = bbox_inches
                    except Exception as ex:
                        self.logger.debug(f"{graph_name} bbox hesaplanamadı: {ex}")
                        bbox_map[graph_name] = 'tight'

                base_name = "spektrum"

                def _do_save_each():
                    saved_files = []
                    for graph_name in selected_graphs:
                        ax = plotted_axes.get(graph_name)
                        if not ax:
                            continue
                        file_name = f"{base_name}_{graph_name.lower().replace(' ', '_')}.{save_options['format']}"
                        full_path = os.path.join(dir_path, file_name)
                        figure.savefig(
                            full_path,
                            dpi=save_options['dpi'],
                            bbox_inches=bbox_map.get(graph_name, 'tight'),
                            facecolor='white',
                            edgecolor='none'
                        )
                        saved_files.append(full_path)
                    if not saved_files:
                        raise RuntimeError("Hiçbir grafik kaydedilemedi.")
                    return saved_files

                def _on_each_saved(files):
                    try:
                        messagebox.showinfo(
                            "Başarılı",
                            "Seçilen grafikler ayrı ayrı kaydedildi:\n" +
                            "\n".join([os.path.basename(f) for f in files]),
                            parent=self.root
                        )
                    except Exception:
                        pass
                    self.logger.info(f"{len(files)} grafik ayrı ayrı kaydedildi")
                    _set_status(f"{len(files)} grafik kaydedildi")

                def _on_each_error(err):
                    messagebox.showerror("Kaydetme Hatası", f"Grafik kaydedilirken hata: {err}", parent=self.root)
                    self.logger.exception(f"Grafik kaydetme hatası: {err}")
                    _set_status("Grafik kaydedilemedi")

                _set_status("Grafikler kaydediliyor...")
                executor = getattr(self, "_executor", None)
                if executor:
                    future = executor.submit(_do_save_each)
                    def _poll_each():
                        if future.done():
                            try:
                                res = future.result()
                            except Exception as exc:
                                _on_each_error(exc)
                            else:
                                _on_each_saved(res)
                        else:
                            try:
                                self.root.after(80, _poll_each)
                            except Exception:
                                pass
                    try:
                        self.root.after(60, _poll_each)
                    except Exception:
                        pass
                else:
                    try:
                        _on_each_saved(_do_save_each())
                    except Exception as exc:
                        _on_each_error(exc)

        except Exception as e:
            messagebox.showerror("Kaydetme Hatası", f"Grafik kaydedilirken hata: {str(e)}", parent=self.root)
            self.logger.exception(f"Grafik kaydetme hatası: {e}")

    def generate_pdf_report(self) -> None:
        """PDF raporu oluÅŸturur"""
        try:
            # Hesaplama sonuçları var mı kontrol et
            if not hasattr(self, 'calculation_results') or not self.calculation_results:
                messagebox.showwarning("Uyarı", "Rapor oluşturma için önce hesaplama yapılmalıdır.", parent=self.root)
                return
            
            # Dosya kaydetme dialogu göster
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="PDF Raporu Kaydet",
                defaultextension=".pdf",
                filetypes=[("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")]
            )
            
            if not file_path:
                return  # Kullanıcı iptal etti
            
            # Girdi parametrelerini al
            input_params = self.input_panel.get_input_parameters()
            
            # Spektrum verilerini hazırla
            spectrum_data = {}
            if hasattr(self, 'spectrum_data') and self.spectrum_data:
                spectrum_data = self.spectrum_data
            
            # Mevcut grafik figure'ını al
            current_figure = None
            if hasattr(self.plot_panel, 'fig') and self.plot_panel.fig:
                current_figure = self.plot_panel.fig
            
            # PDF rapor oluÅŸturucuyu baÅŸlat
            pdf_generator = PDFReportGenerator()
            
            # Raporu oluÅŸtur
            success = pdf_generator.generate_report(
                output_path=file_path,
                spectrum_data=spectrum_data,
                input_params=input_params,
                calculation_results=self.calculation_results,
                plot_figure=current_figure
            )
            
            actual_path = getattr(pdf_generator, "last_output_path", file_path)
            if success:
                messagebox.showinfo("Başarılı", f"PDF raporu başarıyla oluşturuldu:\n{actual_path}", parent=self.root)
                self.logger.info(f"PDF raporu oluşturuldu: {actual_path}")
            else:
                messagebox.showerror("Hata", "PDF raporu oluÅŸturulurken hata oluÅŸtu.", parent=self.root)
                self.logger.error("PDF raporu oluşturulamadı")
                
        except Exception as e:
            messagebox.showerror("Rapor Hatası", f"PDF raporu oluşturulurken hata: {str(e)}", parent=self.root)
            self.logger.exception(f"PDF rapor hatası: {e}")
    
    def _setup_keyboard_handlers(self) -> None:
        """Klavye kısayolları handler'larını kurar"""
        # Handler'ları kaydet
        self.keyboard_manager.register_handler('open_file', self.load_data_file)
        self.keyboard_manager.register_handler('save_graph', self.save_plot)
        self.keyboard_manager.register_handler('run_calculation', self.run_calculation_and_plot)
        self.keyboard_manager.register_handler('show_map', self.show_location_on_map)
        self.keyboard_manager.register_handler('export_data', self._export_data_shortcut)
        self.keyboard_manager.register_handler('copy_data', self._copy_data_shortcut)
        self.keyboard_manager.register_handler('refresh', self._refresh_interface)
    
    def _export_data_shortcut(self) -> None:
        """Ctrl+E: Verileri dışa aktırır"""
        if self.data_table:
            self.data_table.export_to_excel()
    
    def _copy_data_shortcut(self) -> None:
        """Ctrl+C: Verileri panoya kopyalar"""
        if self.data_table:
            self.data_table.copy_to_clipboard()
    
    def _refresh_interface(self) -> None:
        """F5: Arayüzü yeniler"""
        # Mevcut hesaplamaları tekrarla
        if hasattr(self, 'spectrum_data') and self.spectrum_data:
            try:
                params = self.input_panel.get_input_parameters()
                if params["lat"] and params["lon"]:
                    self.run_calculation_and_plot()
            except:
                pass
    
    def _on_data_loaded(self) -> None:
        """Veri yüklendiğinde çağrılacak callback fonksiyonu"""
        # Hesaplama butonunu etkinleÅŸtir
        self.input_panel.enable_calculation_button()
        self.logger.info("Veri başarıyla yüklendi!")
    
    def _on_unit_change(self, new_acc_unit: str, new_disp_unit: str) -> None:
        """Birim değişikliği olduğunda çağrılır"""
        # Mevcut spektrum verisi varsa güncelle
        if hasattr(self, 'spectrum_data') and self.spectrum_data and 'original_data' in self.spectrum_data:
            try:
                # ORIJINAL verilerden yeni birimlere dönüştür (daha güvenli)
                original_df = self.spectrum_data['original_data']
                original_spectrum_info = self.spectrum_data['original_spectrum_info']
                
                # Orijinal spectrum_result oluştur (periyot için merkezi kaynak olarak _last_period_array)
                period_array = self._last_period_array if hasattr(self, '_last_period_array') and self._last_period_array is not None else None
                if period_array is None:
                    try:
                        period_array = original_df.index.values
                        self._last_period_array = period_array
                    except Exception:
                        period_array = None
                original_spectrum_result = {
                    'dataframe': original_df,
                    'spectrum_info': original_spectrum_info,
                    'period_array': period_array
                }
                
                # Birim dönüştürme uygula (orijinalden hedefe)
                converted_result = self._apply_unit_conversion(original_spectrum_result, new_acc_unit, new_disp_unit)
                
                # Güncellenmiş verileri sakla
                self.spectrum_data['all_data'] = converted_result['dataframe']
                self.spectrum_data['spectrum_info'] = converted_result['spectrum_info']
                
                # Spektrum seçeneklerini al
                spectrum_options = self.input_panel.get_spectrum_options()
                
                # Grafikleri yeniden çiz (güncellenmiş birim bilgileriyle)
                self.plot_panel.plot_spectra(converted_result, spectrum_options)
                
                # Tabloyu güncelle (aynı converted DataFrame ile)
                self.data_table.set_dataframe(converted_result['dataframe'])
                
                # Başarı mesajı (opsiyonel - kullanıcı deneyimi için)
                self.logger.info(f"Birimler güncellendi: İvme ({new_acc_unit}), Yerdeğiştirme ({new_disp_unit})")
                
            except Exception as e:
                self.logger.exception(f"Birim dönüştürme hatası: {e}")
                # Hata durumunda kullanıcıyı uyar
                messagebox.showwarning("Birim Dönüştürme Hatası", 
                                     "Birim dönüştürme sırasında bir hata oluştu. Lütfen tekrar hesaplama yapın.", parent=self.root)
        else:
            # Henüz hesaplama yapılmamışsa sadık bilgilendirici mesaj
            self.logger.info("Birim ayarları güncellendi. Yeni hesaplamalar bu birimlerle yapılacak.") 

    def _show_earthquake_stats(self, earthquake_name: str, stats: Dict[str, Any]) -> None:
        """Deprem kaydı istatistiklerini konsola yazdırır"""
        self.logger.info(f"\n{earthquake_name} İstatistikleri:")
        self.logger.info(f"   Süre: {stats.get('duration', 0):.2f} s")
        self.logger.info(f"   Veri noktası: {stats.get('num_points', 0)}")
        
        if 'acceleration' in stats:
            acc_stats = stats['acceleration']
            self.logger.info(f"   İvme - Max: {acc_stats['peak']:.4f} g")
            
        if 'velocity' in stats:
            vel_stats = stats['velocity']
            self.logger.info(f"   Hız - Max: {vel_stats['peak']:.2f} cm/s")
            
        if 'displacement' in stats:
            disp_stats = stats['displacement']
            self.logger.info(f"   Yerdeğiştirme - Max: {disp_stats['peak']:.2f} cm")

    def _clear_data_tables(self) -> None:
        """Tüm veri tablolarını temizler"""
        try:
            # Tüm tabloları temizle
            if getattr(self, 'accel_tree', None) and self._widget_exists(self.accel_tree):
                for item in self.accel_tree.get_children():
                    self.accel_tree.delete(item)
            
            if getattr(self, 'velocity_tree', None) and self._widget_exists(self.velocity_tree):
                for item in self.velocity_tree.get_children():
                    self.velocity_tree.delete(item)
                
            if getattr(self, 'displacement_tree', None) and self._widget_exists(self.displacement_tree):
                for item in self.displacement_tree.get_children():
                    self.displacement_tree.delete(item)
                
        except Exception as e:
            self.logger.debug(f"Tablo temizleme hatası: {e}")

    def _populate_data_tables(self, time_data, accel_data, velocity_data, displacement_data) -> None:
        """Tabloları zaman serisi verileriyle donmadan doldurur (artımlı + iptal edilebilir)."""
        try:
            # Meşgul imleç ve durum
            try:
                self.root.config(cursor="watch")
                if getattr(self, 'status_var', None):
                    self.status_var.set("Veriler tabloya aktarılıyor…")
                self.root.update_idletasks()
            except Exception:
                pass

            # Yeni bir doldurma başlarken varsa önceki işi iptal et
            if hasattr(self, '_table_insert_job') and self._table_insert_job:
                try:
                    self.root.after_cancel(self._table_insert_job)
                except Exception:
                    pass
                self._table_insert_job = None
            # İptal işareti için token
            self._table_fill_token = getattr(self, '_table_fill_token', 0) + 1
            token = self._table_fill_token

            # --- Birimleri ve başlıkları güncelle ---
            accel_unit = "g"
            velocity_unit = "cm/s"
            displacement_unit = "cm"
            try:
                self._update_unit_display()
                if hasattr(self, 'loaded_earthquake_files') and self.loaded_earthquake_files:
                    sel = self.earthquake_listbox.curselection()
                    if sel:
                        idx = sel[0]
                        if idx < len(self.loaded_earthquake_files):
                            params = self.loaded_earthquake_files[idx]['parameters']
                            accel_unit = params.get('accel_unit', 'g')
                            velocity_unit = params.get('velocity_unit', 'cm/s')
                            displacement_unit = params.get('displacement_unit', 'cm')
            except Exception:
                pass

            # Başlıkları güncelle
            try:
                self.accel_tree.heading("acceleration", text=f"İvme ({accel_unit})")
                self.velocity_tree.heading("velocity", text=f"Hız ({velocity_unit})")
                self.displacement_tree.heading("displacement", text=f"Yerdeğiştirme ({displacement_unit})")
                # LabelFrame başlıkları
                try:
                    accel_frame = self.accel_tree.master.master
                    velocity_frame = self.velocity_tree.master.master
                    displacement_frame = self.displacement_tree.master.master
                    accel_frame.config(text=f"İvme Verileri ({accel_unit})")
                    velocity_frame.config(text=f"Hız Verileri ({velocity_unit})")
                    displacement_frame.config(text=f"Yerdeğiştirme Verileri ({displacement_unit})")
                except Exception:
                    pass
            except Exception:
                pass

            # Önce tabloları ve zaman haritalarını temizle
            self._clear_data_tables()
            try:
                self._accel_time_map.clear()
                self._velocity_time_map.clear()
                self._displacement_time_map.clear()
            except Exception:
                self._accel_time_map, self._velocity_time_map, self._displacement_time_map = {}, {}, {}

            # Eksik seriler için güvenli diziler oluştur (boşsa sıfırla)
            try:
                data_len_total = len(time_data)
                _accel_safe = accel_data if isinstance(accel_data, (list, tuple)) and len(accel_data) == data_len_total else [0.0] * data_len_total
                _velocity_safe = velocity_data if isinstance(velocity_data, (list, tuple)) and len(velocity_data) == data_len_total else [0.0] * data_len_total
                _displacement_safe = displacement_data if isinstance(displacement_data, (list, tuple)) and len(displacement_data) == data_len_total else [0.0] * data_len_total
            except Exception:
                _accel_safe = accel_data
                _velocity_safe = velocity_data
                _displacement_safe = displacement_data

            # --- Arka planda batch veriyi hazırla (formatlı metinleri de üret) ---
            def _build_batches():
                from ..config.styles import format_table_value
                import math
                data_len = len(time_data)
                # PEER NGA ise tüm veri, değilse mevcut mantık (1k/750/500)
                is_peer_nga_format = False
                try:
                    if hasattr(self, 'loaded_earthquake_files') and self.loaded_earthquake_files:
                        sel = self.earthquake_listbox.curselection()
                        if sel:
                            idx = sel[0]
                            if idx < len(self.loaded_earthquake_files):
                                params = self.loaded_earthquake_files[idx]['parameters']
                                file_format = params.get('format', '')
                                processed_data = self.loaded_earthquake_files[idx].get('processed_data', {})
                                format_type = processed_data.get('format_type', '')
                                if file_format == 'peer_nga' or format_type in ['AT2', 'VT2', 'DT2']:
                                    is_peer_nga_format = True
                except Exception:
                    pass

                if is_peer_nga_format:
                    max_points = data_len
                else:
                    if data_len > 50000:
                        max_points = 500
                    elif data_len > 10000:
                        max_points = 750
                    else:
                        max_points = min(1000, data_len)

                step = max(1, data_len // max_points if max_points > 0 else 1)

                accel_batch = []
                vel_batch = []
                disp_batch = []
                for i in range(0, data_len, step):
                    if len(accel_batch) >= max_points:
                        break
                    raw_t = time_data[i]
                    t_txt = format_table_value(raw_t, "time")
                    accel_batch.append((raw_t, t_txt, format_table_value(_accel_safe[i], "acceleration")))
                    vel_batch.append((raw_t, t_txt, format_table_value(_velocity_safe[i], "velocity")))
                    disp_batch.append((raw_t, t_txt, format_table_value(_displacement_safe[i], "displacement")))
                return accel_batch, vel_batch, disp_batch

            def _on_batches_ready(result):
                # Bu sonuç halen geçerli mi?
                if token != getattr(self, '_table_fill_token', None):
                    return
                accel_batch, vel_batch, disp_batch = result
                n = min(len(accel_batch), len(vel_batch), len(disp_batch))
                if n == 0:
                    try:
                        self.root.config(cursor="")
                        if getattr(self, 'status_var', None):
                            self.status_var.set("Hazır")
                    except Exception:
                        pass
                    return

                # Dinamik chunk büyüklüğü
                if n >= 20000:
                    chunk = 1000
                elif n >= 5000:
                    chunk = 500
                else:
                    chunk = 200

                idx = 0
                # Çok büyük listelerde ilk görünümü hızlandır: 1-2 bin satırı hemen bas
                try:
                    if n > 50000 and token == getattr(self, '_table_fill_token', None):
                        prime_target = min(2000, n)
                        a_insert = self.accel_tree.insert
                        v_insert = self.velocity_tree.insert
                        d_insert = self.displacement_tree.insert
                        for j in range(idx, prime_target):
                            rt, tt, av = accel_batch[j]
                            iid = a_insert("", "end", values=(tt, av))
                            self._accel_time_map[iid] = float(rt)
                            rt, tt, vv = vel_batch[j]
                            iid = v_insert("", "end", values=(tt, vv))
                            self._velocity_time_map[iid] = float(rt)
                            rt, tt, dv = disp_batch[j]
                            iid = d_insert("", "end", values=(tt, dv))
                            self._displacement_time_map[iid] = float(rt)
                        idx = prime_target
                except Exception:
                    # Herhangi bir hata olursa ilk parça hızlı eklemesi atlanır
                    idx = 0

                def _insert_chunk():
                    nonlocal idx
                    if token != getattr(self, '_table_fill_token', None):
                        return  # iptal edildi
                    end = min(idx + chunk, n)
                    for j in range(idx, end):
                        rt, tt, av = accel_batch[j]
                        iid = self.accel_tree.insert("", "end", values=(tt, av))
                        self._accel_time_map[iid] = float(rt)
                        rt, tt, vv = vel_batch[j]
                        iid = self.velocity_tree.insert("", "end", values=(tt, vv))
                        self._velocity_time_map[iid] = float(rt)
                        rt, tt, dv = disp_batch[j]
                        iid = self.displacement_tree.insert("", "end", values=(tt, dv))
                        self._displacement_time_map[iid] = float(rt)
                    idx = end
                    if idx < n and token == getattr(self, '_table_fill_token', None):
                        self._table_insert_job = self.root.after(1, _insert_chunk)
                    else:
                        self._table_insert_job = None
                        try:
                            self.root.config(cursor="")
                            if getattr(self, 'status_var', None):
                                self.status_var.set("Hazır")
                        except Exception:
                            pass

                _insert_chunk()

            def _on_batches_error(err):
                self.logger.exception(f"Tablo verisi hazırlanırken hata: {err}")
                self._clear_data_tables()
                try:
                    self.root.config(cursor="")
                    if getattr(self, 'status_var', None):
                        self.status_var.set("Hazır")
                except Exception:
                    pass

            # Veriyi arka planda hazırla, UI eklemeyi chunk chunk yap
            self._run_in_executor(_build_batches, _on_batches_ready, _on_batches_error)

        except Exception as e:
            self.logger.exception(f"Tablo doldurma hatası: {e}")
            self._clear_data_tables()
            try:
                self.root.config(cursor="")
                if getattr(self, 'status_var', None):
                    self.status_var.set("Hazır")
            except Exception:
                pass

 

    def _bind_table_shortcuts(self, tree_widget, table_name: str) -> None:
        """Tablo için klavye kısayollarını bağlar"""
        # CTRL+A ile tümünü seç (olayı tüket)
        tree_widget.bind('<Control-a>', lambda e: (self._select_all_in_table(tree_widget), "break")[1])
        tree_widget.bind('<Control-A>', lambda e: (self._select_all_in_table(tree_widget), "break")[1])
        
        # CTRL+C ile kopyala (olayı tüket)
        tree_widget.bind('<Control-c>', lambda e: (self._copy_table_data(tree_widget, table_name), "break")[1])
        tree_widget.bind('<Control-C>', lambda e: (self._copy_table_data(tree_widget, table_name), "break")[1])
        
        # Tab tuşu ile diğer tabloya geç (olayı tüket)
        tree_widget.bind('<Tab>', lambda e: (self._focus_next_table(tree_widget), "break")[1])
        
        # Sağ tık menüsü ekle (olayı tüket)
        tree_widget.bind('<Button-3>', lambda e: (self._show_context_menu(e, tree_widget, table_name), "break")[1])
        
        # Satır seçimi event'i - OPTİMİZE EDİLMÄ°ÅŞ SENKRONIZASYON
        tree_widget.bind('<<TreeviewSelect>>', lambda e: self._sync_table_selection_optimized(tree_widget, table_name))
        
        # Mouse wheel scroll - platform bağımsız + otomatik seçim hareketi
        tree_widget.bind('<MouseWheel>', lambda e: self._on_table_mousewheel(e, tree_widget))
        tree_widget.bind('<Button-4>', lambda e: self._on_table_mousewheel(e, tree_widget))  # Linux scroll up
        tree_widget.bind('<Button-5>', lambda e: self._on_table_mousewheel(e, tree_widget))  # Linux scroll down
    
    def _select_all_in_table(self, tree_widget) -> None:
        """Tablodaki tüm satırları seçer"""
        try:
            all_items = tree_widget.get_children()
            if all_items:
                tree_widget.selection_set(all_items)
            self.logger.info(f"Tablodaki {len(all_items)} satır seçildi")
        except Exception as e:
            self.logger.exception(f"Tümünü seçme hatası: {e}")
    
    def _on_table_mousewheel(self, event, tree_widget) -> None:
        """Tablo mouse wheel scroll handler - platform bağımsız + otomatik seçim hareketi"""
        try:
            # Scroll direction ve miktarını belirle
            if event.num == 4 or event.delta > 0:
                # Yukarı scroll (Linux Button-4 veya Windows pozitif delta)
                delta = -1
                direction = "up"
            elif event.num == 5 or event.delta < 0:
                # Aşağı scroll (Linux Button-5 veya Windows negatif delta)
                delta = 1
                direction = "down"
            else:
                return
            
            # Scroll miktarını ayarla
            scroll_amount = 3  # Varsayılan: 3 satır
            
            # Windows'ta delta değerine göre scroll miktarını ayarlayabilir
            if hasattr(event, 'delta') and event.delta != 0:
                # Delta genellikle 120'nin katlarında gelir
                scroll_multiplier = abs(event.delta) // 120
                scroll_amount = max(1, min(scroll_multiplier, 5))  # 1-5 satır arası
            
            # Önce tabloyu scroll et
            tree_widget.yview_scroll(delta * scroll_amount, "units")
            
            # Seçili item'ı al
            selected_items = tree_widget.selection()
            if selected_items:
                current_item = selected_items[0]
                all_items = tree_widget.get_children()
                
                if all_items:
                    try:
                        # Mevcut seçili item'ın indeksini bul
                        current_index = all_items.index(current_item)
                        
                        # Yeni indeksi hesapla
                        if direction == "down":
                            new_index = min(current_index + scroll_amount, len(all_items) - 1)
                        else:  # direction == "up"
                            new_index = max(current_index - scroll_amount, 0)
                        
                        # Yeni item'ı seç (sadece farklıysa)
                        if new_index != current_index:
                            new_item = all_items[new_index]
                            
                            # Önce mevcut seçimi temizle
                            tree_widget.selection_remove(tree_widget.selection())
                            
                            # Yeni item'ı seç
                            tree_widget.selection_set(new_item)
                            
                            # Seçili item'ı görünür yap
                            tree_widget.see(new_item)
                            
                            # Tablo senkronizasyonu otomatik tetiklenecek (<<TreeviewSelect>> event ile)
                            self.logger.debug(f"Scroll ile seçim hareket etti: {direction} → {new_index + 1}/{len(all_items)}")
                        
                    except (ValueError, IndexError) as e:
                        self.logger.debug(f"Seçim hareket hatası: {e}")
            else:
                # Seçili item yoksa, ilk item'ı seç
                all_items = tree_widget.get_children()
                if all_items:
                    first_item = all_items[0]
                    tree_widget.selection_set(first_item)
                    tree_widget.see(first_item)
                    self.logger.debug("İlk item otomatik seçildi")
            
            # Event'i consume et (başka handler'lara geçmesini önle)
            return "break"
            
        except Exception as e:
            self.logger.debug(f"Tablo scroll hatası: {e}")
            return "break"

    def _widget_exists(self, widget) -> bool:
        """Tk widget'ının halen geçerli olup olmadığını güvenle kontrol eder"""
        try:
            if widget is None:
                return False
            # Tkinter'da _w attribute'u varsa ve tk.call("winfo", "exists", widget) 1 dönerse var demektir
            return bool(widget.winfo_exists())
        except Exception:
            return False
    
    def _copy_table_data(self, tree_widget, table_name: str) -> None:
        """Seçili tablo verilerini panoya kopyalar"""
        try:
            selected_items = tree_widget.selection()
            
            if not selected_items:
                messagebox.showinfo("Bilgi", f"{table_name} tablosunda seçili veri yok.\nÖnce CTRL+A ile tüm verileri seçin.", parent=self.root)
                return
            
            # Başlık satırını al
            columns = tree_widget['columns']
            headers = []
            for col in columns:
                headers.append(tree_widget.heading(col)['text'])
            
            # Veri satırlarını topla
            data_rows = ['\t'.join(headers)]  # Tab ile ayrılmış başlıklar
            
            for item in selected_items:
                values = tree_widget.item(item)['values']
                data_rows.append('\t'.join(str(val) for val in values))
            
            # Panoya kopyala
            clipboard_text = '\n'.join(data_rows)
            tree_widget.clipboard_clear()
            tree_widget.clipboard_append(clipboard_text)
            
            messagebox.showinfo("Başarılı", 
                              f"{table_name} tablosundan {len(selected_items)} satır panoya kopyalandı!\n\n"
                             "Excel veya diğer uygulamalara CTRL+V ile yapıştırabilirsiniz.", parent=self.root)
            
            self.logger.info(f"{table_name} tablosu kopyalandı: {len(selected_items)} satır")
            
        except Exception as e:
            self.logger.exception(f"Kopyalama hatası: {e}")
            messagebox.showerror("Hata", f"Veri kopyalanırken hata oluştu:\n{str(e)}", parent=self.root)
    
    def _focus_next_table(self, current_tree) -> None:
        """Tab tuÅŸu ile sonraki tabloya odaklan"""
        try:
            if current_tree == self.accel_tree:
                self.velocity_tree.focus_set()
            elif current_tree == self.velocity_tree:
                self.displacement_tree.focus_set()
            elif current_tree == self.displacement_tree:
                self.accel_tree.focus_set()
        except Exception as e:
            self.logger.debug(f"Tablo odak değiştirme hatası: {e}")
    
    def _show_context_menu(self, event, tree_widget, table_name: str) -> None:
        """Sağ tık menüsünü gösterir"""
        try:
            # Context menu oluÅŸtur
            context_menu = tk.Menu(self.root, tearoff=0)
            
            # Tümünü seç
            context_menu.add_command(
                label="🔷 Tümünü Seç (Ctrl+A)",
                command=lambda: self._select_all_in_table(tree_widget)
            )
            
            # Seçimi temizle
            context_menu.add_command(
                label="🔶 Seçimi Temizle",
                command=lambda: tree_widget.selection_remove(tree_widget.selection())
            )
            
            context_menu.add_separator()
            
            # Kopyala
            context_menu.add_command(
                label="📋 Kopyala (Ctrl+C)",
                command=lambda: self._copy_table_data(tree_widget, table_name)
            )
            
            # Excel'e aktar
            context_menu.add_command(
                label="📊 Excel'e Aktar",
                command=lambda: self._export_table_to_excel(tree_widget, table_name)
            )
            
            # Menüyü güvenli şekilde göster (tk_popup) ve kapanışta grab bırak
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    context_menu.grab_release()
                except Exception:
                    pass
            
        except Exception as e:
            self.logger.exception(f"Context menu hatası: {e}")
    
    def _export_table_to_excel(self, tree_widget, table_name: str) -> None:
        """Tablo verilerini Excel'e aktarır"""
        try:
            # Seçili deprem kaydını bul
            selection = self.earthquake_listbox.curselection()
            if not selection:
                messagebox.showinfo("Bilgi", "Önce bir deprem kaydı seçin.", parent=self.root)
                return
                
            index = selection[0]
            selected_file = self.loaded_earthquake_files[index]
            selected_name = selected_file['name']
            
            # Orijinal tam veriyi al (1000 satır sınırı olmadan)
            if selected_name not in self.processed_earthquake_data:
                messagebox.showerror("Hata", "Seçili deprem kaydının verisi bulunamadı.", parent=self.root)
                return
            
            earthquake_data = self.processed_earthquake_data[selected_name]
            
            # Pandas DataFrame oluÅŸtur
            import pandas as pd
            
            # Hangi tablo türüne göre veriyi hazırla
            if table_name == "İvme":
                df = pd.DataFrame({
                    'Zaman (s)': earthquake_data['time'],
                    'İvme (g)': earthquake_data['acceleration']
                })
            elif table_name == "Hız":
                df = pd.DataFrame({
                    'Zaman (s)': earthquake_data['time'],
                    'Hız (cm/s)': earthquake_data['velocity']
                })
            elif table_name == "Yerdeğiştirme":
                df = pd.DataFrame({
                    'Zaman (s)': earthquake_data['time'],
                    'Yerdeğiştirme (cm)': earthquake_data['displacement']
                })
            else:
                messagebox.showerror("Hata", f"Bilinmeyen tablo türü: {table_name}", parent=self.root)
                return
            
            # Dosya kaydetme dialogu
            file_path = FileUtils.save_file_dialog(
                title=f"{table_name} Tablosunu Excel'e Aktar - {selected_name}",
                filetypes=[("Excel dosyası", "*.xlsx")],
                default_extension=".xlsx",
                parent=self.root
            )
            
            if file_path:
                # Tüm veriyi Excel'e aktar
                df.to_excel(file_path, index=False)
                
                messagebox.showinfo(
                    "Başarılı",
                    f"{table_name} tablosu Excel'e aktarıldı:\n{file_path}\n\n"
                    f"📊 Dosya: {selected_name}\n"
                    f"📋 Toplam {len(df)} satır kaydedildi (tam veri seti)\n"
                    f"⏱️ Süre: {earthquake_data['time'][-1]:.2f} saniye",
                    parent=self.root
                )
                self.logger.info(f"{table_name} tablosu Excel'e aktarıldı: {file_path}")
                self.logger.debug(f"Kaynak: {selected_name}")
                self.logger.debug(f"Satır sayısı: {len(df):,} (tam veri seti)")
            
        except Exception as e:
            self.logger.exception(f"Excel aktarma hatası: {e}")
            messagebox.showerror("Hata", f"Excel'e aktarırken hata oluştu:\n{str(e)}", parent=self.root) 

    def _sync_table_selection_optimized(self, source_tree, source_table_name: str) -> None:
        """Seçilen satırın zaman deÄŸerine göre diÄŸer tablolarda da aynı zaman deÄŸerini seçer - OPTİMİZE EDİLMÄ°ÅŞ"""
        try:
            # Sonsuz loop'u önlemek için flag kontrol et
            if getattr(self, '_syncing_selection', False):
                return
            
            # Seçili item'ları al
            selected_items = source_tree.selection()
            if not selected_items:
                # Seçim temizlendiyse grafiklerdeki kırmızı noktaları da temizle
                self._clear_plot_markers()
                return
            
            # Sadece tek seçim durumunda senkronize et (çoklu seçimde performans sorunu çıkabilir)
            if len(selected_items) != 1:
                return
            
            # İlk seçili item'ın zaman değerini al
            first_item = selected_items[0]
            values = source_tree.item(first_item)['values']
            if not values:
                return

            # Zaman değerini güvenilir kaynaktan al (map), yoksa görünen metinden parse et
            if source_tree == self.accel_tree:
                selected_time = self._accel_time_map.get(first_item)
            elif source_tree == self.velocity_tree:
                selected_time = self._velocity_time_map.get(first_item)
            elif source_tree == self.displacement_tree:
                selected_time = self._displacement_time_map.get(first_item)
            else:
                selected_time = None

            if selected_time is None:
                try:
                    selected_time = float(str(values[0]))
                except Exception:
                    return
            # String karşılaştırma yerine ham float ile eşleştirme yap
            selected_time_value = float(selected_time)
            
            # Debounce için son senkronizasyondan itibaren minimum süre kontrolü 
            import time
            current_time = time.time()
            last_sync_time = getattr(self, '_last_sync_time', 0)
            
            if current_time - last_sync_time < 0.1:  # 100ms debounce
                return
            
            self._last_sync_time = current_time
            
            # Sync flag'ini set et
            self._syncing_selection = True
            
            self.logger.debug(f"Tablo senkronizasyonu: {source_table_name} → Zaman: {selected_time_value}")
            
            # Diğer tablolarda aynı zaman değerine sahip satırları bul ve seç
            tables_to_sync = []
            
            if source_tree != self.accel_tree:
                tables_to_sync.append((self.accel_tree, "İvme"))
            if source_tree != self.velocity_tree:
                tables_to_sync.append((self.velocity_tree, "Hız"))
            if source_tree != self.displacement_tree:
                tables_to_sync.append((self.displacement_tree, "Yerdeğiştirme"))
            
            for target_tree, target_name in tables_to_sync:
                # Önce seçimi temizle
                target_tree.selection_remove(target_tree.selection())
                
                # Optimize edilmiÅŸ arama: Linear search yerine dictionary kullanabiliriz
                # Ama ÅŸimdilik basit approach
                found = False
                
                # Tüm item'ları kontrol et (optimize edilmiş loop)
                all_items = target_tree.get_children()
                # Hedef tabloya göre doğru zaman haritasını seç
                if target_tree == self.accel_tree:
                    target_time_map = self._accel_time_map
                elif target_tree == self.velocity_tree:
                    target_time_map = self._velocity_time_map
                elif target_tree == self.displacement_tree:
                    target_time_map = self._displacement_time_map
                else:
                    target_time_map = {}

                for item in all_items:
                    # Öncelik: ham zaman haritası
                    target_time = target_time_map.get(item)
                    if target_time is None:
                        # Fallback: görünen metinden parse et (binlik ayırıcı vb. olabilir)
                        try:
                            item_values = target_tree.item(item)['values']
                            if not item_values:
                                continue
                            target_time = float(str(item_values[0]).replace('\u202f', '').replace(' ', '').replace(',', ''))
                        except Exception:
                            continue

                    # Float karşılaştırmayı toleransla yap
                    if abs(float(target_time) - selected_time_value) < 1e-9:
                        target_tree.selection_add(item)
                        # İlk eşleşeni görünür yap
                        target_tree.see(item)
                        found = True
                        break  # İlk eşleşmeyi bulunca dur
                
                if found:
                    self.logger.debug(f"{target_name} tablosunda eÅŸleÅŸme bulundu")
                else:
                    self.logger.debug(f"{target_name} tablosunda eşleşme bulunamadı")
            
            # Grafiklerde seçilen noktayı kırmızı nokta ile işaretle
            self._mark_selected_point_on_plots(selected_time)
            
            # Sync flag'ini temizle
            self._syncing_selection = False
            
        except Exception as e:
            # Hata durumunda flag'i temizle
            self._syncing_selection = False
            self.logger.debug(f"Tablo senkronizasyon hatası: {e}")
            # Performans için hata detayını sadece gerektiğinde göster
            # import traceback
            # traceback.print_exc()
    
    def _mark_selected_point_on_plots(self, selected_time: float) -> None:
        """Seçilen zaman değerini grafiklerde kırmızı nokta ile işaretler"""
        try:
            # Önce önceki kırmızı noktaları temizle
            self._clear_plot_markers()
            
            # Seçili deprem kaydının verilerini al
            selection = self.earthquake_listbox.curselection()
            if not selection:
                return
                
            index = selection[0]
            selected_file = self.loaded_earthquake_files[index]
            selected_name = selected_file['name']
            
            if selected_name not in self.processed_earthquake_data:
                return
                
            earthquake_data = self.processed_earthquake_data[selected_name]
            time_data = earthquake_data['time']
            accel_data = earthquake_data['acceleration']
            velocity_data = earthquake_data['velocity']
            displacement_data = earthquake_data['displacement']
            
            # En yakın zaman değerini ve indeksini bul
            import numpy as np
            time_array = np.array(time_data)
            closest_idx = np.argmin(np.abs(time_array - selected_time))
            actual_time = time_data[closest_idx]
            
            # O anki değerleri al
            accel_value = accel_data[closest_idx]
            velocity_value = velocity_data[closest_idx]
            displacement_value = displacement_data[closest_idx]
            
            self.logger.debug(f"Grafiklerde iÅŸaretleniyor - Zaman: {actual_time:.3f}s")
            self.logger.debug(f"   İvme: {accel_value:.6f} g")
            self.logger.debug(f"   Hız: {velocity_value:.3f} cm/s") 
            self.logger.debug(f"   Yerdeğiştirme: {displacement_value:.3f} cm")
            
            # Her üç grafikte de profesyonel marker ekle
            from ..config.styles import CUSTOM_COLORS
            marker_size = 8
            marker_color = CUSTOM_COLORS['marker']
            marker_edge_color = CUSTOM_COLORS['selection']
            marker_style = 'o'
            
            # İvme grafiğinde işaretleme
            self.accel_marker = self.accel_ax.scatter([actual_time], [accel_value], 
                                                     c=marker_color, s=marker_size**2, 
                                                     marker=marker_style, zorder=10, 
                                                     edgecolors=marker_edge_color, linewidth=2)
            
            # Hız grafiğinde işaretleme
            self.velocity_marker = self.velocity_ax.scatter([actual_time], [velocity_value], 
                                                           c=marker_color, s=marker_size**2, 
                                                           marker=marker_style, zorder=10,
                                                           edgecolors=marker_edge_color, linewidth=2)
            
            # Yerdeğiştirme grafiğinde işaretleme
            self.displacement_marker = self.displacement_ax.scatter([actual_time], [displacement_value], 
                                                                   c=marker_color, s=marker_size**2, 
                                                                   marker=marker_style, zorder=10,
                                                                   edgecolors=marker_edge_color, linewidth=2)
            
            # Canvas'ı güncelle
            self.time_series_canvas.draw_idle()  # draw_idle daha performanslı
            
            self.logger.debug(f"Kırmızı nokta işaretlendi: T={actual_time:.3f}s")
            
        except Exception as e:
            self.logger.exception(f"Grafik işaretleme hatası: {e}")
            import traceback
            traceback.print_exc()
    
    def _clear_plot_markers(self) -> None:
        """Grafiklerdeki kırmızı noktaları temizler"""
        try:
            # Önceki kırmızı noktaları kaldır
            if hasattr(self, 'accel_marker') and self.accel_marker:
                self.accel_marker.remove()
                self.accel_marker = None
                
            if hasattr(self, 'velocity_marker') and self.velocity_marker:
                self.velocity_marker.remove()
                self.velocity_marker = None
                
            if hasattr(self, 'displacement_marker') and self.displacement_marker:
                self.displacement_marker.remove() 
                self.displacement_marker = None
                
            # Canvas'ı güncelle
            if hasattr(self, 'time_series_canvas'):
                self.time_series_canvas.draw_idle()
                
        except Exception as e:
            # Temizleme hatası kritik değil, sessizce geç
            pass
    
    def _show_earthquake_context_menu(self, event) -> None:
        """Deprem kayıtları listesi için sağ tık menüsünü gösterir"""
        try:
            # Tıklanan öğeyi seç
            index = self.earthquake_listbox.nearest(event.y)
            if index >= 0 and index < self.earthquake_listbox.size():
                self.earthquake_listbox.selection_clear(0, tk.END)
                self.earthquake_listbox.selection_set(index)
                
                # Context menu oluÅŸtur
                context_menu = tk.Menu(self.root, tearoff=0)
                
                # Kayıt bilgileri
                context_menu.add_command(
                    label="📋 Kayıt Bilgileri",
                    command=lambda: self._show_earthquake_info(index)
                )
                
                context_menu.add_separator()
                
                # Parametreleri düzenle
                context_menu.add_command(
                    label="⚙️ Parametreleri Düzenle",
                    command=lambda: self._edit_earthquake_parameters(index)
                )
                
                # Kaydı yeniden yükle
                context_menu.add_command(
                    label="🔄 Kaydı Yeniden Yükle",
                    command=lambda: self._reload_earthquake_record(index)
                )
                
                context_menu.add_separator()
                
                # Kaydı kopyala
                context_menu.add_command(
                    label="📄 Kaydı Kopyala",
                    command=lambda: self._duplicate_earthquake_record(index)
                )
                
                # Kaydı sil
                context_menu.add_command(
                    label="🗑️ Kaydı Sil",
                    command=lambda: self._delete_earthquake_record(index)
                )
                
                context_menu.add_separator()
                
                # Tüm kayıtları temizle
                context_menu.add_command(
                    label="🧹 Tüm Kayıtları Temizle",
                    command=self._clear_all_earthquake_records
                )
                
                # Export seçenekleri
                context_menu.add_separator()
                
                # Excel export (mevcut)
                context_menu.add_command(
                    label="📊 Excel'e Aktar (Tüm Veriler)",
                    command=lambda: self._export_earthquake_to_excel(index)
                )
                
                # Gelişmiş export seçenekleri
                export_submenu = tk.Menu(context_menu, tearoff=0)
                context_menu.add_cascade(label="📋 Gelişmiş Export", menu=export_submenu)
                
                export_submenu.add_command(
                    label="📄 CSV Format",
                    command=lambda: self._export_earthquake_advanced(index, 'csv')
                )
                
                export_submenu.add_command(
                    label="🔬 MATLAB Format (.mat)",
                    command=lambda: self._export_earthquake_advanced(index, 'matlab')
                )
                
                export_submenu.add_command(
                    label="🌐 JSON Format",
                    command=lambda: self._export_earthquake_advanced(index, 'json')
                )
                
                export_submenu.add_separator()
                export_submenu.add_command(
                    label="⚙️ Format Seçim Dialogu",
                    command=lambda: self._show_export_dialog(index)
                )
                
                # Menüyü göster
                context_menu.post(event.x_root, event.y_root)
                
        except Exception as e:
            self.logger.exception(f"Deprem context menu hatası: {e}")
    
    def _show_earthquake_info(self, index: int) -> None:
        """Seçili deprem kaydının detay bilgilerini gösterir"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            earthquake_record = self.loaded_earthquake_files[index]
            display_name = earthquake_record['name']
            original_filename = earthquake_record.get('original_filename', earthquake_record['name'])
            file_path = earthquake_record['path']
            parameters = earthquake_record['parameters']
            
            # İstatistikleri hesapla
            if display_name in self.processed_earthquake_data:
                earthquake_data = self.processed_earthquake_data[display_name]
                stats = self.earthquake_data_processor.get_time_series_stats(earthquake_data)
            else:
                stats = {}
            
            # Birim bilgilerini al (parametrelerden)
            accel_unit = parameters.get('accel_unit', 'g')
            velocity_unit = parameters.get('velocity_unit', 'cm/s')
            displacement_unit = parameters.get('displacement_unit', 'cm')
            
            # Info dialogu oluÅŸtur
            info_window = tk.Toplevel(self.root)
            info_window.title(f"Kayıt Bilgileri - {display_name}")
            info_window.geometry("600x500")
            info_window.transient(self.root)
            info_window.grab_set()
            
            # İçerik frame
            content_frame = ttk.Frame(info_window, padding="15")
            content_frame.pack(fill="both", expand=True)
            
            # Başlık
            title_label = ttk.Label(content_frame, text=f"📄 {display_name}", 
                                   font=('Segoe UI', 12, 'bold'))
            title_label.pack(pady=(0, 10))
            
            # Bilgi text widget'ı
            info_text = tk.Text(content_frame, wrap=tk.WORD, height=20, width=70)
            info_scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=info_text.yview)
            info_text.config(yscrollcommand=info_scrollbar.set)
            
            # Bilgileri ekle
            info_text.delete(1.0, tk.END)
            info_content = f"""DOSYA BİLGİLERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ Deprem Adı: {display_name}
📁 Orijinal Dosya Adı: {original_filename}
📂 Dosya Yolu: {file_path}

YÜKLEME PARAMETRELERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Zaman Adımı: {parameters.get('time_step', 'N/A')} saniye
🔢 Veri Başlangıç Satırı: {parameters.get('first_line', 'N/A')}
📊 Son Satır: {parameters.get('last_line', 'N/A')}
📋 İvme Sütunu: {parameters.get('accel_column', 'N/A')}
🏷️ Zaman Sütunu: {parameters.get('time_column', 'N/A')}
📈 Dosya Formatı: {parameters.get('format', 'N/A')}
🔢 Ölçek Faktörü: {parameters.get('scaling_factor', 'N/A')}
📊 Okuma Frekansı: {parameters.get('frequency', 'N/A')}
⚙️ Atlanan Başlangıç: {parameters.get('initial_skip', 'N/A')}

📏 BİRİM BİLGİLERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 İvme Birimi: {accel_unit}
🚀 Hız Birimi: {velocity_unit}
📍 Yerdeğiştirme Birimi: {displacement_unit}
"""
            
            # PEER NGA format bilgilerini ekle
            if display_name in self.processed_earthquake_data:
                processed_data = self.processed_earthquake_data[display_name]
                if processed_data.get('format_type') in ['AT2', 'VT2', 'DT2']:
                    info_content += f"""
🌍 PEER NGA FORMAT BİLGİLERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ Format Tipi: {processed_data.get('format_type', 'N/A')}
📋 Orijinal Birim: {processed_data.get('original_units_info', 'N/A')}
"""
            
            if stats:
                info_content += f"""
VERİ İSTATİSTİKLERİ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️ Toplam Süre: {stats.get('duration', 0):.3f} saniye
🔢 Veri Nokta Sayısı: {stats.get('num_points', 0):,}

📈 İVME BİLGİLERİ:
"""
                if 'acceleration' in stats:
                    acc_stats = stats['acceleration']
                    info_content += f"""   • Maksimum İvme: {acc_stats.get('peak', 0):.6f} {accel_unit}
   • Maksimum İvme Zamanı: {acc_stats.get('time_of_peak', 0):.3f} saniye
   • Minimum İvme: {acc_stats.get('min', 0):.6f} {accel_unit}
   • RMS İvme: {acc_stats.get('rms', 0):.6f} {accel_unit}

"""
                
                info_content += f"""🚀 HIZ BİLGİLERİ:
"""
                if 'velocity' in stats:
                    vel_stats = stats['velocity']
                    info_content += f"""   • Maksimum Hız: {vel_stats.get('peak', 0):.3f} {velocity_unit}
   • Maksimum Hız Zamanı: {vel_stats.get('time_of_peak', 0):.3f} saniye
   • Minimum Hız: {vel_stats.get('min', 0):.3f} {velocity_unit}
   • RMS Hız: {vel_stats.get('rms', 0):.3f} {velocity_unit}

"""
                
                info_content += f"""📍 YERDEÄŞÄ°ÅŞTİRME BİLGİLERİ:
"""
                if 'displacement' in stats:
                    disp_stats = stats['displacement']
                    info_content += f"""   • Maksimum Yerdeğiştirme: {disp_stats.get('peak', 0):.3f} {displacement_unit}
   • Maksimum Yerdeğiştirme Zamanı: {disp_stats.get('time_of_peak', 0):.3f} saniye
   • Minimum Yerdeğiştirme: {disp_stats.get('min', 0):.3f} {displacement_unit}
   • RMS Yerdeğiştirme: {disp_stats.get('rms', 0):.3f} {displacement_unit}

"""

                # Ek parametreler
                if 'vmax_amax_ratio' in stats:
                    info_content += f"""📊 EK PARAMETRELER:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   • Vmax/Amax Oranı: {stats.get('vmax_amax_ratio', 0):.5f} saniye

"""
            
            info_text.insert(1.0, info_content)
            info_text.config(state='disabled')
            
            # Layout
            info_text.pack(side="left", fill="both", expand=True)
            info_scrollbar.pack(side="right", fill="y")
            
            # Kapat butonu
            close_button = ttk.Button(content_frame, text="Kapat", 
                                     command=info_window.destroy)
            close_button.pack(pady=(10, 0))
            
            # Pencereyi ortala
            info_window.transient(self.root)
            info_window.grab_set()
            
        except Exception as e:
            self.logger.exception(f"Kayıt bilgileri gösterme hatası: {e}")
            messagebox.showerror("Hata", f"Kayıt bilgileri gösterilirken hata:\n{str(e)}", parent=self.root)
    
    def _edit_earthquake_parameters(self, index: int) -> None:
        """Seçili deprem kaydının parametrelerini düzenler"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            earthquake_record = self.loaded_earthquake_files[index]
            file_path = earthquake_record['path']
            current_params = earthquake_record['parameters']
            
            # Eski birim bilgilerini sakla
            old_units = {
                'accel_unit': current_params.get('accel_unit', 'g'),
                'velocity_unit': current_params.get('velocity_unit', 'cm/s'),
                'displacement_unit': current_params.get('displacement_unit', 'cm')
            }
            
            # Parametreler dialogunu aç (mevcut değerlerle)
            from ..gui.dialogs.input_file_params_dialog import InputFileParametersDialog
            dialog = InputFileParametersDialog(self.root, file_path, current_params)
            
            if dialog.result is not None:
                new_params = dialog.result
                
                # Yeni birim bilgilerini al
                new_units = {
                    'accel_unit': new_params.get('accel_unit', 'g'),
                    'velocity_unit': new_params.get('velocity_unit', 'cm/s'),
                    'displacement_unit': new_params.get('displacement_unit', 'cm')
                }
                
                # Sadece birimler değiştiyse veri dönüştürme yap, yoksa tam reprocess
                units_changed = (old_units != new_units)
                other_params_changed = any(
                    current_params.get(key) != new_params.get(key) 
                    for key in ['time_step', 'first_line', 'last_line', 'accel_column', 
                               'time_column', 'format', 'scaling_factor', 'frequency', 'initial_skip']
                )
                
                try:
                    if units_changed and not other_params_changed:
                        # Sadece birimler değişti - veri dönüştürme yap
                        self.logger.info(f"Sadece birimler değişti, veri dönüştürülüyor: {earthquake_record['name']}")
                        
                        current_data = self.processed_earthquake_data.get(earthquake_record['name'])
                        if current_data:
                            # Veriyi dönüştür
                            converted_data = self.earthquake_data_processor.convert_units(
                                current_data, old_units, new_units
                            )
                            
                            # Güncellenmiş veriyi kaydet
                            earthquake_record['parameters'] = new_params
                            earthquake_record['processed_data'] = converted_data
                            # Sözlükte referans güncellemesini liste kaydı üzerinden yap
                            self.processed_earthquake_data[earthquake_record['name']] = earthquake_record['processed_data']
                            
                            self.logger.info(f"Birim dönüştürme tamamlandı: {old_units} → {new_units}")
                        else:
                            raise Exception("Mevcut veri bulunamadı, tam reprocess gerekli")
                    else:
                        # DiÄŸer parametreler de deÄŸiÅŸti - tam reprocess yap
                        self.logger.info(f"Parametreler deÄŸiÅŸti, tam reprocess: {earthquake_record['name']}")
                        processed_data = self.earthquake_data_processor.process_earthquake_record(
                            file_path, new_params
                        )
                        
                        # Kayıt bilgilerini güncelle
                        earthquake_record['parameters'] = new_params
                        earthquake_record['processed_data'] = processed_data
                        # Sözlükte sadece liste kaydına referans ver
                        self.processed_earthquake_data[earthquake_record['name']] = earthquake_record['processed_data']
                    
                    # Eğer bu kayıt seçili durumdaysa grafikleri güncelle
                    current_selection = self.earthquake_listbox.curselection()
                    if current_selection and current_selection[0] == index:
                        self._on_earthquake_select(None)
                    
                    update_type = "Birim dönüştürme" if (units_changed and not other_params_changed) else "Tam güncelleme"
                    messagebox.showinfo("Başarılı", 
                                      f"'{earthquake_record['name']}' kaydı güncellendi!\n\n"
                                      f"İşlem tipi: {update_type}\n"
                                      "Grafik ve tablolar yeni parametrelerle yenilendi.", parent=self.root)
                    
                    self.logger.info(f"Deprem kaydı başarıyla güncellendi: {earthquake_record['name']}")
                    
                except Exception as process_error:
                    self.logger.exception(f"Güncelleme hatası: {process_error}")
                    messagebox.showerror("İşleme Hatası", 
                                       f"Yeni parametrelerle güncellenirken hata:\n{str(process_error)}", parent=self.root)
            else:
                self.logger.info("Parametre düzenleme iptal edildi")
                
        except Exception as e:
            self.logger.exception(f"Parametre düzenleme hatası: {e}")
            messagebox.showerror("Hata", f"Parametre düzenlerken hata:\n{str(e)}", parent=self.root)
    
    def _reload_earthquake_record(self, index: int) -> None:
        """Seçili deprem kaydını yeniden yükler"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            earthquake_record = self.loaded_earthquake_files[index]
            file_path = earthquake_record['path']
            file_name = earthquake_record['name']
            
            # Dosyanın hala mevcut olduğunu kontrol et
            import os
            if not os.path.exists(file_path):
                messagebox.showerror("Dosya Bulunamadı", 
                                   f"Dosya artık mevcut değil:\n{file_path}\n\n"
                                   "Kayıt silinecek.", parent=self.root)
                self._delete_earthquake_record(index)
                return
            
            # Onay iste
            result = messagebox.askyesno("Kaydı Yeniden Yükle", 
                                       f"'{file_name}' kaydını yeniden yüklemek istediğinizden emin misiniz?\n\n"
                                       "Mevcut parametreler ve iÅŸlenmiÅŸ veriler korunacak.", parent=self.root)
            
            if result:
                try:
                    # Mevcut parametrelerle yeniden yükle
                    current_params = earthquake_record['parameters']
                    
                    self.logger.info(f"Deprem kaydı yeniden yükleniyor: {file_name}")
                    processed_data = self.earthquake_data_processor.process_earthquake_record(
                        file_path, current_params
                    )
                    
                    # Veriyi güncelle
                    earthquake_record['processed_data'] = processed_data
                    # Sözlükte liste kaydına referans ver
                    self.processed_earthquake_data[file_name] = earthquake_record['processed_data']
                    
                    # Eğer seçili durumdaysa grafikleri güncelle
                    current_selection = self.earthquake_listbox.curselection()
                    if current_selection and current_selection[0] == index:
                        self._on_earthquake_select(None)
                    
                    messagebox.showinfo("Başarılı", f"'{file_name}' kaydı başarıyla yeniden yüklendi!", parent=self.root)
                    self.logger.info(f"Deprem kaydı yeniden yüklendi: {file_name}")
                    
                except Exception as reload_error:
                    self.logger.exception(f"Yeniden yükleme hatası: {reload_error}")
                    messagebox.showerror("Yükleme Hatası", 
                                       f"Kayıt yeniden yüklenirken hata:\n{str(reload_error)}", parent=self.root)
                    
        except Exception as e:
            self.logger.exception(f"Yeniden yükleme hatası: {e}")
            messagebox.showerror("Hata", f"Yeniden yüklerken hata:\n{str(e)}", parent=self.root)
    
    def _duplicate_earthquake_record(self, index: int) -> None:
        """Seçili deprem kaydını kopyalar"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            original_record = self.loaded_earthquake_files[index]
            original_name = original_record['name']
            
            # Yeni isim oluÅŸtur
            base_name = f"{original_name}_kopya"
            new_name = self._generate_unique_name(base_name)
            
            # Kopya kayıt oluştur (derin kopya: numpy dizileri/listeler paylaşılmasın)
            from copy import deepcopy
            try:
                parameters_copy = deepcopy(original_record['parameters'])
            except Exception:
                parameters_copy = dict(original_record['parameters'])

            # processed_data derin kopyası (numpy için güvenli)
            orig_pd = original_record['processed_data']
            try:
                import numpy as np  # noqa: F401 - sadece mevcutsa kullanılır
                processed_data_copy = {}
                for key, value in orig_pd.items():
                    # numpy.ndarray veya list/dict olabilir
                    try:
                        if hasattr(value, 'copy') and callable(getattr(value, 'copy')):
                            processed_data_copy[key] = value.copy()
                        else:
                            processed_data_copy[key] = deepcopy(value)
                    except Exception:
                        processed_data_copy[key] = deepcopy(value)
            except Exception:
                processed_data_copy = deepcopy(orig_pd)

            duplicate_record = {
                'name': new_name,
                'path': original_record['path'],
                'parameters': parameters_copy,
                'processed_data': processed_data_copy
            }
            
            # Listeye ekle
            self.loaded_earthquake_files.append(duplicate_record)
            self.processed_earthquake_data[new_name] = duplicate_record['processed_data']
            
            # Listbox'a ekle
            display_name = f"{len(self.loaded_earthquake_files)}. {new_name}"
            self.earthquake_listbox.insert(tk.END, display_name)
            
            messagebox.showinfo("Başarılı", f"'{original_name}' kaydı kopyalandı!\n\nYeni kayıt: '{new_name}'", parent=self.root)
            self.logger.info(f"Deprem kaydı kopyalandı: {original_name} → {new_name}")
            
        except Exception as e:
            self.logger.exception(f"Kayıt kopyalama hatası: {e}")
            messagebox.showerror("Hata", f"Kayıt kopyalanırken hata:\n{str(e)}", parent=self.root)
    
    def _delete_earthquake_record(self, index: int) -> None:
        """Seçili deprem kaydını siler"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            earthquake_record = self.loaded_earthquake_files[index]
            file_name = earthquake_record['name']
            
            # Onay iste
            result = messagebox.askyesno("Kaydı Sil", 
                                       f"'{file_name}' kaydını silmek istediğinizden emin misiniz?\n\n"
                                       "Bu işlem geri alınamaz!", parent=self.root)
            
            if result:
                # Veriyi temizle
                if file_name in self.processed_earthquake_data:
                    del self.processed_earthquake_data[file_name]
                
                # Listeden kaldır
                del self.loaded_earthquake_files[index]
                
                # Listbox'ı yeniden oluştur
                self._refresh_earthquake_listbox()
                
                # Grafikleri temizle
                self._show_empty_plots()
                if hasattr(self, 'stats_panel'):
                    self.stats_panel.clear_stats()
                self.selected_earthquake_var.set("Seçilen: Yok")
                
                # Durum mesajını güncelle
                remaining_count = len(self.loaded_earthquake_files)
                if remaining_count > 0:
                    self.earthquake_file_status_var.set(f"✅ Kayıt silindi. Kalan: {remaining_count} dosya")
                else:
                    self.earthquake_file_status_var.set("Henüz dosya yüklenmedi")
                    self.earthquake_file_status_label.config(foreground="gray")
                
                messagebox.showinfo("Başarılı", f"'{file_name}' kaydı silindi.", parent=self.root)
                self.logger.info(f"Deprem kaydı silindi: {file_name}")
                
        except Exception as e:
            self.logger.exception(f"Kayıt silme hatası: {e}")
            messagebox.showerror("Hata", f"Kayıt silinirken hata:\n{str(e)}", parent=self.root)
    
    def _clear_all_earthquake_records(self) -> None:
        """Tüm deprem kayıtlarını temizler"""
        try:
            if not self.loaded_earthquake_files:
                messagebox.showinfo("Bilgi", "Temizlenecek kayıt yok.")
                return
            
            record_count = len(self.loaded_earthquake_files)
            
            # Onay iste
            result = messagebox.askyesno("Tüm Kayıtları Temizle", 
                                       f"Tüm {record_count} deprem kaydını silmek istediğinizden emin misiniz?\n\n"
                                       "Bu işlem geri alınamaz!")
            
            if result:
                # Tüm verileri temizle
                self.loaded_earthquake_files.clear()
                self.processed_earthquake_data.clear()
                
                # Listbox'ı temizle
                self.earthquake_listbox.delete(0, tk.END)
                
                # Grafikleri ve tabloları temizle
                self._show_empty_plots()
                if hasattr(self, 'stats_panel'):
                    self.stats_panel.clear_stats()
                self.selected_earthquake_var.set("Seçilen: Yok")
                
                # Durum mesajını güncelle
                self.earthquake_file_status_var.set("Henüz dosya yüklenmedi")
                self.earthquake_file_status_label.config(foreground="gray")
                
                messagebox.showinfo("Başarılı", f"Tüm {record_count} deprem kaydı temizlendi.")
                self.logger.info(f"Tüm deprem kayıtları temizlendi: {record_count} kayıt")
                
        except Exception as e:
            self.logger.exception(f"Kayıtları temizleme hatası: {e}")
            messagebox.showerror("Hata", f"Kayıtlar temizlenirken hata:\n{str(e)}")
    
    def _export_earthquake_to_excel(self, index: int) -> None:
        """Seçili deprem kaydının tüm verilerini Excel'e aktarır"""
        try:
            if index < 0 or index >= len(self.loaded_earthquake_files):
                return
                
            earthquake_record = self.loaded_earthquake_files[index]
            file_name = earthquake_record['name']
            
            if file_name not in self.processed_earthquake_data:
                messagebox.showerror("Hata", "Deprem kaydının verisi bulunamadı.")
                return
            
            earthquake_data = self.processed_earthquake_data[file_name]
            
            # Pandas DataFrame oluştur - tüm veriler
            import pandas as pd
            
            df = pd.DataFrame({
                'Zaman (s)': earthquake_data['time'],
                'İvme (g)': earthquake_data['acceleration'],
                'Hız (cm/s)': earthquake_data['velocity'],
                'Yerdeğiştirme (cm)': earthquake_data['displacement']
            })
            
            # Dosya kaydetme dialogu
            file_path = FileUtils.save_file_dialog(
                title=f"Deprem Kaydını Excel'e Aktar - {file_name}",
                filetypes=[("Excel dosyası", "*.xlsx")],
                default_extension=".xlsx",
                parent=self.root
            )
            
            if file_path:
                df.to_excel(file_path, index=False)
                
                messagebox.showinfo("Başarılı", 
                                  f"Deprem kaydı Excel'e aktarıldı:\n{file_path}\n\n"
                                  f"📊 Dosya: {file_name}\n"
                                  f"📋 Toplam {len(df)} satır kaydedildi\n"
                                  f"📈 Tüm veriler: İvme, Hız, Yerdeğiştirme\n"
                                  f"⏱️ Süre: {earthquake_data['time'][-1]:.2f} saniye")
                
            self.logger.info(f"Deprem kaydı Excel'e aktarıldı: {file_path}")
            self.logger.debug(f"Kaynak: {file_name}")
            self.logger.debug(f"Satır sayısı: {len(df):,}")
                
        except Exception as e:
            self.logger.exception(f"Excel aktarma hatası: {e}")
            messagebox.showerror("Hata", f"Excel'e aktarırken hata:\n{str(e)}")
    
    def _refresh_earthquake_listbox(self) -> None:
        """Deprem kayıtları listbox'ını yeniler"""
        try:
            # Listbox'ı temizle
            self.earthquake_listbox.delete(0, tk.END)
            
            # Tüm kayıtları yeniden ekle
            for i, earthquake_record in enumerate(self.loaded_earthquake_files):
                display_name = f"{i+1}. {earthquake_record['name']}"
                self.earthquake_listbox.insert(tk.END, display_name)
                
        except Exception as e:
            self.logger.exception(f"Listbox yenileme hatası: {e}") 
    
    def _show_plot_context_menu(self, event) -> None:
        """Grafiklerde sağ tık menüsünü gösterir"""
        try:
            # Seçili deprem kaydı var mı kontrol et
            selection = self.earthquake_listbox.curselection()
            if not selection:
                messagebox.showinfo("Bilgi", "Önce bir deprem kaydı seçin.", parent=self.root)
                return
                
            # Context menu oluÅŸtur
            context_menu = tk.Menu(self.root, tearoff=0)
            
            # Hangi grafiğin üzerinde olduğunu tespit et (gelişmiş özellik için)
            mouse_x = event.x
            mouse_y = event.y
            plot_area = self._detect_plot_area(mouse_x, mouse_y)
            
            if plot_area:
                context_menu.add_command(
                    label=f"📊 {plot_area} Grafiğini Kaydet",
                    command=lambda: self._save_specific_plot(plot_area.lower())
                )
                context_menu.add_separator()
            
            # Genel kaydetme seçenekleri
            context_menu.add_command(
                label="💾 Tüm Grafikleri Kaydet (PNG)",
                command=lambda: self._save_all_plots("png")
            )
            
            context_menu.add_command(
                label="🖼️ Tüm Grafikleri Kaydet (PDF)",
                command=lambda: self._save_all_plots("pdf")
            )
            
            context_menu.add_command(
                label="📄 Tüm Grafikleri Kaydet (SVG)",
                command=lambda: self._save_all_plots("svg")
            )
            
            context_menu.add_separator()
            
            # Grafik kopyalama
            context_menu.add_command(
                label="📋 Grafikleri Panoya Kopyala",
                command=self._copy_plots_to_clipboard
            )
            
            context_menu.add_separator()
            
            # Ayrı kaydetme seçenekleri
            submenu = tk.Menu(context_menu, tearoff=0)
            context_menu.add_cascade(label="📈 Ayrı Grafikler", menu=submenu)
            
            submenu.add_command(
                label="📊 İvme Grafiği",
                command=lambda: self._save_specific_plot("acceleration")
            )
            submenu.add_command(
                label="🚀 Hız Grafiği", 
                command=lambda: self._save_specific_plot("velocity")
            )
            submenu.add_command(
                label="📍 Yerdeğiştirme Grafiği",
                command=lambda: self._save_specific_plot("displacement")
            )
            
            context_menu.add_separator()
            
            # Grafik ayarları
            context_menu.add_command(
                label="⚙️ Grafik Ayarları",
                command=self._show_plot_settings
            )
            
            # Menüyü güvenli şekilde göster (tk_popup) ve kapanışta grab bırak
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    context_menu.grab_release()
                except Exception:
                    pass
            
        except Exception as e:
            self.logger.exception(f"Grafik context menu hatası: {e}")
    
    def _export_earthquake_advanced(self, index: int, format_type: str) -> None:
        """Seçili deprem kaydını gelişmiş formatlarda export eder"""
        try:
            if index >= len(self.loaded_earthquake_files):
                return
            
            # Seçili deprem kaydının verilerini al
            earthquake_record = self.loaded_earthquake_files[index]
            processed_data = earthquake_record['processed_data']
            
            time_data = processed_data['time']
            acceleration = processed_data['acceleration']
            velocity = processed_data['velocity']
            displacement = processed_data['displacement']
            
            # Metadata oluÅŸtur
            metadata = {
                'earthquake_info': {
                    'name': earthquake_record.get('name', 'Unknown'),
                    'original_filename': earthquake_record.get('original_filename', 'Unknown'),
                    'path': earthquake_record.get('path', 'Unknown')
                },
                'parameters': earthquake_record.get('parameters', {}),
                'processing_info': {
                    'format_type': processed_data.get('format_type', 'Unknown'),
                    'earthquake_name': processed_data.get('earthquake_name', 'Unknown'),
                    'original_units_info': processed_data.get('original_units_info', 'Unknown')
                },
                'units': {
                    'time': 's',
                    'acceleration': earthquake_record['parameters'].get('accel_unit', 'g'),
                    'velocity': earthquake_record['parameters'].get('velocity_unit', 'cm/s'),
                    'displacement': earthquake_record['parameters'].get('displacement_unit', 'cm')
                }
            }
            
            # Export iÅŸlemi
            success = AdvancedExporter.export_earthquake_data(
                time_data, acceleration, velocity, displacement,
                metadata, format_type
            )
            
            if success:
                self.logger.info(f"Deprem kaydı {format_type.upper()} formatında export edildi")
            
        except Exception as e:
            self.logger.exception(f"Gelişmiş export hatası: {e}")
            messagebox.showerror("Export Hatası", f"Export işlemi başarısız:\n{str(e)}", parent=self.root)
    
    def _show_export_dialog(self, index: int) -> None:
        """Export format seçim dialogunu gösterir"""
        try:
            if index >= len(self.loaded_earthquake_files):
                return
            
            # Seçili deprem kaydının verilerini al
            earthquake_record = self.loaded_earthquake_files[index]
            processed_data = earthquake_record['processed_data']
            
            time_data = processed_data['time']
            acceleration = processed_data['acceleration']
            velocity = processed_data['velocity']
            displacement = processed_data['displacement']
            
            # Metadata oluÅŸtur
            metadata = {
                'earthquake_info': {
                    'name': earthquake_record.get('name', 'Unknown'),
                    'original_filename': earthquake_record.get('original_filename', 'Unknown'),
                    'path': earthquake_record.get('path', 'Unknown')
                },
                'parameters': earthquake_record.get('parameters', {}),
                'processing_info': {
                    'format_type': processed_data.get('format_type', 'Unknown'),
                    'earthquake_name': processed_data.get('earthquake_name', 'Unknown'),
                    'original_units_info': processed_data.get('original_units_info', 'Unknown')
                },
                'units': {
                    'time': 's',
                    'acceleration': earthquake_record['parameters'].get('accel_unit', 'g'),
                    'velocity': earthquake_record['parameters'].get('velocity_unit', 'cm/s'),
                    'displacement': earthquake_record['parameters'].get('displacement_unit', 'cm')
                }
            }
            
            # Export dialog göster
            AdvancedExporter.show_export_dialog(
                time_data, acceleration, velocity, displacement, metadata
            )
            
        except Exception as e:
            self.logger.exception(f"Export dialog hatası: {e}")
            messagebox.showerror("Export Hatası", f"Export dialog açılamadı:\n{str(e)}", parent=self.root)
    
    def _setup_enhanced_keyboard_shortcuts(self) -> None:
        """Gelişmiş klavye kısayollarını ayarlar"""
        try:
            # Global kısayollar
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-o", "Deprem Kaydı Aç", 
                self.load_multiple_earthquake_records, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-s", "Mevcut Projeyi Kaydet", 
                self._save_current_project, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-e", "Export Dialog Aç", 
                self._show_export_dialog_current, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-Shift-s", "Farklı Kaydet", 
                self._save_project_as, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-n", "Yeni Proje", 
                self._new_project, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-q", "Programdan Çık", 
                self._quit_application, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "F1", "Yardım", 
                self._show_help, "global"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "F11", "Tam Ekran", 
                self._toggle_fullscreen, "global"
            )
            
            # Deprem kayıtları kısayolları
            self.enhanced_keyboard_manager.register_shortcut(
                "Delete", "Seçili Kaydı Sil", 
                self._delete_selected_earthquake, "earthquake"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-d", "Kaydı Çoğalt", 
                self._duplicate_selected_earthquake, "earthquake"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-i", "Kayıt Bilgileri", 
                self._show_selected_earthquake_info, "earthquake"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-r", "Kaydı Yeniden Yükle", 
                self._reload_selected_earthquake, "earthquake"
            )
            
            # Grafik kısayolları
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-Shift-e", "Grafikleri Export Et", 
                self._export_all_plots, "earthquake"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-z", "Zoom Reset", 
                self._reset_all_plots, "earthquake"
            )
            
            # Spektrum kısayolları
            self.enhanced_keyboard_manager.register_shortcut(
                "F5", "Spektrum Hesapla", 
                self._calculate_spectrum_shortcut, "spectrum"
            )
            
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-Shift-c", "Katsayıları Hesapla", 
                self._calculate_coefficients_shortcut, "spectrum"
            )
            
            # Yardım kısayolları
            self.enhanced_keyboard_manager.register_shortcut(
                "Control-Shift-k", "Kısayollar Yardımı", 
                self.enhanced_keyboard_manager.show_shortcuts_help, "global"
            )
            

            
            self.logger.info("Gelişmiş klavye kısayolları ayarlandı")
            
        except Exception as e:
            self.logger.exception(f"Klavye kısayolları ayarlama hatası: {e}")
    
    # Kısayol callback fonksiyonları
    def _save_current_project(self) -> None:
        """Mevcut projeyi kaydeder"""
        self.logger.info("Proje kaydetme - henüz implement edilmedi")
        messagebox.showinfo("Bilgi", "Proje kaydetme özelliği henüz geliştirilmemiştir.", parent=self.root)
    
    def _save_project_as(self) -> None:
        """Projeyi farklı kaydet"""
        self.logger.info("Farklı kaydet - henüz implement edilmedi")
        messagebox.showinfo("Bilgi", "Farklı kaydet özelliği henüz geliştirilmemiştir.", parent=self.root)
    
    def _new_project(self) -> None:
        """Yeni proje oluÅŸturur"""
        result = messagebox.askyesno(
            "Yeni Proje", 
            "Mevcut veriler temizlenecek. Devam etmek istiyor musunuz?",
            parent=self.root
        )
        if result:
            self._clear_all_earthquake_records()
            self.logger.info("Yeni proje oluÅŸturuldu")
    
    def _quit_application(self) -> None:
        """Programdan çıkar"""
        result = messagebox.askyesno(
            "Çıkış", 
            "Programdan çıkmak istediğinizden emin misiniz?",
            parent=self.root
        )
        if result:
            self.root.quit()
    
    def _show_help(self) -> None:
        """Yardım penceresini gösterir"""
        help_text = """
🎯 TBDY Spektrum Analiz Araçları

📋 Temel Özellikler:
• Deprem kaydı yükleme ve analiz
• İnteraktif grafik görüntüleme
• İstatistiksel analiz (PGA, PGV, PGD)
• Çoklu format desteği (AT2, VT2, DT2, ESM)
• Gelişmiş export seçenekleri

⌨️ Klavye Kısayolları:
• Ctrl+O: Dosya Aç
• Ctrl+S: Kaydet
• Ctrl+E: Export
• F1: Yardım
• F11: Tam Ekran
• Ctrl+Shift+K: Kısayollar Listesi

🔗 İletişim:
TBDY-2018 uyumlu spektrum analiz araçları
        """
        messagebox.showinfo("Yardım", help_text, parent=self.root)
    
    def _toggle_fullscreen(self) -> None:
        """Tam ekran modunu açar/kapatır"""
        current_state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current_state)
        self.logger.info(f"Tam ekran: {'Açık' if not current_state else 'Kapalı'}")
    
    def _show_export_dialog_current(self) -> None:
        """Mevcut seçili deprem için export dialog gösterir"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                self._show_export_dialog(index)
            else:
                messagebox.showwarning("Uyarı", "Önce bir deprem kaydı seçin!", parent=self.root)
        except Exception as e:
            self.logger.exception(f"Export dialog hatası: {e}")
    
    def _delete_selected_earthquake(self) -> None:
        """Seçili deprem kaydını siler"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                self._delete_earthquake_record(index)
            else:
                messagebox.showwarning("Uyarı", "Önce bir deprem kaydı seçin!", parent=self.root)
        except Exception as e:
            self.logger.exception(f"Deprem silme hatası: {e}")
    
    def _duplicate_selected_earthquake(self) -> None:
        """Seçili deprem kaydını çoğaltır"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                self._duplicate_earthquake_record(index)
            else:
                messagebox.showwarning("Uyarı", "Önce bir deprem kaydı seçin!", parent=self.root)
        except Exception as e:
            self.logger.exception(f"Deprem çoğaltma hatası: {e}")
    
    def _show_selected_earthquake_info(self) -> None:
        """Seçili deprem kaydının bilgilerini gösterir"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                self._show_earthquake_info(index)
            else:
                messagebox.showwarning("Uyarı", "Önce bir deprem kaydı seçin!", parent=self.root)
        except Exception as e:
            self.logger.exception(f"Deprem bilgileri hatası: {e}")
    
    def _reload_selected_earthquake(self) -> None:
        """Seçili deprem kaydını yeniden yükler"""
        try:
            selection = self.earthquake_listbox.curselection()
            if selection:
                index = selection[0]
                self._reload_earthquake_record(index)
            else:
                messagebox.showwarning("Uyarı", "Önce bir deprem kaydı seçin!")
        except Exception as e:
            self.logger.exception(f"Deprem yeniden yükleme hatası: {e}")
    
    def _export_all_plots(self) -> None:
        """Tüm grafikleri export eder"""
        self.logger.info("Tüm grafikleri export - henüz implement edilmedi")
        messagebox.showinfo("Bilgi", "Tüm grafikleri export özelliği henüz geliştirilmemiştir.", parent=self.root)
    
    def _reset_all_plots(self) -> None:
        """Tüm grafiklerin zoom'unu resetler"""
        try:
            if hasattr(self, 'interactive_plot'):
                self.interactive_plot._reset_view()
                self.logger.info("Tüm grafikler resetlendi")
        except Exception as e:
            self.logger.exception(f"Grafik reset hatası: {e}")
    
    def _calculate_spectrum_shortcut(self) -> None:
        """Spektrum hesaplama kısayolu"""
        try:
            self.logger.info("Kısayol: Spektrum hesapla")
            self.run_calculation_and_plot()
        except Exception as e:
            self.logger.exception(f"Kısayol hata: Spektrum hesaplama - {e}")
            messagebox.showerror("Hata", f"Spektrum hesaplanırken hata: {str(e)}", parent=self.root)
    
    def _calculate_coefficients_shortcut(self) -> None:
        """Katsayı hesaplama kısayolu"""
        try:
            self.logger.info("Kısayol: Katsayıları hesapla")
            # Mevcut parametre seti üzerinden sadece katsayılar/parametre sonuçlarını yaz
            params = self.input_panel.get_input_parameters()
            lat = float(params["lat"])
            lon = float(params["lon"])
            dd = params["earthquake_level"]
            zemin = params["soil_class"]
            ss, s1 = self.data_processor.get_parameters_for_location(lat, lon, dd)
            if ss is None:
                messagebox.showerror("Veri Hatası", "AFAD verileri alınamadı.", parent=self.root)
                return
            fs, f1 = self.coefficient_calculator.calculate_site_coefficients(ss, s1, zemin)
            if fs is None:
                messagebox.showerror("Hesaplama Hatası", "Zemin katsayıları hesaplanamadı.", parent=self.root)
                return
            SDS, SD1 = self.coefficient_calculator.calculate_design_parameters(ss, s1, fs, f1)
            results = {"ss": ss, "s1": s1, "fs": fs, "f1": f1, "SDS": SDS, "SD1": SD1}
            self.input_panel.set_results(results)
            self.logger.info("Katsayı hesapları güncellendi")
        except Exception as e:
            self.logger.exception(f"Kısayol hata: Katsayı hesaplama - {e}")
            messagebox.showerror("Hata", f"Katsayı hesaplanırken hata: {str(e)}", parent=self.root)
    

    
    def _detect_plot_area(self, mouse_x: int, mouse_y: int) -> Optional[str]:
        """Mouse pozisyonuna göre hangi grafik alanında olduğunu tespit eder"""
        try:
            # Canvas boyutlarını al
            canvas_width = self.time_series_canvas.get_tk_widget().winfo_width()
            canvas_height = self.time_series_canvas.get_tk_widget().winfo_height()
            
            if canvas_height == 0:
                return None
            
            # Yaklaşık grafik alanlarını hesapla (3 eşit grafik var)
            plot_height = canvas_height // 3
            
            if mouse_y < plot_height:
                return "İvme"
            elif mouse_y < plot_height * 2:
                return "Hız"
            elif mouse_y < plot_height * 3:
                return "Yerdeğiştirme"
            else:
                return None
                
        except Exception as e:
            self.logger.debug(f"Grafik alan tespiti hatası: {e}")
            return None
    
    def _save_all_plots(self, format_type: str = "png") -> None:
        """Tüm grafikleri birlikte kaydeder"""
        try:
            # Seçili deprem kaydının adını al
            selection = self.earthquake_listbox.curselection()
            if not selection:
                return
                
            index = selection[0]
            selected_file = self.loaded_earthquake_files[index]
            file_name = selected_file['name']
            
            # Dosya adını temizle (grafik için uygun hale getir)
            clean_name = file_name.replace('.', '_').replace(' ', '_')
            default_filename = f"{clean_name}_time_series.{format_type}"
            
            # Format'a göre filetypes
            if format_type == "png":
                filetypes = [("PNG dosyası", "*.png"), ("Tüm dosyalar", "*.*")]
            elif format_type == "pdf":
                filetypes = [("PDF dosyası", "*.pdf"), ("Tüm dosyalar", "*.*")]
            elif format_type == "svg":
                filetypes = [("SVG dosyası", "*.svg"), ("Tüm dosyalar", "*.*")]
            else:
                filetypes = [("Tüm dosyalar", "*.*")]
            
            # Kaydetme dialogu
            file_path = FileUtils.save_file_dialog(
                title=f"Tüm Grafikleri Kaydet ({format_type.upper()})",
                filetypes=filetypes,
                default_extension=f".{format_type}",
                parent=self.root
            )
            
            if file_path:
                # DPI ayarı format'a göre
                dpi = 300 if format_type == "png" else 150
                
                # Grafikleri kaydet
                self.time_series_figure.savefig(
                    file_path, 
                    dpi=dpi, 
                    bbox_inches='tight',
                    facecolor='white', 
                    edgecolor='none',
                    format=format_type
                )
                
                messagebox.showinfo("Başarılı", 
                                  f"Tüm grafikler başarıyla kaydedildi:\n{file_path}\n\n"
                                  f"📊 Dosya: {file_name}\n"
                                  f"🖼️ Format: {format_type.upper()}\n"
                                  f"📐 DPI: {dpi}")
                
                self.logger.info(f"Tüm grafikler kaydedildi: {file_path}")
                
        except Exception as e:
            self.logger.exception(f"Grafik kaydetme hatası: {e}")
            messagebox.showerror("Hata", f"Grafik kaydedilirken hata:\n{str(e)}")
    
    def _save_specific_plot(self, plot_type: str = "acceleration") -> None:
        """Belirli bir grafiÄŸi kaydeder"""
        try:
            # Seçili deprem kaydının adını al
            selection = self.earthquake_listbox.curselection()
            if not selection:
                return
                
            index = selection[0]
            selected_file = self.loaded_earthquake_files[index]
            file_name = selected_file['name']
            
            # Plot type'ı normalize et (Türkçe ve İngilizce kabul et)
            plot_type_lower = plot_type.lower()
            
            # Türkçe karakter sorunu için ekstra normalizasyon
            plot_type_normalized = plot_type_lower.replace('i̇', 'i').replace('ı', 'i')
            
            self.logger.debug(f"Grafik türü analizi: '{plot_type}' → '{plot_type_lower}' → '{plot_type_normalized}'")
            
            # Türkçe-İngilizce mapping (tüm varyasyonları kapsayan)
            if (plot_type_normalized in ["acceleration", "ivme", "i̇vme"] or 
                plot_type in ["İvme", "Ivme", "IVME"]):
                ax_to_save = self.accel_ax
                plot_name = "İvme"
                file_suffix = "acceleration"
            elif (plot_type_normalized in ["velocity", "hiz", "hız"] or 
                  plot_type in ["Hız", "HIZ", "Hiz"]):
                ax_to_save = self.velocity_ax
                plot_name = "Hız"
                file_suffix = "velocity"
            elif (plot_type_normalized in ["displacement", "yerdeğiştirme", "yerdegistirme"] or 
                  plot_type in ["Yerdeğiştirme", "YERDEĞİŞTİRME", "Yerdegistirme", "YERDEGISTIRME"]):
                ax_to_save = self.displacement_ax
                plot_name = "Yerdeğiştirme"
                file_suffix = "displacement"
            else:
                self.logger.error(f"Bilinmeyen grafik türü: '{plot_type}'")
                self.logger.debug(f"Lower: '{plot_type_lower}'")
                self.logger.debug(f"Normalized: '{plot_type_normalized}'")
                messagebox.showerror("Hata", f"Bilinmeyen grafik türü: {plot_type}\n\nDesteklenen türler: İvme, Hız, Yerdeğiştirme")
                return
            
            # Dosya adını oluştur
            clean_name = file_name.replace('.', '_').replace(' ', '_')
            default_filename = f"{clean_name}_{file_suffix}.png"
            
            self.logger.info(f"{plot_name} grafiÄŸi kaydediliyor...")
            
            # Kaydetme dialogu
            file_path = FileUtils.save_file_dialog(
                title=f"{plot_name} GrafiÄŸini Kaydet",
                filetypes=[("PNG dosyası", "*.png"), ("PDF dosyası", "*.pdf"), ("SVG dosyası", "*.svg")],
                default_extension=".png",
                parent=self.root
            )
            
            if file_path:
                # Hızlı seçenekler
                save_options = self._ask_quick_save_options(default_format=file_path.split('.')[-1], default_dpi=300) or {'dpi': 300}
                # Renderer güvenceye al ve grafik bounding box'ını al
                try:
                    self.time_series_canvas.draw()
                except Exception:
                    try:
                        self.time_series_figure.canvas.draw()
                    except Exception:
                        pass
                renderer = None
                try:
                    renderer = self.time_series_figure.canvas.get_renderer()
                except Exception:
                    renderer = None
                bbox = ax_to_save.get_tightbbox(renderer) if renderer is not None else None
                if bbox:
                    bbox_inches = bbox.transformed(self.time_series_figure.dpi_scale_trans.inverted())
                else:
                    bbox_inches = 'tight'
                
                # Dosya formatını tespit et
                file_ext = file_path.lower().split('.')[-1]
                
                # GrafiÄŸi kaydet
                self.time_series_figure.savefig(
                    file_path,
                dpi=save_options['dpi'],
                    bbox_inches=bbox_inches,
                    facecolor='white',
                    edgecolor='none',
                    format=file_ext
                )
                
                messagebox.showinfo("Başarılı", 
                                  f"{plot_name} grafiği başarıyla kaydedildi:\n{file_path}\n\n"
                                     f"📊 Dosya: {file_name}\n"
                                     f"📈 Grafik: {plot_name}",
                                     parent=self.root)
                
                self.logger.info(f"{plot_name} grafiÄŸi kaydedildi: {file_path}")
                
        except Exception as e:
            self.logger.exception(f"Spesifik grafik kaydetme hatası: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Hata", f"Grafik kaydedilirken hata:\n{str(e)}", parent=self.root)
    
    def _copy_plots_to_clipboard(self) -> None:
        """Grafikleri panoya kopyalar (Windows)"""
        try:
            # Sadece Windows'ta desteklenir
            import platform
            if platform.system().lower() != 'windows':
                messagebox.showwarning(
                    "Uyarı",
                    "Panoya görüntü kopyalama özelliği şu an sadece Windows'ta desteklenmektedir.",
                    parent=self.root
                )
                return

            # Geçici dosya oluştur
            import tempfile
            import os
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name
            
            # Grafikleri geçici dosyaya kaydet
            self.time_series_figure.savefig(
                temp_path,
                dpi=150,
                bbox_inches='tight',
                facecolor='white',
                edgecolor='none',
                format='png'
            )
            
            try:
                # Windows clipboard'a kopyala
                import subprocess
                
                # PowerShell komutu ile clipboard'a kopyala
                cmd = f'''
                Add-Type -AssemblyName System.Windows.Forms
                [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile("{temp_path}"))
                '''
                
                subprocess.run(['powershell', '-Command', cmd], 
                             check=True, capture_output=True, text=True)
                
                messagebox.showinfo("Başarılı", "Grafikler panoya kopyalandı!\n\nWord, PowerPoint veya diğer uygulamalara Ctrl+V ile yapıştırabilirsiniz.", parent=self.root)
                self.logger.info("Grafikler panoya kopyalandı")
                
            except Exception as clipboard_error:
                self.logger.debug(f"Panoya kopyalama hatası: {clipboard_error}")
                messagebox.showwarning("Uyarı", 
                                     f"Panoya kopyalama başarısız oldu.\n\n"
                                     f"Grafik geçici dosyaya kaydedildi:\n{temp_path}\n\n"
                                     f"Bu dosyayı manuel olarak kopyalayabilirsiniz.",
                                     parent=self.root)
            
            # Geçici dosyayı temizle (biraz bekle)
            def cleanup_temp():
                try:
                    import time
                    time.sleep(2)  # Clipboard işlemi için bekle
                    os.unlink(temp_path)
                except:
                    pass
            
            import threading
            threading.Thread(target=cleanup_temp, daemon=True).start()
            
        except Exception as e:
            self.logger.exception(f"Panoya kopyalama hatası: {e}")
            messagebox.showerror("Hata", f"Grafik panoya kopyalanırken hata:\n{str(e)}", parent=self.root)
    
    def _show_plot_settings(self):
        """Grafik ayarları dialogunu gösterir"""
        try:
            # Basit ayarlar dialogu
            settings_dialog = tk.Toplevel(self.root)
            settings_dialog.title("Grafik Ayarları")
            settings_dialog.geometry("400x300")
            settings_dialog.transient(self.root)
            settings_dialog.grab_set()
            
            # İçerik frame
            content_frame = ttk.Frame(settings_dialog, padding="15")
            content_frame.pack(fill="both", expand=True)
            
            # Başlık
            ttk.Label(content_frame, text="🎨 Grafik Görünüm Ayarları", 
                     font=('Segoe UI', 12, 'bold')).pack(pady=(0, 15))
            
            # DPI ayarı
            dpi_frame = ttk.LabelFrame(content_frame, text="Kaydetme Kalitesi (DPI)", padding=10)
            dpi_frame.pack(fill="x", pady=(0, 10))
            
            dpi_var = tk.StringVar(value="300")
            dpi_options = [("Düşük (150 DPI)", "150"), ("Orta (300 DPI)", "300"), ("Yüksek (600 DPI)", "600")]
            
            for text, value in dpi_options:
                ttk.Radiobutton(dpi_frame, text=text, variable=dpi_var, 
                               value=value).pack(anchor="w", pady=2)
            
            # Format ayarı
            format_frame = ttk.LabelFrame(content_frame, text="Varsayılan Format", padding=10)
            format_frame.pack(fill="x", pady=(0, 10))
            
            format_var = tk.StringVar(value="png")
            format_options = [("PNG (Renkli)", "png"), ("PDF (Vektör)", "pdf"), ("SVG (Vektör)", "svg")]
            
            for text, value in format_options:
                ttk.Radiobutton(format_frame, text=text, variable=format_var,
                               value=value).pack(anchor="w", pady=2)
            
            # Butonlar
            button_frame = ttk.Frame(content_frame)
            button_frame.pack(fill="x", pady=(15, 0))
            
            ttk.Button(button_frame, text="Tamam", 
                      command=settings_dialog.destroy).pack(side="right", padx=(5, 0))
            ttk.Button(button_frame, text="İptal",
                      command=settings_dialog.destroy).pack(side="right")
            
            messagebox.showinfo("Bilgi", "Grafik ayarları özelliÄŸi geliÅŸtirilme aÅŸamasında.\n\nÅŞu an varsayılan ayarlar kullanılmaktadır.", parent=self.root)
            
        except Exception as e:
            self.logger.exception(f"Grafik ayarları hatası: {e}")
            messagebox.showerror("Hata", f"Grafik ayarları açılırken hata:\n{str(e)}", parent=self.root)

    def _ask_quick_save_options(self, default_format='png', default_dpi=300):
        """Hızlı kaydetme seçeneklerini sorar (format + DPI)."""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Kaydetme Seçenekleri")
            dialog.transient(self.root)
            dialog.grab_set()
            frm = ttk.Frame(dialog, padding=10)
            frm.pack(fill='both', expand=True)

            ttk.Label(frm, text="Format:").grid(row=0, column=0, sticky='w')
            fmt_var = tk.StringVar(value=default_format)
            fmt_combo = ttk.Combobox(frm, textvariable=fmt_var, state='readonly', width=12)
            fmt_combo['values'] = ['png', 'pdf', 'svg']
            fmt_combo.grid(row=0, column=1, sticky='w', padx=(6, 0))

            ttk.Label(frm, text="DPI:").grid(row=1, column=0, sticky='w', pady=(6, 0))
            dpi_var = tk.StringVar(value=str(default_dpi))
            dpi_combo = ttk.Combobox(frm, textvariable=dpi_var, state='readonly', width=12)
            dpi_combo['values'] = ['150', '300', '600']
            dpi_combo.grid(row=1, column=1, sticky='w', padx=(6, 0), pady=(6, 0))

            result = {'ok': False}
            def on_ok():
                result['ok'] = True
                dialog.destroy()
            def on_cancel():
                result['ok'] = False
                dialog.destroy()

            btns = ttk.Frame(frm)
            btns.grid(row=2, column=0, columnspan=2, sticky='e', pady=(10, 0))
            ttk.Button(btns, text='İptal', command=on_cancel).pack(side='right', padx=6)
            ttk.Button(btns, text='Tamam', command=on_ok).pack(side='right')

            self.root.wait_window(dialog)
            if not result['ok']:
                return None
            return {
                'format': fmt_var.get(),
                'dpi': int(dpi_var.get())
            }
        except Exception as e:
            self.logger.debug(f"Hızlı kaydet seçenekleri hatası: {e}")
            return {'format': default_format, 'dpi': default_dpi}
    
    def _update_unit_display(self):
        """Toolbar'daki birim göstergelerini günceller"""
        try:
            # Varsayılan birimler
            accel_unit = "g"
            velocity_unit = "cm/s"  
            displacement_unit = "cm"
            
            # Eğer yüklenmiş deprem kaydı varsa, o kaydın birimlerini kullan
            if hasattr(self, 'loaded_earthquake_files') and self.loaded_earthquake_files:
                current_selection = getattr(self, 'earthquake_listbox', None)
                if current_selection and hasattr(current_selection, 'curselection'):
                    selection = current_selection.curselection()
                    if selection:
                        index = selection[0]
                        if index < len(self.loaded_earthquake_files):
                            params = self.loaded_earthquake_files[index]['parameters']
                            accel_unit = params.get('accel_unit', 'g')
                            velocity_unit = params.get('velocity_unit', 'cm/s')
                            displacement_unit = params.get('displacement_unit', 'cm')
            
            # DoÄŸru birim simgelerini al
            from ..utils.unit_converter import UnitConverter
            
            # İvme birimi için doğru symbol al
            accel_unit_info = UnitConverter.get_unit_info('acceleration', accel_unit)
            accel_symbol = accel_unit_info.get('symbol', accel_unit)
            
            # Hız birimi için doğru format (manuel)
            velocity_symbol = velocity_unit  # "cm/s" zaten doÄŸru format
            
            # Yerdeğiştirme birimi için doğru symbol al
            disp_unit_info = UnitConverter.get_unit_info('displacement', displacement_unit)
            disp_symbol = disp_unit_info.get('symbol', displacement_unit)
            
            # Toolbar birim göstergelerini güncelle
            if hasattr(self, 'accel_unit_label'):
                self.accel_unit_label.config(text=f"İvme: {accel_symbol}")
            if hasattr(self, 'velocity_unit_label'):
                self.velocity_unit_label.config(text=f"Hız: {velocity_symbol}")
            if hasattr(self, 'displacement_unit_label'):
                self.displacement_unit_label.config(text=f"Yerdeğiştirme: {disp_symbol}")
                
        except Exception as e:
            self.logger.debug(f"Birim gösterge güncelleme hatası: {e}")

    def _create_basic_scaling_tab(self):
        """Deprem Kaydı Ölçekleme alt sekmesini oluşturur"""
        tab = ttk.Frame(self.earthquake_sub_notebook)
        self.earthquake_sub_notebook.add(tab, text="🧮 Deprem Kaydı Ölçekleme")
        # Records provider from PairManager
        def _records_provider():
            try:
                return self.pair_manager.get_pairs()
            except Exception as ex:
                self.logger.debug(f"PairManager hata: {ex}")
                return []
        # Accel unit getter from InputPanel
        def _accel_unit_getter():
            try:
                return self.input_panel.get_unit_settings().get('acceleration_unit', 'g')
            except Exception:
                return 'g'
        self.basic_scaling_panel = BasicScalingPanel(
            tab,
            _records_provider,
            accel_unit_getter=_accel_unit_getter,
            design_params_model=getattr(self, 'design_params', None),
            input_panel=self.input_panel,
        )
        # PairManager referansını panele ver (manuelleştirme için)
        try:
            setattr(self.basic_scaling_panel, 'pair_manager', self.pair_manager)
        except Exception:
            pass
