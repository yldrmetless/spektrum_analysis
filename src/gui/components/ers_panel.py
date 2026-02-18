"""
Elastic Response Spectrum (ERS) paneli bileşeni
Deprem kayıtlarından ERS hesaplama ve görselleştirme
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from typing import Optional
import matplotlib
matplotlib.use('TkAgg')  # Backend'i zorla ayarla
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import threading
import tkinter.font as tkfont

# Tooltip için mplcursors (opsiyonel)
try:
    import mplcursors
    MPLCURSORS_AVAILABLE = True
except ImportError:
    MPLCURSORS_AVAILABLE = False

from ..dialogs.input_file_params_dialog import ToolTip

# Response spectrum modülünü import et
try:
    from ...calculations.response_spectrum import (
        SpectrumSettings, 
        compute_elastic_response_spectrum,
        export_spectra_to_csv,
        plot_spectra,
        G,
    )
    ERS_AVAILABLE = True
except ImportError:
    ERS_AVAILABLE = False

class ERSPanel:
    """Elastic Response Spectrum paneli sınıfı"""
    
    def __init__(self, parent_frame, spectrum_mode: str = "pseudo"):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        self.spectrum_mode = (spectrum_mode or "pseudo").strip().lower()
        self.is_real_mode = self.spectrum_mode == "real"
        self.calculate_label = (
            "Gerçek Tepki Spektrumu Hesapla" if self.is_real_mode else "Elastik Tepki Spektrumu Hesapla"
        )
        self.params_frame_title = (
            "Gerçek Tepki Spektrumu Parametreleri" if self.is_real_mode else "Pseudo Spectrum Parametreleri"
        )
        self.current_data = None  # (time, acceleration, dt, unit)
        self.current_results = None  # ERS sonuçları
        
        # GUI bileşenleri
        self.ers_frame = None
        self.canvas = None
        self.figure = None
        self.ax = None
        
        # Ana window referansı (diğer grafikleri refresh etmek için)
        self.main_window = None
        
        # Sonuçlar paneli referansı
        self.results_panel = None
        
        # Tooltip ve interaktif özellikler
        self.hover_annotation = None
        self.cursor_handler = None
        self.plot_lines = {}  # Sönüm oranı -> line objesi mapping
        self.default_hover_text = "Grafiğin üzerine gelerek spektrum değerlerini inceleyin."
        self.hover_info_var = tk.StringVar(value=self.default_hover_text)
        self.hover_info_label = None
        self.cursor_vertical_line = None
        self.cursor_horizontal_line = None
        self.hover_marker = None
        self._cursor_visible = False
        self._last_cursor_pos = None
        self._hover_pixel_threshold = 25  # px içinde en yakın veri noktası aranır
        self.motion_event_id = None
        self.axes_leave_event_id = None
        self.figure_leave_event_id = None
        self.manual_hover_cid = None
        
        # Bellek içi ERS sonuç önbelleği
        # Anahtar: (record_name, accel_unit, dt, tuple(damping_list), Tmin, Tmax, nT, logspace, enforce_dt_over_T)
        # Değer: compute_elastic_response_spectrum çıktısı (results)
        self.results_cache = {}
        self.current_record_name = ""
        
        # Parametre değişkenleri
        self.damping_var = tk.StringVar(value="5.0")
        self.tmin_var = tk.StringVar(value="0.01")
        self.tmax_var = tk.StringVar(value="10.0")
        self.nperiods_var = tk.StringVar(value="500")
        # Y ekseni: görüntü ve kod ayrımı
        self._yaxis_pairs = self._build_yaxis_pairs()
        default_display = self._yaxis_pairs[0][0]
        default_internal = self._yaxis_pairs[0][1]
        self.yaxis_display_var = tk.StringVar(value=default_display)
        self.ytype_var = tk.StringVar(value=default_internal)
        # X ekseni: görüntü ve kod ayrımı
        self.xaxis_display_var = tk.StringVar(value="Periyot")
        self.xaxis_var = tk.StringVar(value="period")
        # baseline kaldırıldı
        self.accel_unit_var = tk.StringVar(value="g")
        self.dt_over_t_var = tk.StringVar(value="0.05")
        
        self._create_widgets()
        
        # Çalışma durumu bayrağı
        self.is_running = False

    def _build_yaxis_pairs(self):
        """Seçili spektrum moduna göre Y ekseni seçeneklerini döndürür."""
        if self.is_real_mode:
            return [
                ("Sa_abs (g)", "sa_abs"),
                ("Sv_true (m/s)", "sv_true"),
                ("Sd (m)", "sd"),
                ("Sa_rel (m/s²)", "sa_rel"),
            ]
        return [
            ("Sa", "sa"),
            ("Sv", "sv"),
            ("Sd", "sd"),
        ]

    def _get_yaxis_tooltip(self) -> str:
        if self.is_real_mode:
            return (
                "Y ekseni türü:\n"
                "- Sa_abs (g): Mutlak ivme tepesi [g]\n"
                "- Sv_true (m/s): Gerçek göreli hız tepesi\n"
                "- Sd (m): Göreli yerdeğişim tepesi\n"
                "- Sa_rel (m/s²): Göreli ivme tepesi"
            )
        return (
            "Y ekseni türü:\n"
            "- Sa: Pseudo ivme [g]\n"
            "- Sv: Pseudo hız [m/s]\n"
            "- Sd: Yerdeğiştirme [m]"
        )

    def _get_ylabel_for_ytype(self, ytype: str) -> str:
        labels = {
            "sa": "Pseudo Spektral İvme, Sa (g)",
            "sv": "Pseudo Spektral Hız, Sv (m/s)",
            "sd": "Spektral Yerdeğiştirme, Sd (m)",
            "sa_abs": "Absolute Sa (g)",
            "sv_true": "True Sv (m/s)",
            "sa_rel": "Relative Sa (m/s²)",
        }
        return labels.get(ytype, "Spektral Büyüklük")

    def _extract_series(self, curves, ytype: str) -> np.ndarray:
        if ytype == "sa":
            return curves.Sa_p_g
        if ytype == "sv":
            return curves.Sv_p
        if ytype == "sd":
            return curves.Sd
        if ytype == "sa_abs":
            if curves.Sa_abs is None:
                raise ValueError("Sa_abs verisi hesaplanmadı.")
            return curves.Sa_abs / G
        if ytype == "sv_true":
            if curves.Sv_true is None:
                raise ValueError("Sv_true verisi hesaplanmadı.")
            return curves.Sv_true
        if ytype == "sa_rel":
            if curves.Sa_rel is None:
                raise ValueError("Sa_rel verisi hesaplanmadı.")
            return curves.Sa_rel
        raise ValueError(f"Bilinmeyen y ekseni türü: {ytype}")

    def _create_subscript_label(self, parent, base_text: str, sub_text: str):
        """Alt indisli görünüm için birleşik label döndürür."""
        container = ttk.Frame(parent)
        base_font = tkfont.nametofont('TkDefaultFont')
        sub_font = base_font.copy()
        # Subscript bir tık küçük ama okunur olsun
        sub_font.configure(size=max(base_font.cget('size') - 1, 8))
        base_lbl = ttk.Label(container, text=base_text, font=base_font)
        sub_lbl = ttk.Label(container, text=sub_text, font=sub_font)
        base_lbl.grid(row=0, column=0, sticky="w")
        # Aşağı doğru hafif kaydırma için pady veriyoruz
        sub_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))
        return container
    
    def _create_widgets(self):
        """Widget'ları oluşturur"""
        if not ERS_AVAILABLE:
            # Modül yoksa uyarı göster
            error_frame = ttk.Frame(self.parent_frame)
            error_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            ttk.Label(error_frame, text="⚠️ Elastik Tepki Spektrumu modülü bulunamadı", 
                     font=('Segoe UI', 12, 'bold'), foreground="red").pack(pady=20)
            ttk.Label(error_frame, text="response_spectrum.py dosyasının mevcut olduğundan emin olun.",
                     font=('Segoe UI', 10)).pack(pady=5)
            return
        
        # Ana çerçeve (başlıksız)
        self.ers_frame = ttk.Frame(self.parent_frame, padding=10)
        self.ers_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Sol panel - Parametreler
        left_panel = ttk.Frame(self.ers_frame)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.config(width=300)
        
        # Parametreler frame'i
        params_frame = ttk.LabelFrame(left_panel, text=self.params_frame_title, padding=10)
        params_frame.pack(fill="x", pady=(0, 10))
        
        self._create_parameter_widgets(params_frame)
        
        # Kontrol butonları
        control_frame = ttk.Frame(left_panel)
        control_frame.pack(fill="x", pady=(0, 10))
        
        # Hesapla butonu (ikon + metin)
        calculate_text = self.calculate_label
        calculate_kwargs = {
            'master': control_frame,
            'text': calculate_text,
            'command': self._calculate_ers,
            'state': "disabled"
        }
        try:
            # İkonu yükle ve butonda göster
            self.calculate_icon = tk.PhotoImage(file="icons/calculate_01.png")
            self.calculate_button = ttk.Button(**calculate_kwargs)
            self.calculate_button.configure(image=self.calculate_icon, compound='left')
        except Exception:
            # İkon yüklenemezse sadece metinle devam et
            self.calculate_button = ttk.Button(**calculate_kwargs)
        self.calculate_button.pack(fill="x", pady=2)
        
        # Verileri dışa aktar butonu (ikon + metin)
        export_text = "Verileri Dışarı Aktar"
        export_kwargs = {
            'master': control_frame,
            'text': export_text,
            'command': self._export_data,
            'state': "disabled"
        }
        try:
            # İkonu rapor görselleri klasöründen yükle
            self.export_icon = tk.PhotoImage(file="report_images/file_export_d01.png")
            self.export_data_button = ttk.Button(**export_kwargs)
            self.export_data_button.configure(image=self.export_icon, compound='left')
        except Exception:
            self.export_data_button = ttk.Button(**export_kwargs)
        self.export_data_button.pack(fill="x", pady=2)
        
        self.export_png_button = ttk.Button(
            control_frame,
            text="🖼️ PNG Dışa Aktar",
            command=self._export_png,
            state="disabled"
        )
        self.export_png_button.pack(fill="x", pady=2)
        
        # Progress bar (başlangıçta gizli)
        self.progress_frame = ttk.Frame(left_panel)
        self.progress_frame.pack(fill="x", pady=5)
        
        self.progress_label = ttk.Label(self.progress_frame, text="Hesaplanıyor...")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, 
            mode='indeterminate',
            length=250
        )
        self.progress_bar.pack(fill="x", pady=2)
        
        # Progress frame'i başlangıçta gizle
        self.progress_frame.pack_forget()
        
        # Bilgi etiketi
        self.info_var = tk.StringVar(value="Henüz deprem kaydı seçilmedi")
        info_label = ttk.Label(left_panel, textvariable=self.info_var, 
                              font=('Segoe UI', 9), foreground="gray")
        info_label.pack(pady=10)
        
        # Sağ panel - Grafik
        right_panel = ttk.Frame(self.ers_frame)
        right_panel.pack(side="right", fill="both", expand=True)
        
        self._create_plot_area(right_panel)

    def _create_parameter_widgets(self, parent):
        """Parametre giriş widget'larını oluşturur"""
        row = 0
        
        # Damping
        ttk.Label(parent, text="Sönüm (%) :").grid(row=row, column=0, sticky="w", pady=2)
        damping_entry = ttk.Entry(parent, textvariable=self.damping_var, width=15)
        damping_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(parent, text="Örn: 2,5,10", font=('Segoe UI', 8), foreground="gray").grid(
            row=row, column=2, sticky="w", padx=(5, 0))
        ToolTip(damping_entry, "Sönüm oranları (%). Birden fazla değer için virgül ile ayırın.\nÖrnek: 2, 5, 10")
        row += 1
        
        # Periyot aralığı
        sub_Tmin = self._create_subscript_label(parent, "T", "min")
        sub_Tmin.grid(row=row, column=0, sticky="w", pady=2)
        tmin_entry = ttk.Entry(parent, textvariable=self.tmin_var, width=15)
        tmin_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ToolTip(tmin_entry, "Spektrumun alt periyot sınırı (saniye).\nKısa periyot/rijit davranış başlangıcı. Örn: 0.01")
        row += 1
        
        sub_Tmax = self._create_subscript_label(parent, "T", "max")
        sub_Tmax.grid(row=row, column=0, sticky="w", pady=2)
        tmax_entry = ttk.Entry(parent, textvariable=self.tmax_var, width=15)
        tmax_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ToolTip(tmax_entry, "Spektrumun üst periyot sınırı (saniye).\nUzun periyot/esnek davranış sonu. Örn: 10")
        row += 1
        
        # Y ekseni türü
        ttk.Label(parent, text="Y Ekseni :").grid(row=row, column=0, sticky="w", pady=2)
        ytype_combo = ttk.Combobox(parent, textvariable=self.yaxis_display_var, width=18, state="readonly")
        ytype_combo['values'] = tuple(label for label, _ in self._yaxis_pairs)
        ytype_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ytype_combo.bind('<<ComboboxSelected>>', self._on_yaxis_change)
        ToolTip(ytype_combo, self._get_yaxis_tooltip())
        row += 1
        
        # X ekseni türü
        ttk.Label(parent, text="X Ekseni :").grid(row=row, column=0, sticky="w", pady=2)
        xaxis_combo = ttk.Combobox(parent, textvariable=self.xaxis_display_var, width=12, state="readonly")
        xaxis_combo['values'] = ('Periyot', 'Frekans')
        xaxis_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        xaxis_combo.bind('<<ComboboxSelected>>', self._on_xaxis_change)
        ToolTip(xaxis_combo, "X ekseni türü:\n- Periyot: T [s]\n- Frekans: f [Hz] (1/T)")
        row += 1
        
        # Baseline düzeltme (kaldırıldı)
        # ttk.Label(parent, text="Baseline :").grid(row=row, column=0, sticky="w", pady=2)
        # baseline_combo = ttk.Combobox(parent, textvariable=self.baseline_var, width=12, state="readonly")
        # baseline_combo['values'] = ('none', 'demean', 'linear', 'poly2', 'poly3')
        # baseline_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        # row += 1
        
        # İvme birimi
        ttk.Label(parent, text="İvme Birimi :").grid(row=row, column=0, sticky="w", pady=2)
        unit_combo = ttk.Combobox(parent, textvariable=self.accel_unit_var, width=12, state="readonly")
        unit_combo['values'] = ('g', 'm/s²', 'cm/s²', 'mm/s²')
        unit_combo.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ToolTip(unit_combo, "Giriş ivme verisinin birimi.\nHesaplama öncesi otomatik SI dönüşümü yapılır.")
        row += 1
        
        # dt/T oranı
        ttk.Label(parent, text="dt/T Limit :").grid(row=row, column=0, sticky="w", pady=2)
        dtover_entry = ttk.Entry(parent, textvariable=self.dt_over_t_var, width=15)
        dtover_entry.grid(row=row, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(parent, text="Örn: 0.05", font=('Segoe UI', 8), foreground="gray").grid(
            row=row, column=2, sticky="w", padx=(5, 0))
        ToolTip(dtover_entry, "Numarik doğruluk için zaman adımı oranı sınırı.\ndt/T ≤ bu değer olacak şekilde kontrol edilir.\nÖneri: 0.05")
        
        # Grid yapılandırması
        parent.grid_columnconfigure(1, weight=1)
        
        # Başlangıç eşlemeleri (görüntü → iç kod)
        self._on_yaxis_change()
        self._on_xaxis_change()

    def _on_xaxis_change(self, event=None):
        """X ekseni Türkçe gösterimden iç kod eşleme (Periyot/Frekans → period/frequency)."""
        disp = (self.xaxis_display_var.get() or "").strip().lower()
        if disp.startswith("periyot"):
            self.xaxis_var.set("period")
        else:
            self.xaxis_var.set("frequency")

    def _on_yaxis_change(self, event=None):
        """Y ekseni gösteriminden iç kod eşleme (Sa/Sv/Sd → sa/sv/sd)."""
        disp = (self.yaxis_display_var.get() or "").strip().lower()
        for label, internal in self._yaxis_pairs:
            if disp == label.strip().lower():
                self.ytype_var.set(internal)
                break
        else:
            self.ytype_var.set(self._yaxis_pairs[0][1])
        try:
            if self.ax:
                self.ax.set_ylabel(self._get_ylabel_for_ytype(self.ytype_var.get()))
                if self.canvas:
                    self.canvas.draw_idle()
        except Exception:
            pass

    def _create_plot_area(self, parent):
        """Grafik alanını oluşturur"""
        plot_frame = ttk.Frame(parent, padding=10)
        plot_frame.pack(fill="both", expand=True)
        # Referans: bazı yerlerde erişmek için
        self.frame = plot_frame
        
        # Matplotlib kurulum (önerilen Tk deseni)
        self.fig = Figure(figsize=(12, 7), tight_layout=True)
        self.figure = self.fig  # geriye dönük uyumluluk
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.draw()
        canvas_widget = self.canvas.get_tk_widget()
        try:
            canvas_widget.configure(borderwidth=0, highlightthickness=0)
        except Exception:
            pass
        canvas_widget.pack(side='top', fill='both', expand=True)
        self._create_interactive_overlays()
        self._register_motion_events()
        self._create_hover_info_bar(plot_frame)
        
        # Toolbar
        try:
            self.toolbar = NavigationToolbar2Tk(self.canvas, self.frame)
            self.toolbar.update()
        except Exception:
            self.toolbar = None
        
        # Eksen ve grid varsayılanları
        self.ax.set_title('', pad=8)
        self.ax.set_xlabel('Periyot, T (s)')
        self.ax.set_ylabel(self._get_ylabel_for_ytype(self.ytype_var.get()))
        self.ax.grid(True, which='major', linestyle=':', alpha=0.3)
        self.ax.set_xscale('linear')
        
        # Sağ tık menüsü
        try:
            canvas_widget.bind('<Button-3>', self._show_plot_context_menu)
            canvas_widget.bind('<Button-2>', self._show_plot_context_menu)
            canvas_widget.bind('<Control-Button-1>', self._show_plot_context_menu)
        except Exception:
            pass
        
        # Notebook sekmesi değişince boş kalma sorununa karşı redraw
        try:
            root = self.frame.winfo_toplevel()
            root.bind('<<NotebookTabChanged>>', self._on_notebook_tab_changed, add='+')
        except Exception:
            pass
    
    def _create_hover_info_bar(self, parent):
        """Grafiğin hemen altındaki imleç bilgi alanını hazırlar."""
        if self.hover_info_label is not None:
            return
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill="x", pady=(4, 2))
        ttk.Label(info_frame, text="İmleç:", font=('Segoe UI', 9, 'bold')).pack(side="left")
        self.hover_info_label = ttk.Label(
            info_frame,
            textvariable=self.hover_info_var,
            justify="left",
            wraplength=900
        )
        self.hover_info_label.pack(side="left", padx=(6, 0))
    
    def _create_interactive_overlays(self):
        """İnteraktif çizgiler ve imleç işaretçilerini oluşturur."""
        if not self.ax:
            return
        try:
            self.cursor_vertical_line = self.ax.axvline(
                0,
                color="#6c757d",
                linestyle="--",
                linewidth=0.8,
                alpha=0.7,
                zorder=5,
                label="_nolegend_"
            )
            self.cursor_horizontal_line = self.ax.axhline(
                0,
                color="#6c757d",
                linestyle="--",
                linewidth=0.8,
                alpha=0.7,
                zorder=5,
                label="_nolegend_"
            )
            (self.hover_marker,) = self.ax.plot(
                [],
                [],
                marker="o",
                markersize=6,
                color="#d9534f",
                alpha=0.9,
                zorder=6,
                label="_nolegend_"
            )
            self._hide_cursor_overlay(force=True)
        except Exception:
            self.cursor_vertical_line = None
            self.cursor_horizontal_line = None
            self.hover_marker = None
    
    def _register_motion_events(self):
        """Matplotlib hareket/ayrılma eventlerini tek sefer bağlar."""
        if not self.canvas:
            return
        if self.motion_event_id is None:
            self.motion_event_id = self.canvas.mpl_connect(
                'motion_notify_event', self._on_plot_motion
            )
        if self.axes_leave_event_id is None:
            self.axes_leave_event_id = self.canvas.mpl_connect(
                'axes_leave_event', self._on_axes_leave
            )
        if self.figure_leave_event_id is None:
            self.figure_leave_event_id = self.canvas.mpl_connect(
                'figure_leave_event', self._on_axes_leave
            )
    
    def _on_plot_motion(self, event):
        """Grafikte gezinirken imleç bilgisini günceller."""
        try:
            info = self._find_closest_point(event)
            if info:
                self._update_cursor_overlay(info)
                self._update_hover_info(info)
            else:
                self._hide_cursor_overlay()
        except Exception:
            pass
    
    def _on_axes_leave(self, event=None):
        """Eksenden çıkıldığında yardım çizgilerini gizler."""
        try:
            self._hide_cursor_overlay()
            if self.hover_annotation:
                self.hover_annotation.set_visible(False)
                if self.canvas:
                    self.canvas.draw_idle()
        except Exception:
            pass
    
    def _update_cursor_overlay(self, info):
        """Çapraz imleç çizgilerini ve noktayı günceller."""
        if not self.canvas:
            return
        x = info.get('x_value')
        y = info.get('y_value')
        changed = False
        try:
            if self.cursor_vertical_line:
                self.cursor_vertical_line.set_xdata([x, x])
                if not self.cursor_vertical_line.get_visible():
                    self.cursor_vertical_line.set_visible(True)
                    changed = True
            if self.cursor_horizontal_line:
                self.cursor_horizontal_line.set_ydata([y, y])
                if not self.cursor_horizontal_line.get_visible():
                    self.cursor_horizontal_line.set_visible(True)
                    changed = True
            if self.hover_marker:
                self.hover_marker.set_data([x], [y])
                if not self.hover_marker.get_visible():
                    self.hover_marker.set_visible(True)
                    changed = True
            if changed or (self._last_cursor_pos != (x, y)):
                self._cursor_visible = True
                self._last_cursor_pos = (x, y)
                self.canvas.draw_idle()
        except Exception:
            pass
    
    def _hide_cursor_overlay(self, force=False):
        """Çapraz imleç çizgilerini gizler ve bilgi metnini sıfırlar."""
        changed = False
        for artist in (self.cursor_vertical_line, self.cursor_horizontal_line):
            if artist is not None:
                if artist.get_visible():
                    artist.set_visible(False)
                    changed = True
                elif force:
                    artist.set_visible(False)
        if self.hover_marker is not None:
            if self.hover_marker.get_visible():
                self.hover_marker.set_visible(False)
                changed = True
            elif force:
                self.hover_marker.set_visible(False)
            try:
                self.hover_marker.set_data([], [])
            except Exception:
                pass
        if changed or force:
            self._cursor_visible = False
            self._last_cursor_pos = None
            self.hover_info_var.set(self.default_hover_text)
            if self.canvas:
                self.canvas.draw_idle()
    
    def _update_hover_info(self, info):
        """Alt bilgi etiketini günceller."""
        try:
            axis_text = info.get('x_label', '').replace(" = ", "=")
            y_text = info.get('y_label', '').replace(" = ", "=")
            summary = (
                f"ζ={info.get('damping', 0):.1f}% | "
                f"{axis_text} | "
                f"{y_text} | "
                f"Sa={info.get('Sa_g', 0):.3f} g | "
                f"Sv={info.get('Sv', 0):.3f} m/s | "
                f"Sd={info.get('Sd', 0):.6f} m"
            )
            self.hover_info_var.set(summary)
        except Exception:
            pass
    
    def update_data(self, time_data: np.ndarray, acceleration: np.ndarray, 
                   dt: float, accel_unit: str = "g", record_name: str = ""):
        """
        Yeni deprem kaydı verilerini günceller
        
        Args:
            time_data: Zaman serisi
            acceleration: İvme serisi
            dt: Zaman adımı
            accel_unit: İvme birimi
            record_name: Kayıt adı
        """
        if not ERS_AVAILABLE:
            return
            
        self.current_data = (time_data, acceleration, dt, accel_unit)
        self.current_record_name = record_name or ""
        self.accel_unit_var.set(accel_unit)
        
        # Bilgi güncelle
        duration = time_data[-1] - time_data[0] if len(time_data) > 1 else 0
        info_text = f"Kayıt: {record_name}\n"
        info_text += f"Süre: {duration:.2f} s\n"
        info_text += f"dt: {dt:.4f} s\n"
        info_text += f"Örnekler: {len(acceleration)}\n"
        info_text += f"Birim: {accel_unit}"
        self.info_var.set(info_text)
        
        # Hesapla butonunu etkinleştir
        self.calculate_button.config(state="normal")
        
        # Grafiği temizle
        self.ax.clear()
        self.ax.set_xlabel("Periyot, T (s)")
        self.ax.set_ylabel(self._get_ylabel_for_ytype(self.ytype_var.get()))
        self.ax.grid(True, which="major", linestyle=":")
        self.ax.set_xscale("linear")
        placeholder = f'ERS hesaplamak için\n"{self.calculate_label}" butonuna basın'
        self.ax.text(0.5, 0.5, placeholder,
                    horizontalalignment='center', verticalalignment='center',
                    transform=self.ax.transAxes, fontsize=12, color='gray')
        self._create_interactive_overlays()
        self._hide_cursor_overlay(force=True)
        self.canvas.draw()
        
        # Diğer grafikleri refresh et
        self._refresh_other_plots()

        # Eğer bu deprem ve mevcut parametrelerle önceden hesaplanmış sonuç varsa otomatik yükle
        try:
            if self._try_load_cached_results():
                return
        except Exception:
            pass
    
    def _calculate_ers(self):
        """ERS hesaplamasını başlatır (arka planda)."""
        if not self.current_data:
            messagebox.showerror("Hata", "Önce bir deprem kaydı seçin!")
            return
        if self.is_running:
            return
        
        try:
            # Parametreleri al
            damping_str = self.damping_var.get().strip()
            damping_list = [float(d.strip()) for d in damping_str.split(',') if d.strip()]
            
            tmin = float(self.tmin_var.get())
            tmax = float(self.tmax_var.get())
            nperiods = int(self.nperiods_var.get())
            
            dt_over_t = None
            dt_over_t_str = self.dt_over_t_var.get().strip()
            if dt_over_t_str:
                dt_over_t = float(dt_over_t_str)
            
            # Settings oluştur
            settings = SpectrumSettings(
                damping_list=damping_list,
                Tmin=tmin,
                Tmax=tmax,
                nT=nperiods,
                logspace=True,
                accel_unit=self.accel_unit_var.get(),
                baseline='none',
                enforce_dt_over_T=dt_over_t
            )
            if self.is_real_mode:
                ycode = self.ytype_var.get()
                settings.compute_abs_acc = (ycode == "sa_abs")
                settings.compute_true_sv = True
                settings.compute_rel_acc = (ycode == "sa_rel")
            else:
                settings.compute_abs_acc = False
                settings.compute_true_sv = False
                settings.compute_rel_acc = False
            
            # Girdi verilerini kopyala
            time_data, acceleration, dt, accel_unit = self.current_data

            self._warn_linear_acceleration_instability(dt, tmin, dt_over_t)

            # Önbellek anahtarını hazırla ve varsa doğrudan kullan
            cache_key = self._make_cache_key(
                record_name=self.current_record_name,
                accel_unit=accel_unit,
                dt=dt,
                damping_list=damping_list,
                Tmin=tmin,
                Tmax=tmax,
                nT=nperiods,
                logspace=True,
                enforce_dt_over_T=dt_over_t,
                ytype_code=self.ytype_var.get(),
            )
            if cache_key in self.results_cache:
                self.current_results = self.results_cache[cache_key]
                self._plot_ers()
                self._update_results_panel()
                self.export_data_button.config(state="normal")
                self.export_png_button.config(state="normal")
                self.info_var.set("Önceden hesaplanmış sonuç yüklendi (önbellek)")
                return
            
            # UI: hesaplama süresince butonları devre dışı bırak
            self.is_running = True
            self.calculate_button.config(state="disabled")
            self.export_data_button.config(state="disabled")
            self.export_png_button.config(state="disabled")
            self.parent_frame.config(cursor="watch")
            
            # Progress bar göster
            self.progress_frame.pack(fill="x", pady=5)
            self.progress_bar.start(10)  # 10ms interval
            
            # Performans optimizasyonu bilgisi
            try:
                from ...calculations.response_spectrum import NUMBA_AVAILABLE
                if NUMBA_AVAILABLE:
                    self.info_var.set("ERS hesaplanıyor (Numba JIT optimizasyonu aktif)...")
                    self.progress_label.config(text="Hızlandırılmış hesaplama...")
                else:
                    self.info_var.set("ERS hesaplanıyor (Numba bulunamadı, yavaş hesaplama)...")
                    self.progress_label.config(text="Standart hesaplama (Numba önerilir)...")
            except:
                self.info_var.set("ERS hesaplanıyor, lütfen bekleyin...")
                self.progress_label.config(text="Hesaplanıyor...")
            
            # Arka plan iş parçacığı başlat
            worker = threading.Thread(
                target=self._ers_worker,
                args=(time_data, acceleration, settings, cache_key),
                daemon=True
            )
            worker.start()
            
        except Exception as e:
            messagebox.showerror("Hata", f"ERS hesaplama parametreleri hatalı:\n{str(e)}")

    def _warn_linear_acceleration_instability(self, dt: float, t_min: float, enforce_ratio: Optional[float]) -> None:
        """Lineer ivme yontemi icin dt/T stabilite kosulunu kontrol eder."""
        ratio_limit = 0.551
        try:
            t_min_val = float(t_min)
            dt_val = float(dt)
        except (TypeError, ValueError):
            return
        if t_min_val <= 0 or dt_val <= 0:
            return

        ratio = dt_val / t_min_val
        enforce_val = None
        if enforce_ratio is not None:
            try:
                enforce_val = float(enforce_ratio)
            except (TypeError, ValueError):
                enforce_val = None
        if enforce_val is not None and enforce_val < ratio:
            ratio = enforce_val

        if ratio < ratio_limit:
            return

        msg_lines = [
            "Lineer ivme yontemi yalnizca dt/T < 0.551 kosulu saglandiginda kararlidir.",
            f"Mevcut degerler: dt = {dt_val:.4f} s, Tmin = {t_min_val:.4f} s, dt/T yaklasik {ratio:.3f}."
        ]
        if enforce_val is not None:
            msg_lines.append("Lutfen dt/T sinirini 0.551'den kucuk olacak sekilde ayarlayin.")
        else:
            msg_lines.append("Zaman adimini kucultmeniz, Tmin degerini artirmaniz veya 'dt/T' sinirini etkinlestirmeniz onerilir.")
        messagebox.showwarning("Lineer Ivme Stabilite Uyarisi", "\n".join(msg_lines))
    
    def _ers_worker(self, time_data: np.ndarray, acceleration: np.ndarray, settings: SpectrumSettings, cache_key):
        """Arka planda ERS hesaplamasını yapar ve sonucu ana iş parçacığına bildirir."""
        try:
            results = compute_elastic_response_spectrum(time_data, acceleration, settings)
            # Ana iş parçacığında sonuçları işle
            self.parent_frame.after(0, self._on_ers_done, results, None, cache_key)
        except Exception as e:
            self.parent_frame.after(0, self._on_ers_done, None, e, None)
    
    def _on_ers_done(self, results, error, cache_key=None):
        """ERS hesaplaması tamamlandığında çağrılır (ana iş parçacığı)."""
        # Progress bar durdur ve gizle
        self.progress_bar.stop()
        self.progress_frame.pack_forget()
        
        # UI durumlarını eski haline getir
        self.is_running = False
        self.calculate_button.config(state="normal")
        self.parent_frame.config(cursor="")
        
        if error is not None:
            self.info_var.set("Hata: ERS hesaplanamadı")
            messagebox.showerror("Hata", f"ERS hesaplama hatası:\n{str(error)}")
            return
        
        # Sonuçları güncelle ve çiz
        self.current_results = results
        # Sonucu önbelleğe yaz
        try:
            if cache_key is not None:
                self.results_cache[cache_key] = results
        except Exception:
            pass
        self._plot_ers()
        
        # Sonuçlar panelini güncelle
        self._update_results_panel()
        
        # Export butonlarını etkinleştir
        self.export_data_button.config(state="normal")
        self.export_png_button.config(state="normal")
        self.info_var.set("ERS hesaplaması tamamlandı")
        messagebox.showinfo("Başarılı", "ERS hesaplaması tamamlandı!")

    # ---------------------- Önbellek yardımcıları ----------------------
    def _make_cache_key(self, record_name: str, accel_unit: str, dt: float,
                         damping_list, Tmin: float, Tmax: float, nT: int,
                         logspace: bool, enforce_dt_over_T, ytype_code: str):
        return (
            record_name or "",
            str(accel_unit),
            float(dt),
            tuple(float(d) for d in damping_list),
            float(Tmin), float(Tmax), int(nT), bool(logspace),
            None if enforce_dt_over_T is None else float(enforce_dt_over_T),
            str(ytype_code),
            self.spectrum_mode,
        )

    def _try_load_cached_results(self) -> bool:
        """Geçerli deprem ve parametrelerle önceden hesaplanmış sonuç varsa yükler."""
        try:
            if not self.current_data:
                return False
            time_data, acceleration, dt, accel_unit = self.current_data
            # Anlık UI parametrelerinden anahtar oluştur
            damping_str = self.damping_var.get().strip()
            damping_list = [float(d.strip()) for d in damping_str.split(',') if d.strip()]
            tmin = float(self.tmin_var.get())
            tmax = float(self.tmax_var.get())
            nperiods = int(self.nperiods_var.get())
            dtover = float(self.dt_over_t_var.get()) if self.dt_over_t_var.get().strip() else None
            key = self._make_cache_key(
                record_name=self.current_record_name,
                accel_unit=accel_unit,
                dt=dt,
                damping_list=damping_list,
                Tmin=tmin, Tmax=tmax, nT=nperiods,
                logspace=True,
                enforce_dt_over_T=dtover,
                ytype_code=self.ytype_var.get(),
            )
            if key in self.results_cache:
                self.current_results = self.results_cache[key]
                self._plot_ers()
                self._update_results_panel()
                self.export_data_button.config(state="normal")
                self.export_png_button.config(state="normal")
                self.info_var.set("Önceden hesaplanmış sonuç yüklendi (önbellek)")
                return True
        except Exception:
            return False
        return False
    
    def _plot_ers(self):
        """ERS sonuçlarını çizer"""
        if not self.current_results:
            return
        
        # Grafiği temizle
        self.ax.clear()
        
        # Parametreler
        ytype = self.ytype_var.get()
        xaxis = self.xaxis_var.get()
        
        # Eksenleri ayarla
        dampings = sorted(self.current_results.keys())
        T = self.current_results[dampings[0]].T
        x = T if xaxis == "period" else 1.0 / T
        
        # X ekseni etiketi (birim ile)
        if xaxis == "period":
            xlabel = "Periyot, T (s)"
        else:
            xlabel = "Frekans, f (Hz)"
        
        # Y ekseni etiketi (birim ile)
        ylabel = self._get_ylabel_for_ytype(ytype)
        
        # Eğrileri çiz ve tooltip için sakla
        self.plot_lines.clear()
        for z in dampings:
            curves = self.current_results[z]
            try:
                y = self._extract_series(curves, ytype)
            except ValueError as exc:
                messagebox.showerror("Hata", str(exc))
                return
            label = f"ζ = {z:.1f}%"
            line, = self.ax.plot(x, y, label=label, linewidth=2)
            self.plot_lines[z] = {
                'line': line,
                'x': x,
                'y': y,
                'curves': curves,
                'ytype': ytype
            }
        self._create_interactive_overlays()
        self._hide_cursor_overlay(force=True)
        
        # Grafik ayarları
        self.ax.set_xlabel(xlabel)
        self.ax.set_ylabel(ylabel)
        self.ax.grid(True, which="major", linestyle=":")
        # X ekseni her zaman lineer (logaritmik değil)
        self.ax.set_xscale("linear")
        try:
            legend = self.ax.legend(loc='best', frameon=True, fancybox=True, shadow=True)
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_alpha(0.9)
            try:
                legend.set_draggable(True)
            except Exception:
                pass
        except Exception:
            self.ax.legend()
        self.ax.set_title("")
        
        # Grafik güncelle
        try:
            self.figure.tight_layout()
        except Exception:
            pass
        self.canvas.draw_idle()
        
        # Tooltip özelliğini aktive et
        self._setup_tooltips()
        
        # Diğer grafikleri refresh et (matplotlib state sorununu önlemek için)
        self._refresh_other_plots()

    def _on_notebook_tab_changed(self, event=None):
        """Notebook sekmesi değiştiğinde ERS sekmesi aktifse çizimi tazeler."""
        try:
            nb = event.widget
            selected = nb.nametowidget(nb.select())
            if self._is_descendant(self.frame, selected):
                if self.canvas:
                    self.canvas.draw_idle()
        except Exception:
            # bind_all geldi ise veya beklenmeyen widget ise güvenli çık
            try:
                if self.canvas:
                    self.canvas.draw_idle()
            except Exception:
                pass

    def _is_descendant(self, child, parent):
        try:
            w = child
            while w is not None:
                if w == parent:
                    return True
                w = w.master
        except Exception:
            return False
        return False

    def plot_ers(self, T, Sa, acc_unit_symbol='g'):
        """Basit ERS çizimi (tek eğri)."""
        import numpy as np
        try:
            self.ax.clear()
            self.ax.plot(T, Sa, linewidth=2.0)
            self.ax.set_title('', pad=8)
            self.ax.set_xlabel('Periyot, T (s)')
            self.ax.set_ylabel(f'Spektral İvme, Sa ({acc_unit_symbol})')
            self.ax.grid(True, alpha=0.3, linewidth=0.5)
            T_arr = np.asarray(T)
            self._create_interactive_overlays()
            self._hide_cursor_overlay(force=True)
            tmin = float(np.nanmin(T_arr[T_arr > 0])) if np.any(T_arr > 0) else 1e-3
            self.ax.set_xlim(left=max(1e-3, tmin), right=float(np.nanmax(T_arr)))
            self.ax.set_ylim(bottom=0)
            self.canvas.draw_idle()
        except Exception:
            try:
                self.canvas.draw_idle()
            except Exception:
                pass

    def _show_plot_context_menu(self, event):
        """ERS grafiği için sağ tık menüsünü gösterir"""
        try:
            menu = tk.Menu(self.canvas.get_tk_widget(), tearoff=0)
            menu.add_command(label="💾 Grafiği Kaydet (PNG)", command=lambda: self._save_plot('png'))
            menu.add_command(label="🖼️ Grafiği Kaydet (PDF)", command=lambda: self._save_plot('pdf'))
            menu.add_command(label="📄 Grafiği Kaydet (SVG)", command=lambda: self._save_plot('svg'))
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass
        except Exception:
            pass

    def _save_plot(self, format_type: str = 'png') -> None:
        """Mevcut ERS grafiğini kaydeder"""
        try:
            if not self.figure or not self.ax:
                return
            if format_type not in ['png', 'pdf', 'svg']:
                format_type = 'png'
            # Dosya seçimi
            filetypes = []
            if format_type == 'png':
                filetypes = [("PNG dosyası", "*.png"), ("Tüm dosyalar", "*.*")]
            elif format_type == 'pdf':
                filetypes = [("PDF dosyası", "*.pdf"), ("Tüm dosyalar", "*.*")]
            else:
                filetypes = [("SVG dosyası", "*.svg"), ("Tüm dosyalar", "*.*")]
            filename = filedialog.asksaveasfilename(
                title=f"ERS Grafiğini Kaydet ({format_type.upper()})",
                defaultextension=f".{format_type}",
                filetypes=filetypes
            )
            if not filename:
                return
            # Renderer ve sıkı bounding box
            try:
                self.canvas.draw()
            except Exception:
                try:
                    self.figure.canvas.draw()
                except Exception:
                    pass
            try:
                renderer = self.figure.canvas.get_renderer()
            except Exception:
                renderer = None
            bbox = self.ax.get_tightbbox(renderer) if renderer is not None else None
            bbox_inches = bbox.transformed(self.figure.dpi_scale_trans.inverted()) if bbox else 'tight'
            # DPI: PNG için yüksek, vektör için orta
            dpi = 300 if format_type == 'png' else 150
            self.figure.savefig(
                filename,
                dpi=dpi,
                bbox_inches=bbox_inches,
                facecolor='white',
                edgecolor='none',
                format=format_type
            )
            try:
                messagebox.showinfo("Başarılı", f"ERS grafiği kaydedildi:\n{filename}")
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror("Hata", f"Grafik kaydedilirken hata:\n{str(e)}")
            except Exception:
                pass
    
    def _update_results_panel(self):
        """Sonuçlar panelini günceller"""
        if not self.results_panel or not self.current_results:
            return
        
        try:
            # Hesaplama parametrelerini topla
            parameters = {
                'damping_list': [float(d.strip()) for d in self.damping_var.get().split(',') if d.strip()],
                'Tmin': float(self.tmin_var.get()),
                'Tmax': float(self.tmax_var.get()),
                'nT': int(self.nperiods_var.get()),
                'logspace': True,  # Varsayılan olarak logaritmik
                'accel_unit': self.accel_unit_var.get(),
                'baseline': 'none',  # Baseline kaldırıldı
                'enforce_dt_over_T': float(self.dt_over_t_var.get()) if self.dt_over_t_var.get().strip() else None
            }
            
            # Sonuçlar panelini güncelle
            self.results_panel.update_results(
                results_data=self.current_results,
                parameters_data=parameters,
                earthquake_data=self.current_data
            )
            
        except Exception as e:
            print(f"Sonuçlar paneli güncellenirken hata: {e}")
    
    def _setup_tooltips(self):
        """Tooltip özelliğini kurar"""
        try:
            # Önceki cursor handler'ı temizle
            if self.cursor_handler:
                self.cursor_handler.remove()
                self.cursor_handler = None
            self._disconnect_manual_hover()
            
            # mplcursors kullanılabilirse onu kullan
            if MPLCURSORS_AVAILABLE and self.plot_lines:
                lines = [data['line'] for data in self.plot_lines.values()]
                self.cursor_handler = mplcursors.cursor(lines, hover=True)
                self.cursor_handler.connect("add", self._on_cursor_add)
            else:
                # Manuel hover event sistemi
                self._setup_manual_hover()
                
        except Exception as e:
            # Hata durumunda manuel sisteme geç
            self._setup_manual_hover()
    
    def _disconnect_manual_hover(self):
        """Manuel hover event bağlantısını koparır."""
        try:
            if self.manual_hover_cid and self.canvas:
                self.canvas.mpl_disconnect(self.manual_hover_cid)
            self.manual_hover_cid = None
        except Exception:
            self.manual_hover_cid = None
    
    def _on_cursor_add(self, sel):
        """mplcursors cursor ekleme event'i"""
        try:
            line = sel.artist
            info = None
            for z, data in self.plot_lines.items():
                if data['line'] == line:
                    x_click = sel.target[0]
                    idx = int(np.argmin(np.abs(data['x'] - x_click)))
                    info = self._build_point_info(z, data, idx)
                    break
            if info:
                sel.annotation.set_text(self._format_tooltip_text(info))
                sel.annotation.get_bbox_patch().set(
                    boxstyle="round,pad=0.3",
                    facecolor="lightyellow",
                    alpha=0.9,
                    edgecolor="gray"
                )
        except Exception:
            sel.annotation.set_text("Veri okunamadı")
    
    def _setup_manual_hover(self):
        """Manuel hover event sistemi"""
        try:
            if self.manual_hover_cid and self.canvas:
                self.canvas.mpl_disconnect(self.manual_hover_cid)
                self.manual_hover_cid = None
            if not self.canvas:
                return
            self.manual_hover_cid = self.canvas.mpl_connect('motion_notify_event', self._on_hover)
            
            # Annotation objesi oluştur (gizli)
            if self.hover_annotation:
                self.hover_annotation.remove()
            
            self.hover_annotation = self.ax.annotate('',
                                                   xy=(0, 0),
                                                   xytext=(20, 20),
                                                   textcoords="offset points",
                                                   bbox=dict(boxstyle="round,pad=0.3",
                                                             facecolor="lightyellow",
                                                             alpha=0.9,
                                                             edgecolor="gray"),
                                                   arrowprops=dict(arrowstyle="->",
                                                                   connectionstyle="arc3,rad=0"),
                                                   fontsize=9,
                                                   visible=False)
        except Exception:
            pass
    
    def _on_hover(self, event):
        """Manuel hover event handler"""
        try:
            info = self._find_closest_point(event)
            if info:
                self._show_tooltip(info)
            elif self.hover_annotation:
                self.hover_annotation.set_visible(False)
                if self.canvas:
                    self.canvas.draw_idle()
        except Exception:
            pass
    
    def _show_tooltip(self, info):
        """Tooltip gösterir"""
        try:
            if self.hover_annotation:
                self.hover_annotation.xy = (info['x_value'], info['y_value'])
                self.hover_annotation.set_text(self._format_tooltip_text(info))
                self.hover_annotation.set_visible(True)
                if self.canvas:
                    self.canvas.draw_idle()
        except Exception:
            pass
    
    def _find_closest_point(self, event):
        """Ekren koordinatında en yakın spektrum noktasını döndürür."""
        try:
            if (event is None) or (event.inaxes != self.ax) or not self.plot_lines:
                return None
            mouse_coord = np.array([event.x, event.y])
            threshold = getattr(self, "_hover_pixel_threshold", 25) or 25
            best = None
            for damping, data in self.plot_lines.items():
                line = data.get('line')
                x_data = np.asarray(data.get('x', []))
                y_data = np.asarray(data.get('y', []))
                if line is None or x_data.size == 0 or y_data.size == 0:
                    continue
                try:
                    screen_coords = line.axes.transData.transform(np.column_stack((x_data, y_data)))
                except Exception:
                    continue
                distances = np.sqrt(np.sum((screen_coords - mouse_coord) ** 2, axis=1))
                idx = int(np.argmin(distances))
                dist = float(distances[idx])
                if dist < threshold and (best is None or dist < best.get('distance', float('inf'))):
                    info = self._build_point_info(damping, data, idx)
                    info['distance'] = dist
                    best = info
            return best
        except Exception:
            return None
    
    def _build_point_info(self, damping, line_data, idx):
        """Seçilen eğri noktası için ortak bilgi sözlüğü döndürür."""
        curves = line_data['curves']
        T = float(curves.T[idx])
        freq = (1.0 / T) if T else float('inf')
        xaxis = self.xaxis_var.get()
        if xaxis == "period":
            x_label = f"T = {T:.3f} s"
        else:
            x_label = f"f = {freq:.3f} Hz"
        ytype = line_data['ytype']
        if ytype == "sa":
            y_label = f"Sa = {curves.Sa_p_g[idx]:.3f} g"
        elif ytype == "sv":
            y_label = f"Sv = {curves.Sv_p[idx]:.3f} m/s"
        elif ytype == "sd":
            y_label = f"Sd = {curves.Sd[idx]:.6f} m"
        elif ytype == "sa_abs":
            if curves.Sa_abs is None:
                y_label = "Sa_abs mevcut değil"
            else:
                y_label = f"Sa_abs = {curves.Sa_abs[idx] / G:.3f} g"
        elif ytype == "sv_true":
            if curves.Sv_true is None:
                y_label = "Sv_true mevcut değil"
            else:
                y_label = f"Sv_true = {curves.Sv_true[idx]:.3f} m/s"
        elif ytype == "sa_rel":
            if curves.Sa_rel is None:
                y_label = "Sa_rel mevcut değil"
            else:
                y_label = f"Sa_rel = {curves.Sa_rel[idx]:.3f} m/s²"
        else:
            y_label = "Spektrum değeri"
        return {
            'damping': damping,
            'idx': idx,
            'data': line_data,
            'x_value': float(line_data['x'][idx]),
            'y_value': float(line_data['y'][idx]),
            'x_label': x_label,
            'y_label': y_label,
            'T': T,
            'frequency': freq,
            'Sd': float(curves.Sd[idx]),
            'Sv': float(curves.Sv_p[idx]),
            'Sa_ms2': float(curves.Sa_p[idx]),
            'Sa_g': float(curves.Sa_p_g[idx]),
        }
    
    def _format_tooltip_text(self, info):
        """Tooltip metnini üretir."""
        try:
            return (
                f"Sönüm: ζ = {info.get('damping', 0):.1f}%\n"
                f"{info.get('x_label', '')}\n"
                f"{info.get('y_label', '')}\n"
                f"Sd = {info.get('Sd', 0):.6f} m\n"
                f"Sv = {info.get('Sv', 0):.3f} m/s\n"
                f"Sa = {info.get('Sa_g', 0):.3f} g ({info.get('Sa_ms2', 0):.3f} m/s²)"
            )
        except Exception:
            return ""
    
    def _refresh_other_plots(self):
        """Diğer grafikleri refresh eder (matplotlib state sorununu önlemek için)"""
        try:
            if self.main_window:
                # Time series canvas'ını güvenli şekilde refresh et
                if hasattr(self.main_window, 'time_series_canvas') and self.main_window.time_series_canvas:
                    self.main_window.time_series_canvas.draw_idle()
                
                # İnteraktif plot'u güvenli şekilde refresh et  
                if hasattr(self.main_window, 'interactive_plot') and self.main_window.interactive_plot:
                    if hasattr(self.main_window.interactive_plot, 'canvas') and self.main_window.interactive_plot.canvas:
                        self.main_window.interactive_plot.canvas.draw_idle()
                
                # Matplotlib current figure'ı reset et (ERS figure'ını koruyarak)
                import matplotlib.pyplot as plt
                plt.figure(self.figure.number)  # ERS figure'ını aktif yap
                    
        except Exception as e:
            # Hata durumunda sessizce geç
            pass
    
    def _delayed_refresh(self):
        """Geciktirilmiş refresh - UI thread'de çalışır"""
        # Bu metod şu an kullanılmıyor, basit tutuyoruz
        pass
    
    def set_main_window(self, main_window):
        """Ana window referansını ayarlar"""
        self.main_window = main_window
    
    def set_results_panel(self, results_panel):
        """Sonuçlar paneli referansını ayarlar"""
        self.results_panel = results_panel
    
    def _export_data(self):
        """Veri dışa aktarma (CSV ve XLSX formatları)"""
        if not self.current_results:
            messagebox.showerror("Hata", "Önce ERS hesaplama yapın!")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                title="ERS Verileri Kaydet",
                defaultextension=".xlsx",
                filetypes=[
                    ("Excel dosyaları", "*.xlsx"),
                    ("CSV dosyaları", "*.csv"), 
                    ("Tüm dosyalar", "*.*")
                ]
            )
            
            if filename:
                file_ext = filename.lower().split('.')[-1]
                
                if file_ext == 'xlsx':
                    self._export_to_xlsx(filename)
                else:
                    # CSV veya diğer formatlar için mevcut fonksiyonu kullan
                    from ...calculations.response_spectrum import export_spectra_to_csv
                    export_spectra_to_csv(self.current_results, filename)
                
                messagebox.showinfo("Başarılı", f"ERS verileri kaydedildi:\n{filename}")
                
        except Exception as e:
            messagebox.showerror("Hata", f"Veri dışa aktarma hatası:\n{str(e)}")
    
    def _export_to_xlsx(self, filename):
        """XLSX formatında dışa aktarma"""
        try:
            import pandas as pd
            
            # Her sönüm oranı için ayrı sheet oluştur
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                
                # Özet sheet - tüm veriler tek tabloda
                summary_data = []
                for z_pct, curves in self.current_results.items():
                    for i, T in enumerate(curves.T):
                        row = {
                            'Periyot (s)': T,
                            'Sönüm (%)': z_pct,
                            'Sd (m)': curves.Sd[i],
                            'Sv (m/s)': curves.Sv_p[i],
                            'Sa (m/s²)': curves.Sa_p[i],
                            'Sa (g)': curves.Sa_p_g[i]
                        }
                        if getattr(curves, "Sv_true", None) is not None:
                            row['Sv_true (m/s)'] = curves.Sv_true[i]
                        if getattr(curves, "Sa_rel", None) is not None:
                            row['Sa_rel (m/s²)'] = curves.Sa_rel[i]
                        if getattr(curves, "Sa_abs", None) is not None:
                            row['Sa_abs (m/s²)'] = curves.Sa_abs[i]
                            row['Sa_abs (g)'] = curves.Sa_abs[i] / G
                        summary_data.append(row)
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Özet', index=False)
                
                # Her sönüm oranı için ayrı sheet
                for z_pct, curves in self.current_results.items():
                    data = {
                        'Periyot (s)': curves.T,
                        'Sd (m)': curves.Sd,
                        'Sv (m/s)': curves.Sv_p,
                        'Sa (m/s²)': curves.Sa_p,
                        'Sa (g)': curves.Sa_p_g
                    }
                    if curves.Sv_true is not None:
                        data['Sv_true (m/s)'] = curves.Sv_true
                    if curves.Sa_rel is not None:
                        data['Sa_rel (m/s²)'] = curves.Sa_rel
                    if curves.Sa_abs is not None:
                        data['Sa_abs (m/s²)'] = curves.Sa_abs
                        data['Sa_abs (g)'] = curves.Sa_abs / G
                    
                    df = pd.DataFrame(data)
                    sheet_name = f'Sönüm_{z_pct:.1f}%'
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Meta bilgiler sheet'i
                if self.current_data:
                    time_data, acceleration, dt, accel_unit = self.current_data
                    meta_data = {
                        'Parametre': [
                            'Zaman Adımı (s)',
                            'Örneklem Sayısı',
                            'Toplam Süre (s)',
                            'İvme Birimi',
                            'Sönüm Oranları (%)',
                            'Periyot Aralığı',
                            'Periyot Sayısı'
                        ],
                        'Değer': [
                            f'{dt:.6f}',
                            f'{len(acceleration)}',
                            f'{time_data[-1] - time_data[0]:.2f}',
                            accel_unit,
                            ', '.join([f'{z:.1f}' for z in self.current_results.keys()]),
                            f'{self.tmin_var.get()} - {self.tmax_var.get()} s',
                            f'{len(list(self.current_results.values())[0].T)}'
                        ]
                    }
                    
                    meta_df = pd.DataFrame(meta_data)
                    meta_df.to_excel(writer, sheet_name='Parametreler', index=False)
            
        except ImportError:
            messagebox.showerror("Hata", "XLSX dışa aktarma için pandas ve openpyxl gerekli.\npip install pandas openpyxl")
            raise
    
    def _export_png(self):
        """PNG dışa aktarma"""
        if not self.current_results:
            messagebox.showerror("Hata", "Önce ERS hesaplama yapın!")
            return
        
        try:
            filename = filedialog.asksaveasfilename(
                title="ERS PNG Kaydet",
                defaultextension=".png",
                filetypes=[("PNG dosyaları", "*.png"), ("Tüm dosyalar", "*.*")]
            )
            
            if filename:
                # Yüksek çözünürlüklü grafik oluştur
                plot_spectra(
                    self.current_results,
                    ytype=self.ytype_var.get(),
                    xaxis=self.xaxis_var.get(),
                    title="Gerçek Tepki Spektrumu" if self.is_real_mode else "Elastik Tepki Spektrumu",
                    outfile=filename
                )
                messagebox.showinfo("Başarılı", f"ERS grafiği kaydedildi:\n{filename}")
                
        except Exception as e:
            messagebox.showerror("Hata", f"PNG dışa aktarma hatası:\n{str(e)}")
