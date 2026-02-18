import ctypes
from ctypes import wintypes

FR_PRIVATE = 0x10
FR_NOT_ENUM = 0x20

def load_private_font_windows(font_path: str) -> bool:
    """
    Windows'a oturumluk (private) font yükler.
    Başarılıysa Tkinter artık font family adını görebilir.
    """
    try:
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32 = ctypes.WinDLL("user32", use_last_error=True)

        AddFontResourceExW = gdi32.AddFontResourceExW
        AddFontResourceExW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPVOID]
        AddFontResourceExW.restype = wintypes.INT

        added = AddFontResourceExW(font_path, FR_PRIVATE, None)
        if added > 0:
            # Font değişikliğini sistem mesajı olarak duyur
            user32.SendMessageW(0xFFFF, 0x001D, 0, 0)  # HWND_BROADCAST, WM_FONTCHANGE
            return True
        return False
    except Exception:
        return False