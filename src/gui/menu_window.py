"""
Ana menü penceresi
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import logging
from ..config.styles import BG_COLOR, FONTS, WINDOW_SIZES

logger = logging.getLogger("tbdyspektrum")

class MenuWindow:
    """Ana menü sınıfı"""
    
    def __init__(self, root: tk.Tk) -> None:
        """
        Args:
            root: Tkinter ana penceresi
        """
        self.root = root
        # Açık spektrum penceresi bayrağı (çoklu açılışı engellemek için)
        self._spektrum_open = False
        self.setup_window()
        self.create_widgets()
        # Varsayılan merkezleme
        self.center_window()
        # Kullanıcı tercihli geometriyi yükle
        loaded = self._load_geometry()
        
        # Ana pencereyi göster (gerekliyse)
        try:
            if self.root.state() in ("withdrawn", "iconic"):
                self.root.deiconify()
        except Exception:
            # Bazı WM'lerde state sorgusu hata verebilir, güvenli şekilde geç
            self.root.deiconify()

        # Gösterimden sonra: eğer kullanıcı geometrisi yüklenmediyse tekrar merkezle
        if not loaded:
            try:
                self.center_window()
            except Exception:
                pass

        # Çıkışta geometriyi kaydet (kalıcılık) - tekil kayıt koruması
        try:
            import atexit
            if not getattr(self, "_atexit_registered", False):
                atexit.register(self._save_geometry)
                self._atexit_registered = True
        except Exception:
            pass
    
    def setup_window(self):
        """Pencere ayarlarını yapar"""
        self.root.title("TBDY-2018 Analiz Araçları")
        self.root.geometry(WINDOW_SIZES['menu'])
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)
    
    def create_widgets(self):
        """Ana menü arayüzünü oluşturur"""
        # Ana başlık
        self.create_title_section()
        
        # Menü butonları
        self.create_menu_buttons()
        
        # Alt bilgi
        self.create_footer()
    
    def create_title_section(self):
        """Başlık bölümünü oluşturur"""
        baslik_frame = ttk.Frame(self.root, padding="20")
        baslik_frame.pack(fill="x", pady=(20, 0))
        
        # Ana başlık
        baslik_label = ttk.Label(
            baslik_frame,
            text="TBDY-2018",
            style="Title.TLabel",
            takefocus=False
        )
        baslik_label.pack()
        
        # Alt başlık
        alt_baslik_label = ttk.Label(
            baslik_frame, 
            text="Türkiye Bina Deprem Yönetmeliği Analiz Araçları", 
            font=FONTS['subtitle'],
            takefocus=False
        )
        alt_baslik_label.pack(pady=(5, 0))
    
    def create_menu_buttons(self):
        """Menü butonlarını oluşturur"""
        menu_frame = ttk.Frame(self.root, padding="40")
        menu_frame.pack(fill="both", expand=True)
        
        # Deprem Yer Hareketi Spektrumları butonu
        spektrum_button = ttk.Button(
            menu_frame, 
            text="🌊 Deprem Yer Hareketi Spektrumları", 
            command=self.open_spektrum_module,
            style="Accent.TButton",
            underline=0
        )
        spektrum_button.pack(fill="x", pady=10, ipady=15)
        # Odak: Return ile tetiklenebilir olsun
        try:
            spektrum_button.focus_set()
        except Exception:
            pass
        # Mnemonik: Alt+D ile tetikle ve olayı tüket
        try:
            self.spektrum_button = spektrum_button
            def _invoke_and_break(btn):
                def _h(e):
                    btn.invoke()
                    return "break"
                return _h
            self.root.bind_all("<Alt-d>", _invoke_and_break(self.spektrum_button))
            self.root.bind_all("<Alt-D>", _invoke_and_break(self.spektrum_button))
        except Exception:
            pass
    
    def create_footer(self):
        """Alt bilgi bölümünü oluşturur"""
        info_frame = ttk.Frame(self.root, padding="10")
        info_frame.pack(fill="x", side="bottom", anchor="se")
        
        footer_text = "Emre Haberdar"

        info_label = ttk.Label(
            info_frame,
            text=footer_text,
            style="Footer.TLabel",
            takefocus=False
        )
        info_label.pack(side="right", anchor="se")

    # ------------------------------------------------------------------
    # Geometri kalıcılığı yardımcıları
    # ------------------------------------------------------------------
    def _settings_path(self) -> str:
        try:
            home = os.path.expanduser("~")
            settings_dir = os.path.join(home, ".tbdyspektrum")
            os.makedirs(settings_dir, exist_ok=True)
            return os.path.join(settings_dir, "settings.json")
        except Exception:
            # Yedek: proje kökü
            module_dir = os.path.dirname(__file__)
            src_dir = os.path.dirname(module_dir)
            project_root = os.path.dirname(src_dir)
            return os.path.join(project_root, "settings.json")

    def _load_geometry(self) -> bool:
        path = self._settings_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                geom = data.get("menu_geometry")
                if isinstance(geom, str) and geom:
                    self.root.geometry(geom)
                    return True
        except Exception:
            pass
        return False

    def _save_geometry(self) -> None:
        path = self._settings_path()
        try:
            geom = self.root.wm_geometry()
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data["menu_geometry"] = geom
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_window_geometry(self, key: str, win: tk.Toplevel) -> bool:
        """Belirtilen anahtar ile pencere geometrisini yükle."""
        path = self._settings_path()
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                geom = data.get(key)
                if isinstance(geom, str) and geom:
                    win.geometry(geom)
                    return True
        except Exception:
            pass
        return False

    def _save_window_geometry(self, key: str, win: tk.Toplevel) -> None:
        """Belirtilen anahtar ile pencere geometrisini kaydet."""
        path = self._settings_path()
        try:
            geom = win.wm_geometry()
            data = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                except Exception:
                    data = {}
            data[key] = geom
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def center_window(self):
        """Pencereyi ekranın ortasına yerleştirir"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def open_spektrum_module(self) -> None:
        """Spektrum modülünü açar"""
        if getattr(self, "_spektrum_open", False):
            return
        self._spektrum_open = True
        # Butonu pasifleştir (isteğe bağlı UX)
        try:
            if hasattr(self, "spektrum_button") and isinstance(self.spektrum_button, ttk.Button):
                self.spektrum_button.configure(state='disabled')
        except Exception:
            pass

        win = None
        try:
            # Ana menü penceresini gizle
            self.root.withdraw()

            # Spektrum modülü penceresini oluştur - lazy import
            from .main_window import MainWindow

            win = tk.Toplevel(self.root)
            # Pencere başlığı ve (varsa) simge
            try:
                win.title("Spektrum Analizi")
                # Icon ayarı (opsiyonel)
                try:
                    module_dir = os.path.dirname(__file__)
                    src_dir = os.path.dirname(module_dir)
                    project_root = os.path.dirname(src_dir)
                    icon_path = os.path.join(project_root, "icons", "earthquake_01.png")
                    if os.path.exists(icon_path):
                        win._icon_img = tk.PhotoImage(file=icon_path)
                        win.iconphoto(True, win._icon_img)
                    else:
                        logger.debug("İkon bulunamadı: %s", icon_path)
                except Exception as ex:
                    logger.exception("Pencere simgesi yüklenemedi: %s", ex)
            except Exception:
                pass
            self._load_window_geometry("spektrum_geometry", win)
            self.spektrum_window = win
            self.spektrum_app = MainWindow(win)

            # Modal/odak ve görünürlük sırası
            try:
                win.update_idletasks()
                # Kök görünür ise transient uygula; gizliyken bazı WM'lerde görünürlük sorunları olabilir
                try:
                    if self.root.state() == "normal":
                        win.transient(self.root)
                except Exception:
                    pass
                # Ön plana al ve odak ver
                try:
                    win.deiconify()
                except Exception:
                    pass
                try:
                    win.lift()
                    win.focus_force()
                except Exception:
                    pass
                # Kısa süre topmost ile öne it
                try:
                    win.attributes("-topmost", True)
                    win.after(200, lambda: win.attributes("-topmost", False))
                except Exception:
                    pass
                # En sonda grab uygula
                try:
                    win.grab_set()
                except Exception:
                    pass
            except Exception:
                pass

            def _on_close():
                try:
                    # Geometriyi kaydet
                    try:
                        self._save_window_geometry("spektrum_geometry", win)
                    except Exception:
                        pass
                    win.grab_release()
                except Exception:
                    pass
                try:
                    win.destroy()
                finally:
                    self._spektrum_open = False
                    self.spektrum_window = None
                    self.spektrum_app = None
                    self.root.deiconify()
                    try:
                        self.root.focus_force()
                    except Exception:
                        pass
                    # Butonu yeniden etkinleştir
                    try:
                        if hasattr(self, "spektrum_button") and isinstance(self.spektrum_button, ttk.Button):
                            self.spektrum_button.configure(state='normal')
                    except Exception:
                        pass

            win.protocol("WM_DELETE_WINDOW", _on_close)
            # Hızlı kapanış için ESC bağla ve olayı tüket
            try:
                win.bind("<Escape>", lambda e: (_on_close(), "break"))
            except Exception:
                pass

        except Exception as e:
            # Eğer bir pencere açıldıysa temizle
            try:
                if win is not None and win.winfo_exists():
                    try:
                        try:
                            self._save_window_geometry("spektrum_geometry", win)
                        except Exception:
                            pass
                        win.grab_release()
                    except Exception:
                        pass
                    try:
                        win.destroy()
                    except Exception:
                        pass
            finally:
                self._spektrum_open = False
                self.spektrum_window = None
                self.spektrum_app = None
                self.root.deiconify()
                # Butonu yeniden etkinleştir
                try:
                    if hasattr(self, "spektrum_button") and isinstance(self.spektrum_button, ttk.Button):
                        self.spektrum_button.configure(state='normal')
                except Exception:
                    pass
            messagebox.showerror("Hata", f"Spektrum modülü açılırken hata oluştu:\n{e}", parent=self.root)
    
    def on_spektrum_close(self, win: tk.Toplevel) -> None:
        """Belirtilen spektrum penceresini kapatır ve ana menüyü geri getirir."""
        try:
            try:
                win.grab_release()
            except Exception:
                pass
            win.destroy()
        finally:
            self._spektrum_open = False
            self.spektrum_window = None
            self.spektrum_app = None
            self.root.deiconify()
            try:
                self.root.focus_force()
            except Exception:
                pass
