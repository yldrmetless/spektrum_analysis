"""
tidy-2018 Spektrum Analiz Araçları - Ana Giriş Noktası

Bu dosya modüler yapıyı koordine eder ve uygulamayı başlatır.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import logging
import argparse
import locale
from logging.handlers import RotatingFileHandler
import ctypes
from ctypes import wintypes
import tkinter.font as tkfont
import traceback

FR_PRIVATE = 0x10

def load_private_font_windows(font_path: str) -> bool:
    try:
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        AddFontResourceExW = gdi32.AddFontResourceExW
        AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        AddFontResourceExW.restype = wintypes.INT

        added = AddFontResourceExW(font_path, FR_PRIVATE, None)
        if added > 0:
            user32.SendMessageW(0xFFFF, 0x001D, 0, 0)  # WM_FONTCHANGE
            return True
        return False
    except Exception:
        return False


def apply_global_font(root: tk.Tk, family="Poppins", size=9):
    # Tk named fonts
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        try:
            f = tkfont.nametofont(name)
            f.configure(family=family, size=size)
        except Exception:
            pass

    # ttk defaults
    try:
        style = ttk.Style(master=root)
        style.configure(".", font=(family, size))
        style.configure("TLabelframe.Label", font=(family, size, "bold"))
    except Exception:
        pass



# Modül yolunu ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
# Basit logging yapılandırması (en erken aşamada)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("tbdyspektrum")

try:
    from src.gui.menu_window import MenuWindow
    from src.config.styles import configure_ttk_styles
except ImportError as e:
    logger.exception("Modül import hatası: %s", e)
    logger.error("Lütfen src klasörünün doğru konumda olduğundan emin olun.")
    sys.exit(1)
def _force_utf8_stdio():
    # Ensure stdout/stderr use UTF-8 so Turkish characters show correctly in Windows console.
    try:
        if sys.platform == "win32":
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass
            try:
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass
            try:
                locale.setlocale(locale.LC_ALL, "tr_TR.UTF-8")
            except Exception:
                pass
    except Exception:
        pass
def configure_logging(log_level: str = "INFO") -> None:
    """Konsol ve dosyaya log yazımı için kök logger'ı yapılandır.

    Var olan handler'lar olsa dahi seviye ve format güncellenir.
    """
    level_name = str(log_level).upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Var olan handler'ları güncelle
    if root_logger.handlers:
        for h in list(root_logger.handlers):
            try:
                h.setLevel(level)
                h.setFormatter(formatter)
            except Exception:
                pass
    else:
        # Konsol handler ekle
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Döndürmeli dosya handler'ı: ~/.tbdyspektrum/logs/app.log
    desired_file_handler_path = None
    try:
        home_dir = os.path.expanduser("~")
        app_log_dir = os.path.join(home_dir, ".tbdyspektrum", "logs")
        os.makedirs(app_log_dir, exist_ok=True)
        desired_file_handler_path = os.path.join(app_log_dir, "app.log")
    except Exception:
        desired_file_handler_path = None

    # Mevcut dosya handler'larını temizle (farklı konumlara yazıyorsa)
    try:
        for h in list(root_logger.handlers):
            if isinstance(h, logging.FileHandler):
                try:
                    if (desired_file_handler_path is None) or (getattr(h, 'baseFilename', None) != desired_file_handler_path):
                        root_logger.removeHandler(h)
                        try:
                            h.close()
                        except Exception:
                            pass
                except Exception:
                    pass
    except Exception:
        pass

    # İstenen dosya handler'ı ekle
    if desired_file_handler_path is not None:
        try:
            rotating = RotatingFileHandler(
                desired_file_handler_path,
                maxBytes=5 * 1024 * 1024,
                backupCount=5,
                encoding="utf-8"
            )
            rotating.setLevel(level)
            rotating.setFormatter(formatter)
            root_logger.addHandler(rotating)
        except Exception:
            # Dosyaya yazılamıyorsa sessizce geç, konsol yetersiz kalmasın
            pass

def configure_windows_dpi_awareness():
    """Windows'ta DPI farkındalığını Tk penceresi oluşturulmadan önce ayarla.

    Sıralı denemeler:
    1) user32.SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)
    2) shcore.SetProcessDpiAwareness(2)  # Per-Monitor
    3) shcore.SetProcessDpiAwareness(1)  # System
    4) user32.SetProcessDPIAware()       # Eski API
    """
    if sys.platform != 'win32':
        return
    # Gerekli sembolleri import et; bu adım başarısızsa sessiz çık
    try:
        from ctypes import windll, wintypes, c_void_p
    except Exception:
        return

    # WinAPI imzalarını parça parça ata; herhangi bir adımın hatası diğerlerini engellemesin
    try:
        windll.user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        windll.user32.SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
    except Exception:
        pass
    try:
        windll.shcore.SetProcessDpiAwareness.restype = wintypes.HRESULT
        windll.shcore.SetProcessDpiAwareness.argtypes = [wintypes.INT]
    except Exception:
        pass
    try:
        windll.user32.SetProcessDPIAware.restype = wintypes.BOOL
        windll.user32.SetProcessDPIAware.argtypes = []
    except Exception:
        pass

    E_ACCESSDENIED = 0x80070005  # Zaten ayarlıysa dönebilir

    success = False
    # 1) Per-Monitor v2 (Windows 10 ve sonrası)
    try:
        DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = c_void_p(-4)
        success = bool(
            windll.user32.SetProcessDpiAwarenessContext(
                DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            )
        )
    except Exception:
        pass
    # 2) Per-Monitor (2)
    if not success:
        try:
            hr = windll.shcore.SetProcessDpiAwareness(2)
            success = (hr == 0 or hr == E_ACCESSDENIED)
        except Exception:
            pass
    # 3) System (1)
    if not success:
        try:
            hr = windll.shcore.SetProcessDpiAwareness(1)
            success = (hr == 0 or hr == E_ACCESSDENIED)
        except Exception:
            pass
    # 4) Eski API
    if not success:
        try:
            success = bool(windll.user32.SetProcessDPIAware())
        except Exception:
            pass

def set_windows_titlebar_color(window, background="#FFFFFF", text="#000000"):
    """Windows başlık çubuğu renkleri için DWM API'sini kullan (destekleniyorsa)."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll, wintypes, byref, sizeof
    except Exception:
        return
    try:
        hwnd = window.winfo_id()
    except Exception:
        return

    def _hex_to_colorref(hex_color: str) -> int:
        hex_color = str(hex_color).strip()
        if hex_color.startswith("#"):
            hex_color = hex_color[1:]
        if len(hex_color) != 6:
            raise ValueError("Renk #RRGGBB formatında olmalı")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return r | (g << 8) | (b << 16)  # COLORREF: 0x00BBGGRR

    DWMWA_CAPTION_COLOR = 35
    DWMWA_TEXT_COLOR = 36

    try:
        bg = wintypes.DWORD(_hex_to_colorref(background))
        windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_CAPTION_COLOR,
            byref(bg),
            sizeof(bg)
        )
    except Exception:
        pass

    try:
        fg = wintypes.DWORD(_hex_to_colorref(text))
        windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_TEXT_COLOR,
            byref(fg),
            sizeof(fg)
        )
    except Exception:
        pass

