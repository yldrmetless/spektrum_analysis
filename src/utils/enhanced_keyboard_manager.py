"""
Gelişmiş klavye kısayol yönetimi
"""

import tkinter as tk
from typing import Dict, Callable, Optional, List
from dataclasses import dataclass

@dataclass
class KeyboardShortcut:
    """Klavye kısayolu veri sınıfı"""
    key_combination: str
    description: str
    callback: Callable
    context: str = "global"  # global, earthquake, spectrum, etc.
    enabled: bool = True

class EnhancedKeyboardManager:
    """Gelişmiş klavye kısayol yöneticisi"""
    
    def __init__(self, root_window: tk.Tk):
        """
        Args:
            root_window: Ana pencere
        """
        self.root = root_window
        self.shortcuts: Dict[str, KeyboardShortcut] = {}
        self.context_shortcuts: Dict[str, List[str]] = {}
        self.current_context = "global"
        
        # Varsayılan kısayolları kaydet
        self._register_default_shortcuts()
    
    def register_shortcut(self, key_combination: str, description: str, 
                         callback: Callable, context: str = "global") -> None:
        """
        Klavye kısayolu kaydeder
        
        Args:
            key_combination: Tuş kombinasyonu (örn: "Control-o", "Control-Shift-s")
            description: Açıklama
            callback: Çağrılacak fonksiyon
            context: Bağlam (global, earthquake, spectrum)
        """
        shortcut = KeyboardShortcut(
            key_combination=key_combination,
            description=description,
            callback=callback,
            context=context
        )
        
        self.shortcuts[key_combination] = shortcut
        
        # Context'e göre grupla
        if context not in self.context_shortcuts:
            self.context_shortcuts[context] = []
        self.context_shortcuts[context].append(key_combination)
        
        # Tkinter'a bind et (kombinasyonu doğrudan geçirerek, platform farklarını elimine eder)
        self.root.bind(
            f"<{key_combination}>",
            lambda event, kc=key_combination: self._invoke_shortcut(kc)
        )
        
        print(f"⌨️ Kısayol kaydedildi: {key_combination} - {description}")
    
    def _handle_shortcut(self, event):
        """Kısayol tuşu basıldığında çağrılır"""
        try:
            # Event'ten key combination'ı oluştur
            key_parts = []
            if event.state & 0x4:  # Control
                key_parts.append("Control")
            if event.state & 0x1:  # Shift
                key_parts.append("Shift")
            if event.state & 0x8:  # Alt
                key_parts.append("Alt")
            
            # Keysym ekle
            # Keysym'i normalize et (harfler küçük, özel tuşlar olduğu gibi)
            ks = event.keysym
            if ks and len(ks) == 1:
                ks = ks.lower()
            key_parts.append(ks)
            key_combination = "-".join(key_parts)
            
            # Kısayolu bul ve çalıştır
            return self._invoke_shortcut(key_combination)
            
        except Exception as e:
            print(f"❌ Kısayol hatası: {e}")
        
        return None

    def _invoke_shortcut(self, key_combination: str):
        """Kısayolu anahtar string üzerinden çağır (bağlam ve enable kontrolüyle)."""
        try:
            if key_combination in self.shortcuts:
                shortcut = self.shortcuts[key_combination]
                if shortcut.context == "global" or shortcut.context == self.current_context:
                    if shortcut.enabled:
                        print(f"⌨️ Kısayol çalıştırılıyor: {key_combination}")
                        shortcut.callback()
                        return "break"
        except Exception as e:
            print(f"❌ Kısayol çağırma hatası: {e}")
        return None
    
    def set_context(self, context: str) -> None:
        """Mevcut bağlamı değiştirir"""
        self.current_context = context
        print(f"⌨️ Kısayol bağlamı değiştirildi: {context}")
    
    def enable_shortcut(self, key_combination: str, enabled: bool = True) -> None:
        """Kısayolu etkinleştirir/devre dışı bırakır"""
        if key_combination in self.shortcuts:
            self.shortcuts[key_combination].enabled = enabled
            status = "etkinleştirildi" if enabled else "devre dışı bırakıldı"
            print(f"⌨️ Kısayol {status}: {key_combination}")
    
    def get_shortcuts_by_context(self, context: str) -> List[KeyboardShortcut]:
        """Belirtilen bağlamdaki kısayolları döndürür"""
        if context not in self.context_shortcuts:
            return []
        
        shortcuts = []
        for key_combination in self.context_shortcuts[context]:
            shortcuts.append(self.shortcuts[key_combination])
        
        return shortcuts
    
    def get_all_shortcuts(self) -> Dict[str, List[KeyboardShortcut]]:
        """Tüm kısayolları bağlamlarına göre gruplandırarak döndürür"""
        result = {}
        for context in self.context_shortcuts:
            result[context] = self.get_shortcuts_by_context(context)
        return result
    
    def show_shortcuts_help(self) -> None:
        """Kısayollar yardım penceresini gösterir"""
        try:
            # Yardım penceresi
            help_window = tk.Toplevel(self.root)
            help_window.title("⌨️ Klavye Kısayolları")
            help_window.geometry("600x500")
            help_window.resizable(True, True)
            help_window.grab_set()  # Modal
            
            # Ana frame
            main_frame = tk.Frame(help_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Başlık
            title_label = tk.Label(main_frame, text="⌨️ Klavye Kısayolları", 
                                  font=('Segoe UI', 14, 'bold'))
            title_label.pack(pady=(0, 20))
            
            # Notebook için context'ler
            from tkinter import ttk
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill="both", expand=True)
            
            # Her context için sekme
            context_title_map = {
                'global': 'Genel',
                'earthquake': 'Deprem Kayıtları',
                'spectrum': 'Spektrum Oluşturma',
                'plot': 'Grafikler',
            }
            for context, shortcuts in self.get_all_shortcuts().items():
                if not shortcuts:
                    continue
                
                # Context frame
                context_frame = tk.Frame(notebook)
                display_title = context_title_map.get(context, context.title())
                notebook.add(context_frame, text=display_title)
                
                # Scrollable text
                text_frame = tk.Frame(context_frame)
                text_frame.pack(fill="both", expand=True, padx=5, pady=5)
                
                text_widget = tk.Text(text_frame, wrap="word", font=('Courier New', 10))
                scrollbar = tk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)
                
                text_widget.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                
                # Kısayolları ekle
                for shortcut in shortcuts:
                    status = "✅" if shortcut.enabled else "❌"
                    key_display = shortcut.key_combination.replace("-", " + ")
                    text_widget.insert("end", f"{status} {key_display:<20} {shortcut.description}\n")
                
                text_widget.configure(state="disabled")  # Read-only
            
            # Kapat butonu
            close_button = tk.Button(main_frame, text="❌ Kapat", 
                                   command=help_window.destroy)
            close_button.pack(pady=(10, 0))
            
            # Pencereyi ortala
            help_window.transient(self.root)
            help_window.update_idletasks()
            x = (help_window.winfo_screenwidth() // 2) - (help_window.winfo_width() // 2)
            y = (help_window.winfo_screenheight() // 2) - (help_window.winfo_height() // 2)
            help_window.geometry(f"+{x}+{y}")
            
        except Exception as e:
            print(f"❌ Kısayollar yardım hatası: {e}")
            import tkinter.messagebox as msgbox
            msgbox.showerror("Hata", f"Kısayollar yardımı açılamadı:\n{str(e)}")
    
    def _register_default_shortcuts(self) -> None:
        """Varsayılan kısayolları kaydeder"""
        # Bu fonksiyon daha sonra main_window'dan çağrılacak
        pass
    
    def unregister_shortcut(self, key_combination: str) -> None:
        """Kısayolu kaldırır"""
        if key_combination in self.shortcuts:
            shortcut = self.shortcuts[key_combination]
            
            # Tkinter binding'ini kaldır
            self.root.unbind(f"<{key_combination}>")
            
            # Dictionary'den kaldır
            del self.shortcuts[key_combination]
            
            # Context listesinden kaldır
            if shortcut.context in self.context_shortcuts:
                if key_combination in self.context_shortcuts[shortcut.context]:
                    self.context_shortcuts[shortcut.context].remove(key_combination)
            
            print(f"⌨️ Kısayol kaldırıldı: {key_combination}")
    
    def clear_context_shortcuts(self, context: str) -> None:
        """Belirtilen bağlamdaki tüm kısayolları kaldırır"""
        if context in self.context_shortcuts:
            shortcuts_to_remove = self.context_shortcuts[context].copy()
            for key_combination in shortcuts_to_remove:
                self.unregister_shortcut(key_combination)
            print(f"⌨️ {context} bağlamındaki tüm kısayollar kaldırıldı")
    
    def import_shortcuts_from_config(self, config_dict: Dict) -> None:
        """Konfigürasyon dictionary'sinden kısayolları yükler"""
        try:
            for key_combination, config in config_dict.items():
                # Config'den callback'i resolve et (string olarak saklanmış olabilir)
                # Bu implementasyon için basit bir örnek
                print(f"⌨️ Konfigürasyondan kısayol yüklendi: {key_combination}")
        except Exception as e:
            print(f"❌ Kısayol konfigürasyonu yükleme hatası: {e}")
    
    def export_shortcuts_to_config(self) -> Dict:
        """Kısayolları konfigürasyon dictionary'sine aktarır"""
        config = {}
        for key_combination, shortcut in self.shortcuts.items():
            config[key_combination] = {
                'description': shortcut.description,
                'context': shortcut.context,
                'enabled': shortcut.enabled
                # callback fonksiyonu serialize edilemez, string olarak saklanabilir
            }
        return config