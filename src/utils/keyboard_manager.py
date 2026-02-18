"""
Keyboard Shortcuts Yöneticisi
Klavye kısayolları desteği
"""

import tkinter as tk
from tkinter import messagebox

class KeyboardManager:
    """Klavye kısayol yöneticisi"""
    
    def __init__(self, root):
        """
        Args:
            root: Ana tkinter penceresi
        """
        self.root = root
        self.shortcuts = {}  # Kısayol -> fonksiyon mapping
        self.command_handlers = {}  # Komut adı -> handler mapping
        
        # Varsayılan kısayolları tanımla
        self._setup_default_shortcuts()
        
        # Kısayolları bağla
        self._bind_shortcuts()
    
    def _setup_default_shortcuts(self):
        """Varsayılan klavye kısayollarını tanımlar"""
        self.shortcuts = {
            '<Control-o>': 'open_file',
            '<Control-s>': 'save_graph', 
            '<Control-r>': 'run_calculation',
            '<F5>': 'refresh',
            '<Control-m>': 'show_map',
            '<Control-e>': 'export_data',
            '<Control-c>': 'copy_data',
            '<Control-h>': 'show_help',
            '<Control-q>': 'quit_app',
            '<Control-z>': 'undo_last',
            '<Control-Shift-D>': 'toggle_dark_mode',
            '<Control-Shift-F>': 'toggle_fullscreen',
            '<Escape>': 'close_dialogs'
        }
    
    def _bind_shortcuts(self):
        """Kısayolları pencereye bağlar"""
        for shortcut, command in self.shortcuts.items():
            try:
                self.root.bind_all(shortcut, lambda e, cmd=command: self._execute_command(cmd))
            except Exception as e:
                print(f"Kısayol bağlama hatası {shortcut}: {e}")
    
    def register_handler(self, command_name, handler_function):
        """
        Bir komut için handler fonksiyonu kaydeder
        
        Args:
            command_name (str): Komut adı
            handler_function (callable): Handler fonksiyonu
        """
        self.command_handlers[command_name] = handler_function
    
    def _execute_command(self, command_name):
        """
        Komut adına göre handler çalıştırır
        
        Args:
            command_name (str): Çalıştırılacak komut adı
        """
        try:
            handler = self.command_handlers.get(command_name)
            if handler:
                handler()
            else:
                self._handle_unregistered_command(command_name)
        except Exception as e:
            messagebox.showerror("Kısayol Hatası", f"Komut çalıştırılırken hata oluştu:\n{command_name}\n{str(e)}")
    
    def _handle_unregistered_command(self, command_name):
        """Kayıtlı olmayan komutlar için varsayılan davranış"""
        if command_name == 'show_help':
            self._show_shortcuts_help()
        elif command_name == 'quit_app':
            if messagebox.askokcancel("Çıkış", "Programdan çıkmak istediğinizden emin misiniz?"):
                self.root.quit()
        elif command_name == 'toggle_fullscreen':
            self._toggle_fullscreen()
        elif command_name == 'close_dialogs':
            # Açık dialogları kapatmaya çalış
            pass
    
    def _show_shortcuts_help(self):
        """Klavye kısayolları yardım penceresi gösterir"""
        help_text = """
🔸 TBDY-2018 Spektrum Analizi - Klavye Kısayolları 🔸

📂 DOSYA İŞLEMLERİ
   Ctrl+O          → Veri Dosyası Aç
   Ctrl+S          → Grafikleri Kaydet
   Ctrl+E          → Verileri Dışa Aktar

🔧 HESAPLAMA & ANALİZ  
   Ctrl+R          → Spektrum Hesapla
   F5              → Sayfayı Yenile
   Ctrl+M          → Haritada Göster

📋 VERİ İŞLEMLERİ
   Ctrl+C          → Verileri Kopyala
   Ctrl+Z          → Son İşlemi Geri Al

🎨 GÖRÜNÜM
   Ctrl+Shift+D    → Koyu Mod Aç/Kapat
   Ctrl+Shift+F    → Tam Ekran Aç/Kapat

❓ YARDIM & KONTROL
   Ctrl+H          → Bu Yardım Penceresi
   Ctrl+Q          → Programdan Çık
   Esc             → Dialog Pencerelerini Kapat

💡 İPUCU: Fare ile de tüm işlemleri yapabilirsiniz!
        """
        
        messagebox.showinfo("Klavye Kısayolları", help_text)
    
    def _toggle_fullscreen(self):
        """Tam ekran modunu aç/kapat"""
        current_state = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not current_state)
    
    def add_custom_shortcut(self, shortcut, command_name, handler=None):
        """
        Özel kısayol ekler
        
        Args:
            shortcut (str): Kısayol (örn: '<Control-Alt-t>')
            command_name (str): Komut adı
            handler (callable): Handler fonksiyonu (opsiyonel)
        """
        try:
            # Kısayolu kaydet
            self.shortcuts[shortcut] = command_name
            
            # Handler varsa kaydet
            if handler:
                self.command_handlers[command_name] = handler
            
            # Kısayolu bağla
            self.root.bind_all(shortcut, lambda e: self._execute_command(command_name))
            
            return True
        except Exception as e:
            print(f"Özel kısayol ekleme hatası: {e}")
            return False
    
    def remove_shortcut(self, shortcut):
        """
        Kısayolu kaldırır
        
        Args:
            shortcut (str): Kaldırılacak kısayol
        """
        try:
            if shortcut in self.shortcuts:
                command = self.shortcuts[shortcut]
                
                # Binding'i kaldır
                self.root.unbind_all(shortcut)
                
                # Kayıtlardan sil
                del self.shortcuts[shortcut]
                
                return True
        except Exception as e:
            print(f"Kısayol kaldırma hatası: {e}")
            return False
    
    def get_all_shortcuts(self):
        """Tüm kayıtlı kısayolları döndürür"""
        return self.shortcuts.copy()
    
    def get_shortcut_for_command(self, command_name):
        """Bir komut için kısayol döndürür"""
        for shortcut, command in self.shortcuts.items():
            if command == command_name:
                return shortcut
        return None 