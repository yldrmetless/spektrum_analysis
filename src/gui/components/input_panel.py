"""
Parametre giriş paneli bileşeni
"""

import tkinter as tk
from tkinter import ttk, font as tkfont
from tkinter import PhotoImage
from ...config.constants import (
    EARTHQUAKE_LEVELS, SOIL_CLASSES, DEFAULT_LOCATION,
    DEFAULT_EARTHQUAKE_LEVEL, DEFAULT_SOIL_CLASS
)
from ...utils.unit_converter import UnitConverter
from pathlib import Path
import sys
import customtkinter as ctk

# Sabit aralık: değer sütunu sol boşluğu (px)
VALUE_COLUMN_PAD = 8
class RoundedButton(tk.Canvas):
    def __init__(
        self, parent, text="", on_click=None,
        height=40, radius=10,
        btn_bg="#2F6FED", hover_bg="#255BD0",
        fg="white",
        font=None,  # ✅ default fontu kullanmak için None
        image=None, canvas_bg="#FFFFFF",
        border_color=None, border_width=0,
        **kwargs
    ):
        cmd = kwargs.pop("command", None)
        if on_click is None and callable(cmd):
            on_click = cmd

        super().__init__(
            parent,
            height=height,
            highlightthickness=0,
            bd=0,
            background=canvas_bg
        )

        self._on_click = on_click
        self._btn_bg = btn_bg
        self._hover_bg = hover_bg
        self._fg = fg
        self._radius = int(radius)
        self._text = text
        self._image = image
        self._current_bg = self._btn_bg
        self._disabled_bg = "#AFAFAF",
        self._state = "normal",

        # ✅ Font: verilmediyse TkDefaultFont (senin global Poppins)
        if font is None:
            try:
                self._font = tkfont.nametofont("TkDefaultFont")
            except Exception:
                self._font = None
        else:
            self._font = font

        self.bind("<Enter>", lambda e: self._set_bg(self._hover_bg) if self._state != "disabled" else None)
        self.bind("<Leave>", lambda e: self._set_bg(self._btn_bg) if self._state != "disabled" else None)
        self.bind("<Button-1>", lambda e: self._on_click() if callable(self._on_click) else None)
        self.bind("<Configure>", lambda e: self._draw(self._current_bg))

        self._draw(self._current_bg)

    def _set_bg(self, color):
        self._current_bg = color
        self._draw(self._current_bg)

    def configure(self, cnf=None, **kw):
        cmd = kw.pop("command", None)
        if callable(cmd):
            self._on_click = cmd

        state = kw.pop("state", None)
        if state is not None:
            self._state = state
            if state == "disabled":
                self._set_bg(self._disabled_bg)
            else:
                self._set_bg(self._btn_bg)

        return super().configure(cnf or {}, **kw)


    config = configure

    def _draw(self, color):
        self.delete("all")

        w = self.winfo_width()
        h = int(self["height"])
        if w <= 2:
            return

        r = min(self._radius, h // 2, w // 2)

        # ✅ Border yoksa eski davranış (outline=color, width=0 gibi)
        use_border = bool(getattr(self, "_border_color", None)) and int(getattr(self, "_border_width", 0)) > 0
        outline = self._border_color if use_border else color
        ow = int(self._border_width) if use_border else 0

        # rounded rect
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=color, outline=outline, width=ow)
        self.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, fill=color, outline=outline, width=ow)
        self.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, fill=color, outline=outline, width=ow)
        self.create_arc(0, h-r*2, r*2, h, start=180, extent=90, fill=color, outline=outline, width=ow)
        self.create_rectangle(r, 0, w-r, h, fill=color, outline=outline, width=ow)
        self.create_rectangle(0, r, w, h-r, fill=color, outline=outline, width=ow)

        cy = h // 2

        # ✅ metin genişliği ölç
        text_w = 0
        try:
            if self._font is not None:
                text_w = tkfont.Font(font=self._font).measure(self._text)
            else:
                text_w = tkfont.nametofont("TkDefaultFont").measure(self._text)
        except Exception:
            text_w = 0

        gap = 10  # ikon ile yazı arası boşluk

        if self._image:
            try:
                img_w = int(self._image.width())
            except Exception:
                img_w = 0

            group_w = img_w + (gap if text_w else 0) + text_w
            start_x = (w - group_w) // 2

            # ikon
            self.create_image(start_x + img_w // 2, cy, image=self._image)

            # yazı
            self.create_text(
                start_x + img_w + gap,
                cy,
                text=self._text,
                fill=self._fg,
                anchor="w",
                font=self._font
            )
        else:
            # sadece yazı: tam ortala
            self.create_text(
                w // 2,
                cy,
                text=self._text,
                fill=self._fg,
                font=self._font
            )

###################

class RoundedStatusBox(tk.Canvas):
    def __init__(
        self, parent,
        radius=8,
        bg="#FDECEC", border="#F5C2C7",
        fg="#B42318",
        font=None,
        icon_font=None,
        padx=10, pady=8,
        icon_text="!",
        textvariable=None,
        canvas_bg="#FFFFFF",
        **kwargs
    ):
        super().__init__(
            parent,
            highlightthickness=0,
            bd=0,
            background=canvas_bg,
            **kwargs
        )
        self.grid_propagate(False) 

        self._r = int(radius)
        self._bg = bg
        self._border = border
        self._fg = fg

        # Font default: sistemin TkDefaultFont'u (Poppins vs ne ayarladıysan onu kullanır)
        if font is None:
            try:
                font = tkfont.nametofont("TkDefaultFont")
            except Exception:
                font = ("TkDefaultFont", 9)
        if icon_font is None:
            try:
                base = tkfont.nametofont("TkDefaultFont").copy()
                base.configure(weight="bold")
                icon_font = base
            except Exception:
                icon_font = ("TkDefaultFont", 10, "bold")

        self._font = font
        self._icon_font = icon_font

        self._padx = int(padx)
        self._pady = int(pady)
        self._icon_text = icon_text
        self._textvariable = textvariable

        self.bind("<Configure>", self._on_configure)

        if self._textvariable is not None:
            try:
                self._textvariable.trace_add("write", lambda *a: self._redraw())
            except Exception:
                pass

        # İlk çizim
        self.after(0, self._redraw)

    def _on_configure(self, e=None):
        # her resize'ta redraw
        self._redraw()

    def set_style(self, *, bg=None, border=None, fg=None, icon_text=None):
        if bg is not None:
            self._bg = bg
        if border is not None:
            self._border = border
        if fg is not None:
            self._fg = fg
        if icon_text is not None:
            self._icon_text = icon_text
        self._redraw()

    def _rounded_rect(self, x1, y1, x2, y2, r, fill, outline):
        # Tek parça smooth polygon -> iç çizgi/seam yok
        points = [
            x1+r, y1,
            x2-r, y1,
            x2,   y1,
            x2,   y1+r,
            x2,   y2-r,
            x2,   y2,
            x2-r, y2,
            x1+r, y2,
            x1,   y2,
            x1,   y2-r,
            x1,   y1+r,
            x1,   y1
        ]
        self.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=fill,
            outline=outline,
            width=1
        )

    def _redraw(self):
        self.delete("all")

        w = self.winfo_width()
        h = self.winfo_height()

        if w <= 2 or h <= 2:
            if int(self.cget("height") or 0) < 30:
                self.configure(height=44)
            self.after(0, self._redraw)
            return

        r = min(self._r, h // 2, w // 2)

        self._rounded_rect(1, 1, w-1, h-1, r, fill=self._bg, outline=self._border)

        icon = self._icon_text or ""
        txt = self._textvariable.get() if self._textvariable is not None else ""

        y_mid = h // 2
        x_icon = self._padx

        icon_id = self.create_text(
            x_icon, y_mid,
            text=icon,
            fill=self._fg,
            font=self._icon_font,
            anchor="w"
        )
        icon_bbox = self.bbox(icon_id) or (0, 0, 0, 0)
        icon_w = icon_bbox[2] - icon_bbox[0]

        x_text = x_icon + icon_w + 8
        max_text_w = max(50, w - x_text - self._padx)

        self.create_text(
            x_text, y_mid,
            text=txt,
            fill=self._fg,
            font=self._font,
            anchor="w",
            width=max_text_w
        )


        
        
############################################

class RoundedFrame(tk.Canvas):
    def __init__(self, parent, bg="#FFFFFF", radius=8, canvas_bg=None, **kwargs):
        if canvas_bg is None:
            try:
                canvas_bg = parent.cget("background")  # ttk'de çalışır
            except Exception:
                canvas_bg = "#F1F1F1"

        super().__init__(
            parent,
            highlightthickness=0,
            bd=0,
            background=canvas_bg,
            **kwargs
        )
        self._bg = bg
        self._r = int(radius)
        self.bind("<Configure>", self._draw)
        self.after(0, self._draw)

    def _draw(self, e=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return

        r = min(self._r, w // 2, h // 2)

        points = [
            r, 0,
            w - r, 0,
            w, 0,
            w, r,
            w, h - r,
            w, h,
            w - r, h,
            r, h,
            0, h,
            0, h - r,
            0, r,
            0, 0
        ]
        self.create_polygon(points, smooth=True, splinesteps=24, fill=self._bg, outline="")
        
#############################################




class RoundedCard(tk.Canvas):
    def __init__(
        self,
        parent,
        radius=12,
        card_bg="#FFFFFF",
        border_color="#D9DDE3",
        border_width=1,
        canvas_bg=None,  # parent arkaplanı
        **kwargs
    ):
        if canvas_bg is None:
            try:
                canvas_bg = parent.cget("bg")
            except Exception:
                canvas_bg = "#FFFFFF"

        super().__init__(
            parent,
            highlightthickness=0,
            bd=0,
            background=canvas_bg,
            **kwargs
        )

        self._radius = int(radius)
        self._card_bg = card_bg
        self._border_color = border_color
        self._border_width = int(border_width)

        # İçerik frame'i (kartın içine gömülecek)
        self.content = tk.Frame(self, bg=self._card_bg)
        self._content_window = self.create_window(0, 0, window=self.content, anchor="nw")

        self.bind("<Configure>", self._on_configure)
        self.content.bind("<Configure>", self._fit_to_content)

    def _on_configure(self, _e=None):
        self._redraw()
        self._reposition_content()
        
    def _fit_to_content(self, _e=None):
        """pack(fill='x') ile kullanıldığında içeriği kesmesin diye canvas yüksekliğini içerikten türet."""
        try:
            self.update_idletasks()
            bw = self._border_width
            needed_h = self.content.winfo_reqheight() + 2 * bw

            # sonsuz configure döngüsüne girmemek için küçük eşik
            if abs(self.winfo_height() - needed_h) > 2:
                self.configure(height=needed_h)
        except Exception:
            pass

    def _reposition_content(self):
        w = self.winfo_width()
        h = self.winfo_height()
        bw = self._border_width

        # İçerik alanını border'ın içine oturt
        self.coords(self._content_window, bw, bw)
        self.itemconfigure(self._content_window, width=max(0, w - 2 * bw), height=max(0, h - 2 * bw))

    def _redraw(self):
        self.delete("card")

        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            return

        bw = self._border_width
        r = min(self._radius, (h // 2), (w // 2))

        x0, y0 = bw, bw
        x1, y1 = w - bw, h - bw

        fill = self._card_bg
        outline = self._border_color

        # Köşeler
        self.create_arc(x0, y0, x0 + 2*r, y0 + 2*r, start=90,  extent=90,  fill=fill, outline=outline, width=bw, tags="card")
        self.create_arc(x1 - 2*r, y0, x1, y0 + 2*r, start=0,   extent=90,  fill=fill, outline=outline, width=bw, tags="card")
        self.create_arc(x1 - 2*r, y1 - 2*r, x1, y1, start=270, extent=90,  fill=fill, outline=outline, width=bw, tags="card")
        self.create_arc(x0, y1 - 2*r, x0 + 2*r, y1, start=180, extent=90,  fill=fill, outline=outline, width=bw, tags="card")

        # Gövde
        self.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline=outline, width=bw, tags="card")
        self.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline=outline, width=bw, tags="card")
        
        
    
########################################333



            
class InputPanel:
    """Parametre giriş paneli sınıfı"""
    
    def __init__(self, parent_frame, data_loaded_callback=None, design_params_model=None):
        """
        Args:
            parent_frame: Ana çerçeve
            data_loaded_callback: Veri yüklendiğinde çağrılacak fonksiyon
        """
        self._base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        self._icons_dir = self._base_dir / "icons"
        self._report_images_dir = self._base_dir / "report_images"
        
        self.parent_frame = parent_frame
        self.data_loaded_callback = data_loaded_callback
        self._design_params_model = design_params_model
        
        # Callback fonksiyonları
        self.unit_change_callback = None  # Birim değişikliği için callback
        
        # Değişkenler
        self._init_variables()
        
        # Widget'ları oluştur
        self._create_widgets()
        
    def _load_icon(self, path: Path):
        try:
            return PhotoImage(file=str(path))
        except Exception as e:
            print(f"İkon yüklenemedi: {path} -> {e}")
            return None
        
    def _load_ctk_icon(self, path, size=(24,24)):
        from PIL import Image
        try:
            img = Image.open(path)
            return ctk.CTkImage(light_image=img, size=size)
        except Exception as e:
            print(f"CTk ikon yüklenemedi: {path} -> {e}")
            return None
    
    def _init_variables(self):
        """Tkinter değişkenlerini başlatır"""
        self.enlem_var = tk.StringVar(value=str(DEFAULT_LOCATION["lat"]))
        self.boylam_var = tk.StringVar(value=str(DEFAULT_LOCATION["lon"]))
        self.dd_var = tk.StringVar(value=DEFAULT_EARTHQUAKE_LEVEL)
        self.zemin_var = tk.StringVar(value=DEFAULT_SOIL_CLASS)
        
        # Sonuç değişkenleri
        self.ss_var = tk.StringVar()
        self.s1_var = tk.StringVar()
        self.fs_var = tk.StringVar()
        self.f1_var = tk.StringVar()
        # Spektrum parametreleri: ortak model varsa ona bağla
        if self._design_params_model is not None:
            self.sds_var = self._design_params_model.sds_var
            self.sd1_var = self._design_params_model.sd1_var
            self.tl_var = self._design_params_model.tl_var
        else:
            self.sds_var = tk.StringVar()
            self.sd1_var = tk.StringVar()
            self.tl_var = tk.StringVar(value="6.0")
        
        # Spektrum seçenekleri
        self.yatay_var = tk.BooleanVar(value=True)
        self.dusey_var = tk.BooleanVar(value=True)
        self.yerdeğiştirme_var = tk.BooleanVar(value=False)
        self.log_t_var = tk.BooleanVar(value=False)
        # Kullanıcı referans çizgileri (T ekseni)
        self.ref_lines_enabled_var = tk.BooleanVar(value=False)
        self.ref_lines_var = tk.StringVar(value="1.0, 6.0")
        
        # Birim seçimi değişkenleri
        self.acceleration_unit_var = tk.StringVar(value='g')
        self.displacement_unit_var = tk.StringVar(value='cm')
        
        # Dosya durumu
        self.afad_dosya_durum_var = tk.StringVar(value="Lütfen veri setini içeren dosyayı yükleyin.")
        
        # Command bağlama değişkenleri
        self.load_command = None
        self.calculation_command = None
        self.map_command = None
        self.save_command = None
        self.report_command = None
        self.peer_export_command = None
        
        # İkonları yükle
        try:
            self.upload_icon = self._load_icon(self._icons_dir / "bytesize_upload.png")
            print("İkon başarıyla yüklendi: icons/bytesize_upload.png")
        except tk.TclError as e:
            print(f"Upload ikonu yüklenemedi: {e}")
            self.upload_icon = None
            
        try:
            self.calculate_icon = self._load_icon(self._icons_dir / "calculate_01.png")
            print("İkon başarıyla yüklendi: icons/calculate_01.png")
        except tk.TclError as e:
            print(f"Calculate ikonu yüklenemedi: {e}")
            self.calculate_icon = None
            
        try:
            self.spectrum_icon = self._load_icon(self._icons_dir / "calculate.png")
            print("İkon başarıyla yüklendi: icons/calculate.png")
        except tk.TclError as e:
            print(f"Calculate ikonu yüklenemedi: {e}")
            self.spectrum_icon = None
            
        try:
            self.map_icon = self._load_icon(self._icons_dir / "map.png")
            print("İkon başarıyla yüklendi: icons/map_01.png")
        except tk.TclError as e:
            print(f"Map ikonu yüklenemedi: {e}")
            self.map_icon = None
            
        try:
            self.save_icon = self._load_icon(self._icons_dir / "save.png")
            print("İkon başarıyla yüklendi: icons/save.png")
        except tk.TclError as e:
            print(f"Save ikonu yüklenemedi: {e}")
            self.save_icon = None
            
        try:
            self.report_icon = self._load_icon(self._icons_dir / "report.png")
            print("İkon başarıyla yüklendi: icons/report.png")
        except tk.TclError as e:
            print(f"Report ikonu yüklenemedi: {e}")
            self.report_icon = None
            
        try:
            self.peer_export_icon = self._load_icon(self._icons_dir / "csv.png")
            print("İkon başarıyla yüklendi: report_images/csv.png")
        except tk.TclError as e:
            print(f"PEER export ikonu yüklenemedi: {e}")
            self.peer_export_icon = None
    
    def _create_widgets(self):
        """Tüm widget'ları oluşturur"""
        # 1. Dosya yükleme bölümü
        self._create_file_section()
        
        # 2. Girdi parametreleri bölümü
        try:
            self._create_input_section()
        except Exception as e:
            import traceback
            print(traceback.format_exc())  # terminale tam hatayı basar
            raise
        
        # 3. Spektrum seçenekleri bölümü (Spektrum Türlerini Seç)
        self._create_spectrum_options()
        
        # 5. Hesaplama butonu (Spektrumları Hesapla)
        self._create_calculation_button()
        
        # 6. Sonuç değerleri bölümü (Hesaplanan Parametreleri Görüntüle)
        self._create_results_section()
        
        # 7. Birim seçimi bölümü (Birim Ayarla)
        self._create_unit_selection()
        
        # 8. Eylem butonları bölümü (Eylem Yap - Kaydet/Rapor/vb.)
        self._create_action_buttons()
    
    def _create_file_section(self):
        """Dosya yükleme bölümünü oluşturur"""
        from pathlib import Path

        # === DIŞ KART (Border katmanı - tam genişlik) ===
        outer = ctk.CTkFrame(
            self.parent_frame,
            fg_color="#FFFFFF",
            border_color="#D9DDE3",
            border_width=1,
            corner_radius=12
        )
        outer.pack(fill="x", pady=(0,10), padx=0)

        # === İÇ PADDING ALANI ===
        content = tk.Frame(outer, bg="#FFFFFF")
        content.pack(fill="x", padx=12, pady=12)

        # Bundan sonra tüm elemanlar content içine gelecek
        dosya_ana_cerceve = content

        dosya_ana_cerceve.columnconfigure(0, weight=1)
        dosya_ana_cerceve.columnconfigure(1, weight=1)

        # --- HEADER (ikon + başlık) ---
        header_frame = tk.Frame(dosya_ana_cerceve, bg="#FFFFFF")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        this_file = Path(__file__).resolve()
        icon_path = None
        for p in [this_file.parent] + list(this_file.parents):
            candidate = p / "icons" / "upload_01.png"
            if candidate.exists():
                icon_path = candidate
                break

        self.param_icon = None
        if icon_path is not None:
            try:
                self.param_icon = tk.PhotoImage(file=str(icon_path))
            except Exception:
                self.param_icon = None

        if self.param_icon is not None:
            tk.Label(header_frame, image=self.param_icon, bg="#FFFFFF").pack(side="left", padx=(0, 6))

        try:
            poppins = tkfont.Font(family="Poppins", size=11, weight="bold")
        except Exception:
            poppins = tkfont.nametofont("TkDefaultFont").copy()
            poppins.configure(size=11, weight="bold")

        tk.Label(
            header_frame,
            text="Parametre Dosyası",
            font=poppins,
            fg="#444444",
            bg="#FFFFFF"
        ).pack(side="left")
        
        f = tkfont.nametofont("TkDefaultFont").copy()
        f.configure(size=10, weight="bold")

        # --- YÜKLE BUTONU ---
        self.load_button = RoundedButton(
            dosya_ana_cerceve,
            text="AFAD TDTH Veri Setini Yükle",
            image=self.upload_icon if self.upload_icon else None,
            on_click=getattr(self, "on_load_click", None),
            height=40,
            radius=8,
            canvas_bg="#FFFFFF",
            font=f
        )
        self.load_button.grid(row=1, column=0, columnspan=2, sticky="ew")

        # --- STATUS BOX ---
        self.afad_status_box = RoundedStatusBox(
            dosya_ana_cerceve,
            radius=8,
            bg="#FDECEC",
            border="#F5C2C7",
            fg="#B42318",
            icon_text="!",
            textvariable=self.afad_dosya_durum_var,
            height=44
        )
        self.afad_status_box.grid(
            row=2, column=0, columnspan=2,
            sticky="ew", pady=(6, 0)
        )

        # İlk mesaj
        if not (self.afad_dosya_durum_var.get() or "").strip():
            self.afad_dosya_durum_var.set(
                "Lütfen veri setini içeren dosyayı yükleyin."
            )

    
    def _create_input_section(self):
        """Girdi parametreleri (2 kolon layout, web'e yakın)"""
        import customtkinter as ctk
        import tkinter as tk
        from tkinter import font as tkfont

        LABEL_COLOR = "#565656"
        BG = "#FFFFFF"

        # Input wrapper stil
        INPUT_BG = "#FFFFFF"
        INPUT_BORDER = "#E5E7EB"   # açık gri
        INPUT_RADIUS = 4
        INPUT_BORDER_W = 1

        # === DIŞ KART (padx=0) ===
        card = ctk.CTkFrame(
            self.parent_frame,
            fg_color=BG,
            border_color="#D9DDE3",
            border_width=1,
            corner_radius=12
        )
        card.pack(fill="x", pady=(0, 10), padx=0, anchor="n")

        # === İÇ CONTENT (padding içeride) ===
        content = tk.Frame(card, bg=BG)
        content.pack(fill="x", padx=14, pady=14)

        # === HEADER ===
        header = tk.Frame(content, bg=BG)
        header.pack(fill="x", pady=(0, 10))

        self._girdi_icon = self._load_icon(self._icons_dir / "filters.png")
        if self._girdi_icon is not None:
            tk.Label(header, image=self._girdi_icon, bg=BG).pack(side="left", padx=(0, 8))

        # Chevron icon (select ok) - tamamen bizim kontrolümüzde olacak
        self._chevron_down_icon = self._load_icon(self._icons_dir / "chevron-down.png")

        # Başlık fontunu family'e dokunmadan büyüt/bold yap
        try:
            base = tkfont.nametofont("TkDefaultFont")
            title_font = base.copy()
            title_font.configure(size=max(base.cget("size") + 2, 12), weight="bold")
        except Exception:
            title_font = None

        tk.Label(
            header,
            text="GİRDİ PARAMETRELERİ",
            bg=BG,
            fg=LABEL_COLOR,
            font=title_font
        ).pack(side="left")

        # === 2 KOLON GRID ===
        grid = tk.Frame(content, bg=BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="col")
        grid.grid_columnconfigure(1, weight=1, uniform="col")

        # Dropdown menu referansını tutalım (GC olmasın)
        if not hasattr(self, "_dropdown_menus"):
            self._dropdown_menus = {}

        def _wrap_input(box, is_combo=False):
            """
            dışına CTkFrame (border + radius) koyuyoruz.
            """
            wrapper = ctk.CTkFrame(
                box,
                fg_color=INPUT_BG,
                border_color=INPUT_BORDER,
                border_width=INPUT_BORDER_W,
                corner_radius=INPUT_RADIUS
            )
            wrapper.grid(row=1, column=0, sticky="ew")
            wrapper.grid_columnconfigure(0, weight=1)

            # İç host (wrapper içi padding)
            inner = tk.Frame(wrapper, bg=INPUT_BG)
            inner.pack(fill="x", padx=10, pady=8)

            if is_combo:
                inner.grid_columnconfigure(0, weight=1)
                inner.grid_columnconfigure(1, weight=0)

                value_parent = tk.Frame(inner, bg=INPUT_BG)
                value_parent.grid(row=0, column=0, sticky="ew")

                icon_lbl = None
                if self._chevron_down_icon is not None:
                    icon_lbl = tk.Label(inner, image=self._chevron_down_icon, bg=INPUT_BG)
                    icon_lbl.grid(row=0, column=1, sticky="e", padx=(8, 0))

                return value_parent, icon_lbl, wrapper
            else:
                return inner, None, wrapper

        def _make_dropdown(parent, icon_lbl, wrapper, values, variable, key):
            """
            Custom select:
            - Değer ctk.CTkLabel olarak gösterilir (Entry ile aynı görünüm için)
            """
            # Değer göstergesi (ctk.CTkLabel kullanarak Enlem/Boylam ile stili eşitledik)
            lbl = ctk.CTkLabel(
                parent,
                textvariable=variable,
                fg_color="transparent",
                text_color="#111827",
                anchor="w",
                height=24
            )
            lbl.pack(fill="x")

            # --- Menü fontu ---
            try:
                base_font = tkfont.nametofont("TkDefaultFont")
                menu_font = base_font.copy()
                menu_font.configure(size=max(base_font.cget("size"), 9))
            except Exception:
                menu_font = None

            # --- Menü (beyaz + yumuşak hover) ---
            menu = tk.Menu(
                self.parent_frame,
                tearoff=0,
                bg="#FFFFFF",
                fg="#111827",
                activebackground="#F3F4F6",
                activeforeground="#111827",
                relief="solid",
                bd=1,
                font=menu_font
            )

            # Menü genişliği: en az wrapper kadar olsun (space padding ile)
            try:
                wrapper.update_idletasks()
                wrapper_px = wrapper.winfo_width()
            except Exception:
                wrapper_px = 0

            try:
                f = menu_font or tkfont.nametofont("TkDefaultFont")
                char_px = max(f.measure("0"), 7)
            except Exception:
                char_px = 8

            min_chars = int(wrapper_px / char_px) if wrapper_px else 0
            labels = [str(v) for v in values]
            max_label_len = max((len(s) for s in labels), default=0)
            target_len = max(max_label_len + 4, min_chars)

            def _pad_label(s: str) -> str:
                pad = max(0, target_len - len(s))
                return s + (" " * pad)

            for v in labels:
                menu.add_command(label=_pad_label(v), command=lambda vv=v: variable.set(vv))

            self._dropdown_menus[key] = menu

            def _open_menu(_e=None):
                try:
                    x = wrapper.winfo_rootx()
                    y = wrapper.winfo_rooty() + wrapper.winfo_height()
                    menu.tk_popup(x, y)
                finally:
                    try:
                        menu.grab_release()
                    except Exception:
                        pass

            # Tıklanabilir alan: wrapper + label + chevron
            wrapper.bind("<Button-1>", _open_menu)
            lbl.bind("<Button-1>", _open_menu)
            if icon_lbl is not None:
                icon_lbl.bind("<Button-1>", _open_menu)

            return lbl


        def field(parent, col, row, label_text, widget_kind, values=None, variable=None, key=None):
            """Label üstte, widget altta"""
            box = tk.Frame(parent, bg=BG)
            box.grid(
                row=row,
                column=col,
                sticky="ew",
                padx=(0, 10) if col == 0 else (10, 0),
                pady=6
            )
            box.grid_columnconfigure(0, weight=1)

            tk.Label(
                box,
                text=label_text,
                bg=BG,
                fg=LABEL_COLOR,
                anchor="w"
            ).grid(row=0, column=0, sticky="w", pady=(0, 4))

            host, icon_lbl, wrapper = _wrap_input(box, is_combo=(widget_kind == "select"))

            if widget_kind == "entry":
                e = ctk.CTkEntry(
                    host,
                    textvariable=variable,
                    fg_color=INPUT_BG,
                    border_width=0,
                    corner_radius=0,
                    height=24
                )
                e.pack(fill="x")
                
                # Kopyalama düzeltmesi: Ctrl+C sadece bu entry'nin değerini kopyalasın
                def _copy_entry_value(event, var=variable):
                    try:
                        widget = event.widget
                        if widget.selection_present():
                            text = widget.selection_get()
                        else:
                            text = var.get()
                        widget.clipboard_clear()
                        widget.clipboard_append(text)
                    except Exception:
                        try:
                            widget.clipboard_clear()
                            widget.clipboard_append(var.get())
                        except Exception:
                            pass
                    return "break"  # Varsayılan davranışı engelle
                
                # CTkEntry içindeki asıl tk.Entry widget'ına bağla
                try:
                    inner_entry = e._entry if hasattr(e, '_entry') else e
                    inner_entry.bind('<Control-c>', _copy_entry_value)
                    inner_entry.bind('<Control-C>', _copy_entry_value)
                except Exception:
                    pass
                
                return e

            if widget_kind == "select":
                # custom dropdown
                return _make_dropdown(
                    parent=host,
                    icon_lbl=icon_lbl,
                    wrapper=wrapper,
                    values=values,
                    variable=variable,
                    key=key
                )

            raise ValueError("widget_kind must be 'entry' or 'select'")

        # Sol üst: Enlem
        self.enlem_entry = field(
            grid, 0, 0, "Enlem (°)",
            widget_kind="entry",
            variable=self.enlem_var
        )

        # Sağ üst: Boylam
        self.boylam_entry = field(
            grid, 1, 0, "Boylam (°)",
            widget_kind="entry",
            variable=self.boylam_var
        )

        # Sol alt: Deprem Düzeyi (select)
        self.dd_select = field(
            grid, 0, 1, "Deprem Yer Hareketi Düzeyi",
            widget_kind="select",
            values=list(EARTHQUAKE_LEVELS),
            variable=self.dd_var,
            key="dd_level"
        )

        # Sağ alt: Zemin Sınıfı (select)
        self.zemin_select = field(
            grid, 1, 1, "Zemin Sınıfı",
            widget_kind="select",
            values=list(SOIL_CLASSES),
            variable=self.zemin_var,
            key="soil_class"
        )
    
    def _create_calculation_button(self):
        """Spektrumları Hesapla butonu (CTk'siz, sadece tasarım)"""
        import tkinter as tk
        from tkinter import font as tkfont

        hesapla_frame = tk.Frame(self.parent_frame, bg="#FFFFFF")
        hesapla_frame.pack(fill="x", pady=(4, 6), padx=0)

        # Font: mevcut TkDefaultFont (Poppins) kalsın, sadece bold yap
        try:
            f = tkfont.nametofont("TkDefaultFont").copy()
            f.configure(size=f.cget("size") + 1, weight="bold")
        except Exception:
            f = None

        # RoundedButton: command/on_click vermiyoruz -> akışa dokunmuyoruz
        self.hesapla_button = RoundedButton(
            hesapla_frame,
            text="SPEKTRUMLARI HESAPLA",
            image=self.spectrum_icon if self.spectrum_icon else None,  # tk.PhotoImage
            height=52,
            radius=12,
            btn_bg="#2F6FED",
            hover_bg="#2A62D8",
            fg="white",
            font=f,
            canvas_bg="#FFFFFF"
        )
        self.hesapla_button.pack(fill="x")

        # başlangıçta disabled (eski davranış)
        self.hesapla_button.configure(state="disabled")

   
    def _create_results_section(self):
        """Tasarım Parametreleri (web kart görünümü)"""
        import tkinter as tk
        from tkinter import font as tkfont

        BG = "#FFFFFF"
        BORDER = "#D9DDE3"
        TITLE_COLOR = "#565656"

        PANEL_BG = "#F8FAFC"
        PANEL_BORDER = "#EEF2F7"
        SEP = "#E5E7EB"

        CODE_COLOR = "#111827"
        DESC_COLOR = "#6B7280"
        VALUE_COLOR = "#2563EB"
        VALUE_EMPTY = "#9CA3AF"

        # === parent bg (tk.Frame / CTkFrame uyumlu) ===
        try:
            canvas_bg = self.parent_frame.cget("bg")
        except Exception:
            try:
                canvas_bg = self.parent_frame.cget("fg_color")
                if isinstance(canvas_bg, (tuple, list)):
                    canvas_bg = canvas_bg[0]
            except Exception:
                canvas_bg = "#FFFFFF"

        # === DIŞ KART (rounded) ===
        card = RoundedCard(
            self.parent_frame,
            radius=12,
            card_bg=BG,
            border_color=BORDER,
            border_width=1,
            canvas_bg=canvas_bg
        )
        card.pack(fill="x", pady=(0, 10), padx=0, anchor="n")

        content = tk.Frame(card.content, bg=BG)
        content.pack(fill="x", padx=14, pady=14)

        # Başlık font
        try:
            base = tkfont.nametofont("TkDefaultFont")
            title_font = base.copy()
            title_font.configure(size=max(base.cget("size") + 2, 12), weight="bold")
        except Exception:
            title_font = None

        tk.Label(
            content,
            text="TASARIM PARAMETRELERİ",
            bg=BG,
            fg=TITLE_COLOR,
            font=title_font,
            anchor="w"
        ).pack(fill="x", pady=(0, 12))

        # === İç panel (açık gri) ===
        panel = RoundedCard(
            content,
            radius=12,
            card_bg=PANEL_BG,
            border_color=PANEL_BORDER,
            border_width=1,
            canvas_bg=BG
        )
        panel.pack(fill="x")

        panel_in = tk.Frame(panel.content, bg=PANEL_BG)
        panel_in.pack(fill="x", padx=14, pady=14)

        # Fontlar
        try:
            f_code = tkfont.nametofont("TkDefaultFont").copy()
            f_code.configure(weight="bold")
        except Exception:
            f_code = None

        try:
            f_desc = tkfont.nametofont("TkDefaultFont").copy()
        except Exception:
            f_desc = None

        try:
            f_val = tkfont.nametofont("TkDefaultFont").copy()
            f_val.configure(weight="bold")
        except Exception:
            f_val = None

        # --- Değer bağlama: var değişince label otomatik güncellensin ---
        def _bind_value_var(src_var):
            """
            src_var (StringVar/DoubleVar/IntVar) -> display StringVar
            Boşsa '—' gösterir, doluysa değeri gösterir.
            """
            disp = tk.StringVar(value="—")

            def _update(*_):
                try:
                    v = src_var.get()
                except Exception:
                    v = None

                if v is None:
                    disp.set("—")
                    return

                s = str(v).strip()
                if s == "" or s.lower() in {"none", "nan"}:
                    disp.set("—")
                else:
                    disp.set(s)

            try:
                src_var.trace_add("write", _update)
            except Exception:
                # eski tkinter sürümleri için
                try:
                    src_var.trace("w", _update)
                except Exception:
                    pass

            _update()
            return disp

        def _row(parent, code_text, src_var, desc, add_sep=True):
            row = tk.Frame(parent, bg=PANEL_BG)
            row.pack(fill="x")

            # 2 kolon: sol sabit, sağ esner
            row.grid_columnconfigure(0, weight=0, minsize=72)  # kod alanı
            row.grid_columnconfigure(1, weight=1)              # sağ kolon

            # Sol: Kod (sol üstte sabit)
            tk.Label(
                row,
                text=code_text,
                bg=PANEL_BG,
                fg=CODE_COLOR,
                font=f_code,
                anchor="w"
            ).grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 14), pady=(2, 0))

            # Sağ üst: Açıklama (soldan başlar, aynı hizada)
            tk.Label(
                row,
                text=desc,
                bg=PANEL_BG,
                fg=DESC_COLOR,
                font=f_desc,
                anchor="w",
                justify="left"
            ).grid(row=0, column=1, sticky="nw", pady=(0, 0))

            # Sağ alt: Değer (açıklamanın ALTINDA, sağa hizalı)
            disp_var = _bind_value_var(src_var)
            val_lbl = tk.Label(
                row,
                textvariable=disp_var,
                bg=PANEL_BG,
                fg=VALUE_COLOR,   # boşsa rengini trace ile değiştireceğiz
                font=f_val,
                anchor="e"
            )
            val_lbl.grid(row=1, column=1, sticky="e", pady=(4, 0))

            # boşsa value rengini gri yap / doluysa mavi
            def _recolor(*_):
                if disp_var.get() == "—":
                    val_lbl.configure(fg=VALUE_EMPTY)
                else:
                    val_lbl.configure(fg=VALUE_COLOR)

            try:
                disp_var.trace_add("write", _recolor)
            except Exception:
                try:
                    disp_var.trace("w", _recolor)
                except Exception:
                    pass
            _recolor()

            if add_sep:
                tk.Frame(parent, bg=SEP, height=1).pack(fill="x", pady=12)

        # === Satırlar (7 adet) ===
        _row(panel_in, "Ss",   self.ss_var,  "Kısa periyot harita spektral katsayısı")
        _row(panel_in, "S₁",   self.s1_var,  "1.0 sn periyot harita spektral katsayısı")

        _row(panel_in, "Fs",   self.fs_var,  "Kısa periyot zemin katsayısı")
        _row(panel_in, "F₁",   self.f1_var,  "1.0 sn periyot zemin katsayısı")

        _row(panel_in, "Sᴅₛ",  self.sds_var, "Kısa periyot tasarım spektral katsayısı")
        _row(panel_in, "Sᴅ₁",  self.sd1_var, "1.0 sn periyot tasarım spektral katsayısı")
        _row(panel_in, "Tʟ",   self.tl_var,  "Uzun periyot geçiş periyodu", add_sep=False)
                
        # --- DEĞİŞİKLİK SONU ---
    
    def _create_subscript_label(self, parent, base_text: str, sub_text: str = "", suffix: str = ""):
        container = ttk.Frame(parent)

        sub_font = None
        if sub_text:
            try:
                # Default zaten Poppins oldu -> kopyala, küçült
                base = tkfont.nametofont("TkDefaultFont")
                sub_font = base.copy()
                sub_font.configure(size=max(base.cget("size") - 1, 8))
            except Exception:
                sub_font = None

        base_lbl = ttk.Label(
            container,
            text=base_text,
            style="Small.TLabel"
        )
        base_lbl.grid(row=0, column=0, sticky="w")

        if sub_text:
            sub_lbl = ttk.Label(
                container,
                text=sub_text,
                style="Small.TLabel"
            )
            # sadece burada küçült
            if sub_font is not None:
                sub_lbl.configure(font=sub_font)

            sub_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))

        if suffix:
            suffix_lbl = ttk.Label(
                container,
                text=suffix,
                style="Small.TLabel"
            )
            suffix_lbl.grid(row=0, column=2, sticky="w", padx=(0, VALUE_COLUMN_PAD))

        return container

    def _create_parameter_row(self, parent, param_name, param_var, description, row, highlight=False):
        """Parametre satırı oluşturur (artık doğrudan ana grid'e yerleştiriyor)"""
        # --- DEĞİŞİKLİK BAŞLANGICI ---
        # Artık her satır için ayrı bir Frame oluşturmuyoruz.
        # row_frame = ttk.Frame(parent)
        # row_frame.pack(fill="x", pady=2)
        # row_frame.grid_columnconfigure(...) satırları kaldırıldı.
        
        # Parametre adı - indisli gösterim için özel işlem
        if "_" in param_name:
            parts = param_name.split("_", 1)
            # Parent olarak doğrudan gelen LabelFrame'i kullanıyoruz.
            name_widget = self._create_subscript_label(parent, parts[0], parts[1], ":")
            # `row=row` kullanarak doğru satıra yerleştiriyoruz.
            name_widget.grid(row=row, column=0, sticky="w", padx=(5, 0))
        else:
            name_label = ttk.Label(parent, text=f"{param_name}:", 
                                  style="Small.TLabel",
                                  anchor='w')
            name_label.grid(row=row, column=0, sticky="w", padx=(5, 0))
        
        # Değer alanı
        value_label_style = "Value.TLabel"
        
        if highlight:
            value_label = ttk.Label(parent, textvariable=param_var,
                                   style=value_label_style,
                                   foreground='#2E86AB',
                                   anchor='w',
                                   relief='solid', borderwidth=1)
        else:
            value_label = ttk.Label(parent, textvariable=param_var,
                                   style=value_label_style,
                                   anchor='w')
        # Değer ve açıklama arasındaki boşluk artık grid_columnconfigure'daki 'pad' ile sağlanıyor.
        value_label.grid(row=row, column=1, sticky="w", padx=(VALUE_COLUMN_PAD, 0))
        
        # Açıklama
        desc_label = ttk.Label(parent, text=description,
                              style="Small.TLabel",
                              foreground='gray',
                              wraplength=400) 
        desc_label.grid(row=row, column=2, sticky="ew")
        
        # --- DEĞİŞİKLİK SONU ---
    
    def _create_spectrum_options(self):
        """Çizilecek spektrumlar (web kart görünümü)"""
        import customtkinter as ctk
        import tkinter as tk
        from tkinter import font as tkfont

        BG = "#FFFFFF"
        LABEL_COLOR = "#565656"

        # Kart
        card = ctk.CTkFrame(
            self.parent_frame,
            fg_color=BG,
            border_color="#D9DDE3",
            border_width=1,
            corner_radius=12
        )
        card.pack(fill="x", pady=(0, 10), padx=0, anchor="n")

        # İç padding (kart genişliği tam; içeride boşluk var)
        content = tk.Frame(card, bg=BG)
        content.pack(fill="x", padx=14, pady=14)

        # Başlık (Büyütüldü ve Poppins yapıldı)
        tk.Label(
            content,
            text="ÇİZİLECEK SPEKTRUMLAR",
            bg=BG,
            fg=LABEL_COLOR,
            font=("Poppins", 13, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Vars
        self.opt_horizontal = tk.BooleanVar(value=False)
        self.opt_vertical = tk.BooleanVar(value=False)
        self.opt_disp = tk.BooleanVar(value=False)
        self.logT_var = tk.BooleanVar(value=False)

        # Checkbox style (Poppins ve 13px eklendi)
        def _ck(text, var):
            cb = ctk.CTkCheckBox(
                content,
                text=text,
                variable=var,
                onvalue=True,
                offvalue=False,
                fg_color="#2F6FED",
                border_color="#CBD5E1",
                text_color="#111827",
                checkbox_width=22,
                checkbox_height=22,
                corner_radius=11,
                font=("Poppins", 13)
            )
            cb.pack(fill="x", pady=6)
            return cb

        _ck("Yatay Elastik Tasarım Spektrumu", self.opt_horizontal)
        _ck("Düşey Elastik Tasarım Spektrumu", self.opt_vertical)
        _ck("Yerdeğiştirme Tasarım Spektrumu", self.opt_disp)

        # Ayraç
        sep = tk.Frame(content, bg="#E5E7EB", height=1)
        sep.pack(fill="x", pady=(10, 10))

        _ck("Periyot ekseni Log(T)", self.logT_var)

        # Referans periyot label (Poppins ve 11px yapıldı)
        tk.Label(
            content,
            text="REFERANS PERİYOT ÇİZGİLERİ (T)",
            bg=BG,
            fg=LABEL_COLOR,
            font=("Poppins", 11, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(14, 6))

        # Input wrapper (web input görünümü)
        wrapper = ctk.CTkFrame(
            content,
            fg_color="#FFFFFF",
            border_color="#E5E7EB",
            border_width=1,
            corner_radius=10
        )
        wrapper.pack(fill="x")

        self.ref_periods_var = tk.StringVar(value="0.35, 1.0, 6.0")
        self.ref_periods_entry = ctk.CTkEntry(
            wrapper,
            textvariable=self.ref_periods_var,
            fg_color="#FFFFFF",
            border_width=0,
            corner_radius=0,
            height=42,
            text_color="#111827",
            font=("Poppins", 13)  # İŞTE BURAYA EKLEDİM
        )
        self.ref_periods_entry.pack(fill="x", padx=12, pady=10)

        # Tooltip + validasyon (mevcut fonksiyonların aynen)
        self._attach_tooltip(
            self.ref_periods_entry,
            "Grafiğe referans çizgileri eklemek için virgülle ayrılmış T değerleri girin.\nÖrnek: 0.35, 1.0, 6.0"
        )
        try:
            vcmd = (self.parent_frame.register(self._validate_ref_periods), '%P')
        except Exception:
            pass
    def _create_unit_selection(self):
        """Birim seçimi paneli - Input'taki (Zemin Sınıfı) ile aynı custom select"""

        import tkinter as tk
        from tkinter import font as tkfont
        import customtkinter as ctk

        BG = "#FFFFFF"
        BORDER = "#D9DDE3"
        TITLE_COLOR = "#565656"

        PANEL_BG = "#F8FAFC"
        PANEL_BORDER = "#EEF2F7"

        LABEL_COLOR = "#111827"

        # Select wrapper stil (Input'taki ile aynı)
        SELECT_BG = "#FFFFFF"
        SELECT_BORDER = "#E5E7EB"
        SELECT_RADIUS = 4
        SELECT_BORDER_W = 1

        # === Dış kart bg güvenli al ===
        try:
            canvas_bg = self.parent_frame.cget("bg")
        except Exception:
            try:
                canvas_bg = self.parent_frame.cget("fg_color")
                if isinstance(canvas_bg, (tuple, list)):
                    canvas_bg = canvas_bg[0]
            except Exception:
                canvas_bg = "#FFFFFF"

        # Chevron icon (Input'taki gibi)
        if not hasattr(self, "_chevron_down_icon"):
            try:
                self._chevron_down_icon = self._load_icon(self._icons_dir / "chevron-down.png")
            except Exception:
                self._chevron_down_icon = None

        # Dropdown menu referanslarını tut (Input'taki ile aynı)
        if not hasattr(self, "_dropdown_menus"):
            self._dropdown_menus = {}

        # === DIŞ KART (rounded) ===
        card = RoundedCard(
            self.parent_frame,
            radius=12,
            card_bg=BG,
            border_color=BORDER,
            border_width=1,
            canvas_bg=canvas_bg
        )
        card.pack(fill="x", pady=(10, 0), padx=0, anchor="n")

        content = tk.Frame(card.content, bg=BG)
        content.pack(fill="x", padx=14, pady=14)

        # Başlık font
        try:
            base = tkfont.nametofont("TkDefaultFont")
            title_font = base.copy()
            title_font.configure(size=max(base.cget("size") + 2, 12), weight="bold")
        except Exception:
            title_font = None

        tk.Label(
            content,
            text="BİRİM SEÇİMİ",
            bg=BG,
            fg=TITLE_COLOR,
            font=title_font,
            anchor="w"
        ).pack(fill="x", pady=(0, 12))

        # === İç panel ===
        panel = RoundedCard(
            content,
            radius=12,
            card_bg=PANEL_BG,
            border_color=PANEL_BORDER,
            border_width=1,
            canvas_bg=BG
        )
        panel.pack(fill="x")

        panel_in = tk.Frame(panel.content, bg=PANEL_BG)
        panel_in.pack(fill="x", padx=14, pady=14)

        # 2 kolon grid
        grid = tk.Frame(panel_in, bg=PANEL_BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="u")
        grid.grid_columnconfigure(1, weight=1, uniform="u")

        # üst label font (bold)
        try:
            label_font = tkfont.nametofont("TkDefaultFont").copy()
            label_font.configure(weight="bold")
        except Exception:
            label_font = None

        def _wrap_select(box):
            """
            Input'taki select wrapper ile aynı:
            dışına CTkFrame (border + radius) koyuyoruz,
            içine tk.Frame + (değer label) + (chevron)
            """
            wrapper = ctk.CTkFrame(
                box,
                fg_color=SELECT_BG,
                border_color=SELECT_BORDER,
                border_width=SELECT_BORDER_W,
                corner_radius=SELECT_RADIUS
            )
            wrapper.grid(row=1, column=0, sticky="ew")
            wrapper.grid_columnconfigure(0, weight=1)

            inner = tk.Frame(wrapper, bg=SELECT_BG)
            inner.pack(fill="x", padx=10, pady=8)

            inner.grid_columnconfigure(0, weight=1)
            inner.grid_columnconfigure(1, weight=0)

            value_parent = tk.Frame(inner, bg=SELECT_BG)
            value_parent.grid(row=0, column=0, sticky="ew")

            icon_lbl = None
            if self._chevron_down_icon is not None:
                icon_lbl = tk.Label(inner, image=self._chevron_down_icon, bg=SELECT_BG)
                icon_lbl.grid(row=0, column=1, sticky="e", padx=(8, 0))

            return value_parent, icon_lbl, wrapper

        def _make_dropdown(parent, icon_lbl, wrapper, values, variable, key):
            """
            Input'taki _make_dropdown ile aynı custom select:
            - Label textvariable
            - tk.Menu popup
            """
            # değer label
            lbl = tk.Label(
                parent,
                textvariable=variable,
                bg=SELECT_BG,
                fg="#111827",
                anchor="w"
            )
            lbl.pack(fill="x")

            # Menü font
            try:
                base_font = tkfont.nametofont("TkDefaultFont")
                menu_font = base_font.copy()
                menu_font.configure(size=max(base_font.cget("size"), 9))
            except Exception:
                menu_font = None

            menu = tk.Menu(
                self.parent_frame,
                tearoff=0,
                bg="#FFFFFF",
                fg="#111827",
                activebackground="#F3F4F6",
                activeforeground="#111827",
                relief="solid",
                bd=1,
                font=menu_font
            )

            # Menü genişliği wrapper'a yakın olsun (padding ile)
            try:
                wrapper.update_idletasks()
                wrapper_px = wrapper.winfo_width()
            except Exception:
                wrapper_px = 0

            try:
                f = menu_font or tkfont.nametofont("TkDefaultFont")
                char_px = max(f.measure("0"), 7)
            except Exception:
                char_px = 8

            min_chars = int(wrapper_px / char_px) if wrapper_px else 0
            labels = [str(v) for v in values]
            max_label_len = max((len(s) for s in labels), default=0)
            target_len = max(max_label_len + 4, min_chars)

            def _pad_label(s: str) -> str:
                pad = max(0, target_len - len(s))
                return s + (" " * pad)

            for v in labels:
                menu.add_command(
                    label=_pad_label(v),
                    command=lambda vv=v: (variable.set(vv), self._on_unit_change(None))
                )

            self._dropdown_menus[key] = menu

            def _open_menu(_e=None):
                try:
                    x = wrapper.winfo_rootx()
                    y = wrapper.winfo_rooty() + wrapper.winfo_height()
                    menu.tk_popup(x, y)
                finally:
                    try:
                        menu.grab_release()
                    except Exception:
                        pass

            wrapper.bind("<Button-1>", _open_menu)
            lbl.bind("<Button-1>", _open_menu)
            if icon_lbl is not None:
                icon_lbl.bind("<Button-1>", _open_menu)

            return lbl

        def field(parent, col, row, label_text, values, variable, key):
            box = tk.Frame(parent, bg=PANEL_BG)
            box.grid(
                row=row,
                column=col,
                sticky="ew",
                padx=(0, 10) if col == 0 else (10, 0),
                pady=6
            )
            box.grid_columnconfigure(0, weight=1)

            tk.Label(
                box,
                text=label_text,
                bg=PANEL_BG,
                fg=LABEL_COLOR,
                font=label_font,
                anchor="w"
            ).grid(row=0, column=0, sticky="w", pady=(0, 6))

            host, icon_lbl, wrapper = _wrap_select(box)
            return _make_dropdown(
                parent=host,
                icon_lbl=icon_lbl,
                wrapper=wrapper,
                values=values,
                variable=variable,
                key=key
            )

        # ==== Unit options ====
        unit_options = UnitConverter.create_unit_selection_options()
        acc_values = [opt["display_name"] for opt in unit_options["acceleration"]]
        disp_values = [opt["display_name"] for opt in unit_options["displacement"]]

        # Varsayılanlar (boşsa set et)
        if not (self.acceleration_unit_var.get() or "").strip():
            self.acceleration_unit_var.set("Yerçekimi İvmesi (g)")
        if not (self.displacement_unit_var.get() or "").strip():
            self.displacement_unit_var.set("Santimetre (cm)")

        # Sol: İvme birimi
        field(
            grid, 0, 0,
            "İVME BİRİMİ",
            values=acc_values,
            variable=self.acceleration_unit_var,
            key="unit_acc"
        )

        # Sağ: Yerdeğiştirme
        field(
            grid, 1, 0,
            "YERDEĞİŞTİRME",
            values=disp_values,
            variable=self.displacement_unit_var,
            key="unit_disp"
        )
        
        if not hasattr(self, "unit_info_label"):
            self.unit_info_label = tk.Label(
                content,                 # dış kartın content alanına koy
                text="",
                bg=BG,
                fg="#9CA3AF",
                anchor="w"
            )
            # gizli başlasın
            self._unit_info_visible = False

    
    def _on_unit_change(self, event=None):
        """Birim değiştirildiğinde çağrılır"""
        # Aktif birim kodlarını al
        acc_code = self._get_unit_code_from_display(self.acceleration_unit_var.get(), 'acceleration')
        disp_code = self._get_unit_code_from_display(self.displacement_unit_var.get(), 'displacement')
        
        # Doğru birim simgelerini al
        acc_unit_info = UnitConverter.get_unit_info('acceleration', acc_code)
        acc_symbol = acc_unit_info.get('symbol', acc_code)
        
        disp_unit_info = UnitConverter.get_unit_info('displacement', disp_code)
        disp_symbol = disp_unit_info.get('symbol', disp_code)
        
        # Unit info etiketini güncelle
        if acc_code != 'g' or disp_code != 'cm':
            self.unit_info_label.config(
                text=f"⚡ Seçili birimler: {acc_symbol} (İvme), {disp_symbol} (Yerdeğiştirme) - Hesaplanacak veriler bu birimlerde gösterilecek.",
                foreground='blue'
            )
            if not self._unit_info_visible:
                self.unit_info_label.pack(pady=(5, 0))
                self._unit_info_visible = True
        else:
            if self._unit_info_visible:
                self.unit_info_label.pack_forget()
                self._unit_info_visible = False
        
        # Ana pencereyi birim değişikliğinden haberdar et
        if self.unit_change_callback:
            self.unit_change_callback(acc_code, disp_code)
    
    def _get_unit_code_from_display(self, display_name, unit_type):
        """Display adından unit kod'unu çıkarır"""
        unit_options = UnitConverter.create_unit_selection_options()
        options = unit_options.get(unit_type, [])
        
        for option in options:
            if option['display_name'] == display_name:
                return option['code']
        
        default_code = 'g' if unit_type == 'acceleration' else 'cm'
        return default_code
    
    def _create_action_buttons(self):

        actions = ttk.LabelFrame(self.parent_frame, text="İşlemler", padding=(10, 8))
        actions.pack(fill="x", pady=(6, 0))

        # Mevcut renk hissi: beyaz + ince border (senin screenshot gibi)
        BTN_BG = "#FFFFFF"
        HOVER_BG = "#F3F4F6"      # hoverda hafif gri (renk mantığı aynı)
        BORDER = "#D1D5DB"
        FG = "#111827"

        try:
            f = tkfont.nametofont("TkDefaultFont").copy()
            f.configure(size=f.cget("size"))  # aynı kalsın
        except Exception:
            f = None

        def make_btn(text, icon):
            b = RoundedButton(
                actions,
                text=text,
                image=icon if icon else None,
                height=44,            # ttk buton yüksekliği hissi
                radius=8,             # köşe yumuşaklığı (istersen 10-12 yap)
                btn_bg=BTN_BG,
                hover_bg=HOVER_BG,
                fg=FG,
                font=f,
                canvas_bg=BTN_BG,     # içerisi beyaz kalsın
                border_color=BORDER,
                border_width=1
            )
            b.pack(fill="x", pady=2)
            b.configure(state="disabled")
            return b

        self.show_map_btn = make_btn("Haritada Göster", self.map_icon)
        self.report_btn = make_btn("Rapor Oluştur", self.report_icon)
        self.save_graph_btn = make_btn("Grafikleri Kaydet", self.save_icon)
        self.peer_btn = make_btn("PEER Kullanıcı Tanımlı Spektrum (CSV)", self.peer_export_icon)

        # Kısayollar butonu kaldırıldı; yalnızca ana penceredeki "? Kısayollar" bağlantısı kullanılacak
    
    def bind_load_command(self, command):
        """Dosya yükleme komutunu bağlar"""
        self.load_command = command
        self.load_button.config(command=command)
    
    def bind_calculation_command(self, command):
        """Hesaplama komutunu bağlar"""
        self.calculation_command = command
        self.hesapla_button.config(command=command)
    
    def bind_map_command(self, command):
        """Harita komutunu bağlar"""
        self.map_command = command
        self._map_cmd = command
        if hasattr(self, 'show_map_btn'):
            self.show_map_btn.config(command=command)
    
    def bind_save_command(self, command):
        """Kaydetme komutunu bağlar"""
        self.save_command = command
        self._save_cmd = command
        if hasattr(self, 'save_graph_btn'):
            self.save_graph_btn.config(command=command)
    
    def bind_report_command(self, command):
        """Rapor oluşturma komutunu bağlar"""
        self.report_command = command
        self._report_cmd = command
        if hasattr(self, 'report_btn'):
            self.report_btn.config(command=command)
    
    def bind_peer_export_command(self, command):
        """PEER kullanıcı tanımlı spektrum aktarım komutunu bağlar"""
        self.peer_export_command = command
        self._peer_cmd = command
        if hasattr(self, 'peer_btn'):
            self.peer_btn.config(command=command)

    
    def bind_unit_change_callback(self, callback):
        """Birim değişikliği callback'ini bağlar"""
        self.unit_change_callback = callback
    
    def get_input_parameters(self):
        """Girdi parametrelerini döndürür"""
        return {
            "lat": self.enlem_var.get(),
            "lon": self.boylam_var.get(),
            "earthquake_level": self.dd_var.get().split(' ')[0],  # DD-2 gibi
            "soil_class": self.zemin_var.get().split(' ')[0]      # ZC gibi
        }

    def get_spectrum_options(self):
        """Spektrum seçeneklerini döndürür"""
        return {
            "horizontal": self.opt_horizontal.get(),
            "vertical": self.opt_vertical.get(),
            "displacement": self.opt_disp.get(),
            "log_period": self.logT_var.get(),
            "reference_periods": self.ref_periods_var.get(),  # virgülle ayrılmış metin
        }

    def _parse_ref_lines(self, text):
        """Kullanıcıdan alınan T çizgisi metnini float listesine çevirir"""
        try:
            if not text:
                return []
            # Virgül veya boşluk ayırıcıları destekle
            parts = [p.strip() for p in text.replace(';', ',').replace(' ', ',').split(',') if p.strip()]
            values = []
            for p in parts:
                try:
                    v = float(p)
                    if v >= 0:
                        values.append(v)
                except Exception:
                    continue
            # Tekrarlananları sıralı ve benzersiz yap
            return sorted(list(set(values)))
        except Exception:
            return []

    def _validate_ref_periods(self, proposed: str) -> bool:
        """Referans periyot giriş validasyonu: rakam, nokta, virgül, boşluk izinli"""
        allowed = set("0123456789., ")
        return all((ch in allowed) for ch in proposed)

    def _attach_tooltip(self, widget, text: str):
        """Web stili: Beyaz arkaplan, gri border ve Poppins fontuyla tooltip"""
        import tkinter as tk  # tk'nın erişilebilir olduğundan emin olun
        
        try:
            tooltip_data = {'win': None}

            def show_tip(event=None):
                if tooltip_data['win'] is not None:
                    return
                try:
                    # Konumlandırma
                    x = widget.winfo_rootx() + 20
                    y = widget.winfo_rooty() + widget.winfo_height() + 5
                    
                    # Pencere oluşturma
                    win = tk.Toplevel(widget)
                    win.wm_overrideredirect(True)
                    win.wm_geometry(f"+{x}+{y}")
                    
                    # Dış çerçeve (Gri border burada sağlanıyor)
                    # highlightthickness border kalınlığını, highlightbackground rengini belirler
                    container = tk.Frame(
                        win, 
                        bg="#FFFFFF", 
                        highlightbackground="#D1D5DB", 
                        highlightthickness=1,
                        padx=10, 
                        pady=8
                    )
                    container.pack()

                    # Metin (Poppins font ve beyaz bg)
                    label = tk.Label(
                        container,
                        text=text,
                        justify="left",
                        bg="#FFFFFF",
                        fg="#374151",
                        font=("Poppins", 8),
                        wraplength=400
                    )
                    label.pack()
                    
                    tooltip_data['win'] = win
                except Exception:
                    pass

            def hide_tip(event=None):
                try:
                    if tooltip_data['win'] is not None:
                        tooltip_data['win'].destroy()
                        tooltip_data['win'] = None
                except Exception:
                    tooltip_data['win'] = None

            widget.bind("<Enter>", show_tip)
            widget.bind("<Leave>", hide_tip)
            
        except Exception:
            pass
    
    def get_unit_settings(self):
        """Mevcut birim ayarlarını döndürür"""
        acc_code = self._get_unit_code_from_display(self.acceleration_unit_var.get(), 'acceleration')
        disp_code = self._get_unit_code_from_display(self.displacement_unit_var.get(), 'displacement')
        
        return {
            "acceleration_unit": acc_code,
            "displacement_unit": disp_code
        }
    
    def set_results(self, results_dict):
        """Hesaplama sonuçlarını ayarlar"""
        self.ss_var.set(f"{results_dict.get('ss', 0):.3f}")
        self.s1_var.set(f"{results_dict.get('s1', 0):.3f}")
        self.fs_var.set(f"{results_dict.get('fs', 0):.3f}")
        self.f1_var.set(f"{results_dict.get('f1', 0):.3f}")
        self.sds_var.set(f"{results_dict.get('SDS', 0):.3f}")
        self.sd1_var.set(f"{results_dict.get('SD1', 0):.3f}")
    
    def update_file_status(self, status_text, color="gray"):
        """Dosya durumunu günceller: kutu rengi + ikon + metin"""

        # 1) Metindeki emoji ikonları temizle (isteğe bağlı ama önerilir)
        status_text = (status_text or "").replace("✅", "").replace("❌", "").strip()
        self.afad_dosya_durum_var.set(status_text)

        c = (color or "").lower().strip()

        if c in ("green", "success"):
            bg = "#EAF7EE"
            border = "#B7E4C7"
            fg = "#1F7A3F"
            icon = "✓"
        elif c in ("red", "error"):
            bg = "#FDECEC"
            border = "#F5C2C7"
            fg = "#B42318"
            icon = "!"
        else:
            bg = "#F1F5F9"
            border = "#CBD5E1"
            fg = "#334155"
            icon = "i"
            
        self.afad_status_box.set_style(bg=bg, border=border, fg=fg, icon_text=icon)

        # 2) Yeni UI (tk.Frame + tk.Label) varsa burayı kullan
        if hasattr(self, "afad_status_box") and hasattr(self, "afad_status_icon") and hasattr(self, "afad_status_text"):
            # bg + border
            self.afad_status_box.configure(bg=bg)
            self.afad_status_box.configure(highlightbackground=border, highlightcolor=border)

            # ikon
            self.afad_status_icon.configure(text=icon, bg=bg, fg=fg)

            # metin
            self.afad_status_text.configure(bg=bg, fg=fg)

            # wrap
            try:
                w = self.afad_status_box.winfo_width()
                self.afad_status_text.configure(wraplength=max(200, w - 60))
            except Exception:
                pass

            # bazı sistemlerde border hemen güncellenmiyor, zorla refresh
            try:
                self.afad_status_box.update_idletasks()
            except Exception:
                pass
            return

        # 3) Eski ttk label fallback (kalmışsa)
        if hasattr(self, "afad_dosya_durum_label"):
            self.afad_dosya_durum_label.config(foreground=fg, wraplength=0, anchor="w", justify="left")
            try:
                self._sync_file_status_wraplength()
            except Exception:
                pass
            
    def _sync_file_status_wraplength(self) -> None:
        """Durum etiketinin sarma ayarini kapatir."""
        try:
            self.afad_dosya_durum_label.configure(wraplength=0)
        except Exception:
            pass

    def enable_calculation_button(self):
        """Hesaplama butonunu etkinleştirir"""
        self.hesapla_button.config(state="normal")
    
    def disable_calculation_button(self):
        """Hesaplama butonunu devre dışı bırakır"""
        self.hesapla_button.config(state="disabled")
    
    def enable_map_button(self):
        """Harita tuşunu aktif eder"""
        if hasattr(self, 'show_map_btn'):
            self.show_map_btn.config(state="normal")
            print("🗺️ Harita tuşu aktif edildi")
        # Progress gizli
        if hasattr(self, 'map_progress'):
            self.map_progress.grid_remove()
    
    def disable_map_button(self):
        """Harita tuşunu devre dışı bırakır"""
        if hasattr(self, 'show_map_btn'):
            self.show_map_btn.config(state="disabled")
            print("🗺️ Harita tuşu devre dışı bırakıldı")
        # Progress göster
        if hasattr(self, 'map_progress'):
            try:
                self.map_progress.grid()
                self.map_progress.start(10)
            except Exception:
                pass
    
    def enable_report_button(self):
        """Rapor tuşunu aktif eder"""
        if hasattr(self, 'report_btn'):
            self.report_btn.config(state="normal")
            print("📄 Rapor tuşu aktif edildi")
        # Progress gizle
        if hasattr(self, 'report_progress'):
            try:
                self.report_progress.stop()
            except Exception:
                pass
            self.report_progress.grid_remove()
        if hasattr(self, 'peer_btn'):
            # Spektrum sonrası PEER aktarımını da aktif edebiliriz
            try:
                self.peer_btn.config(state="normal")
            except Exception:
                pass
    
    def enable_save_button(self):
        """Grafik kaydet tuşunu aktif eder"""
        if hasattr(self, 'save_graph_btn'):
            self.save_graph_btn.config(state="normal")
            print("💾 Grafik kaydet tuşu aktif edildi")
    
    def disable_save_button(self):
        """Grafik kaydet tuşunu devre dışı bırakır"""
        if hasattr(self, 'save_graph_btn'):
            self.save_graph_btn.config(state="disabled")
            print("💾 Grafik kaydet tuşu devre dışı bırakıldı")
    
    def disable_report_button(self):
        """Rapor tuşunu devre dışı bırakır"""
        if hasattr(self, 'report_btn'):
            self.report_btn.config(state="disabled")
            print("📄 Rapor tuşu devre dışı bırakıldı")
        # Progress göster
        if hasattr(self, 'report_progress'):
            try:
                self.report_progress.grid()
                self.report_progress.start(10)
            except Exception:
                pass
    
    def clear_results(self):
        """Sonuç alanlarını temizler"""
        for var in [self.ss_var, self.s1_var, self.fs_var, 
                   self.f1_var, self.sds_var, self.sd1_var]:
            var.set("")
        
                # Sonuçlar temizlendi - harita ve rapor tuşlarını devre dışı bırak
        self.disable_map_button()
        self.disable_report_button()
        self.disable_save_button()
        if hasattr(self, 'peer_export_button'):
            self.peer_export_button.config(state="disabled")
