"""
3B Basit Ölçeklendirme sekmesi için panel bileşeni.
Kaynak: TBDY2018_3B_Basit_Olceklendirme_Algoritmasi.md
"""

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from typing import Callable, List, Sequence, Tuple, Dict
import numpy as np
import re

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
except Exception:
    FigureCanvasTkAgg = None
    plt = None

from ...calculations.basic_scaling import basic_scaling_3d, _validate_records
from ...scaling.tbdy_scaling import scale_3d_simple_tbdy, export_tbdy_results_csv
from ...config.constants import MIN_RECORD_COUNT
from ...models.design_params import DesignParamsModel
from .pairing_dialog import PairingDialog

# Tooltip için basit yardımcı sınıf
class SimpleToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self._show_tip)
        widget.bind("<Leave>", self._hide_tip)

    def _show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + 20
            self.tipwindow = tk.Toplevel(self.widget)
            self.tipwindow.wm_overrideredirect(True)
            self.tipwindow.wm_geometry(f"+{x}+{y}")
            label = ttk.Label(self.tipwindow, text=self.text, justify="left", 
                            background="#ffffe0", relief="solid", borderwidth=1)
            label.pack(ipadx=1)
        except Exception:
            pass

    def _hide_tip(self, event=None):
        try:
            if self.tipwindow:
                self.tipwindow.destroy()
                self.tipwindow = None
        except Exception:
            pass


