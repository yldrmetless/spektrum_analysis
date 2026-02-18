"""
Responsive Boyutlandırma Yöneticisi
Pencere boyutuna göre otomatik layout ayarlama
"""

import tkinter as tk
from ..config.styles import (
    RESPONSIVE_SETTINGS, get_screen_size_category, 
    get_responsive_font
)

class ResponsiveManager:
    """Responsive layout yöneticisi"""
    
    def __init__(self, root):
        """
        Args:
            root: Ana tkinter penceresi
        """
        self.root = root
        self.current_size_category = 'medium_screen'
        self.components = []  # Responsive bileşenler listesi
        
        # Minimum boyut ayarları
        self.root.minsize(
            RESPONSIVE_SETTINGS['min_window_width'],
            RESPONSIVE_SETTINGS['min_window_height']
        )
        
        # Resize event'ini bağla
        self.root.bind('<Configure>', self._on_window_resize)
        
        # İlk boyut kontrolü
        self._update_layout()
    
    def register_component(self, component, component_type='generic'):
        """
        Bir bileşeni responsive yönetim altına alır
        
        Args:
            component: Yönetilecek bileşen
            component_type: Bileşen türü ('input_panel', 'plot_panel', 'data_table')
        """
        self.components.append({
            'component': component,
            'type': component_type
        })
    
    def _on_window_resize(self, event=None):
        """Pencere boyutu değiştiğinde çağrılır"""
        # Sadece root pencere için kontrol et
        if event and event.widget != self.root:
            return
            
        self._update_layout()
    
    def _update_layout(self):
        """Layout'u mevcut pencere boyutuna göre günceller"""
        # Mevcut pencere boyutunu al
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        
        # Boyut kategorisini belirle
        new_category = get_screen_size_category(width, height)
        
        # Değişiklik varsa güncelle
        if new_category != self.current_size_category:
            self.current_size_category = new_category
            self._apply_responsive_changes()
    
    def _apply_responsive_changes(self):
        """Responsive değişiklikleri uygular"""
        # Her bileşen için responsive ayarları uygula
        for comp_info in self.components:
            component = comp_info['component']
            comp_type = comp_info['type']
            
            try:
                if hasattr(component, 'apply_responsive_changes'):
                    component.apply_responsive_changes(self.current_size_category)
                elif comp_type == 'input_panel':
                    self._apply_input_panel_changes(component)
                elif comp_type == 'plot_panel':
                    self._apply_plot_panel_changes(component)
                elif comp_type == 'data_table':
                    self._apply_data_table_changes(component)
            except Exception as e:
                print(f"Responsive değişiklik hatası: {e}")
    
    def _apply_input_panel_changes(self, input_panel):
        """Input panel için responsive değişiklikler"""
        if hasattr(input_panel, 'update_fonts'):
            input_panel.update_fonts(self.current_size_category)
    
    def _apply_plot_panel_changes(self, plot_panel):
        """Plot panel için responsive değişiklikler"""
        if hasattr(plot_panel, 'update_plot_size'):
            plot_panel.update_plot_size(self.current_size_category)
    
    def _apply_data_table_changes(self, data_table):
        """Data table için responsive değişiklikler"""
        if hasattr(data_table, 'update_table_size'):
            data_table.update_table_size(self.current_size_category)
    
    def get_responsive_width(self, component_type, base_width=None):
        """
        Bileşen türüne göre responsive genişlik döndürür
        
        Args:
            component_type: Bileşen türü
            base_width: Temel genişlik (opsiyonel)
            
        Returns:
            int: Hesaplanmış genişlik
        """
        window_width = self.root.winfo_width()
        
        if component_type == 'input_panel':
            min_width = RESPONSIVE_SETTINGS['input_panel_min_width']
            max_width = RESPONSIVE_SETTINGS['input_panel_max_width']
            
            # Pencere genişliğinin %30'u, ama min-max aralığında
            calculated_width = min(max(int(window_width * 0.3), min_width), max_width)
            return calculated_width
        
        elif component_type == 'plot_panel':
            min_width = RESPONSIVE_SETTINGS['plot_panel_min_width']
            input_width = self.get_responsive_width('input_panel')
            
            # Kalan alan - padding
            available_width = window_width - input_width - 60  # 60px padding
            return max(available_width, min_width)
        
        return base_width or 400
    
    def get_responsive_height(self, component_type, base_height=None):
        """
        Bileşen türüne göre responsive yükseklik döndürür
        
        Args:
            component_type: Bileşen türü
            base_height: Temel yükseklik (opsiyonel)
            
        Returns:
            int: Hesaplanmış yükseklik
        """
        window_height = self.root.winfo_height()
        
        if component_type == 'data_table':
            min_height = RESPONSIVE_SETTINGS['data_table_min_height']
            
            # Pencere yüksekliğinin %80'i, ama minimum değerin üstünde
            calculated_height = max(int(window_height * 0.8), min_height)
            return calculated_height
        
        return base_height or 300
    
    def get_current_fonts(self):
        """Mevcut ekran kategorisi için font ayarlarını döndürür"""
        return {
            'title': get_responsive_font(self.current_size_category, 'title'),
            'label': get_responsive_font(self.current_size_category, 'label'),
            'entry': get_responsive_font(self.current_size_category, 'entry'),
            'button': get_responsive_font(self.current_size_category, 'button')
        } 