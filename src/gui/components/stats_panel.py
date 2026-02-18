"""
Deprem kaydı istatistik paneli bileşeni
PGA, PGV, PGD ve diğer deprem mühendisliği parametrelerini gösterir
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional

try:
    from ..dialogs.pair_selection_dialog import PairSelectionDialog
except Exception:
    try:
        from src.gui.dialogs.pair_selection_dialog import PairSelectionDialog
    except Exception:
        PairSelectionDialog = None

# Renk paleti (tutarlı kullanım için)
_COLOR_PGA = "#d32f2f"   # accent/red
_COLOR_PGV = "#2e7d32"   # green
_COLOR_PGD = "#6a1b9a"   # purple
_COLOR_RMS = "#1976d2"   # blue

# Matplotlib (opsiyonel)
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
except Exception:
    FigureCanvasTkAgg = None
    plt = None

# Opsiyonel formatlayıcı (kullanılmayacak); panel için sabit 4 ondalık + binlik
_fmt_eng = None

# Opsiyonel FileUtils: Excel aktarma için merkezi yardımcı
try:
    from src.utils.file_utils import FileUtils as _FileUtils
except Exception:
    try:
        from utils.file_utils import FileUtils as _FileUtils
    except Exception:
        _FileUtils = None

def _fallback_format(value, unit, precision: Optional[int] = None) -> str:
    try:
        prec = 4 if precision is None else int(precision)
        return f"{float(value):,.{prec}f} {unit}".strip()
    except Exception:
        return f"{value} {unit}".strip()

def _format_value(value, unit, precision: Optional[int] = None) -> str:
    # Bu panel için sabit 4 ondalık + binlik ayracı kullan
    return _fallback_format(value, unit, precision)

def _format_value_only(value, precision: Optional[int] = None) -> str:
    """Sadece sayısal değeri biçimlendirir (birimsiz)."""
    try:
        prec = 4 if precision is None else int(precision)
        return f"{float(value):,.{prec}f}"
    except Exception:
        return f"{value}"

# ────────────────────────────────
# Basit Tooltip yardımcıları
# ────────────────────────────────
class _ToolTip:
    def __init__(self, widget, text: str, delay_ms: int = 500):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tipwindow = None
        self._after_id = None
        try:
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)
            widget.bind("<ButtonPress>", self._on_leave)
        except Exception:
            pass

    def _on_enter(self, event=None):
        try:
            self._after_id = self.widget.after(self.delay_ms, self._show_tip)
        except Exception:
            pass

    def _on_leave(self, event=None):
        try:
            if self._after_id is not None:
                self.widget.after_cancel(self._after_id)
                self._after_id = None
            self._hide_tip()
        except Exception:
            pass

    def _show_tip(self):
        if self.tipwindow or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        except Exception:
            x, y, cx, cy = (0, 0, 0, 0)
        x = x + self.widget.winfo_rootx() + 20
        y = y + self.widget.winfo_rooty() + 20
        try:
            tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(tw, text=self.text, justify="left", background="#ffffe0", relief="solid", borderwidth=1, padding=(6, 4))
            label.pack(ipadx=1)
            self.tipwindow = tw
        except Exception:
            self.tipwindow = None

    def _hide_tip(self):
        try:
            tw = self.tipwindow
            self.tipwindow = None
            if tw is not None:
                tw.destroy()
        except Exception:
            pass

class StatsPanel:
    """Deprem istatistik paneli sınıfı"""
    
    def __init__(self, parent_frame, main_window=None):
        """
        Args:
            parent_frame: Ana çerçeve
            main_window: Ana pencere referansı (isteğe bağlı)
        """
        self.parent_frame = parent_frame
        self.main_window = main_window
        self.stats_data = {}
        
        # GUI bileşenleri
        self.stats_tree = None
        self.stats_frame = None
        
        # Değişkenler
        self.stats_vars = {}
        self.spark_canvases = {}
        
        self._create_widgets()

    def set_main_window(self, main_window) -> None:
        """Ana pencere referansını günceller."""
        self.main_window = main_window

    # ────────────────────────────────
    # Zaman serisi aktarımı (sparkline için)
    # ────────────────────────────────
    def update_series(self, time, acceleration=None, velocity=None, displacement=None):
        """Sparkline çizimleri için ham zaman serilerini saklar."""
        try:
            import numpy as _np
            self.series_time = _np.asarray(time) if time is not None else None
            self.series_acceleration = _np.asarray(acceleration) if acceleration is not None else None
            self.series_velocity = _np.asarray(velocity) if velocity is not None else None
            self.series_displacement = _np.asarray(displacement) if displacement is not None else None
        except Exception:
            self.series_time = time
            self.series_acceleration = acceleration
            self.series_velocity = velocity
            self.series_displacement = displacement

    def _create_sparkline(self, parent, key: str, color: str, row: int, column: int, columnspan: int = 3):
        """Kart içine 60px yükseklikte sparkline alanı oluşturur."""
        if FigureCanvasTkAgg is None or plt is None:
            return
        try:
            dpi = 100
            fig = plt.Figure(figsize=(3.0, 0.6), dpi=dpi)
            ax = fig.add_subplot(111)
            ax.set_axis_off()
            ax.margins(x=0.01, y=0.1)
            canvas = FigureCanvasTkAgg(fig, master=parent)
            widget = canvas.get_tk_widget()
            widget.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=0, pady=(6, 0))
            self.spark_canvases[key] = { 'fig': fig, 'ax': ax, 'canvas': canvas }
        except Exception:
            pass

    def _update_sparkline(self, key: str, x_data, y_data, color: str):
        """Belirtilen sparkline tuvalini günceller."""
        if FigureCanvasTkAgg is None or plt is None:
            return
        try:
            sp = self.spark_canvases.get(key)
            if sp is None:
                return
            ax = sp['ax']
            ax.clear()
            ax.set_axis_off()
            if x_data is not None and y_data is not None and len(x_data) > 1 and len(y_data) > 1:
                # NaN temizliği (görsellik için)
                try:
                    import numpy as _np
                    x_arr = _np.asarray(x_data)
                    y_arr = _np.asarray(y_data)
                    finite = _np.isfinite(x_arr) & _np.isfinite(y_arr)
                    x_arr = x_arr[finite]
                    y_arr = y_arr[finite]
                except Exception:
                    x_arr, y_arr = x_data, y_data
                if len(x_arr) > 1 and len(y_arr) > 1:
                    ax.plot(x_arr, y_arr, color=color, linewidth=0.9)
                    ax.margins(x=0.01, y=0.1)
            sp['canvas'].draw_idle()
        except Exception:
            pass
    
    def _create_widgets(self):
        """Widget'ları oluşturur"""
        # Ana çerçeve
        self.stats_frame = ttk.Frame(self.parent_frame, padding=6)
        self.stats_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Kart tarzı görünümler için basit stil (varsa üzerine yazmaz)
        try:
            style = ttk.Style()
            style.configure("Card.TLabelframe", padding=8)
            style.configure("Card.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
            style.configure("MetricBig.TLabel", font=("Segoe UI", 12, "bold"))
            style.configure("MetricUnit.TLabel", foreground="#666")
            style.configure("Info.TLabel", foreground="#777", font=("Segoe UI", 9))
        except Exception:
            pass
        
        # Sekmesiz görünüm: Kayıt Bilgileri içeriğini doğrudan panelde göster
        self._create_record_info_tab()
    
    def _create_basic_stats_tab(self):
        """Temel istatistikler sekmesini oluşturur (PGA, PGV, PGD, RMS)"""
        basic_tab = ttk.Frame(self.stats_notebook)
        self.stats_notebook.add(basic_tab, text="Temel")
        
        # Scrollable frame
        canvas = tk.Canvas(basic_tab)
        scrollbar = ttk.Scrollbar(basic_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        # İç çerçeveyi tuvale ekle ve genişliği tuval genişliğine eşitle
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        def _on_canvas_configure(event):
            try:
                canvas.itemconfigure(window_id, width=event.width)
            except Exception:
                pass
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Tek sütunlu kart ızgarası
        try:
            scrollable_frame.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        card_padx, card_pady = 6, 6
        
        # PGA Bölümü (Kart görünümü)
        pga_frame = ttk.LabelFrame(scrollable_frame, text="PGA", padding=8, style="Card.TLabelframe")
        pga_frame.grid(row=0, column=0, sticky="ew", padx=card_padx, pady=card_pady)
        try:
            pga_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.stats_vars['pga_value'] = tk.StringVar(value="--")
        self.stats_vars['pga_unit'] = tk.StringVar(value="g")
        self.stats_vars['pga_pos'] = tk.StringVar(value="--")
        self.stats_vars['pga_neg'] = tk.StringVar(value="--")
        
        pga_lbl_max = ttk.Label(pga_frame, text="Maksimum:", width=12, anchor="w")
        pga_lbl_max.grid(row=0, column=0, sticky="w", padx=5)
        # Değer + birim için sıkı yatay konteyner
        pga_max_container = ttk.Frame(pga_frame)
        pga_max_container.grid(row=0, column=1, sticky="ew")
        try:
            pga_max_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        pga_val_max = ttk.Label(pga_max_container, textvariable=self.stats_vars['pga_value'], style="MetricBig.TLabel", 
                 foreground=_COLOR_PGA, anchor="e")
        pga_val_max.grid(row=0, column=0, sticky="e", padx=(0, 2))
        pga_unit_max = ttk.Label(pga_max_container, textvariable=self.stats_vars['pga_unit'], style="MetricUnit.TLabel")
        pga_unit_max.grid(row=0, column=1, sticky="w")
        # Sparkline alanı kaldırıldı (PGA)
        # Başlık yanına ‘i’ tooltip etiketi
        try:
            info_pga = ttk.Label(pga_frame, text="ⓘ", style="Info.TLabel", cursor="question_arrow")
            info_pga.grid(row=0, column=2, sticky="e", padx=(4, 0))
            _ToolTip(info_pga, "PGA: Peak Ground Acceleration (tepe ivme)")
        except Exception:
            pass
        
        pga_lbl_pos = ttk.Label(pga_frame, text="Pozitif:", width=12, anchor="w")
        pga_lbl_pos.grid(row=1, column=0, sticky="w", padx=5)
        pga_val_pos = ttk.Label(pga_frame, textvariable=self.stats_vars['pga_pos'], style="Value.TLabel")
        pga_val_pos.grid(row=1, column=1, sticky="e", padx=5)
        
        pga_lbl_neg = ttk.Label(pga_frame, text="Negatif:", width=12, anchor="w")
        pga_lbl_neg.grid(row=2, column=0, sticky="w", padx=5)
        pga_val_neg = ttk.Label(pga_frame, textvariable=self.stats_vars['pga_neg'], style="Value.TLabel")
        pga_val_neg.grid(row=2, column=1, sticky="e", padx=5)
        
        # PGV Bölümü
        pgv_frame = ttk.LabelFrame(scrollable_frame, text="PGV", padding=8, style="Card.TLabelframe")
        pgv_frame.grid(row=1, column=0, sticky="ew", padx=card_padx, pady=card_pady)
        try:
            pgv_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.stats_vars['pgv_value'] = tk.StringVar(value="--")
        self.stats_vars['pgv_unit'] = tk.StringVar(value="cm/s")
        self.stats_vars['pgv_pos'] = tk.StringVar(value="--")
        self.stats_vars['pgv_neg'] = tk.StringVar(value="--")
        
        pgv_lbl_max = ttk.Label(pgv_frame, text="Maksimum:", width=12, anchor="w")
        pgv_lbl_max.grid(row=0, column=0, sticky="w", padx=5)
        pgv_max_container = ttk.Frame(pgv_frame)
        pgv_max_container.grid(row=0, column=1, sticky="ew")
        try:
            pgv_max_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        pgv_val_max = ttk.Label(pgv_max_container, textvariable=self.stats_vars['pgv_value'], style="MetricBig.TLabel", 
                 foreground=_COLOR_PGV, anchor="e")
        pgv_val_max.grid(row=0, column=0, sticky="e", padx=(0, 2))
        pgv_unit_max = ttk.Label(pgv_max_container, textvariable=self.stats_vars['pgv_unit'], style="MetricUnit.TLabel")
        pgv_unit_max.grid(row=0, column=1, sticky="w")
        # Sparkline alanı kaldırıldı (PGV)
        try:
            info_pgv = ttk.Label(pgv_frame, text="ⓘ", style="Info.TLabel", cursor="question_arrow")
            info_pgv.grid(row=0, column=2, sticky="e", padx=(4, 0))
            _ToolTip(info_pgv, "PGV: Peak Ground Velocity (tepe hız)")
        except Exception:
            pass
        
        pgv_lbl_pos = ttk.Label(pgv_frame, text="Pozitif:", width=12, anchor="w")
        pgv_lbl_pos.grid(row=1, column=0, sticky="w", padx=5)
        pgv_val_pos = ttk.Label(pgv_frame, textvariable=self.stats_vars['pgv_pos'], style="Value.TLabel")
        pgv_val_pos.grid(row=1, column=1, sticky="e", padx=5)
        
        pgv_lbl_neg = ttk.Label(pgv_frame, text="Negatif:", width=12, anchor="w")
        pgv_lbl_neg.grid(row=2, column=0, sticky="w", padx=5)
        pgv_val_neg = ttk.Label(pgv_frame, textvariable=self.stats_vars['pgv_neg'], style="Value.TLabel")
        pgv_val_neg.grid(row=2, column=1, sticky="e", padx=5)
        
        # PGD Bölümü
        pgd_frame = ttk.LabelFrame(scrollable_frame, text="PGD", padding=8, style="Card.TLabelframe")
        pgd_frame.grid(row=2, column=0, sticky="ew", padx=card_padx, pady=card_pady)
        try:
            pgd_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.stats_vars['pgd_value'] = tk.StringVar(value="--")
        self.stats_vars['pgd_unit'] = tk.StringVar(value="cm")
        self.stats_vars['pgd_pos'] = tk.StringVar(value="--")
        self.stats_vars['pgd_neg'] = tk.StringVar(value="--")
        
        pgd_lbl_max = ttk.Label(pgd_frame, text="Maksimum:", width=12, anchor="w")
        pgd_lbl_max.grid(row=0, column=0, sticky="w", padx=5)
        pgd_max_container = ttk.Frame(pgd_frame)
        pgd_max_container.grid(row=0, column=1, sticky="ew")
        try:
            pgd_max_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        pgd_val_max = ttk.Label(pgd_max_container, textvariable=self.stats_vars['pgd_value'], style="MetricBig.TLabel", 
                 foreground=_COLOR_PGD, anchor="e")
        pgd_val_max.grid(row=0, column=0, sticky="e", padx=(0, 2))
        pgd_unit_max = ttk.Label(pgd_max_container, textvariable=self.stats_vars['pgd_unit'], style="MetricUnit.TLabel")
        pgd_unit_max.grid(row=0, column=1, sticky="w")
        # Sparkline alanı kaldırıldı (PGD)
        try:
            info_pgd = ttk.Label(pgd_frame, text="ⓘ", style="Info.TLabel", cursor="question_arrow")
            info_pgd.grid(row=0, column=2, sticky="e", padx=(4, 0))
            _ToolTip(info_pgd, "PGD: Peak Ground Displacement (tepe yerdeğiştirme)")
        except Exception:
            pass
        
        pgd_lbl_pos = ttk.Label(pgd_frame, text="Pozitif:", width=12, anchor="w")
        pgd_lbl_pos.grid(row=1, column=0, sticky="w", padx=5)
        pgd_val_pos = ttk.Label(pgd_frame, textvariable=self.stats_vars['pgd_pos'], style="Value.TLabel")
        pgd_val_pos.grid(row=1, column=1, sticky="e", padx=5)
        
        pgd_lbl_neg = ttk.Label(pgd_frame, text="Negatif:", width=12, anchor="w")
        pgd_lbl_neg.grid(row=2, column=0, sticky="w", padx=5)
        pgd_val_neg = ttk.Label(pgd_frame, textvariable=self.stats_vars['pgd_neg'], style="Value.TLabel")
        pgd_val_neg.grid(row=2, column=1, sticky="e", padx=5)
        
        # RMS Bölümü
        rms_frame = ttk.LabelFrame(scrollable_frame, text="RMS", padding=8, style="Card.TLabelframe")
        rms_frame.grid(row=3, column=0, sticky="ew", padx=card_padx, pady=card_pady)
        try:
            rms_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.stats_vars['rms_accel_value'] = tk.StringVar(value="--")
        self.stats_vars['rms_accel_unit'] = tk.StringVar(value="")
        self.stats_vars['rms_velocity_value'] = tk.StringVar(value="--")
        self.stats_vars['rms_velocity_unit'] = tk.StringVar(value="")
        self.stats_vars['rms_displacement_value'] = tk.StringVar(value="--")
        self.stats_vars['rms_displacement_unit'] = tk.StringVar(value="")
        
        rms_lbl_acc = ttk.Label(rms_frame, text="İvme RMS:", width=12, anchor="w")
        rms_lbl_acc.grid(row=0, column=0, sticky="w", padx=5)
        rms_acc_container = ttk.Frame(rms_frame)
        rms_acc_container.grid(row=0, column=1, sticky="ew", padx=5)
        try:
            rms_acc_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        rms_val_acc = ttk.Label(
            rms_acc_container,
            textvariable=self.stats_vars['rms_accel_value'],
            style="MetricBig.TLabel",
            foreground=_COLOR_RMS
        )
        rms_val_acc.grid(row=0, column=0, sticky="e", padx=(0, 2))
        rms_unit_acc = ttk.Label(rms_acc_container, textvariable=self.stats_vars['rms_accel_unit'], style="MetricUnit.TLabel")
        rms_unit_acc.grid(row=0, column=1, sticky="w")
        
        rms_lbl_vel = ttk.Label(rms_frame, text="Hız RMS:", width=12, anchor="w")
        rms_lbl_vel.grid(row=1, column=0, sticky="w", padx=5)
        rms_vel_container = ttk.Frame(rms_frame)
        rms_vel_container.grid(row=1, column=1, sticky="ew", padx=5)
        try:
            rms_vel_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        rms_val_vel = ttk.Label(rms_vel_container, textvariable=self.stats_vars['rms_velocity_value'])
        rms_val_vel.grid(row=0, column=0, sticky="e", padx=(0, 2))
        rms_unit_vel = ttk.Label(rms_vel_container, textvariable=self.stats_vars['rms_velocity_unit'], style="MetricUnit.TLabel")
        rms_unit_vel.grid(row=0, column=1, sticky="w")
        
        rms_lbl_disp = ttk.Label(rms_frame, text="Yerdeğiştirme RMS:", width=12, anchor="w")
        rms_lbl_disp.grid(row=2, column=0, sticky="w", padx=5)
        rms_disp_container = ttk.Frame(rms_frame)
        rms_disp_container.grid(row=2, column=1, sticky="ew", padx=5)
        try:
            rms_disp_container.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        rms_val_disp = ttk.Label(rms_disp_container, textvariable=self.stats_vars['rms_displacement_value'])
        rms_val_disp.grid(row=0, column=0, sticky="e", padx=(0, 2))
        rms_unit_disp = ttk.Label(rms_disp_container, textvariable=self.stats_vars['rms_displacement_unit'], style="MetricUnit.TLabel")
        rms_unit_disp.grid(row=0, column=1, sticky="w")
        # Sparkline alanı kaldırıldı (RMS)
        try:
            info_rms = ttk.Label(rms_frame, text="ⓘ", style="Info.TLabel", cursor="question_arrow")
            info_rms.grid(row=0, column=2, sticky="e")
            _ToolTip(info_rms, "RMS: Kök ortalama kare; sinyalin etkin değeri")
        except Exception:
            pass
    
    def _create_advanced_stats_tab(self):
        """Gelişmiş istatistikler sekmesini oluşturur"""
        advanced_tab = ttk.Frame(self.stats_notebook)
        self.stats_notebook.add(advanced_tab, text="Gelişmiş")
        
        # Scrollable frame
        canvas = tk.Canvas(advanced_tab)
        scrollbar = ttk.Scrollbar(advanced_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        # İç çerçevenin genişliğini tuval genişliği ile eşitle (tek sütun, ortalanmış görünüm)
        def _on_canvas_configure_adv(event):
            try:
                canvas.itemconfigure(window_id, width=event.width)
            except Exception:
                pass
        canvas.bind("<Configure>", _on_canvas_configure_adv)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Tek sütun grid için kolon ağırlığı
        try:
            scrollable_frame.grid_columnconfigure(0, weight=1)
        except Exception:
            pass
        card_padx, card_pady = 6, 6
        
        # Arias Intensity ve Significant Duration bölümleri kaldırıldı
        
        # CAV
        cav_frame = ttk.LabelFrame(scrollable_frame, text="📈 Cumulative Absolute Velocity", padding=10)
        cav_frame.grid(row=2, column=0, sticky="ew", padx=card_padx, pady=card_pady)
        
        self.stats_vars['cav'] = tk.StringVar(value="--")
        
        ttk.Label(cav_frame, text="CAV:").grid(row=0, column=0, sticky="w", padx=5)
        cav_val = ttk.Label(cav_frame, textvariable=self.stats_vars['cav'], 
                 font=('Segoe UI', 9, 'bold'))
        cav_val.grid(row=0, column=1, sticky="w", padx=5)
        try:
            _ToolTip(cav_val, "CAV: ∫ |a(t)| dt, kümülatif mutlak ivme")
        except Exception:
            pass
    
    def _create_record_info_tab(self):
        """Kayıt bilgileri sekmesini oluşturur"""
        # Sekmesiz kullanım: doğrudan stats_frame içinde oluştur
        info_tab = ttk.Frame(self.stats_frame)
        info_tab.pack(fill="both", expand=True)
        
        # Kayıt bilgileri alanı (başlıksız) - simetrik iç/dış boşluklar
        info_frame = ttk.Frame(info_tab, padding=(10, 8))
        info_frame.pack(fill="x", padx=10, pady=5)
        # Değer sütununu genişler hale getir (sağa hizalı değerler için)
        try:
            info_frame.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        self.stats_vars['record_length'] = tk.StringVar(value="--")
        self.stats_vars['data_points'] = tk.StringVar(value="--")
        self.stats_vars['sampling_rate'] = tk.StringVar(value="--")
        self.stats_vars['time_step'] = tk.StringVar(value="--")
        
        ttk.Label(info_frame, text="Kayıt Süresi:", font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        rec_len_val = ttk.Label(info_frame, textvariable=self.stats_vars['record_length'], 
                 font=('Segoe UI', 9, 'bold'))
        rec_len_val.grid(row=0, column=1, sticky="e", padx=5, pady=2)
        
        ttk.Label(info_frame, text="Veri Noktası:", font=('Segoe UI', 9, 'bold')).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        data_pts_val = ttk.Label(info_frame, textvariable=self.stats_vars['data_points'], 
                 font=('Segoe UI', 9))
        data_pts_val.grid(row=1, column=1, sticky="e", padx=5, pady=2)
        
        ttk.Label(info_frame, text="Örnekleme Hızı:", font=('Segoe UI', 9, 'bold')).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        samp_rate_val = ttk.Label(info_frame, textvariable=self.stats_vars['sampling_rate'], 
                 font=('Segoe UI', 9))
        samp_rate_val.grid(row=2, column=1, sticky="e", padx=5, pady=2)
        
        ttk.Label(info_frame, text="Zaman Adımı:", font=('Segoe UI', 9, 'bold')).grid(row=3, column=0, sticky="w", padx=5, pady=2)
        time_step_val = ttk.Label(info_frame, textvariable=self.stats_vars['time_step'], 
                 font=('Segoe UI', 9))
        time_step_val.grid(row=3, column=1, sticky="e", padx=5, pady=2)

        # Divider (Zaman Adımı'ndan sonra)
        try:
            ttk.Separator(info_frame, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', padx=5, pady=(6, 2))
        except Exception:
            pass

        # Divider altı: Maksimum değerler ve zamanları
        self.stats_vars['pga_abs'] = tk.StringVar(value="--")
        self.stats_vars['t_pga_abs'] = tk.StringVar(value="--")
        self.stats_vars['pgv_abs'] = tk.StringVar(value="--")
        self.stats_vars['t_pgv_abs'] = tk.StringVar(value="--")
        self.stats_vars['pgd_abs'] = tk.StringVar(value="--")
        self.stats_vars['t_pgd_abs'] = tk.StringVar(value="--")
        # YENİ: PGV/PGA oranı değişkeni
        self.stats_vars['pgv_pga_ratio'] = tk.StringVar(value="--")

        ttk.Label(info_frame, text="Maksimum İvme (PGA):", font=('Segoe UI', 9, 'bold')).grid(row=5, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['pga_abs'], font=('Segoe UI', 9)).grid(row=5, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Maksimum İvme Zamanı:", font=('Segoe UI', 9, 'bold')).grid(row=6, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['t_pga_abs'], font=('Segoe UI', 9)).grid(row=6, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Maksimum Hız (PGV):", font=('Segoe UI', 9, 'bold')).grid(row=7, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['pgv_abs'], font=('Segoe UI', 9)).grid(row=7, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Maksimum Hız Zamanı:", font=('Segoe UI', 9, 'bold')).grid(row=8, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['t_pgv_abs'], font=('Segoe UI', 9)).grid(row=8, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Maksimum Deplasman (PGD):", font=('Segoe UI', 9, 'bold')).grid(row=9, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['pgd_abs'], font=('Segoe UI', 9)).grid(row=9, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Maksimum Deplasman Zamanı:", font=('Segoe UI', 9, 'bold')).grid(row=10, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['t_pgd_abs'], font=('Segoe UI', 9)).grid(row=10, column=1, sticky="e", padx=5, pady=2)

        # YENİ: PGV/PGA Oranı
        ttk.Label(info_frame, text="PGV/PGA:", font=('Segoe UI', 9, 'bold')).grid(row=11, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['pgv_pga_ratio'], font=('Segoe UI', 9)).grid(row=11, column=1, sticky="e", padx=5, pady=2)

        # İkinci ayraç (PGV/PGA oranının ardından)
        try:
            ttk.Separator(info_frame, orient='horizontal').grid(row=12, column=0, columnspan=2, sticky='ew', padx=5, pady=(6, 2))
        except Exception:
            pass

        # Arias Şiddeti
        self.stats_vars['arias_intensity_value'] = tk.StringVar(value="--")
        self.stats_vars['a95_value'] = tk.StringVar(value="--")
        ttk.Label(info_frame, text="Arias Şiddeti:", font=('Segoe UI', 9, 'bold')).grid(row=13, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['arias_intensity_value'], font=('Segoe UI', 9)).grid(row=13, column=1, sticky="e", padx=5, pady=2)
        ttk.Label(info_frame, text="A95:", font=('Segoe UI', 9, 'bold')).grid(row=14, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['a95_value'], font=('Segoe UI', 9)).grid(row=14, column=1, sticky="e", padx=5, pady=2)

        # Arias sonrası divider
        try:
            ttk.Separator(info_frame, orient='horizontal').grid(row=15, column=0, columnspan=2, sticky='ew', padx=5, pady=(6, 2))
        except Exception:
            pass

        # RMS özetleri
        self.stats_vars['rms_accel_display'] = tk.StringVar(value="--")
        self.stats_vars['rms_velocity_display'] = tk.StringVar(value="--")
        self.stats_vars['rms_displacement_display'] = tk.StringVar(value="--")

        ttk.Label(info_frame, text="İvme RMS:", font=('Segoe UI', 9, 'bold')).grid(row=16, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['rms_accel_display'], font=('Segoe UI', 9)).grid(row=16, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Hız RMS:", font=('Segoe UI', 9, 'bold')).grid(row=17, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['rms_velocity_display'], font=('Segoe UI', 9)).grid(row=17, column=1, sticky="e", padx=5, pady=2)

        ttk.Label(info_frame, text="Deplasman RMS:", font=('Segoe UI', 9, 'bold')).grid(row=18, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_frame, textvariable=self.stats_vars['rms_displacement_display'], font=('Segoe UI', 9)).grid(row=18, column=1, sticky="e", padx=5, pady=2)

        try:
            _ToolTip(rec_len_val, "Kayıt süresi (s): zaman aralığı")
            _ToolTip(data_pts_val, "Toplam veri noktası sayısı")
            _ToolTip(samp_rate_val, "Örnekleme hızı (Hz)")
            _ToolTip(time_step_val, "Zaman adımı (s)")
        except Exception:
            pass
        
        # Export butonu
        export_frame = ttk.Frame(info_tab)
        export_frame.pack(anchor="w", pady=10)
        
        ttk.Button(export_frame, text="📊 İstatistikleri Excel'e Aktar", 
                  command=self._export_stats).pack(pady=5)

        self._clear_pair_results()
    
    def _clear_pair_results(self) -> None:
        """Çift sonuçlarını ana pencerede temizler."""
        main = getattr(self, "main_window", None)
        if main is None:
            return
        clear_fn = getattr(main, "clear_paired_arias_display", None)
        if callable(clear_fn):
            try:
                clear_fn()
            except Exception:
                pass

    def _get_processed_data(self, record_name: str):
        """Ana pencereden işlem görmüş veri dict'ini döndürür."""
        main = getattr(self, "main_window", None)
        if main is None or not record_name:
            return None
        processed_map = getattr(main, "processed_earthquake_data", {}) or {}
        if record_name in processed_map:
            return processed_map.get(record_name)
        try:
            for rec in getattr(main, "loaded_earthquake_files", []):
                if rec.get("name") == record_name:
                    return rec.get("processed_data")
        except Exception:
            pass
        return None

    def _get_record_stats(self, record_name: str) -> Dict:
        """Verilen kayıt için Arias dahil istatistik sözlüğünü döndürür."""
        main = getattr(self, "main_window", None)
        if main is None:
            return {}
        processor = getattr(main, "earthquake_data_processor", None)
        if processor is None:
            return {}
        data = self._get_processed_data(record_name)
        if not data:
            return {}
        try:
            stats = processor.get_time_series_stats(data)
            return stats or {}
        except Exception:
            return {}

    def open_pair_selection_dialog(self) -> None:
        """Deprem çifti seçme diyalog penceresini açar."""
        parent = self.stats_frame or self.parent_frame
        if PairSelectionDialog is None:
            messagebox.showerror("Hata", "Çift seçim diyalogu yüklenemedi.", parent=parent)
            return

        main = getattr(self, "main_window", None)
        if main is None:
            messagebox.showerror("Hata", "Ana pencere referansı bulunamadı.", parent=parent)
            return

        records = [
            rec.get("name")
            for rec in getattr(main, "loaded_earthquake_files", [])
            if rec.get("name")
        ]

        if len(records) < 2:
            messagebox.showerror("Hata", "Lütfen önce en az iki deprem kaydı yükleyin.", parent=parent)
            return

        dialog = PairSelectionDialog(parent, records)
        selected_pair = dialog.get_selected_pair()

        if not selected_pair:
            return

        comp1_name, comp2_name = selected_pair
        if comp1_name == comp2_name:
            messagebox.showwarning("Uyarı", "Farklı iki bileşen seçmelisiniz.", parent=parent)
            return

        self.calculate_paired_arias(comp1_name, comp2_name)

    def calculate_paired_arias(self, comp1_name: str, comp2_name: str) -> None:
        """Seçilen iki kayıt için toplam Arias Şiddetini hesaplar."""
        parent = self.stats_frame or self.parent_frame
        main = getattr(self, "main_window", None)
        if main is None:
            messagebox.showerror("Hata", "Ana pencere referansı bulunamadı.", parent=parent)
            return

        stats1 = self._get_record_stats(comp1_name)
        stats2 = self._get_record_stats(comp2_name)

        if not stats1:
            messagebox.showerror("Hata", f"'{comp1_name}' kaydı için istatistik bulunamadı.", parent=parent)
            return
        if not stats2:
            messagebox.showerror("Hata", f"'{comp2_name}' kaydı için istatistik bulunamadı.", parent=parent)
            return

        try:
            ia1 = float(stats1.get("arias_intensity", {}).get("arias_intensity"))
            ia2 = float(stats2.get("arias_intensity", {}).get("arias_intensity"))
        except (TypeError, ValueError):
            messagebox.showerror("Hata", "Arias Şiddeti değerleri sayıya dönüştürülemedi.", parent=parent)
            return

        total_ia = ia1 + ia2

        update_fn = getattr(main, "update_paired_arias_display", None)
        if callable(update_fn):
            try:
                update_fn(total_ia, comp1_name, comp2_name)
            except Exception as exc:
                messagebox.showerror("Hata", f"Arias sonuçları güncellenemedi:\n{exc}", parent=parent)
        else:
            messagebox.showwarning(
                "Uyarı",
                "Arias Şiddeti sekmesi güncellenemedi (ana pencere fonksiyonu eksik).",
                parent=parent,
            )
    def update_stats(self, stats_data: Dict):
        """İstatistikleri günceller"""
        self.stats_data = stats_data
        
        try:
            # PGA / PGV / PGD değerleri (sekmesiz özet)
            pga = stats_data.get('pga', {})
            unit = pga.get('unit', 'g')
            self.stats_vars['pga_abs'].set(_format_value(pga.get('pga_abs', 0), unit))
            t_pga = pga.get('t_peak_abs', None)
            self.stats_vars['t_pga_abs'].set(f"{float(t_pga):.6f} s" if t_pga is not None else "--")

            pgv = stats_data.get('pgv', {})
            unit = pgv.get('unit', 'cm/s')
            self.stats_vars['pgv_abs'].set(_format_value(pgv.get('pgv_abs', 0), unit))
            t_pgv = pgv.get('t_peak_abs', None)
            self.stats_vars['t_pgv_abs'].set(f"{float(t_pgv):.6f} s" if t_pgv is not None else "--")

            pgd = stats_data.get('pgd', {})
            unit = pgd.get('unit', 'cm')
            self.stats_vars['pgd_abs'].set(_format_value(pgd.get('pgd_abs', 0), unit))
            t_pgd = pgd.get('t_peak_abs', None)
            self.stats_vars['t_pgd_abs'].set(f"{float(t_pgd):.6f} s" if t_pgd is not None else "--")

            # GÜNCELLENDİ: PGV/PGA Oranı Hesaplaması (Birim: s)
            try:
                # Standart yerçekimi ivmesi (g -> cm/s^2 dönüşümü için)
                G_CM_S2 = 980.665 
                
                pga_val_g = pga.get('pga_abs', 0)      # Değer 'g' cinsinden
                pgv_val_cm_s = pgv.get('pgv_abs', 0)  # Değer 'cm/s' cinsinden
                
                # Sıfıra bölme hatasını engelle
                if pga_val_g is not None and pgv_val_cm_s is not None and float(pga_val_g) != 0:
                    # 1. PGA'yı g'den cm/s^2'ye çevir
                    pga_val_cm_s2 = float(pga_val_g) * G_CM_S2
                    
                    # 2. Oranı hesapla: (cm/s) / (cm/s^2) = s
                    ratio_seconds = float(pgv_val_cm_s) / pga_val_cm_s2
                    
                    # 3. Yeni birim 's' olarak ayarla
                    self.stats_vars['pgv_pga_ratio'].set(_format_value(ratio_seconds, "s", precision=4))
                else:
                    self.stats_vars['pgv_pga_ratio'].set("--")
            except Exception:
                self.stats_vars['pgv_pga_ratio'].set("--")

            # RMS özetleri (sekmesiz)
            rms = stats_data.get('rms', {})
            try:
                self.stats_vars['rms_accel_display'].set(_format_value(rms.get('acceleration', 0), rms.get('accel_unit', 'g')))
                self.stats_vars['rms_velocity_display'].set(_format_value(rms.get('velocity', 0), rms.get('velocity_unit', 'cm/s')))
                self.stats_vars['rms_displacement_display'].set(_format_value(rms.get('displacement', 0), rms.get('displacement_unit', 'cm')))
            except Exception:
                self.stats_vars['rms_accel_display'].set("--")
                self.stats_vars['rms_velocity_display'].set("--")
                self.stats_vars['rms_displacement_display'].set("--")
            # Arias Şiddeti (m/s)
            ai = stats_data.get('arias_intensity', {})
            try:
                ai_unit = ai.get('unit', 'm/s')
                # Arias Şiddeti için 5 ondalık basamak
                self.stats_vars['arias_intensity_value'].set(_format_value(ai.get('arias_intensity', 0), ai_unit, precision=5))
            except Exception:
                self.stats_vars['arias_intensity_value'].set("--")
            # A95 ivme seviyesi
            a95 = stats_data.get('arias_a95', {})
            try:
                a95_value = a95.get('value')
                if a95_value is None:
                    raise ValueError("A95 value is missing")
                a95_unit = a95.get('unit', stats_data.get('pga', {}).get('unit', 'g'))
                self.stats_vars['a95_value'].set(_format_value(a95_value, a95_unit, precision=5))
            except Exception:
                self.stats_vars['a95_value'].set("--")
            
            # Kayıt bilgileri - özel formatlar
            record_info = stats_data.get('record_info', {})
            length = record_info.get('length', 0)
            data_points = record_info.get('data_points', 0)
            sampling_rate = record_info.get('sampling_rate', 0)
            time_step = record_info.get('time_step', 0)
            
            self.stats_vars['record_length'].set(_format_value(length, "s", precision=3))
            self.stats_vars['data_points'].set(f"{data_points:,}")  # Binlik ayırıcı ile
            self.stats_vars['sampling_rate'].set(f"{sampling_rate:.1f} Hz")
            self.stats_vars['time_step'].set(_format_value(time_step, "s", precision=6))
            
            print("📊 İstatistikler güncellendi")
            
        except Exception as e:
            print(f"❌ İstatistik güncelleme hatası: {e}")
        finally:
            self._clear_pair_results()
    
    def clear_stats(self):
        """İstatistikleri temizler"""
        for var in self.stats_vars.values():
            var.set("--")
        self.stats_data = {}
        self._clear_pair_results()
        print("🧹 İstatistikler temizlendi")
        # Sparkline'ları temizle
        try:
            for sp in getattr(self, 'spark_canvases', {}).values():
                ax = sp.get('ax')
                canvas = sp.get('canvas')
                if ax is not None:
                    ax.clear()
                    ax.set_axis_off()
                if canvas is not None:
                    canvas.draw_idle()
        except Exception:
            pass
    
    def _export_stats(self):
        """İstatistikleri Excel'e aktarır"""
        if not self.stats_data:
            import tkinter.messagebox as msgbox
            msgbox.showwarning("Uyarı", "İstatistik verisi bulunamadı!")
            return
        
        try:
            import pandas as pd
            
            # İstatistik verilerini DataFrame'e çevir
            stats_list = []
            
            # PGA
            pga = self.stats_data.get('pga', {})
            stats_list.extend([
                ['PGA', 'Maksimum', f"{pga.get('pga_abs', 0):.6g}", pga.get('unit', 'g')],
                ['PGA', 'Pozitif', f"{pga.get('pga_pos', 0):.6g}", pga.get('unit', 'g')],
                ['PGA', 'Negatif', f"{pga.get('pga_neg', 0):.6g}", pga.get('unit', 'g')]
            ])
            
            # PGV
            pgv = self.stats_data.get('pgv', {})
            stats_list.extend([
                ['PGV', 'Maksimum', f"{pgv.get('pgv_abs', 0):.6g}", pgv.get('unit', 'cm/s')],
                ['PGV', 'Pozitif', f"{pgv.get('pgv_pos', 0):.6g}", pgv.get('unit', 'cm/s')],
                ['PGV', 'Negatif', f"{pgv.get('pgv_neg', 0):.6g}", pgv.get('unit', 'cm/s')]
            ])
            
            # PGD
            pgd = self.stats_data.get('pgd', {})
            stats_list.extend([
                ['PGD', 'Maksimum', f"{pgd.get('pgd_abs', 0):.6g}", pgd.get('unit', 'cm')],
                ['PGD', 'Pozitif', f"{pgd.get('pgd_pos', 0):.6g}", pgd.get('unit', 'cm')],
                ['PGD', 'Negatif', f"{pgd.get('pgd_neg', 0):.6g}", pgd.get('unit', 'cm')]
            ])
            
            # RMS
            rms = self.stats_data.get('rms', {})
            stats_list.extend([
                ['RMS', 'İvme', f"{rms.get('acceleration', 0):.6g}", rms.get('accel_unit', 'g')],
                ['RMS', 'Hız', f"{rms.get('velocity', 0):.6g}", rms.get('velocity_unit', 'cm/s')],
                ['RMS', 'Yerdeğiştirme', f"{rms.get('displacement', 0):.6g}", rms.get('displacement_unit', 'cm')]
            ])
            
            # Gelişmiş istatistikler
            arias = self.stats_data.get('arias_intensity', {})
            stats_list.append(['Arias Intensity', 'Değer', f"{arias.get('arias_intensity', 0):.6g}", arias.get('unit', 'm/s')])
            a95 = self.stats_data.get('arias_a95', {})
            perc = a95.get('percentile', 95)
            try:
                perc_int = int(round(float(perc)))
            except (TypeError, ValueError):
                perc_int = 95
            label = f"A{perc_int}"
            a95_unit = a95.get('unit', self.stats_data.get('pga', {}).get('unit', 'g'))
            try:
                a95_value_text = f"{float(a95.get('value')):.6g}"
            except (TypeError, ValueError):
                a95_value_text = "--"
            stats_list.append([label, 'Değer', a95_value_text, a95_unit])
            
            dur_5_95 = self.stats_data.get('significant_duration_5_95', {})
            dur_5_75 = self.stats_data.get('significant_duration_5_75', {})
            stats_list.extend([
                ['Significant Duration', '5%-95%', f"{dur_5_95.get('duration', 0):.3f}", 's'],
                ['Significant Duration', '5%-75%', f"{dur_5_75.get('duration', 0):.3f}", 's']
            ])
            
            cav = self.stats_data.get('cav', {})
            stats_list.append(['CAV', 'Değer', f"{cav.get('cav', 0):.6g}", cav.get('unit', 'g·s')])
            
            # DataFrame oluştur
            df = pd.DataFrame(stats_list, columns=['Kategori', 'Parametre', 'Değer', 'Birim'])

            # Merkezileştirilmiş kaydetme akışı
            if _FileUtils is not None:
                success = _FileUtils.export_dataframe_to_excel(df, file_path=None, title="İstatistikleri Kaydet")
                if success:
                    print("📊 İstatistikler Excel'e aktarıldı (FileUtils)")
                return
            
            # Fallback: doğrudan kaydetme (FileUtils yoksa)
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                title="İstatistikleri Kaydet",
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if not file_path:
                return
            df.to_excel(file_path, index=False, sheet_name='Deprem İstatistikleri')
            print(f"📊 İstatistikler Excel'e aktarıldı: {file_path}")
            import tkinter.messagebox as msgbox
            msgbox.showinfo("Başarılı", f"İstatistikler başarıyla kaydedildi:\n{file_path}")
            
        except Exception as e:
            print(f"❌ İstatistik export hatası: {e}")
            import tkinter.messagebox as msgbox
            msgbox.showerror("Hata", f"İstatistikler kaydedilemedi:\n{str(e)}")
    
    def get_stats_frame(self):
        """Stats frame'ini döndürür"""
        return self.stats_frame