class BasicScalingPanel:
    def __init__(self, parent_frame,
                 records_provider: Callable[[], Sequence[Tuple[np.ndarray, np.ndarray, float, Dict]]],
                 accel_unit_getter: Callable[[], str] = lambda: 'g',
                 design_params_model: DesignParamsModel | None = None,
                 input_panel=None):
        self.parent = parent_frame
        self.records_provider = records_provider
        self._get_accel_unit = accel_unit_getter
        self.dp = design_params_model
        self.input_panel = input_panel
        self.frame = ttk.Frame(self.parent)
        self._build()
        try:
            self.frame.pack(fill="both", expand=True)
        except Exception:
            pass

    def _create_subscript_label(self, parent, base_text: str, sub_text: str = "", suffix: str = ""):
        """Alt indisli görünüm için birleşik label döndürür."""
        container = ttk.Frame(parent)
        
        try:
            base_font = tkfont.nametofont('TkDefaultFont')
            sub_font = base_font.copy()
            # Subscript bir tık küçük ama okunur olsun
            sub_font.configure(size=max(base_font.cget('size') - 1, 8))
        except Exception:
            # Fallback
            base_font = None
            sub_font = None
        
        base_lbl = ttk.Label(container, text=base_text, font=base_font)
        base_lbl.grid(row=0, column=0, sticky="w")
        
        if sub_text:
            sub_lbl = ttk.Label(container, text=sub_text, font=sub_font)
            # Alt indis için aşağı doğru hafif kaydırma
            sub_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))
        
        if suffix:
            suffix_lbl = ttk.Label(container, text=suffix, font=base_font)
            suffix_lbl.grid(row=0, column=2, sticky="w")
        
        return container

    def _build(self):
        # PanedWindow düzeni: sol parametreler, sağ grafik
        paned = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")
        self.frame.grid_rowconfigure(0, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        container_left = ttk.Frame(paned)
        container_right = ttk.Frame(paned)
        try:
            paned.add(container_left, weight=0)
            paned.add(container_right, weight=1)
        except Exception:
            # Eski temalarda weight desteklenmeyebilir
            paned.add(container_left)
            paned.add(container_right)
        container_right.grid_columnconfigure(0, weight=1)
        container_right.grid_rowconfigure(0, weight=1)

        # Parametreler
        params = ttk.LabelFrame(container_left, text="Hedef Spektrum Bilgileri", padding=10)
        params.pack(fill="x", padx=8, pady=8)

        self.var_Tp = tk.DoubleVar(value=1.0)
        grid = ttk.Frame(params)
        grid.pack(fill="x")
        # Dinamik genişleme: kolonu ayarla (sol sabit, sağ esnek)
        try:
            grid.grid_columnconfigure(0, weight=0)
            grid.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        
        # Tp alanı kaldırıldı (yalnızca SDS, SD1, TL gösterilecek)
        
        # SDS label with subscript
        sds_label_container = self._create_subscript_label(grid, "S", "DS", " (g):")
        sds_label_container.grid(row=2, column=0, sticky="w")
        self.lbl_sds = ttk.Label(grid, textvariable=(self.dp.sds_var if self.dp else tk.StringVar(value="--")))
        try:
            self.lbl_sds.configure(anchor="w", justify="left")
        except Exception:
            pass
        self.lbl_sds.grid(row=2, column=1, sticky="w")
        
        # SD1 label with subscript
        sd1_label_container = self._create_subscript_label(grid, "S", "D1", " (g):")
        sd1_label_container.grid(row=3, column=0, sticky="w")
        self.lbl_sd1 = ttk.Label(grid, textvariable=(self.dp.sd1_var if self.dp else tk.StringVar(value="--")))
        try:
            self.lbl_sd1.configure(anchor="w", justify="left")
        except Exception:
            pass
        self.lbl_sd1.grid(row=3, column=1, sticky="w")
        
        # TL label with subscript
        tl_label_container = self._create_subscript_label(grid, "T", "L", " (s):")
        tl_label_container.grid(row=4, column=0, sticky="w")
        self.lbl_tl = ttk.Label(grid, textvariable=(self.dp.tl_var if self.dp else tk.StringVar(value="--")))
        try:
            self.lbl_tl.configure(anchor="w", justify="left")
        except Exception:
            pass
        self.lbl_tl.grid(row=4, column=1, sticky="w")

        # Divider
        ttk.Separator(grid, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8,6))
        # Spektrum Ölçekleme Katsayısı (α)
        ttk.Label(grid, text="Spektrum Ölçekleme Katsayısı:").grid(row=6, column=0, sticky="w")
        # α girişini buraya taşı (varsayılan 1.0)
        self.var_alpha = getattr(self, 'var_alpha', tk.DoubleVar(value=1.0))
        self.alpha_entry = ttk.Entry(grid, textvariable=self.var_alpha, width=10)
        self.alpha_entry.grid(row=6, column=1, sticky="w")
        SimpleToolTip(self.alpha_entry, "Ölçekleme katsayısı α. Varsayılan 1.3\n(Yönetmelik 2.5.2.1-b bağlamında tipik değer)")


        # Gelişmiş ayarlar
        adv = ttk.LabelFrame(container_left, text="Gelişmiş", padding=10)
        adv.pack(fill="x", padx=8, pady=(0,8))
        # Referansı sakla (No Scaling modunda gizlemek için)
        self.adv_frame = adv
        
        # Sönüm parametresi
        self.var_damping = tk.DoubleVar(value=5.0)
        damping_frame = ttk.Frame(adv)
        damping_frame.pack(fill="x", pady=(0,6))
        ttk.Label(damping_frame, text="Sönüm (%):", width=15).pack(side="left")
        damping_entry = ttk.Entry(damping_frame, textvariable=self.var_damping, width=8)
        damping_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(damping_entry, "Spektral analiz için sönüm oranı (%)\nTBDY-2018'de genellikle %5 kullanılır")
        
        # Yalıtımlı seçeneği
        self.var_is_isolated = tk.BooleanVar(value=False)
        isolated_frame = ttk.Frame(adv)
        isolated_frame.pack(fill="x", pady=(0,6))
        isolated_check = ttk.Checkbutton(isolated_frame, text="Yalıtımlı (0.5Tₘ - 1.25Tₘ)", variable=self.var_is_isolated)
        isolated_check.pack(side="left")
        SimpleToolTip(isolated_check, "Yalıtımlı yapılar için özel periyot aralığı\nTₘ: Yalıtım sisteminin etkin periyodu\nKontrol aralığı: [0.5Tₘ, 1.25Tₘ]")
        
        # Zarf Periyot seçeneği
        self.var_use_envelope = tk.BooleanVar(value=False)
        envelope_frame = ttk.Frame(adv)
        envelope_frame.pack(fill="x", pady=(0,6))
        envelope_check = ttk.Checkbutton(envelope_frame, text="Zarf Periyot (Tₚ,ₓ/Tₚ,ᵧ)", variable=self.var_use_envelope)
        envelope_check.pack(side="left")
        SimpleToolTip(envelope_check, "İki yönlü periyot zarfı kullanımı\nTₚ,ₓ: X yönündeki hakim periyot\nTₚ,ᵧ: Y yönündeki hakim periyot")
        
        # Periyot parametreleri
        period_frame = ttk.LabelFrame(adv, text="Periyot Parametreleri", padding=5)
        period_frame.pack(fill="x", pady=(6,0))
        
        # İlk satır: Tp,x ve Tp,y
        row1 = ttk.Frame(period_frame)
        row1.pack(fill="x", pady=(0,4))
        self.var_Tp_x = tk.StringVar(value="")
        self.var_Tp_y = tk.StringVar(value="")
        
        # Tp,x
        tpx_container = self._create_subscript_label(row1, "T", "p,x", " (s):")
        tpx_container.pack(side="left")
        tpx_entry = ttk.Entry(row1, textvariable=self.var_Tp_x, width=8)
        tpx_entry.pack(side="left", padx=(5,15))
        SimpleToolTip(tpx_entry, "X yönündeki hakim periyot (saniye)\nZarf periyot seçeneği için gerekli\nTₚ,ₓ ile gösterilir")
        
        # Tp,y
        tpy_container = self._create_subscript_label(row1, "T", "p,y", " (s):")
        tpy_container.pack(side="left")
        tpy_entry = ttk.Entry(row1, textvariable=self.var_Tp_y, width=8)
        tpy_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(tpy_entry, "Y yönündeki hakim periyot (saniye)\nZarf periyot seçeneği için gerekli\nTₚ,ᵧ ile gösterilir")
        
        # İkinci satır: TM ve Teval
        row2 = ttk.Frame(period_frame)
        row2.pack(fill="x", pady=(0,4))
        self.var_TM = tk.StringVar(value="")
        self.var_Teval = tk.StringVar(value="")
        
        # TM
        tm_container = self._create_subscript_label(row2, "T", "M", " (s):")
        tm_container.pack(side="left")
        tm_entry = ttk.Entry(row2, textvariable=self.var_TM, width=8)
        tm_entry.pack(side="left", padx=(5,15))
        SimpleToolTip(tm_entry, "Yalıtım sisteminin etkin periyodu (saniye)\nYalıtımlı yapılar için gerekli\nTₘ ile gösterilir")
        
        # Teval
        teval_container = self._create_subscript_label(row2, "T", "eval", " (s):")
        teval_container.pack(side="left")
        teval_entry = ttk.Entry(row2, textvariable=self.var_Teval, width=8)
        teval_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(teval_entry, "Değerlendirme periyodu (saniye)\nBoş bırakılırsa Tₚ kullanılır\nTₑᵥₐₗ ile gösterilir")
        
        # Ölçekleme parametreleri
        scale_frame = ttk.LabelFrame(adv, text="Ölçekleme Parametreleri", padding=5)
        scale_frame.pack(fill="x", pady=(6,0))
        
        # Alpha ve fmax
        scale_row = ttk.Frame(scale_frame)
        scale_row.pack(fill="x")
        
        # α alanı bu bölümden kaldırıldı (üstte yer alıyor)
        # α görünümünü başlık altında da göster
        try:
            self._alpha_display_var.set(f"α = {float(self.var_alpha.get()):.2f}")
            self.var_alpha.trace_add('write', lambda *_: self._alpha_display_var.set(f"α = {float(self.var_alpha.get() or 0):.2f}"))
        except Exception:
            pass
        
        # fmax
        fmax_container = self._create_subscript_label(scale_row, "f", "max", ":")
        fmax_container.pack(side="left")
        self.var_max_scale = tk.StringVar(value="")
        fmax_entry = ttk.Entry(scale_row, textvariable=self.var_max_scale, width=8)
        fmax_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(fmax_entry, "Maksimum ölçek katsayısı sınırı\nBoş bırakılırsa sınır uygulanmaz\nfₘₐₓ ile gösterilir")
        
        # Kayıt-bazlı (LP) seçeneği
        lp_frame = ttk.Frame(scale_frame)
        lp_frame.pack(fill="x", pady=(6,0))
        self.var_use_record_based = tk.BooleanVar(value=False)
        lp_check = ttk.Checkbutton(lp_frame, text="Kayıt-bazlı (LP) Ölçekleme", variable=self.var_use_record_based)
        lp_check.pack(side="left")
        SimpleToolTip(lp_check, "Kayıt-bazlı lineer programlama ölçeklemesi\nHer kayıt için ayrı ölçek katsayısı hesaplar\n(Kısıt-Tatmin modu)")

        # Yöntem seçimi
        method_box = ttk.LabelFrame(container_left, text="Yöntem", padding=6)
        # Üste taşı: params'tan önce yerleştir
        method_box.pack(fill="x", padx=8, pady=(0,8), before=params)
        self.var_scale_mode = tk.StringVar(value="TBDY-2018 (3B Basit)")
        ttk.Label(method_box, text="Ölçekleme Yöntemi:").grid(row=0, column=0, sticky="w")
        self.cmb_scale_mode = ttk.Combobox(method_box, state="readonly", width=28, textvariable=self.var_scale_mode)
        self.cmb_scale_mode['values'] = (
            "TBDY-2018 (3B Basit)",
            "PEER – No Scaling",
            "PEER – Minimize MSE",
            "PEER – Single Period",
        )
        self.cmb_scale_mode.grid(row=0, column=1, sticky="w", padx=6)
        self.cmb_scale_mode.bind('<<ComboboxSelected>>', lambda e: self._toggle_peer_panel())

        # Global Bileşke Spektrum seçimi KALDIRILDI (varsayılan SRSS)
        self.var_global_ordinate = tk.StringVar(value='SRSS')
        self.cmb_global_ordinate = None

        # Ölçek Katsayısı Limiti (kaldırıldı)

        # PEER ayarları (yalnızca PEER modunda görünür)
        self.peer_frame = ttk.LabelFrame(container_left, text="PEER Ayarları", padding=10)
        self.var_peer_ppd = tk.IntVar(value=100)
        self.var_peer_enforce = tk.BooleanVar(value=True)  # Her zaman True (checkbox kaldırıldı)
        self.var_peer_tmin = tk.StringVar(value="")
        self.var_peer_tmax = tk.StringVar(value="")
        self.var_peer_max_global = tk.StringVar(value="")
        self.var_peer_method = tk.StringVar(value="min_mse")
        self.var_peer_use_custom_weights = tk.BooleanVar(value=False)
        self.var_peer_period_knots = tk.StringVar(value="")
        self.var_peer_weight_knots = tk.StringVar(value="")
        self.var_peer_single_period = tk.StringVar(value="")
        if not hasattr(self, 'var_peer_limit_min'):
            self.var_peer_limit_min = tk.StringVar(value="")
        if not hasattr(self, 'var_peer_limit_max'):
            self.var_peer_limit_max = tk.StringVar(value="")
        # PEER için varsayılan spektral ordinat: SRSS
        self.var_peer_ordinate = tk.StringVar(value="SRSS")
        
        # Metot seçimi (Kaldırıldı: No Scaling/Min MSE/Single Period combobox'ı gösterilmeyecek)
        self.method_combo = None

        # Bileşke seçimi (Kaldırıldı: PEER bileşke combobox'ı göstermiyoruz)
        self.ordinate_combo = None

        # Points/decade parametresi
        ppd_frame = ttk.Frame(self.peer_frame)
        ppd_frame.pack(fill="x", pady=(0,6))
        ttk.Label(ppd_frame, text="Points/decade:", width=15).pack(side="left")
        ppd_entry = ttk.Entry(ppd_frame, textvariable=self.var_peer_ppd, width=8)
        ppd_entry.pack(side="left", padx=(5,15))
        SimpleToolTip(ppd_entry, "Dekad başına nokta sayısı\nPGMD standardı: 100 nokta/dekad\nLog-uzayda periyot ızgarası yoğunluğunu belirler")
        
        # Ağırlık parametresi
        weight_row = ttk.Frame(self.peer_frame)
        weight_row.pack(fill="x", pady=(0,6))
        chk = ttk.Checkbutton(weight_row, text="Özel ağırlık kullan", variable=self.var_peer_use_custom_weights, command=self._toggle_peer_weights)
        chk.pack(side="left")
        SimpleToolTip(chk, "Kullanıcı tanımlı periyot/ağırlık düğümleri ile log-T üzerinde ağırlık fonksiyonu")
        ttk.Label(weight_row, text="Period düğümleri (s):").pack(side="left", padx=(10,0))
        self.entry_peer_period_knots = ttk.Entry(weight_row, textvariable=self.var_peer_period_knots, width=18, state="disabled")
        self.entry_peer_period_knots.pack(side="left", padx=(5,0))
        SimpleToolTip(self.entry_peer_period_knots, "Periyot düğümleri (saniye). Örnek: 0.01,0.1,1,10")
        ttk.Label(weight_row, text="Ağırlıklar:").pack(side="left", padx=(10,0))
        self.entry_peer_weight_knots = ttk.Entry(weight_row, textvariable=self.var_peer_weight_knots, width=18, state="disabled")
        self.entry_peer_weight_knots.pack(side="left", padx=(5,0))
        SimpleToolTip(self.entry_peer_weight_knots, "Düğüm ağırlıkları. Örnek: 1,2,3,2,1")
        
        # Periyot aralığı
        range_frame = ttk.Frame(self.peer_frame)
        range_frame.pack(fill="x", pady=(0,6))
        ttk.Label(range_frame, text="Periyot aralığı (s):", width=15).pack(side="left")
        tmin_entry = ttk.Entry(range_frame, textvariable=self.var_peer_tmin, width=8)
        tmin_entry.pack(side="left", padx=(5,5))
        SimpleToolTip(tmin_entry, "Minimum periyot (saniye)\nBoş bırakılırsa otomatik hesaplanır\nÖrnek: 0.01")
        
        ttk.Label(range_frame, text="-").pack(side="left")
        tmax_entry = ttk.Entry(range_frame, textvariable=self.var_peer_tmax, width=8)
        tmax_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(tmax_entry, "Maksimum periyot (saniye)\nBoş bırakılırsa otomatik hesaplanır\nÖrnek: 10.0")
        
        # Single period alanı
        single_frame = ttk.Frame(self.peer_frame)
        single_frame.pack(fill="x", pady=(0,6))
        ttk.Label(single_frame, text="T_s (Single Period):", width=15).pack(side="left")
        self.entry_peer_single_period = ttk.Entry(single_frame, textvariable=self.var_peer_single_period, width=8, state="disabled")
        self.entry_peer_single_period.pack(side="left", padx=(5,0))
        SimpleToolTip(self.entry_peer_single_period, "Single Period modunda hedef periyot (saniye)")

        # Ölçek limitleri
        limits_frame = ttk.Frame(self.peer_frame)
        limits_frame.pack(fill="x", pady=(0,6))
        ttk.Label(limits_frame, text="f_min/f_max:", width=15).pack(side="left")
        self.entry_peer_limit_min = ttk.Entry(limits_frame, textvariable=self.var_peer_limit_min, width=8)
        self.entry_peer_limit_min.pack(side="left", padx=(5,5))
        self.entry_peer_limit_max = ttk.Entry(limits_frame, textvariable=self.var_peer_limit_max, width=8)
        self.entry_peer_limit_max.pack(side="left", padx=(5,0))
        SimpleToolTip(self.entry_peer_limit_min, "Opsiyonel alt ölçek limiti (boş = sınırsız)")
        SimpleToolTip(self.entry_peer_limit_max, "Opsiyonel üst ölçek limiti (boş = sınırsız)")

        # Max global scale
        global_frame = ttk.Frame(self.peer_frame)
        global_frame.pack(fill="x")
        ttk.Label(global_frame, text="Max global scale:", width=15).pack(side="left")
        global_entry = ttk.Entry(global_frame, textvariable=self.var_peer_max_global, width=8)
        global_entry.pack(side="left", padx=(5,0))
        SimpleToolTip(global_entry, "Maksimum küresel ölçek katsayısı\nTüm kayıtlara uygulanacak üst sınır\nBoş bırakılırsa sınır uygulanmaz")
        
        # Başlangıçta gizle
        self.peer_frame.pack_forget()

        # PEER yardımcı alan davranışları
        self._toggle_peer_method_fields()

        # Basitleştirilmiş yöntem seçimi değişince PEER/TBDY UI'ına yansıt
        # (Untitled-1.py davranışı)

        # TBDY-2018 ayarları (varsayılan olarak görünür)
        self.tbdy_frame = ttk.LabelFrame(container_left, text="TBDY-2018 3B Basit Ölçeklendirme", padding=10)
        
        # Validasyon bilgileri
        validation_frame = ttk.Frame(self.tbdy_frame)
        validation_frame.pack(fill="x", pady=(0,6))
        
        # Kayıt sayısı bilgisi
        self.lbl_record_validation = ttk.Label(validation_frame, text="Kayıt sayısı: ≥11 (TBDY 2.5.1.3)", foreground="blue")
        self.lbl_record_validation.pack(side="left")
        SimpleToolTip(self.lbl_record_validation, "TBDY-2018'e göre 3B analiz için:\n• En az 11 kayıt takımı gereklidir\n• Aynı depremden en fazla 3 takım seçilebilir")
        
        # Aynı olay bilgisi
        self.lbl_event_validation = ttk.Label(validation_frame, text=" | Aynı olay: ≤3 (zorunlu)", foreground="red")
        self.lbl_event_validation.pack(side="left")
        
        # Spektrum bilgisi
        spectrum_frame = ttk.Frame(self.tbdy_frame)
        spectrum_frame.pack(fill="x", pady=(0,6))
        
        ttk.Label(spectrum_frame, text="Bileşke spektrum:").pack(side="left")
        ttk.Label(spectrum_frame, text="SRSS = √(SAₓ² + SAᵧ²)", font=("Consolas", 9), foreground="darkgreen").pack(side="left", padx=(5,15))
        SimpleToolTip(spectrum_frame, "TBDY 2.5.2.1-b: İki yatay bileşenin bileşke spektrumu\nSRSS (Square Root of Sum of Squares) yöntemi")
        
        ttk.Label(spectrum_frame, text="Kontrol aralığı:").pack(side="left")
        self.lbl_control_range = ttk.Label(spectrum_frame, text="[0.2×T₁, 1.5×T₁]", font=("Consolas", 9), foreground="darkblue")
        self.lbl_control_range.pack(side="left", padx=(5,0))
        SimpleToolTip(self.lbl_control_range, "TBDY 2.5.2.1-b: 3B analiz için kontrol aralığı\nT₁: Birinci doğal periyot")
        
        # 1.30 koşulu
        condition_frame = ttk.Frame(self.tbdy_frame)
        condition_frame.pack(fill="x", pady=(0,6))
        
        ttk.Label(condition_frame, text="TBDY koşulu:").pack(side="left")
        ttk.Label(condition_frame, text="Ortalama ≥ 1.30 × S_tasarım", font=("Consolas", 9), foreground="red").pack(side="left", padx=(5,0))
        SimpleToolTip(condition_frame, "TBDY 2.5.2.1-b: 3B analiz için zorunlu koşul\nÖlçeklenmiş bileşke spektrumların ortalaması\nkontrol aralığında tasarım spektrumunun en az 1.30 katı olmalı")
        
        # Global gamma bilgisi
        gamma_frame = ttk.Frame(self.tbdy_frame)
        gamma_frame.pack(fill="x")
        
        ttk.Label(gamma_frame, text="Global düzeltme:").pack(side="left")
        self.lbl_gamma_info = ttk.Label(gamma_frame, text="γ = 1.0 / min_ratio", font=("Consolas", 9), foreground="purple")
        self.lbl_gamma_info.pack(side="left", padx=(5,0))
        SimpleToolTip(self.lbl_gamma_info, "Koşul sağlanmazsa tüm ölçek katsayıları\naynı oranda büyütülür (global gamma)")
        
        # Başlangıçta göster
        self.tbdy_frame.pack(fill="x", padx=8, pady=(0,8))

        # Bilgi ve butonlar
        info = ttk.Frame(container_left)
        info.pack(fill="x", padx=8, pady=4)
        self.lbl_pairs = ttk.Label(info, text="Kayıt çifti: 0")
        self.lbl_pairs.pack(side="left")
        self.var_fmin = tk.StringVar(value="--")
        self.var_min_ratio = tk.StringVar(value="--")
        self._last_records = None
        self._last_result = None
        ttk.Label(info, text="  |  f_min: ").pack(side="left")
        ttk.Label(info, textvariable=self.var_fmin, font=("Segoe UI", 10, "bold")).pack(side="left")
        ttk.Label(info, text="  |  Min Oran: ").pack(side="left")
        self.lbl_min_ratio = ttk.Label(info, textvariable=self.var_min_ratio)
        self.lbl_min_ratio.pack(side="left")
        btns = ttk.Frame(container_left)
        btns.pack(fill="x", padx=8, pady=(0,6))
        try:
            btns.grid_columnconfigure(0, weight=1)
            btns.grid_columnconfigure(1, weight=0)
        except Exception:
            pass
        ttk.Button(btns, text="Eşleştir…", command=self._open_pair_dialog).pack(side="left")
        self._btn_compute = ttk.Button(btns, text="Hesapla", command=self._on_compute)
        self._btn_compute.pack(side="left", padx=(6,0))
        ttk.Button(btns, text="Dışa Aktar", command=self._on_export).pack(side="left", padx=(6,0))
        ttk.Button(btns, text="Temizle", command=self._on_clear).pack(side="left", padx=(6,0))

        # Grafik alanı
        plot_box = ttk.LabelFrame(container_right, text="Grafik")
        plot_box.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        if FigureCanvasTkAgg is not None and plt is not None:
            try:
                from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
            except Exception:
                NavigationToolbar2Tk = None
            self.fig = plt.Figure(figsize=(7, 4), dpi=100)
            self.ax = self.fig.add_subplot(111)
            self.ax.set_xlabel("Periyot, T (s)")
            self.ax.set_ylabel("Spektral İvme, Sa [g]")
            self.ax.grid(True, which="both", linestyle=":")
            # Eksen modu: Linear / Loglog
            self._axis_mode = tk.StringVar(value="Loglog")
            axis_toolbar = ttk.Frame(plot_box)
            try:
                axis_toolbar.pack(fill="x", pady=(4,0))
                ttk.Label(axis_toolbar, text="Eksen:").pack(side="left")
                cmb = ttk.Combobox(axis_toolbar, state="readonly", width=8, textvariable=self._axis_mode)
                cmb['values'] = ("Linear", "Loglog")
                cmb.current(1)
                cmb.pack(side="left", padx=6)
                cmb.bind('<<ComboboxSelected>>', lambda e: self._redraw_plot())
                # Metot rozeti
                self._method_badge = tk.StringVar(value="")
                badge = ttk.Label(axis_toolbar, textvariable=self._method_badge, foreground="#00695c")
                badge.pack(side="right")
            except Exception:
                pass
            # Katman anahtarları
            layers = ttk.Frame(plot_box)
            try:
                layers.pack(fill="x", pady=(4,0))
                self._show_target = tk.BooleanVar(value=True)
                self._show_suite = tk.BooleanVar(value=True)
                self._show_stdev = tk.BooleanVar(value=False)
                ttk.Checkbutton(layers, text="Target", variable=self._show_target, command=self._redraw_plot).pack(side="left")
                ttk.Checkbutton(layers, text="Suite Mean", variable=self._show_suite, command=self._redraw_plot).pack(side="left", padx=(6,0))
                ttk.Checkbutton(layers, text="±StDev", variable=self._show_stdev, command=self._redraw_plot).pack(side="left", padx=(6,0))
            except Exception:
                pass
            self.canvas = FigureCanvasTkAgg(self.fig, master=plot_box)
            self.canvas.get_tk_widget().pack(fill="both", expand=True)
            if NavigationToolbar2Tk is not None:
                try:
                    toolbar = NavigationToolbar2Tk(self.canvas, plot_box)
                    toolbar.update()
                except Exception:
                    pass
        else:
            self.fig = None
            self.ax = None
            self.canvas = None

        # Durum şeridi
        status = ttk.Frame(container_right)
        status.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,8))
        self.var_status = tk.StringVar(value="Kayıt çifti: 0 | f_min: -- | Min Oran: -- | Aralık: --")
        self.lbl_status = ttk.Label(status, textvariable=self.var_status)
        self.lbl_status.pack(side="left")

        # Sonuç Tablosu (PGMD uyumlu başlıklar)
        table_box = ttk.LabelFrame(container_right, text="Sonuç Tablosu - Deprem Kaydı Ölçekleme Sonuçları", padding=6)
        table_box.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0,8))
        # container_right satır ağırlıkları
        try:
            container_right.grid_rowconfigure(2, weight=1)
        except Exception:
            pass
        # Ara ve dışa aktar satırı
        top_bar = ttk.Frame(table_box)
        top_bar.pack(fill="x", pady=(0,4))
        ttk.Label(top_bar, text="Ara:").pack(side="left")
        self.var_search = tk.StringVar(value="")
        ent_search = ttk.Entry(top_bar, textvariable=self.var_search, width=30)
        ent_search.pack(side="left", padx=6)
        try:
            ent_search.bind('<KeyRelease>', lambda e: self._filter_results_table())
        except Exception:
            pass
        ttk.Button(top_bar, text="CSV'ye Dışa Aktar", command=lambda: self._export_results_table_csv()).pack(side="right")

        # Treeview Container with Scrollbars
        tree_container = ttk.Frame(table_box)
        tree_container.pack(fill="both", expand=True)
        
        # Treeview
        self._results_columns = (
            "No",
            "Grup Adı", 
            "Ölçek Katsayısı",
            "MSE",
            "D5-75 (s)",
            "D5-95 (s)",
            "Arias Şiddeti (m/s)",
            # Standartlaştırılmış sütunlar (rapor/CSV için)
            "Metot",
            "γ (suite)",
            "min_ratio@T",
            "pass_3D",
        )
        
        # Treeview oluştur
        self.results_tree = ttk.Treeview(tree_container, columns=self._results_columns, show="headings", height=8)
        
        # Başlık ve sütun ayarları
        self._column_configs = {
            "No": {"width": 50, "minwidth": 40, "stretch": False},
            "Grup Adı": {"width": 150, "minwidth": 100, "stretch": True},
            "Ölçek Katsayısı": {"width": 120, "minwidth": 100, "stretch": True},
            "MSE": {"width": 100, "minwidth": 80, "stretch": True},
            "D5-75 (s)": {"width": 90, "minwidth": 70, "stretch": True},
            "D5-95 (s)": {"width": 90, "minwidth": 70, "stretch": True},
            "Arias Şiddeti (m/s)": {"width": 140, "minwidth": 120, "stretch": True},
            "Metot": {"width": 100, "minwidth": 80, "stretch": True},
            "γ (suite)": {"width": 100, "minwidth": 80, "stretch": True},
            "min_ratio@T": {"width": 100, "minwidth": 80, "stretch": True},
            "pass_3D": {"width": 100, "minwidth": 80, "stretch": True},
        }
        
        for col in self._results_columns:
            config = self._column_configs[col]
            self.results_tree.heading(col, text=col, anchor="center")
            self.results_tree.column(
                col, 
                width=config["width"], 
                minwidth=config["minwidth"],
                anchor="center",
                stretch=config["stretch"]
            )
        
        # Grid layout for proper scrollbar positioning
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Treeview placement
        self.results_tree.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.results_tree.yview)
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.results_tree.configure(yscrollcommand=v_scrollbar.set)
        
        h_scrollbar = ttk.Scrollbar(tree_container, orient="horizontal", command=self.results_tree.xview)
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.results_tree.configure(xscrollcommand=h_scrollbar.set)
        
        # Otomatik sütun genişliği ayarlama için bind
        self.results_tree.bind('<Button-1>', self._on_treeview_click)
        self.results_tree.bind('<Configure>', self._on_treeview_configure)
        
        # Sağ tık menüsü (sütun genişliği ayarlama)
        self.results_tree.bind('<Button-3>', self._show_column_menu)
        # Tam veri satırlarını sakla (filtreleme için)
        self._results_full_rows = []

        # Başlangıçta Hesapla butonunu yalnızca α geçerli olduğunda aktif et
        try:
            self._update_compute_button_state()
            # α değişimlerini izleyerek butonu güncelle
            if hasattr(self, 'var_alpha'):
                self.var_alpha.trace_add('write', lambda *_: self._update_compute_button_state())
        except Exception:
            pass

        # İlk sayım
        self.refresh_pair_count()
        # PEER panel görünürlüğünü başlat
        try:
            self._toggle_peer_panel()
        except Exception:
            pass
        # <11 kayıt iken enforce butonunu güncelle
        try:
            self._update_enforce_state()
        except Exception:
            pass

    def _on_treeview_click(self, event):
        """Treeview tıklama olayını işler"""
        try:
            # Çift tıklama ile otomatik sütun genişliği ayarlama
            if event.num == 1:  # Sol tık
                region = self.results_tree.identify_region(event.x, event.y)
                if region == "separator":
                    # Sütun ayırıcısına çift tıklama ile otomatik boyutlandırma
                    self.results_tree.after_idle(self._auto_resize_columns)
        except Exception:
            pass

    def _on_treeview_configure(self, event):
        """Treeview boyut değişikliği olayını işler"""
        try:
            # Pencere boyutu değiştiğinde sütunları yeniden ayarla
            self.results_tree.after_idle(self._adjust_columns_to_content)
        except Exception:
            pass

    def _show_column_menu(self, event):
        """Sağ tık menüsü gösterir"""
        try:
            menu = tk.Menu(self.results_tree, tearoff=0)
            menu.add_command(label="Sütunları Otomatik Boyutlandır", command=self._auto_resize_columns)
            menu.add_command(label="Sütunları Sıfırla", command=self._reset_column_widths)
            menu.add_separator()
            menu.add_command(label="Tümünü Genişlet", command=self._expand_all_columns)
            menu.add_command(label="Tümünü Daralt", command=self._compress_all_columns)
            
            # Menüyü göster
            menu.tk_popup(event.x_root, event.y_root)
        except Exception:
            pass
        finally:
            try:
                menu.grab_release()
            except:
                pass

    def _auto_resize_columns(self):
        """Sütunları içeriğe göre otomatik boyutlandırır"""
        try:
            for col in self._results_columns:
                # Başlık genişliğini hesapla
                header_text = self.results_tree.heading(col)['text']
                header_width = len(str(header_text)) * 8  # Yaklaşık karakter genişliği
                
                # İçerik genişliğini hesapla
                max_content_width = header_width
                for item in self.results_tree.get_children():
                    try:
                        cell_value = self.results_tree.set(item, col)
                        content_width = len(str(cell_value)) * 7
                        max_content_width = max(max_content_width, content_width)
                    except Exception:
                        continue
                
                # Minimum ve maksimum sınırları uygula
                config = self._column_configs.get(col, {})
                min_width = config.get("minwidth", 50)
                max_width = 300  # Maksimum genişlik sınırı
                
                optimal_width = max(min_width, min(max_content_width + 20, max_width))
                self.results_tree.column(col, width=optimal_width)
        except Exception:
            pass

    def _adjust_columns_to_content(self):
        """Mevcut içeriğe göre sütun genişliklerini ayarlar"""
        try:
            if not self.results_tree.get_children():
                return
            
            # Sadece stretch=True olan sütunları ayarla
            for col in self._results_columns:
                config = self._column_configs.get(col, {})
                if config.get("stretch", False):
                    current_width = self.results_tree.column(col, "width")
                    min_width = config.get("minwidth", 50)
                    
                    # İçerik uzunluğunu kontrol et
                    max_content = 0
                    for item in self.results_tree.get_children():
                        try:
                            cell_value = str(self.results_tree.set(item, col))
                            max_content = max(max_content, len(cell_value) * 7)
                        except Exception:
                            continue
                    
                    # Optimal genişlik hesapla
                    optimal = max(min_width, max_content + 15)
                    if abs(current_width - optimal) > 20:  # Büyük fark varsa güncelle
                        self.results_tree.column(col, width=optimal)
        except Exception:
            pass

    def _update_compute_button_state(self):
        """α (Spektrum Ölçekleme Katsayısı) girilmeden Hesapla pasif olsun."""
        try:
            alpha_txt = str(self.var_alpha.get()) if hasattr(self, 'var_alpha') else ""
            is_valid = True
            try:
                alpha_val = float(alpha_txt)
                # Geçerli sayı ve pozitif olmalı
                is_valid = np.isfinite(alpha_val) and (alpha_val > 0)
            except Exception:
                is_valid = False
            state = "normal" if is_valid else "disabled"
            if hasattr(self, '_btn_compute') and self._btn_compute:
                self._btn_compute.configure(state=state)
        except Exception:
            pass

    def _reset_column_widths(self):
        """Sütun genişliklerini varsayılan değerlere sıfırlar"""
        try:
            for col in self._results_columns:
                config = self._column_configs.get(col, {})
                default_width = config.get("width", 100)
                self.results_tree.column(col, width=default_width)
        except Exception:
            pass

    def _expand_all_columns(self):
        """Tüm sütunları genişletir"""
        try:
            for col in self._results_columns:
                current_width = self.results_tree.column(col, "width")
                new_width = min(current_width * 1.2, 400)
                self.results_tree.column(col, width=int(new_width))
        except Exception:
            pass

    def _compress_all_columns(self):
        """Tüm sütunları daraltır"""
        try:
            for col in self._results_columns:
                config = self._column_configs.get(col, {})
                current_width = self.results_tree.column(col, "width")
                min_width = config.get("minwidth", 50)
                new_width = max(current_width * 0.8, min_width)
                self.results_tree.column(col, width=int(new_width))
        except Exception:
            pass

    def _toggle_peer_panel(self):
        try:
            mode_label = self.var_scale_mode.get()
            is_peer = bool(mode_label and str(mode_label).startswith("PEER"))
            is_tbdy = (mode_label == "TBDY-2018 (3B Basit)")
            
            # PEER seçenekleri için metot dropdown'ını otomatik ayarla
            if mode_label == "PEER – No Scaling":
                self.var_peer_method.set("no_scaling")
            elif mode_label == "PEER – Minimize MSE":
                self.var_peer_method.set("min_mse")
            elif mode_label == "PEER – Single Period":
                self.var_peer_method.set("single_period")
            
            if is_peer:
                self.peer_frame.pack(fill="x", padx=8, pady=(0,8))
                self.tbdy_frame.pack_forget()
            elif is_tbdy:
                self.tbdy_frame.pack(fill="x", padx=8, pady=(0,8))
                self.peer_frame.pack_forget()
            else:
                self.peer_frame.pack_forget()
                self.tbdy_frame.pack_forget()
            # No Scaling modunda Gelişmiş alanını gizle; diğer modlarda göster
            try:
                if mode_label == "PEER – No Scaling":
                    if hasattr(self, 'adv_frame'):
                        self.adv_frame.pack_forget()
                else:
                    if hasattr(self, 'adv_frame'):
                        # Zaten packed ise yeniden pack etmeye gerek yok; güvenli çağrı
                        self.adv_frame.pack(fill="x", padx=8, pady=(0,8))
            except Exception:
                pass
            self._toggle_peer_method_fields()
            # Enforce buton durumunu güncelle
            self._update_enforce_state()
        except Exception:
            pass

    def _apply_global_ordinate(self):
        """Üstteki 'Bileşke Spektrum' seçiminin PEER bileşke combobox'ına yansıması."""
        try:
            ord_sel = (self.var_global_ordinate.get() or "SRSS").strip().upper()
            # TBDY modunda sadece SRSS; PEER modunda combobox'a yansıt
            mode_label = self.var_scale_mode.get()
            if mode_label == "TBDY-2018 (3B Basit)":
                try:
                    self.var_global_ordinate.set("SRSS")
                except Exception:
                    pass
                return
            # PEER ise combobox'ı güncelle
            try:
                if ord_sel in ("SRSS", "GM"):
                    self.var_peer_ordinate.set(ord_sel)
                    if hasattr(self, 'ordinate_combo'):
                        vals = ("SRSS", "GM")
                        try:
                            self.ordinate_combo['values'] = vals
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass

    def _update_enforce_state(self):
        try:
            self.var_peer_enforce.set(True)
        except Exception:
            pass

    def _toggle_peer_method_fields(self):
        try:
            method = self.var_peer_method.get()
            use_custom = bool(self.var_peer_use_custom_weights.get())

            state_weights = "normal" if use_custom else "disabled"
            self.entry_peer_period_knots.configure(state=state_weights)
            self.entry_peer_weight_knots.configure(state=state_weights)

            # Single Period alanı sadece single_period yönteminde aktif
            if method == "single_period":
                self.entry_peer_single_period.configure(state="normal")
            else:
                self.entry_peer_single_period.configure(state="disabled")
                self.var_peer_single_period.set("")

            # No Scaling'de factor limit alanlarını devre dışı bırak
            limits_state = "disabled" if method == "no_scaling" else "normal"
            try:
                self.entry_peer_limit_min.configure(state=limits_state)
                self.entry_peer_limit_max.configure(state=limits_state)
            except Exception:
                pass
        except Exception:
            pass

    def _toggle_peer_weights(self):
        self._toggle_peer_method_fields()

    def refresh_pair_count(self):
        try:
            n = len(self.records_provider() or [])
            self.lbl_pairs.configure(text=f"Kayıt çifti: {n}")
            # Enforce buton durumunu güncelle
            self._update_enforce_state()
        except Exception:
            self.lbl_pairs.configure(text="Kayıt çifti: ?")

    
    def _on_compute(self):
        try:
            records = list(self.records_provider() or [])
            self.refresh_pair_count()
            if len(records) == 0:
                messagebox.showwarning("Uyarı", "En az bir kayıt çifti gerekli. Lütfen iki yatay bileşen içeren kayıtları yükleyin.")
                return
            # TBDY-2018 kural kontrolleri: M>=11 ve ≤3/event
            # 11 kayıt kuralı uyarıya dönüştürüldü, ≤3/event kuralı hala zorunlu
            n = len(records)
            allow_below_11 = True  # Varsayılan olarak izin ver
            
            if n < MIN_RECORD_COUNT:
                msg = (
                    f"Kayıt sayısı uyarısı: {n} < {MIN_RECORD_COUNT}\n\n"
                    f"TBDY-2018 Madde 2.5.1.3'e göre 3B analiz için:\n"
                    f"• En az {MIN_RECORD_COUNT} kayıt takımı önerilir\n"
                    f"• Daha az kayıtla hesaplama yapılabilir ancak sonuçlar güvenilir olmayabilir\n\n"
                    f"Bu uyarıyı kabul edip hesaplamaya devam etmek istiyor musunuz?"
                )
                if not messagebox.askyesno("TBDY-2018 Uyarısı", msg, icon="warning"):
                    return
                allow_below_11 = True
            
            try:
                # ≤3/event kuralı hala zorunlu, 11 kayıt kuralı uyarı
                _validate_records(records, allow_below_11=allow_below_11)
            except Exception as ve:
                # Sadece ≤3/event ihlali için hata
                messagebox.showerror("TBDY-2018 Kural İhlali", str(ve))
                return
            Tp = float(self.var_Tp.get())
            # Model bağından değerleri al
            if self.dp is not None:
                try:
                    SDS = float(self.dp.sds_var.get())
                    SD1 = float(self.dp.sd1_var.get())
                    TL  = float(self.dp.tl_var.get())
                except Exception:
                    SDS = float(self.var_SDS.get())
                    SD1 = float(self.var_SD1.get())
                    TL  = float(self.var_TL.get())
            else:
                SDS = float(self.var_SDS.get())
                SD1 = float(self.var_SD1.get())
                TL  = float(self.var_TL.get())

            # T aralığı seçimi (No Scaling'de kullanılmaz)
            T_override = None
            if self.var_is_isolated.get():
                TM = float(self.var_TM.get()) if self.var_TM.get() else None
                if TM:
                    T_override = np.linspace(0.5*TM, 1.25*TM, 400)
            if self.var_use_envelope.get() and not self.var_is_isolated.get():
                if self.var_Tp_x.get() and self.var_Tp_y.get():
                    Tp_x = float(self.var_Tp_x.get()); Tp_y = float(self.var_Tp_y.get())
                    T_override = np.linspace(0.2*min(Tp_x,Tp_y), 1.5*max(Tp_x,Tp_y), 400)
            # No Scaling modunda T_override'ı kullanma
            try:
                if is_peer and self.var_peer_method.get() == "no_scaling":
                    T_override = None
            except Exception:
                pass

            accel_unit = self._get_accel_unit() if callable(self._get_accel_unit) else 'g'
            damping = float(self.var_damping.get() or 5.0)
            alpha = float(self.var_alpha.get() or 1.3)
            try:
                max_scale = float(self.var_max_scale.get()) if self.var_max_scale.get() else None
            except Exception:
                max_scale = None

            # Ölçekleme modu ve parametreler
            mode_label = self.var_scale_mode.get()
            is_peer = bool(mode_label and str(mode_label).startswith("PEER"))
            is_tbdy = (mode_label == "TBDY-2018 (3B Basit)")
            
            if is_tbdy:
                # TBDY-2018 modunu kullan
                try:
                    tbdy_result = scale_3d_simple_tbdy(
                        records=records,
                        T1=Tp,
                        SDS=SDS,
                        SD1=SD1,
                        TL=TL,
                        alpha=alpha,
                        damping=damping
                    )
                    
                    # Sonuçları eski ScaleResult formatına dönüştür
                    result = self._convert_tbdy_to_scale_result(tbdy_result, T_override, Tp)
                    self._last_tbdy_result = tbdy_result  # TBDY sonuçlarını sakla
                    
                except Exception as e:
                    messagebox.showerror("TBDY Hesaplama Hatası", f"TBDY-2018 ölçeklendirmesi başarısız:\n{e}")
                    return
                    
            else:
                # Mevcut PEER/tbdx_min modunu kullan
                scale_mode = "peer" if is_peer else "tbdx_min"
            peer_ppd = int(self.var_peer_ppd.get() or 100)
            tmin_txt = (self.var_peer_tmin.get() or "").strip()
            tmax_txt = (self.var_peer_tmax.get() or "").strip()
            peer_range = None
            try:
                if tmin_txt and tmax_txt:
                    peer_range = (float(tmin_txt), float(tmax_txt))
            except Exception:
                peer_range = None
            # <11 kayıt ise PEER modunda zorlamayı kapat (UI koruması)
            enforce_tbdx = bool(self.var_peer_enforce.get()) if is_peer else True
            try:
                max_global_scale = float(self.var_peer_max_global.get()) if (self.var_peer_max_global.get() and is_peer) else None
            except Exception:
                max_global_scale = None
            if is_peer and (max_global_scale is None):
                max_global_scale = 3.0

            peer_method = "min_mse"
            peer_period_knots = None
            peer_weight_knots = None
            peer_single_period = None
            peer_scale_limits = (None, None)

            if is_peer:
                peer_method = self.var_peer_method.get()
                if bool(self.var_peer_use_custom_weights.get()):
                    try:
                        peer_period_knots = [float(x.strip()) for x in self.var_peer_period_knots.get().split(',') if x.strip()]
                        peer_weight_knots = [float(x.strip()) for x in self.var_peer_weight_knots.get().split(',') if x.strip()]
                    except Exception:
                        messagebox.showerror("PEER Ağırlık Hatası", "Özel ağırlık düğümleri sayısal olarak parse edilemedi.")
                        return
                if peer_method == "single_period":
                    try:
                        peer_single_period = float(self.var_peer_single_period.get())
                    except Exception:
                        messagebox.showerror("PEER Single Period", "Single Period yöntemi için geçerli bir T_s değeri girin.")
                        return
                try:
                    fmin_txt = self.var_peer_limit_min.get().strip()
                    fmax_txt = self.var_peer_limit_max.get().strip()
                    fmin_val = float(fmin_txt) if fmin_txt else None
                    fmax_val = float(fmax_txt) if fmax_txt else None
                    peer_scale_limits = (fmin_val, fmax_val)
                except Exception:
                    messagebox.showerror("PEER Limit Hatası", "f_min / f_max değerleri sayısal olmalıdır.")
                    return

            if not is_tbdy:
                custom_weighting = "uniform"
                if peer_period_knots is not None and peer_weight_knots is not None:
                    custom_weighting = "custom_knots"
                result = basic_scaling_3d(
                    records, Tp=Tp, SDS=SDS, SD1=SD1, TL=TL, accel_unit=accel_unit,
                    T_override=T_override, damping_percent=damping,
                    alpha=alpha, use_record_based=bool(self.var_use_record_based.get()), max_scale=max_scale,
                    allow_below_11=allow_below_11,
                    scale_mode=scale_mode,
                    peer_points_per_decade=peer_ppd,
                    peer_weighting=custom_weighting,
                    peer_range=peer_range,
                    enforce_tbdx=enforce_tbdx,
                    max_global_scale=max_global_scale,
                    peer_method=peer_method,
                    peer_period_knots=peer_period_knots,
                    peer_weight_knots=peer_weight_knots,
                    peer_single_period=peer_single_period,
                    peer_scale_limits=peer_scale_limits,
                    peer_spectral_ordinate=str(self.var_peer_ordinate.get() or "srss"),
                )
            self._last_records = records
            self._last_result = result
            self.var_fmin.set(f"{result.f_min:.3f}")
            try:
                ratios = result.ratios
                rmin = float(np.min(ratios))
                self.var_min_ratio.set(f"{rmin:.3f}")
                # <1.0 durumunda uyarı rengi
                color = "red" if rmin < 1.0 else ("orange" if rmin < 1.02 else "green")
                try:
                    self.lbl_min_ratio.configure(foreground=color)
                except Exception:
                    pass
                # Durum şeridi
                try:
                    # No Scaling: Tp kullanılmaz; ağırlık aralığını yaz
                    peer_dbg = (getattr(result, 'peer_debug', {}) or {})
                    peer_meth = peer_dbg.get('method', '')
                    if getattr(result, 'mode', '') == 'peer' and peer_meth == 'no_scaling':
                        rng = peer_dbg.get('range', None)
                        if not rng:
                            try:
                                rng = (float(result.T[0]), float(result.T[-1]))
                            except Exception:
                                rng = (0.01, 10.0)
                    else:
                        rng = (T_override[0], T_override[-1]) if T_override is not None else (0.2*Tp, 1.5*Tp)
                    warn_tag = " (onaylandı)" if allow_below_11 else ""
                    status_text = f"Kayıt çifti: {len(records)}{warn_tag} | f_min: {result.f_min:.3f} | Min Oran: {rmin:.3f} | Aralık: [{rng[0]:.3f}, {rng[1]:.3f}]"
                    # PEER No-Scaling ise statüyü daha net yaz
                    try:
                        if getattr(result, 'mode', '') == 'peer':
                            meth = (getattr(result, 'peer_debug', {}) or {}).get('method', '')
                            if meth == 'no_scaling':
                                status_text = f"Kayıt çifti: {len(records)}{warn_tag} | No Scaling (f=1.0) | Min Oran: {rmin:.3f} | Aralık: [{rng[0]:.3f}, {rng[1]:.3f}]"
                    except Exception:
                        pass
                    self.var_status.set(status_text)
                except Exception:
                    pass
            except Exception:
                self.var_min_ratio.set("--")
            if self.ax is not None:
                self._draw_plot_curves(result, T_override, Tp)
                # PEER seçiliyse rmin ve T@rmin'i statüde göster
                try:
                    if getattr(result, 'mode', 'tbdx_min') == 'peer' and getattr(result, 'rmin', None) is not None:
                        self.var_status.set(self.var_status.get() + f" | rmin: {float(result.rmin):.3f} @ T={float(result.t_at_rmin):.3f}s")
                        # Tavan sınırlaması bilgisi
                        try:
                            if bool(getattr(result, 'global_capped', False)):
                                self.var_status.set(self.var_status.get() + " | z tavanla sınırlandı")
                                # Eğer tavan nedeniyle şart sağlanmadıysa kullanıcıyı uyar
                                try:
                                    if float(result.rmin) < 1.0 and bool(enforce_tbdx):
                                        messagebox.showwarning(
                                            "TBDY Koşulu Sağlanamadı",
                                            "Global ölçek tavanı nedeniyle [0.2·T_p, 1.5·T_p] aralığında 1.3×S_tas(T) koşulu sağlanamadı.\n\n"
                                            "Lütfen kayıt sayısını artırın veya farklı kayıtlar seçin, ya da daha yüksek bir tavan deneyin.")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    # Metot rozeti
                    try:
                        badge = ""
                        mode_label = self.var_scale_mode.get()
                        if mode_label.startswith("PEER"):
                            # PEER: yöntem ayrımı
                            meth = (getattr(result, 'peer_debug', {}) or {}).get('method', '')
                            ordn = str(((getattr(result, 'peer_debug', {}) or {}).get('spectral_ordinate', 'srss'))).upper()
                            if meth == 'single_period':
                                badge = f"PEER: {ordn}@Single(T_s)"
                            elif meth == 'min_mse':
                                badge = f"PEER: {ordn}@MSE"
                            else:
                                # no_scaling veya bilinmeyen
                                badge = f"PEER: {ordn}@NoScaling"
                        else:
                            badge = "TBDY: SRSS@Mean"
                        if hasattr(self, '_method_badge'):
                            self._method_badge.set(badge)
                    except Exception:
                        pass
                except Exception:
                    pass
                try:
                    if T_override is not None and len(T_override) > 1:
                        tmin, tmax = float(T_override[0]), float(T_override[-1])
                    else:
                        tmin, tmax = 0.2*Tp, 1.5*Tp
                    self.ax.axvspan(tmin, tmax, alpha=0.12, color="#7cb342")
                    self.ax.axvline(tmin, ls="--", color="#558b2f")
                    self.ax.axvline(tmax, ls="--", color="#558b2f")
                    self.ax.margins(x=0.02, y=0.10)
                    # y_scaled bu scope'ta tanımlı değil; y_max'ı result içinden hesapla
                    y_mean_for_ylim = getattr(result, 'S_suite_mean', None)
                    if y_mean_for_ylim is None or np.size(y_mean_for_ylim) == 0:
                        y_mean_for_ylim = result.ratios * np.maximum(result.S_target, 1e-12)
                    y_max = float(np.nanmax([np.max(y_mean_for_ylim), np.max(result.S_target)]))
                    if y_max > 0:
                        self.ax.set_ylim(0, 1.1*y_max)
                except Exception:
                    pass
                self.ax.legend()
                self.canvas.draw_idle()
            # Sonuç tablosunu doldur
            try:
                try:
                    Teval = float(self.var_Teval.get()) if (self.var_Teval.get() or "").strip() else float(Tp)
                except Exception:
                    Teval = float(Tp)
                self._populate_results_table(records, result, Tp, Teval, accel_unit, damping)
            except Exception as e:
                # Tablo doldurma hatası arayüzü bozmasın
                print(f"Tablo doldurma hatası: {e}")  # Console'da göster
                pass
        except Exception as e:
            messagebox.showerror("Hata", f"Ölçeklendirme hesaplanamadı:\n{e}")

    def _draw_plot_curves(self, result, T_override, Tp):
        try:
            self.ax.clear()
            self.ax.grid(True, which="both", linestyle=":")
            eps = 1e-12
            y_mean = np.asarray(getattr(result, 'S_suite_mean', None))
            y_std = np.asarray(getattr(result, 'S_suite_std', None)) if getattr(result, 'S_suite_std', None) is not None else None
            if y_mean is None or y_mean.size == 0:
                y_mean = result.ratios * np.maximum(result.S_target, eps)
            # Katman kontrolleri
            show_suite = bool(getattr(self, '_show_suite', None).get()) if hasattr(self, '_show_suite') else True
            show_stdev = bool(getattr(self, '_show_stdev', None).get()) if hasattr(self, '_show_stdev') else True
            show_target = bool(getattr(self, '_show_target', None).get()) if hasattr(self, '_show_target') else True
            if show_suite:
                suite_label = "Suite Mean (ölçekli)"
                try:
                    if getattr(result, 'mode', '') == 'peer':
                        meth = (getattr(result, 'peer_debug', {}) or {}).get('method', '')
                        if meth == 'no_scaling':
                            z = float(getattr(result, 'global_factor', 1.0) or 1.0)
                            suite_label = "Suite Mean (γ‑ölçekli)" if abs(z - 1.0) > 1e-6 else "Suite Mean (unscaled)"
                except Exception:
                    pass
                self.ax.plot(result.T, y_mean, label=suite_label, linewidth=2.5)
            if show_stdev and (y_std is not None) and (y_std.size == y_mean.size):
                # Ln-uzayda ±1σ bant (PGMD uyumlu görselleme)
                try:
                    mu_ln = np.log(np.maximum(y_mean, eps))
                    sig_ln = np.log(np.maximum(y_std + eps, eps)) * 0.0  # std doğrudan verilmişse çizim için lineer bandı kullan
                except Exception:
                    mu_ln, sig_ln = None, None
                # Mevcut std zaten ölçekli ortalamanın std'si olduğundan lineer bant çiz
                y_upper = y_mean + y_std
                y_lower = np.clip(y_mean - y_std, 0.0, None)
                try:
                    self.ax.fill_between(result.T, y_lower, y_upper, color="#90caf9", alpha=0.35, label="±1σ")
                except Exception:
                    pass
            if show_target:
                self.ax.plot(result.T, result.S_target, label="1.3 × S_tas(T)", linestyle="--")
            # Band vurgusu
            try:
                # PEER No Scaling: ağırlık aralığını gölgele
                dbg = getattr(result, 'peer_debug', {}) or {}
                meth = (dbg.get('method', '') or '').lower()
                if getattr(result, 'mode', '') == 'peer' and meth == 'no_scaling':
                    rng = dbg.get('range', None)
                    if rng and len(rng) == 2:
                        tmin, tmax = float(rng[0]), float(rng[1])
                    else:
                        tmin, tmax = 0.01, 10.0
                else:
                    if T_override is not None and len(T_override) > 1:
                        tmin, tmax = float(T_override[0]), float(T_override[-1])
                    else:
                        tmin, tmax = 0.2*Tp, 1.5*Tp
                self.ax.axvspan(tmin, tmax, alpha=0.12, color="#7cb342")
                self.ax.axvline(tmin, ls="--", color="#558b2f")
                self.ax.axvline(tmax, ls="--", color="#558b2f")
            except Exception:
                pass
            # Eksen modu
            try:
                mode = (self._axis_mode.get() if hasattr(self, '_axis_mode') else "Linear")
                if mode == "Loglog":
                    self.ax.set_xscale('log')
                    self.ax.set_yscale('log')
                else:
                    self.ax.set_xscale('linear')
                    self.ax.set_yscale('linear')
            except Exception:
                pass
            # Y limitleri
            try:
                y_max = float(np.nanmax([np.max(y_mean), np.max(result.S_target)]))
                if y_max > 0:
                    self.ax.set_ylim(0, 1.1*y_max)
            except Exception:
                pass
            self.ax.legend()
            self.canvas.draw_idle()
        except Exception:
            pass

    def _redraw_plot(self):
        try:
            if self._last_result is None:
                return
            # T_override bilgisini yeniden oluştur
            Tp = float(self.var_Tp.get())
            T_override = None
            if self.var_is_isolated.get():
                TM = float(self.var_TM.get()) if self.var_TM.get() else None
                if TM:
                    T_override = np.linspace(0.5*TM, 1.25*TM, 400)
            if self.var_use_envelope.get() and not self.var_is_isolated.get():
                if self.var_Tp_x.get() and self.var_Tp_y.get():
                    Tp_x = float(self.var_Tp_x.get()); Tp_y = float(self.var_Tp_y.get())
                    T_override = np.linspace(0.2*min(Tp_x,Tp_y), 1.5*max(Tp_x,Tp_y), 400)
            self._draw_plot_curves(self._last_result, T_override, Tp)
        except Exception:
            pass

    def _on_clear(self):
        try:
            self._last_records = None
            self._last_result = None
            self.var_fmin.set("--")
            self.var_min_ratio.set("--")
            try:
                self.lbl_min_ratio.configure(foreground="")
            except Exception:
                pass
            try:
                self.var_status.set("Kayıt çifti: 0 | f_min: -- | Min Oran: -- | Aralık: --")
            except Exception:
                pass
            if self.ax is not None:
                self.ax.clear()
                self.ax.grid(True, which="both", linestyle=":")
                self.canvas.draw_idle()
            # Sonuç tablosunu temizle
            try:
                for item in self.results_tree.get_children():
                    self.results_tree.delete(item)
                self._results_full_rows = []
                self.var_search.set("")
            except Exception:
                pass
        except Exception:
            pass

    def _open_pair_dialog(self):
        try:
            dlg = PairingDialog(self.frame, getattr(self, 'pair_manager', None) or getattr(self, 'pm', None))
            self.frame.wait_window(dlg)
            # Diyalog kapanınca kayıt çiftini yeniden say
            try:
                pairs = self.records_provider() or []
                self.lbl_pairs.configure(text=f"Kayıt çifti: {len(pairs)}")
                # durum satırını da sıfırla
                self.var_status.set(f"Kayıt çifti: {len(pairs)} | f_min: -- | Min Oran: -- | Aralık: --")
            except Exception:
                pass
        except Exception:
            messagebox.showerror("Hata", "Eşleştirme penceresi açılamadı.")


    def _on_export(self):
        try:
            if not self._last_records or not self._last_result:
                messagebox.showwarning("Önce Hesaplayın", "Önce 'Hesapla' ile ölçek faktörünü bulun.")
                return
                
            # TBDY modu için özel CSV dışa aktarma
            mode_label = self.var_scale_mode.get()
            if mode_label == "TBDY-2018 (3B Basit)" and hasattr(self, '_last_tbdy_result'):
                self._export_tbdy_csv()
                return
            import os
            from tkinter import filedialog
            save_dir = filedialog.askdirectory(title="Ölçekli kayıtları kaydet (klasör seçin)")
            if not save_dir:
                return
            # Kayıt-bazlı ise per-record faktörleri uygula, değilse tümüne f_min
            factors = list(getattr(self._last_result, 'per_record_factors', []) or [])
            has_per_record = len(factors) == len(self._last_records) and len(factors) > 0
            fmin = float(self._last_result.f_min)
            for idx, (ax, ay, dt, meta) in enumerate(self._last_records, start=1):
                f_use = float(factors[idx-1]) if has_per_record else fmin
                t = np.arange(len(ax)) * dt
                ax_s = f_use * np.asarray(ax, dtype=float)
                ay_s = f_use * np.asarray(ay, dtype=float)
                # Opsiyonel düşey bileşen (aynı ölçek katsayısı ile)
                az = None
                try:
                    if isinstance(meta, dict) and ('az' in meta):
                        az_arr = np.asarray(meta.get('az'), dtype=float)
                        if az_arr.size == ax_s.size:
                            az = f_use * az_arr
                except Exception:
                    az = None
                pair_name = (meta or {}).get('pair_name', f"pair_{idx}")
                base = re.sub(r'[^A-Za-z0-9_\\-]+', '_', pair_name)
                file_path = os.path.join(save_dir, f"{base}_scaled_{f_use:.3f}.csv")
                try:
                    import pandas as pd
                    data_dict = {'time_s': t, 'ax_scaled': ax_s, 'ay_scaled': ay_s}
                    if az is not None:
                        data_dict['az_scaled'] = az
                    df = pd.DataFrame(data_dict)
                    df.to_csv(file_path, index=False)
                except Exception:
                    # Pandas yoksa basit yaz
                    with open(file_path, 'w', encoding='utf-8') as f:
                        if az is not None:
                            f.write("time_s,ax_scaled,ay_scaled,az_scaled\n")
                            for i in range(len(t)):
                                f.write(f"{t[i]:.6f},{ax_s[i]:.8f},{ay_s[i]:.8f},{az[i]:.8f}\n")
                        else:
                            f.write("time_s,ax_scaled,ay_scaled\n")
                            for i in range(len(t)):
                                f.write(f"{t[i]:.6f},{ax_s[i]:.8f},{ay_s[i]:.8f}\n")
            if has_per_record:
                messagebox.showinfo("Tamamlandı", "Ölçekli kayıtlar (kayıt-bazlı faktörlerle) kaydedildi.")
            else:
                messagebox.showinfo("Tamamlandı", f"Ölçekli kayıtlar kaydedildi. f_min={fmin:.3f}")
        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarma başarısız:\n{e}")

    # ───────────────────────────────────────────────────────────
    # Sonuç Tablosu Yardımcıları (PGMD uyumlu sütun başlıkları)
    # ───────────────────────────────────────────────────────────
    def _extract_meta_value(self, meta: Dict, keys: List[str], default=None):
        try:
            if not isinstance(meta, dict):
                return default
            for k in keys:
                if k in meta and meta[k] is not None:
                    return meta[k]
        except Exception:
            pass
        return default

    def _populate_results_table(self, records, result, Tp: float, Teval: float, accel_unit: str, damping_percent: float):
        # Ham satırları hazırla ve metrikleri hesapla
        rows = []
        per_record = list(getattr(result, 'per_record_factors', []) or [])
        has_per = (len(per_record) == len(records) and len(records) > 0)
        T_ctx = np.asarray(getattr(result, 'T', []), dtype=float)
        target_ctx = np.asarray(getattr(result, 'S_target', []), dtype=float)
        eps = 1e-12
        try:
            idx_eval = int(np.argmin(np.abs(T_ctx - float(Teval)))) if T_ctx.size > 0 else 0
        except Exception:
            idx_eval = 0

        def _interp_safe(src_T: np.ndarray, src_S: np.ndarray, tgt_T: np.ndarray) -> np.ndarray:
            """Log(T)-ln(SA) uzayında güvenli interpolasyon (PGMD uyumlu)."""
            eps = 1e-15
            order = np.argsort(np.asarray(src_T))
            x = np.asarray(src_T, dtype=float)[order]
            y = np.asarray(src_S, dtype=float)[order]
            xi = np.asarray(tgt_T, dtype=float)
            xlog = np.log(np.maximum(x, eps))
            ylog = np.log(np.maximum(y, eps))
            xilog = np.log(np.maximum(xi, eps))
            yi = np.interp(xilog, xlog, ylog, left=ylog[0], right=ylog[-1])
            return np.exp(yi)

        lo, hi = 0.2*float(Tp), 1.5*float(Tp)
        mask_ctx = (T_ctx >= lo) & (T_ctx <= hi) if T_ctx.size > 0 else slice(None)
        def _mse_log(target_arr: np.ndarray, record_arr: np.ndarray) -> float:
            ta = np.maximum(np.asarray(target_arr)[mask_ctx], eps)
            ra = np.maximum(np.asarray(record_arr)[mask_ctx], eps)
            if ta.size == 0 or ra.size == 0:
                return float('nan')
            r = np.log(ta) - np.log(ra)
            return float(np.mean(r*r))

        def _mse_log_weighted(target_arr: np.ndarray, record_arr: np.ndarray, weights_arr: np.ndarray) -> float:
            ta = np.maximum(np.asarray(target_arr), eps)
            ra = np.maximum(np.asarray(record_arr), eps)
            w = np.asarray(weights_arr, dtype=float)
            if ta.size == 0 or ra.size == 0 or w.size != ta.size:
                return float('nan')
            if np.sum(w) <= 0:
                return float('nan')
            r = np.log(ta) - np.log(ra)
            return float(np.sum(w * r*r) / float(np.sum(w)))

        from ...calculations.response_spectrum import compute_elastic_response_spectrum, SpectrumSettings
        settings = SpectrumSettings(
            damping_list=(float(damping_percent),),
            Tmin=float(T_ctx.min() if T_ctx.size > 0 else 0.01),
            Tmax=float(T_ctx.max() if T_ctx.size > 0 else 5.0),
            nT=max(int(T_ctx.size), 256),
            logspace=True,
            accel_unit=accel_unit,
            baseline="linear",
        )
        try:
            from ...calculations.earthquake_stats import EarthquakeStats
        except Exception:
            EarthquakeStats = None

        for idx, (ax, ay, dt, meta) in enumerate(records, start=1):
            f_use = float(per_record[idx-1]) if has_per else float(result.f_min)
            record_seq = self._extract_meta_value(meta, [
                'record_seq', 'nga_no', 'id', 'record_id', 'seq', 'index'
            ], default=idx)
            
            # Grup adını meta verilerden al
            group_name = self._extract_meta_value(meta, [
                'event_id', 'group_id', 'pair_name', 'name', 'group_name'
            ], default=f"Grup_{idx}")
            
            h1 = self._extract_meta_value(meta, ['h1', 'file_x', 'ax_file', 'file1', 'fname_x', 'filename_x'], default="")
            h2 = self._extract_meta_value(meta, ['h2', 'file_y', 'ay_file', 'file2', 'fname_y', 'filename_y'], default="")
            v  = self._extract_meta_value(meta, ['v', 'file_z', 'az_file', 'file3', 'fname_z', 'filename_z'], default="")

            try:
                time = np.arange(len(ax), dtype=float) * float(dt)
                sX = compute_elastic_response_spectrum(time, np.asarray(ax, dtype=float), settings)
                curvesX = next(iter(sX.values()))
                sY = compute_elastic_response_spectrum(time, np.asarray(ay, dtype=float), settings)
                curvesY = next(iter(sY.values()))
                SaX_ctx = _interp_safe(curvesX.T, curvesX.Sa_p_g, T_ctx) if T_ctx.size > 0 else np.asarray(curvesX.Sa_p_g)
                SaY_ctx = _interp_safe(curvesY.T, curvesY.Sa_p_g, T_ctx) if T_ctx.size > 0 else np.asarray(curvesY.Sa_p_g)
                SRSS_ctx = np.sqrt(np.maximum(SaX_ctx, 0.0)**2 + np.maximum(SaY_ctx, 0.0)**2)
                GM_ctx = np.sqrt(np.maximum(SaX_ctx, eps) * np.maximum(SaY_ctx, eps))
            except Exception:
                SRSS_ctx = np.zeros_like(T_ctx)
                GM_ctx = np.zeros_like(T_ctx)

            try:
                sa_eval_g = float(f_use * SRSS_ctx[idx_eval]) if SRSS_ctx.size > 0 else float('nan')
            except Exception:
                sa_eval_g = float('nan')

            try:
                # PEER sonuçları için: seçilen bileşkeye ve PEER ağırlıklarına göre MSE (ln-uzayı)
                spec_sel = str(((getattr(result, 'peer_debug', {}) or {}).get('spectral_ordinate', 'srss'))).lower()
                comp_ctx = GM_ctx if spec_sel == 'gm' else SRSS_ctx
                if getattr(result, 'mode', '') == 'peer':
                    dbg = getattr(result, 'peer_debug', {}) or {}
                    T_peer = np.asarray(dbg.get('T_peer', []), dtype=float)
                    W_peer = np.asarray(dbg.get('weights_peer', []), dtype=float)
                    if T_ctx.size > 0 and T_peer.size > 0 and W_peer.size == T_peer.size:
                        # Ağırlıkları log(T) ekseninde T_ctx'e enterpole et ve LUF maskesi uygula
                        try:
                            xsrc = np.log(np.maximum(T_peer, eps))
                            xdst = np.log(np.maximum(T_ctx, eps))
                            w_ctx = np.interp(xdst, xsrc, W_peer, left=0.0, right=0.0)
                            # Lowest Useable Frequency (Hz) → T_max_use = 1/LUF
                            luf_keys = (
                                'lowest_useable_frequency', 'lowest_usable_frequency', 'luf',
                                'low_useable_frequency', 'low_usable_frequency', 'min_freq', 'fmin'
                            )
                            luf_val = None
                            try:
                                for k in luf_keys:
                                    if isinstance(meta, dict) and (k in meta) and meta[k] is not None:
                                        luf_val = float(meta[k])
                                        break
                            except Exception:
                                luf_val = None
                            if luf_val is not None and np.isfinite(luf_val) and (luf_val > 0):
                                try:
                                    T_max_use = float(1.0 / luf_val)
                                    w_ctx = np.where(T_ctx <= T_max_use, w_ctx, 0.0)
                                except Exception:
                                    pass
                            s = float(np.sum(w_ctx))
                            w_ctx = (w_ctx / s) if s > 0 else None
                        except Exception:
                            w_ctx = None
                        if w_ctx is not None:
                            mse_val = _mse_log_weighted(target_ctx, f_use * comp_ctx, w_ctx)
                        else:
                            # Ağırlık enterpolasyonu başarısızsa tüm T üzerinde ağırlıksız hesapla
                            mse_val = float(np.mean((np.log(np.maximum(target_ctx, eps)) - np.log(np.maximum(f_use * comp_ctx, eps)))**2))
                    else:
                        mse_val = float(np.mean((np.log(np.maximum(target_ctx, eps)) - np.log(np.maximum(f_use * comp_ctx, eps)))**2))
                else:
                    # TBDY ve diğer modlar için: mevcut band maskesi ile (SRSS)
                    mse_val = _mse_log(target_ctx, f_use * SRSS_ctx)
            except Exception:
                mse_val = float('nan')

            ia_val = ""
            d575_val = ""
            d595_val = ""
            if EarthquakeStats is not None:
                try:
                    ia = EarthquakeStats.calculate_arias_intensity(np.asarray(ax, dtype=float), float(dt), unit=accel_unit).to_dict().get('arias_intensity', None)
                    if ia is not None and np.isfinite(ia):
                        ia_val = float(ia)
                except Exception:
                    pass
                # D5-75 / D5-95: iki yatay bileşen üzerinden birleşik Husid ile hesapla
                try:
                    ax_arr = np.asarray(ax, dtype=float)
                    ay_arr = np.asarray(ay, dtype=float)
                    # LUF (Hz) oku (varsa) ve PEER çağrılarına aktar
                    luf_val = None
                    for k in ('lowest_useable_frequency','lowest_usable_frequency','luf','low_useable_frequency','low_usable_frequency','min_freq','fmin'):
                        try:
                            if isinstance(meta, dict) and (k in meta) and meta[k] is not None:
                                luf_val = float(meta[k]); break
                        except Exception:
                            pass
                    # PEER arama çıktılarıyla uyum için süre metriklerinde LUF uygulanmaz
                    d95 = EarthquakeStats.calculate_d5_95_peer(ax_arr, ay_arr, float(dt), unit=accel_unit)
                    if d95 is not None and np.isfinite(getattr(d95, 'duration', np.nan)):
                        d595_val = float(d95.duration)
                    # D5-75 (PEER uyumlu tek çağrı)
                    d575_obj = EarthquakeStats.calculate_d5_75_peer(ax_arr, ay_arr, float(dt), unit=accel_unit)
                    if d575_obj is not None and np.isfinite(getattr(d575_obj, 'duration', np.nan)):
                        d575_val = float(d575_obj.duration)
                except Exception:
                    # Geriye uyumluluk: tek bileşen (ax) üzerinden hesapla
                    try:
                        dur_575 = EarthquakeStats.calculate_significant_duration(np.asarray(ax, dtype=float), float(dt), 5.0, 75.0, unit=accel_unit).to_dict()
                        if dur_575 and np.isfinite(dur_575.get('duration', np.nan)):
                            d575_val = float(dur_575.get('duration'))
                    except Exception:
                        pass
                    try:
                        d95_fallback = EarthquakeStats.calculate_significant_duration(np.asarray(ax, dtype=float), float(dt), 5.0, 95.0, unit=accel_unit).to_dict()
                        if d95_fallback and np.isfinite(d95_fallback.get('duration', np.nan)):
                            d595_val = float(d95_fallback.get('duration'))
                    except Exception:
                        pass

            try:
                # Suite bilgileri: PEER veya TBDY moduna göre doldur
                mode = getattr(result, 'mode', '')
                if mode == 'peer':
                    gamma_suite = getattr(result, 'global_factor', 1.0)
                    rmin_val = getattr(result, 'rmin', None)
                    t_at_rmin = getattr(result, 't_at_rmin', None)
                    # No Scaling için Tp tabanlı alanlar N/A
                    meth = str(((getattr(result, 'peer_debug', {}) or {}).get('method', ''))).lower()
                    if meth == 'no_scaling':
                        min_ratio_at_T = "N/A"
                        pass_3d_flag = "N/A"
                    else:
                        min_ratio_at_T = f"{float(rmin_val):.3f}@{float(t_at_rmin):.3f}s" if (rmin_val is not None and t_at_rmin is not None) else ""
                        pass_3d_flag = ""
                    method_label = (getattr(result, 'peer_debug', {}) or {}).get('method', self.var_peer_method.get())
                else:
                    gamma_suite = getattr(self, '_last_tbdy_result', None).global_gamma if hasattr(self, '_last_tbdy_result') else 1.0
                    rmin_val = getattr(self, '_last_tbdy_result', None).min_ratio if hasattr(self, '_last_tbdy_result') else None
                    # TBDY'de T@rmin GUI'de zaten band vurgusundan okunabiliyor; uygun değilse boş bırak
                    min_ratio_at_T = f"{float(rmin_val):.3f}" if (rmin_val is not None) else ""
                    pass_3d_flag = ("GEÇTİ" if getattr(self, '_last_tbdy_result', None) and getattr(self._last_tbdy_result, 'pass_tbdy', False) else ("KALDI" if hasattr(self, '_last_tbdy_result') else ""))
                    method_label = "tbdy_3d"
            except Exception:
                gamma_suite = 1.0
                min_ratio_at_T = ""
                pass_3d_flag = ""
                method_label = self.var_peer_method.get()

            # Arias görüntüleme: 1 ondalık (yuvarlanmış)
            ia_display = f"{ia_val:.1f}" if isinstance(ia_val, (int, float)) and np.isfinite(ia_val) else ""
            # D5-95 görüntüleme: 1 ondalık (yuvarlanmış)
            d595_display = f"{d595_val:.1f}" if isinstance(d595_val, (int, float)) and np.isfinite(d595_val) else ""
            # D5-75 görüntüleme: 1 ondalık (yuvarlanmış)
            d575_display = f"{d575_val:.1f}" if isinstance(d575_val, (int, float)) and np.isfinite(d575_val) else ""

            row = {
                "No": record_seq,
                "Grup Adı": str(group_name),
                "Ölçek Katsayısı": f_use,
                "MSE": mse_val,
                "D5-75 (s)": d575_display,
                "D5-95 (s)": d595_display,
                "Arias Şiddeti (m/s)": ia_display,
                "Metot": method_label,
                "γ (suite)": gamma_suite,
                "min_ratio@T": min_ratio_at_T,
                "pass_3D": pass_3d_flag,
            }
            rows.append(row)
        self._set_results_table_rows(rows)

    def _set_results_table_rows(self, rows: List[Dict]):
        # Sakla ve UI'ı güncelle
        self._results_full_rows = list(rows or [])
        # Treeview temizle
        try:
            for item in self.results_tree.get_children():
                self.results_tree.delete(item)
        except Exception:
            pass
        # Ekle
        for r in (rows or []):
            values = [r.get(col, "") for col in self._results_columns]
            try:
                self.results_tree.insert("", "end", values=values)
            except Exception:
                pass
        
        # Veriler eklendikten sonra otomatik sütun genişliği ayarlama
        self.results_tree.after_idle(self._auto_resize_columns)

    def _filter_results_table(self):
        text = (self.var_search.get() or "").strip().lower()
        if not text:
            self._set_results_table_rows(self._results_full_rows)
            return
        filtered = []
        for r in self._results_full_rows:
            try:
                combined = " ".join(str(r.get(k, "")) for k in self._results_columns).lower()
            except Exception:
                combined = ""
            if text in combined:
                filtered.append(r)
        self._set_results_table_rows(filtered)

    def _export_results_table_csv(self):
        try:
            from tkinter import filedialog
            import csv
            if not self._results_full_rows:
                messagebox.showwarning("Uyarı", "Dışa aktarılacak satır bulunamadı.")
                return
            path = filedialog.asksaveasfilename(title="CSV'ye Dışa Aktar",
                                                defaultextension=".csv",
                                                filetypes=[("CSV", "*.csv"), ("Tüm Dosyalar", "*.*")])
            if not path:
                return
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self._results_columns)
                for r in self._results_full_rows:
                    writer.writerow([r.get(col, "") for col in self._results_columns])
            messagebox.showinfo("Tamamlandı", f"Sonuç tablosu dışa aktarıldı:\n{path}")
        except Exception as e:
            messagebox.showerror("Hata", f"CSV dışa aktarma başarısız:\n{e}")
    
    def _convert_tbdy_to_scale_result(self, tbdy_result, T_override, Tp):
        """TBDY sonuçlarını eski ScaleResult formatına dönüştürür."""
        from ...calculations.basic_scaling import ScaleResult
        
        # Ortalama ölçek katsayısı
        f_min = float(np.mean(tbdy_result.f_list)) if tbdy_result.f_list else 1.0
        
        # Ratios hesapla
        ratios = tbdy_result.srss_avg / np.maximum(tbdy_result.target_spectrum, 1e-12)
        
        # Uyumlu ScaleResult oluştur
        result = ScaleResult(
            f_min=f_min,
            T=tbdy_result.T_grid,
            S_avg=tbdy_result.srss_avg / tbdy_result.global_gamma,  # Ölçeklenmemiş ortalama
            S_target=tbdy_result.target_spectrum,
            ratios=ratios,
            per_record_factors=tbdy_result.f_list,
            mode="tbdy_3d",
            rmin=tbdy_result.min_ratio,
            t_at_rmin=None,  # TBDY sonucunda yok
            global_factor=tbdy_result.global_gamma,
            S_suite_mean=tbdy_result.srss_avg,
            S_suite_std=None,  # TBDY sonucunda yok
            global_capped=False,
            mode_note=f"TBDY-2018 3B Basit Ölçeklendirme (γ={tbdy_result.global_gamma:.3f})"
        )
        
        return result
    
    def _export_tbdy_csv(self):
        """TBDY-2018 sonuçlarını belirtilen şemaya göre CSV'ye aktarır."""
        try:
            from tkinter import filedialog
            
            # Dosya kaydetme diyalogu
            filename = filedialog.asksaveasfilename(
                title="TBDY-2018 Sonuçlarını Kaydet",
                defaultextension=".csv",
                filetypes=[("CSV dosyaları", "*.csv"), ("Tüm dosyalar", "*.*")],
                initialvalue="tbdy_3d_scaling_results.csv"
            )
            
            if not filename:
                return
            
            # Meta verileri hazırla
            records_meta = []
            for i, (ax, ay, dt, meta) in enumerate(self._last_records):
                meta_dict = {
                    "event_id": meta.get("event_id", f"Event_{i+1}"),
                    "station": meta.get("station", f"Station_{i+1}"),
                    "nga_number": meta.get("nga_number", f"NGA_{i+1:04d}")
                }
                records_meta.append(meta_dict)
            
            # CSV'ye aktar
            csv_path = export_tbdy_results_csv(self._last_tbdy_result, records_meta, filename)
            
            messagebox.showinfo(
                "TBDY Dışa Aktarma Tamamlandı", 
                f"TBDY-2018 sonuçları başarıyla kaydedildi:\n{csv_path}\n\n"
                f"Kayıt sayısı: {self._last_tbdy_result.n_records}\n"
                f"TBDY koşulu: {'GEÇTİ' if self._last_tbdy_result.pass_tbdy else 'KALDI'}\n"
                f"Global gamma: {self._last_tbdy_result.global_gamma:.6f}\n"
                f"Minimum oran: {self._last_tbdy_result.min_ratio:.6f}"
            )
            
        except Exception as e:
            messagebox.showerror("TBDY Dışa Aktarma Hatası", f"CSV dışa aktarma başarısız:\n{e}")