def on_tk_error(exc, val, tb):
    """Tkinter callback istisnalarını yakala ve logla."""
    try:
        logger.exception("Tkinter callback error", exc_info=(exc, val, tb))
        # Kullanıcıya hatayı bildir
        messagebox.showerror("Hata", f"Beklenmeyen bir hata:\n{val}")
    except Exception:
        # UI kapalıysa veya messagebox başarısızsa en azından sessizce geç
        pass

def make_tk_error_handler(parent):
    """MessageBox ebeveynini bağlayan Tk hata geri çağrısı üreticisi."""
    def _handler(exc, val, tb):
        logger.exception("Tkinter callback error", exc_info=(exc, val, tb))
        try:
            messagebox.showerror("Hata", f"Beklenmeyen bir hata:\n{val}", parent=parent)
        except Exception:
            pass
    return _handler

def main() -> int:
    """Ana uygulama fonksiyonu

    Returns:
        int: 0 başarı, 1 hata
    """
    try:
        _force_utf8_stdio()
        # Argümanlar
        parser = argparse.ArgumentParser(description="TBDY-2018 Spektrum Analiz Araçları")
        parser.add_argument("--log-level", dest="log_level", default="INFO", help="Log seviyesi: DEBUG, INFO, WARNING, ERROR, CRITICAL")
        parser.add_argument("--no-withdraw", dest="no_withdraw", action="store_true", help="Kök pencereyi gizleme")
        parser.add_argument("--safe-mode", dest="safe_mode", action="store_true", help="Güvenli mod: riskli/ileri özellikleri pasifleştir")
        args = parser.parse_args()

        # Log yapılandırması
        configure_logging(args.log_level)
        # DPI ayarları (Windows için) - Tk penceresi oluşturulmadan önce
        if not args.safe_mode:
            configure_windows_dpi_awareness()
        else:
            os.environ["TBDY_SAFE_MODE"] = "1"

        # Ana Tkinter penceresini oluÅŸtur
        root = tk.Tk()
        
        try:
            import customtkinter as ctk
            ctk.set_appearance_mode("light")  # zaten kullanıyorsan sorun yok
            ctk.set_default_color_theme("blue")
            ctk.deactivate_automatic_dpi_awareness()
        except Exception:
            pass
                
        if sys.platform == "win32":
            poppins_path = os.path.join(parent_dir, "fonts", "Poppins-Regular.ttf")
            ok = load_private_font_windows(poppins_path)
            logger.info("Poppins font yükleme: %s (%s)", ok, poppins_path)

        apply_global_font(root, family="Poppins", size=9)
        
        
        set_windows_titlebar_color(root, background="#FFFFFF", text="#000000")
        if not args.no_withdraw:
            root.withdraw()  # Ana pencereyi gizle
        # Tk callback hatalarını yakala (ebeveyn bağlayarak)
        root.report_callback_exception = make_tk_error_handler(root)
        
        # TTK stillerini yapılandır
        style = ttk.Style(master=root)
        configure_ttk_styles(style)
        
        style.configure("NoBorder.TLabelframe",
            background="#FFFFFF",
            borderwidth=0,
            relief="flat"
        )

        style.configure("NoBorder.TLabelframe.Label",
            background="#FFFFFF",
            foreground="#444444"
        )


        BG = "#F1F1F1"
        root.configure(bg=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", background=BG, foreground="#444444")
        
        # Ana menü penceresini oluştur ve çalıştır
        menu_app = MenuWindow(root)
        # Kapanış: MenuWindow bir Toplevel ise kapatıldığında uygulamayı sonlandır
        bound_close = False
        try:
            if hasattr(menu_app, "protocol") and callable(getattr(menu_app, "protocol")):
                menu_app.protocol("WM_DELETE_WINDOW", root.destroy)
                bound_close = True
                # Opsiyonel: görev çubuğunda tek pencere gibi dursun
                if hasattr(menu_app, "transient") and callable(getattr(menu_app, "transient")):
                    try:
                        menu_app.transient(root)
                    except Exception:
                        pass
        except Exception:
            pass
        if not bound_close:
            # Aksi halde doğrudan kök pencereye bağla
            try:
                root.protocol("WM_DELETE_WINDOW", root.destroy)
            except Exception:
                pass
        
        # Ana döngüyü başlat
        root.mainloop()
        return 0
    except Exception as e:
        logger.exception("Uygulama başlatılırken beklenmeyen hata: %s", e)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

