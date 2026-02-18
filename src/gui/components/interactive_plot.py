"""
İnteraktif grafik bileşeni - Pan, Zoom, Hover, Peak Detection
"""

from tkinter import ttk, filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.widgets import RectangleSelector
from typing import Dict
import io
import logging
from src.gui.components.input_panel import RoundedButton
from pathlib import Path
from tkinter import PhotoImage
import sys


logger = logging.getLogger(__name__)

class InteractivePlot:
    """İnteraktif grafik sınıfı"""
    
    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        # Ana kapsayıcı (canvas + kontrol barları)
        self.root_frame = ttk.Frame(self.parent_frame)
        self.root_frame.pack(fill="both", expand=True)
        
        # Matplotlib objeler
        self.figure = None
        self.canvas = None
        self.canvas_holder = None
        self.controls_frame = None
        self.toolbar = None
        self.axes = []
        
        # İnteraktif özellikler
        self.hover_annotations = []  # Her eksen için bir annotation tutulur (eksene bağlı)
        self.peak_markers = []
        self.plot_lines = []
        self.plot_data = []
        self.action_bar = None
        self.pan_button = None
        self.zoom_button = None
        self.peak_button = None
        
        # Pan ve zoom durumu
        self.pan_active = False
        self.zoom_active = False
        self.rectangle_selector = None
        
        # Mouse tracking
        self.last_mouse_pos = None
        self.mouse_pressed = False
        
        # Peak detection ayarları (deprem kaydına uygun)
        self.show_peaks = True  # Otomatik olarak açık
        self.peak_prominence = 0.05  # Daha hassas peak detection
        self.peak_distance = 20     # Daha uzak peak'ler
        self.min_peak_height = None # Minimum peak yüksekliği
        
        # Animasyon desteği
        self.animation_markers = []  # Animasyon için zaman işaretçileri
        self.current_time_line = None  # Mevcut zaman çizgisi
        
        self._base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        self._icons_dir = self._base_dir / "icons"
        
    def create_interactive_figure(self, nrows=3, ncols=1, figsize=(12, 10)):
        """İnteraktif figure oluşturur"""
        # Figure oluştur
        self.figure = plt.figure(figsize=figsize)
        self.figure.patch.set_facecolor('#FAFAFA')
        
        # Subplotları oluştur
        self.axes = []
        for i in range(nrows * ncols):
            ax = self.figure.add_subplot(nrows, ncols, i + 1)
            ax.set_facecolor('#FFFFFF')
            ax.grid(True, alpha=0.3)
            self.axes.append(ax)
        
        # Her eksen için birer hover annotation oluştur (eksene sabit)
        self.hover_annotations = [self._create_annotation_for_axis(ax) for ax in self.axes]
        
        # Kontrol çerçevesini hazırla (toolbar + butonlar)
        self._ensure_controls_frame()

        # Canvas oluştur
        self._create_canvas()

        # Hızlı erişim barı (grafiklerin altında)
        self._create_action_bar()
        
        # Event handlers başla
        self._bind_events()
        
        # Toolbar oluştur
        self._create_toolbar()
        
        return self.figure, self.axes
    
    def _create_canvas(self):
        """Canvas oluşturur"""
        # Eski holder varsa temizle
        try:
            if self.canvas_holder:
                self.canvas_holder.destroy()
        except Exception:
            pass

        self.canvas_holder = ttk.Frame(self.root_frame)
        self.canvas_holder.pack(side="top", fill="both", expand=True)

        self.canvas = FigureCanvasTkAgg(self.figure, master=self.canvas_holder)
        canvas_widget = self.canvas.get_tk_widget()
        canvas_widget.pack(side="top", fill="both", expand=True)
        
        # İlk çizimde layout'u zorla güncelle
        def _initial_layout_fix():
            try:
                # Canvas boyutlarını al ve figure'ı yeniden boyutlandır
                canvas_widget.update_idletasks()
                width = canvas_widget.winfo_width()
                height = canvas_widget.winfo_height()
                if width > 100 and height > 100:  # Geçerli boyutlar varsa
                    dpi = self.figure.get_dpi()
                    self.figure.set_size_inches(width/dpi, height/dpi)
                    self.canvas.draw()
            except Exception:
                pass
        
        # Layout düzeltmesini biraz geciktir (widget'lar tam yerleştikten sonra)
        try:
            # Tkinter root'a erişim için root_frame'den yukarı çık
            root_widget = self.root_frame
            while root_widget.master:
                root_widget = root_widget.master
            root_widget.after(100, _initial_layout_fix)
        except Exception:
            pass

        self.canvas.draw()

    def _ensure_controls_frame(self):
        """Toolbar ve hızlı butonlar için alt çerçeveyi oluşturur."""
        try:
            if self.controls_frame and str(self.controls_frame) != "":
                return self.controls_frame
        except Exception:
            pass
        self.controls_frame = ttk.Frame(self.root_frame)
        self.controls_frame.pack(side="bottom", fill="x", pady=(0, 2))
        return self.controls_frame

    # def _create_action_bar(self):
    #     """Grafiklerin altında hızlı erişim butonlarını oluşturur."""
    #     try:
    #         if self.action_bar:
    #             self.action_bar.destroy()
    #     except Exception:
    #         pass

    #     controls_parent = self._ensure_controls_frame()

    #     bar = ttk.Frame(controls_parent)
    #     bar.pack(side="right", fill="x", expand=True, padx=(8, 4), pady=(2, 6))
    #     self.action_bar = bar

    #     ttk.Button(bar, text="↔ Pan", width=14, command=self._toggle_pan).pack(side="left", padx=2)
    #     ttk.Button(bar, text="⬚ Zoom", width=14, command=self._toggle_zoom_box).pack(side="left", padx=2)
    #     ttk.Button(bar, text="⟳ Reset", width=14, command=self._reset_view).pack(side="left", padx=2)
    #     ttk.Button(bar, text="📋 PNG Kopyala", width=16, command=self._copy_png_to_clipboard).pack(side="left", padx=6)
    #     ttk.Button(bar, text="⬇ CSV Dışa Aktar", width=16, command=self._export_csv).pack(side="left", padx=2)
    
    def _load_icon(self, path: Path):
        try:
            return PhotoImage(file=str(path))
        except Exception as e:
            print(f"İkon yüklenemedi: {path} -> {e}")
            return None
    
    def _create_action_bar(self):
        """Grafiklerin altındaki hızlı erişim tuşlarını oluşturur."""
        try:
            if self.action_bar:
                self.action_bar.destroy()
        except Exception:
            pass

        controls_parent = getattr(self, 'controls_frame', None) or self.parent_frame
        bar = ttk.Frame(controls_parent)
        bar.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=(2, 6))
        self.action_bar = bar

        # --- ikonlar (SENİN KODUN) ---
        if not hasattr(self, "_action_icons"):
            self._action_icons = {}
            self._action_icons["pan"]  = self._load_icon(self._icons_dir / "pan.png")
            self._action_icons["zoom"] = self._load_icon(self._icons_dir / "zoom.png")
            self._action_icons["home"] = self._load_icon(self._icons_dir / "reset.png")
            self._action_icons["copy"] = self._load_icon(self._icons_dir / "image.png")
            self._action_icons["csv2"] = self._load_icon(self._icons_dir / "csv2.png")
            

        f = getattr(self, "font", None)

        BTN_H = 34
        R = 8
        CANVAS_BG = "#FFFFFF"

        W14 = 140
        W16 = 140

        b = RoundedButton(
            bar, text="↔ Pan",
            image=self._action_icons.get("pan"),
            on_click=lambda: self._toolbar_action("pan"),
            height=BTN_H, radius=R,
            canvas_bg=CANVAS_BG, font=f
        )
        b.pack(side="left", padx=2)
        b.config(width=W16)

        b = RoundedButton(
            bar, text="⬚ Zoom",
            image=self._action_icons.get("zoom"),
            on_click=lambda: self._toolbar_action("zoom"),
            height=BTN_H, radius=R,
            canvas_bg=CANVAS_BG, font=f
        )
        b.pack(side="left", padx=2)
        b.config(width=W16)

        b = RoundedButton(
            bar, text="⟳ Reset",
            image=self._action_icons.get("home"),
            on_click=lambda: self._toolbar_action("home"),
            height=BTN_H, radius=R,
            canvas_bg=CANVAS_BG, font=f
        )
        b.pack(side="left", padx=2)
        b.config(width=W16)

        b = RoundedButton(
            bar, text="📋 PNG Kopyala",
            image=self._action_icons.get("copy"),
            on_click=self._copy_png_to_clipboard,
            height=BTN_H, radius=R,
            canvas_bg=CANVAS_BG, font=f
        )
        b.pack(side="left", padx=6)
        b.config(width=W16)

        b = RoundedButton(
            bar, text="⬇ CSV Dışa Aktar",
            image=self._action_icons.get("csv2"),
            on_click=self._export_csv,
            height=BTN_H, radius=R,
            canvas_bg=CANVAS_BG, font=f
        )
        b.pack(side="left", padx=2)
        b.config(width=W16)


    def _create_toolbar(self):
        """Özel toolbar oluşturur"""
        # Ana toolbar frame (kontrol çerçevesi içinde)
        try:
            if self.toolbar:
                self.toolbar.destroy()
        except Exception:
            pass

        controls_parent = self._ensure_controls_frame()

        toolbar_frame = ttk.Frame(controls_parent)
        toolbar_frame.pack(side="left", padx=(4, 8), pady=(2, 6))
        
        # Matplotlib navigation toolbar
        try:
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame, pack_toolbar=False)
        except TypeError:
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            try:
                self.toolbar.pack_forget()
            except Exception:
                pass
        try:
            self.toolbar.pack(side="left")
        except Exception:
            pass
    
    def _bind_events(self):
        """Event handlers başlar"""
        # Mouse events
        self.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.canvas.mpl_connect('button_press_event', self._on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self._on_mouse_release)
        self.canvas.mpl_connect('scroll_event', self._on_scroll)
        
        # Keyboard events
        self.canvas.mpl_connect('key_press_event', self._on_key_press)
    
    def _toggle_pan(self):
        """Pan modunu açar/kapatır"""
        self.pan_active = not self.pan_active
        
        if self.pan_active:
            if self.pan_button:
                self.pan_button.configure(text="Pan ON", style="Accent.TButton")
            self.canvas.get_tk_widget().configure(cursor="fleur")
            # Zoom box'ı kapat
            if self.zoom_active:
                self._toggle_zoom_box()
        else:
            if self.pan_button:
                self.pan_button.configure(text="Pan", style="TButton")
            self.canvas.get_tk_widget().configure(cursor="")
    
    def _toggle_zoom_box(self):
        """Zoom box modunu açar/kapatır"""
        self.zoom_active = not self.zoom_active
        
        if self.zoom_active:
            if self.zoom_button:
                self.zoom_button.configure(text="Zoom ON", style="Accent.TButton")
            # Pan'i kapat
            if self.pan_active:
                self._toggle_pan()
            # Rectangle selector oluştur
            self._create_rectangle_selector()
        else:
            if self.zoom_button:
                self.zoom_button.configure(text="Zoom Box", style="TButton")
            if self.rectangle_selector:
                self.rectangle_selector.set_active(False)
                self.rectangle_selector = None
    
    def _create_rectangle_selector(self):
        """Rectangle selector oluşturur"""
        if self.axes:
            # İlk axis için rectangle selector
            self.rectangle_selector = RectangleSelector(
                self.axes[0],
                self._on_rectangle_select,
                useblit=True,
                button=[1],  # Sol mouse tuşu
                minspanx=5, minspany=5,
                spancoords='pixels',
                interactive=True
            )
    
    def _on_rectangle_select(self, eclick, erelease):
        """Rectangle selection callback"""
        if not self.zoom_active:
            return
            
        # Seçilen alanı al
        coords = [eclick.xdata, erelease.xdata, eclick.ydata, erelease.ydata]
        if any(v is None for v in coords):
            return
        x1, x2 = sorted([eclick.xdata, erelease.xdata])
        y1, y2 = sorted([eclick.ydata, erelease.ydata])
        target_ax = getattr(eclick, "inaxes", None) or getattr(erelease, "inaxes", None)
        if target_ax is None and self.axes:
            target_ax = self.axes[0]
        
        # X zoom'unu tüm eksenlere uygula, Y sadece hedef eksene
        for ax in self.axes:
            ax.set_xlim(x1, x2)
            if ax is target_ax:
                ax.set_ylim(y1, y2)
        
        self.canvas.draw()
        
        # Zoom box modunu kapat
        self._toggle_zoom_box()
    
    def _toggle_peaks(self):
        """Peak detection açar/kapatır"""
        self.show_peaks = not self.show_peaks
        
        if self.show_peaks:
            if self.peak_button:
                self.peak_button.configure(text="Peaks ON", style="Accent.TButton")
            self._detect_and_show_peaks()
        else:
            if self.peak_button:
                self.peak_button.configure(text="Peaks", style="TButton")
            self._clear_peaks()
    
    def _detect_and_show_peaks(self):
        """Peak noktalarOn tespit eder ve gösterir - Deprem verilerine uygun"""
        self._clear_peaks()
        
        for i, (ax, plot_data) in enumerate(zip(self.axes, self.plot_data)):
            if not plot_data:
                continue
                
            try:
                # Veriyi al
                x_data = plot_data.get('x', [])
                y_data = plot_data.get('y', [])
                
                if len(y_data) == 0:
                    continue
                
                # Veri tipine gçre peak detection parametreleri ayarla
                data_type = plot_data.get('title', '').lower()
                
                if 'ivme' in data_type:
                    # İvme için daha hassas peak detection
                    prominence_factor = 0.03
                    min_distance = 15
                    height_threshold = np.max(np.abs(y_data)) * 0.1
                elif 'hız' in data_type:
                    # Hız için orta seviye
                    prominence_factor = 0.05
                    min_distance = 25
                    height_threshold = np.max(np.abs(y_data)) * 0.15
                else:  # yerdeğiştirme
                    # Yerdeğiştirme için daha az hassas
                    prominence_factor = 0.08
                    min_distance = 30
                    height_threshold = np.max(np.abs(y_data)) * 0.2
                
                # En büyük ve en küçük değerleri bul
                max_idx = np.argmax(y_data)
                min_idx = np.argmin(y_data)
                
                max_value = y_data[max_idx]
                min_value = y_data[min_idx]
                max_time = x_data[max_idx]
                min_time = x_data[min_idx]
                
                # Profesyonel renkler
                from src.config.styles import CUSTOM_COLORS
                
                # En büyük deeri iaretle (krmz daire)
                max_marker = ax.scatter([max_time], [max_value], 
                                        marker='o', s=100, c=CUSTOM_COLORS['peak_positive'], 
                                        alpha=0.9, zorder=5,
                                        edgecolors=CUSTOM_COLORS['selection'], linewidth=2.0,
                                        label=f'En büyük değer: {max_value:.4f}')
                self.peak_markers.append(max_marker)
                
                # En küçük deeri iaretle (mavi daire)
                min_marker = ax.scatter([min_time], [min_value],
                                        marker='o', s=100, c=CUSTOM_COLORS['peak_negative'],
                                        alpha=0.9, zorder=5,
                                        edgecolors=CUSTOM_COLORS['selection'], linewidth=2.0,
                                        label=f'En küçük değer: {min_value:.4f}')
                self.peak_markers.append(min_marker)
                
                # Legend ekle
                ax.legend(loc='upper right', fontsize=8, framealpha=0.8)
                logger.debug("Peaks: %s | max=%.4f @ %.4fs, min=%.4f @ %.4fs",
                             ax.get_title(), max_value, max_time, min_value, min_time)
                    
            except Exception as e:
                logger.debug("Peak detection hatas: %s", e)
        
        try:
            self.canvas.draw()
        except Exception:
            pass

    def _clear_peaks(self):
        """Peak işaretlerini temizler"""
        removed_any = False
        for marker in list(self.peak_markers):
            try:
                # Parent'ı olan artist güvenle kaldırılabilir
                has_parent = (getattr(marker, 'axes', None) is not None) or (getattr(marker, 'figure', None) is not None)
                if has_parent and hasattr(marker, 'remove'):
                    marker.remove()
                    removed_any = True
                else:
                    # Kaldırılamıyorsa görünürlüğünü kapat
                    if hasattr(marker, 'set_visible'):
                        marker.set_visible(False)
            except Exception:
                # Her ihtimale karşı görünürlüğünü kapat
                try:
                    marker.set_visible(False)
                except Exception:
                    pass
        self.peak_markers.clear()
        # Daha hafif yeniden çizim
        if hasattr(self, 'canvas') and self.canvas:
            try:
                if removed_any:
                    self.canvas.draw_idle()
                else:
                    self.canvas.draw()
            except Exception:
                pass
    
    def _reset_view(self):
        """Grafik görünümünü resetler"""
        for ax in self.axes:
            ax.relim()
            ax.autoscale()
        self.canvas.draw()

    def _copy_png_to_clipboard(self):
        """Figürü panoya kopyalar ya da PNG olarak kaydeder."""
        try:
            import win32clipboard, win32con  # type: ignore
            from PIL import Image  # type: ignore

            self.figure.canvas.draw()
            w, h = self.figure.canvas.get_width_height()
            rgb = self.figure.canvas.tostring_rgb()
            img = Image.frombytes('RGB', (w, h), rgb)
            with io.BytesIO() as output:
                img = img.transpose(Image.FLIP_TOP_BOTTOM)
                img.save(output, 'BMP')
                data = output.getvalue()[14:]
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_DIB, data)
            finally:
                win32clipboard.CloseClipboard()
            return
        except Exception:
            pass

        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG dosyası", "*.png")],
                title="PNG olarak kaydet"
            )
            if file_path:
                self.figure.savefig(file_path, format="png", dpi=300)
        except Exception as e:
            try:
                messagebox.showerror("Hata", f"PNG kaydedilemedi: {e}")
            except Exception:
                pass

    def _export_csv(self):
        """Zaman serisi verilerini CSV'ye aktarır."""
        try:
            if not self.plot_data or len(self.plot_data) < 3:
                messagebox.showinfo("Bilgi", "Dışa aktarılacak veri yok.")
                return
            time_data = self.plot_data[0].get('x', [])
            accel_data = self.plot_data[0].get('y', [])
            velocity_data = self.plot_data[1].get('y', [])
            displacement_data = self.plot_data[2].get('y', [])
            if not time_data:
                messagebox.showinfo("Bilgi", "Veri bulunamadı.")
                return

            acc_unit = self.plot_data[0].get('unit', '')
            vel_unit = self.plot_data[1].get('unit', '')
            disp_unit = self.plot_data[2].get('unit', '')

            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV dosyası", "*.csv")],
                title="CSV Dışa Aktar"
            )
            if not file_path:
                return

            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([f"Zaman (s)", f"İvme ({acc_unit})", f"Hız ({vel_unit})", f"Yerdeğiştirme ({disp_unit})"])
                for row in zip(time_data, accel_data, velocity_data, displacement_data):
                    writer.writerow(row)
        except Exception as e:
            try:
                messagebox.showerror("Hata", f"CSV dışa aktarım hatası: {e}")
            except Exception:
                pass

    def _on_mouse_move(self, event):
        """Mouse hareket eventi"""
        if not event.inaxes:
            self._hide_all_tooltips()
            return
        
        # Pan işlemi
        if self.pan_active and self.mouse_pressed and self.last_mouse_pos:
            self._handle_pan(event)
        
        # Hover tooltip göster
        self._show_hover_tooltip(event)
    
    def _on_mouse_press(self, event):
        """Mouse basma eventi"""
        if event.button == 1:  # Sol tuş
            self.mouse_pressed = True
            self.last_mouse_pos = (event.x, event.y)
    
    def _on_mouse_release(self, event):
        """Mouse bırakma eventi"""
        if event.button == 1:  # Sol tuş
            self.mouse_pressed = False
            self.last_mouse_pos = None
    
    def _on_scroll(self, event):
        """Mouse scroll eventi (zoom)"""
        if not event.inaxes:
            return
        
        # Zoom faktörü
        zoom_factor = 1.1 if event.step > 0 else 1/1.1
        
        # Mouse pozisyonuna göre zoom
        xlim = event.inaxes.get_xlim()
        ylim = event.inaxes.get_ylim()
        
        # Mouse pozisyonu
        xdata, ydata = event.xdata, event.ydata
        
        # Yeni limitler
        x_range = (xlim[1] - xlim[0]) * zoom_factor
        y_range = (ylim[1] - ylim[0]) * zoom_factor
        
        new_xlim = [xdata - x_range/2, xdata + x_range/2]
        new_ylim = [ydata - y_range/2, ydata + y_range/2]
        
        # Tüm axes'lere uygula (X ekseni için)
        for ax in self.axes:
            ax.set_xlim(new_xlim)
        
        # Sadece ilgili axis'e Y zoom uygula
        event.inaxes.set_ylim(new_ylim)
        
        self.canvas.draw()
    
    def _on_key_press(self, event):
        """Klavye basma eventi"""
        if event.key == 'r':
            self._reset_view()
        elif event.key == 'p':
            self._toggle_peaks()
        elif event.key == 'h':
            self._show_help()
    
    def _handle_pan(self, event):
        """Pan işlemini yapar"""
        if not self.last_mouse_pos:
            return
        
        # Mouse hareket miktarı
        dx = event.x - self.last_mouse_pos[0]
        dy = event.y - self.last_mouse_pos[1]
        
        # Canvas boyutları
        canvas_width = self.canvas.get_tk_widget().winfo_width()
        canvas_height = self.canvas.get_tk_widget().winfo_height()
        
        # Tüm axes'lerde pan yap
        for ax in self.axes:
            xlim = ax.get_xlim()
            ylim = ax.get_ylim()
            
            # X ekseni pan (tüm grafikler senkron)
            x_range = xlim[1] - xlim[0]
            x_shift = -dx * x_range / canvas_width
            ax.set_xlim(xlim[0] + x_shift, xlim[1] + x_shift)
            
            # Y ekseni pan (sadece ilgili grafik)
            if event.inaxes == ax:
                y_range = ylim[1] - ylim[0]
                y_shift = dy * y_range / canvas_height
                ax.set_ylim(ylim[0] + y_shift, ylim[1] + y_shift)
        
        self.canvas.draw()
        self.last_mouse_pos = (event.x, event.y)
    
    def _show_hover_tooltip(self, event):
        """Hover tooltip gösterir"""
        if not event.inaxes or not self.plot_data:
            return
        
        # İlgili axis'i bul
        ax_index = None
        for i, ax in enumerate(self.axes):
            if event.inaxes == ax:
                ax_index = i
                break
        
        if ax_index is None or ax_index >= len(self.plot_data):
            return
        
        plot_data = self.plot_data[ax_index]
        if not plot_data:
            return
        
        try:
            # En yakın veri noktasını bul
            x_data = plot_data.get('x', [])
            y_data = plot_data.get('y', [])
            
            if len(x_data) == 0 or len(y_data) == 0:
                return
            
            # Mouse pozisyonuna en yakın nokta
            distances = np.abs(np.array(x_data) - event.xdata)
            closest_idx = np.argmin(distances)
            
            closest_x = x_data[closest_idx]
            closest_y = y_data[closest_idx]
            
            # Tooltip metnini oluştur
            title = plot_data.get('title', 'Veri')
            unit = plot_data.get('unit', '')
            
            tooltip_text = f'{title}\nZaman: {closest_x:.4f} s\nDeğer: {closest_y:.6g} {unit}'
            
            # Annotation: ilgili eksene ait olmasını garanti et
            if ax_index >= len(self.hover_annotations) or \
               self.hover_annotations[ax_index] is None or \
               getattr(self.hover_annotations[ax_index], 'axes', None) is not event.inaxes:
                # Eksene özel annotation oluştur/yenile
                ann = self._create_annotation_for_axis(event.inaxes)
                # Liste boyutunu eksen sayısına eşitle
                if ax_index >= len(self.hover_annotations):
                    # Eksik indeksler için None ile doldur
                    self.hover_annotations.extend([None] * (ax_index + 1 - len(self.hover_annotations)))
                self.hover_annotations[ax_index] = ann
            annotation = self.hover_annotations[ax_index]
            
            # Annotation güncelle
            annotation.set_text(tooltip_text)
            annotation.xy = (closest_x, closest_y)
            annotation.set_visible(True)
            
            # Diğer annotations'ları gizle
            for i, ann in enumerate(self.hover_annotations):
                if i != ax_index:
                    ann.set_visible(False)
            
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.debug("Tooltip hatas: %s", e)

    def _create_annotation_for_axis(self, ax):
        """Verilen eksene başlı, stilize bir annotation oluşturur ve döndürür."""
        try:
            ann = ax.annotate('', xy=(0, 0), xytext=(20, 20),
                              textcoords="offset points",
                              bbox=dict(boxstyle="round,pad=0.5",
                                        facecolor='#FFFACD',
                                        alpha=0.95,
                                        edgecolor='#333333',
                                        linewidth=1),
                              arrowprops=dict(arrowstyle='->',
                                              connectionstyle='arc3,rad=0.1',
                                              color='#333333',
                                              alpha=0.8),
                              fontsize=9,
                              fontweight='normal',
                              visible=False)
            return ann
        except Exception:
            # Hata halinde boş bir placeholder döndür
            class _DummyAnn:
                def set_visible(self, *_args, **_kwargs):
                    pass
                def set_text(self, *_args, **_kwargs):
                    pass
                def __setattr__(self, name, value):
                    object.__setattr__(self, name, value)
            return _DummyAnn()
    
    def _hide_all_tooltips(self):
        """Tüm tooltipleri gizler"""
        for annotation in self.hover_annotations:
            annotation.set_visible(False)
        self.canvas.draw_idle()
    
    def _show_help(self):
        """Yardım mesajı gösterir"""
        help_text = (
            "İnteraktif Grafik Kısayolları:\n\n"
            "Mouse:\n"
            "- Scroll: Zoom in/out\n"
            "- Sürükle (Pan modu): Grafik kaydır\n"
            "- Sol tık + sürükle (Zoom modu): Alan seç\n\n"
            "Klavye:\n"
            "- R: Görünümü sıfırla\n"
            "- P: Peak detection aç/kapat\n"
            "- H: Bu yardımı göster\n\n"
            "Butonlar:\n"
            "- Pan: Grafik sürükleme modu\n"
            "- Zoom Box: Alan seçerek zoom\n"
            "- Peaks: Peak noktalarını göster\n"
            "- Reset: Orijinal görünüme dön"
        )
        import tkinter.messagebox as msgbox
        msgbox.showinfo("İnteraktif Grafik Yardımı", help_text)

    def plot_time_series(self, time_data, accel_data, velocity_data, displacement_data,
                         accel_unit="g", velocity_unit="cm/s", displacement_unit="cm"):
        """Time series verilerini çizer"""
        
        # Verileri sakla (hover için)
        self.plot_data = [
            {
                'x': time_data,
                'y': accel_data,
                'title': 'İvme',
                'unit': accel_unit
            },
            {
                'x': time_data,
                'y': velocity_data,
                'title': 'Hız',
                'unit': velocity_unit
            },
            {
                'x': time_data,
                'y': displacement_data,
                'title': 'Yerdeğiştirme',
                'unit': displacement_unit
            }
        ]
        
        # Grafikleri temizle
        from src.config.styles import CUSTOM_COLORS
        for ax in self.axes:
            ax.clear()
            ax.grid(True, alpha=0.3, color=CUSTOM_COLORS['grid'])
        
        # Peak markers temizle
        self._clear_peaks()
        
        # Profesyonel renk paleti
        from src.config.styles import CUSTOM_COLORS
        
        # İvme grafiği - profesyonel renk
        if len(self.axes) > 0:
            self.axes[0].plot(time_data, accel_data, color=CUSTOM_COLORS['acceleration'], linewidth=1.2, alpha=0.8)
            self.axes[0].set_ylabel(f'İvme ({accel_unit})', fontsize=10, color=CUSTOM_COLORS['text'])
            self.axes[0].set_title('İvme Zaman Grafiği', fontsize=11, fontweight='bold', color=CUSTOM_COLORS['text'], loc='center')
            self.axes[0].grid(True, alpha=0.3, color=CUSTOM_COLORS['grid'])
        
        # Hız grafiği - profesyonel renk
        if len(self.axes) > 1:
            self.axes[1].plot(time_data, velocity_data, color=CUSTOM_COLORS['velocity'], linewidth=1.2, alpha=0.8)
            self.axes[1].set_ylabel(f'Hız ({velocity_unit})', fontsize=10, color=CUSTOM_COLORS['text'])
            self.axes[1].set_title('Hız Zaman Grafiği', fontsize=11, fontweight='bold', color=CUSTOM_COLORS['text'], loc='center')
            self.axes[1].grid(True, alpha=0.3, color=CUSTOM_COLORS['grid'])
        
        # Yerdeğiştirme grafiği - profesyonel renk
        if len(self.axes) > 2:
            self.axes[2].plot(time_data, displacement_data, color=CUSTOM_COLORS['displacement'], linewidth=1.2, alpha=0.8)
            self.axes[2].set_ylabel(f'Yerdeğiştirme ({displacement_unit})', fontsize=10, color=CUSTOM_COLORS['text'])
            self.axes[2].set_xlabel('Zaman (saniye)', fontsize=10, color=CUSTOM_COLORS['text'])
            self.axes[2].set_title('Yerdeğiştirme Zaman Grafiği', fontsize=11, fontweight='bold', color=CUSTOM_COLORS['text'], loc='center')
            self.axes[2].grid(True, alpha=0.3, color=CUSTOM_COLORS['grid'])
        
        # Layout ayarla
        self.figure.tight_layout(pad=2.0)
        
        # Peak detection aktifse yeniden göster
        if self.show_peaks:
            self._detect_and_show_peaks()
        
        # Canvas güncelle
        self.canvas.draw()
        logger.debug("İnteraktif grafik çizildi: %s veri noktası", f"{len(time_data):,}")

    def show_animation_marker(self, current_time: float):
        """Animasyon için mevcut zaman işaretçisini gösterir"""
        try:
            # Önceki zaman çizgisini temizle
            if self.current_time_line:
                self.current_time_line.remove()
                self.current_time_line = None
            
            # Tüm axes'lerde zaman çizgisi çiz - profesyonel renk
            from src.config.styles import CUSTOM_COLORS
            for ax in self.axes:
                ylim = ax.get_ylim()
                line = ax.axvline(x=current_time, color=CUSTOM_COLORS['marker'], linewidth=2, 
                                alpha=0.8, linestyle='--', zorder=10)
                if self.current_time_line is None:
                    self.current_time_line = line
            
            # Canvas'ı güncelle
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.debug("Animasyon marker hatas: %s", e)
    
    def hide_animation_marker(self):
        """Animasyon zaman işaretçisini gizler"""
        try:
            if self.current_time_line:
                self.current_time_line.remove()
                self.current_time_line = None
                self.canvas.draw_idle()
        except Exception as e:
            logger.debug("Animasyon marker gizleme hatas: %s", e)
    
    def highlight_current_values(self, current_time: float, data_values: Dict[str, float]):
        """Mevcut değerleri highlight eder"""
        try:
            # Mevcut marker'ları temizle
            for marker in self.animation_markers:
                marker.remove()
            self.animation_markers.clear()
            
            # Her axis için mevcut değeri işaretle
            for i, (ax, plot_data) in enumerate(zip(self.axes, self.plot_data)):
                if not plot_data:
                    continue
                
                # Veri tipine göre değeri al
                data_key = plot_data.get('title', '').lower()
                value = None
                
                if 'ivme' in data_key and 'İvme' in data_values:
                    value = data_values['İvme']
                elif 'hız' in data_key and 'Hız' in data_values:
                    value = data_values['Hız']
                elif 'yerdeğiştirme' in data_key and 'Yerdeğiştirme' in data_values:
                    value = data_values['Yerdeğiştirme']
                
                if value is not None:
                    # Mevcut değeri profesyonel marker ile işaretle
                    from src.config.styles import CUSTOM_COLORS
                    marker = ax.scatter([current_time], [value], 
                                      s=100, c=CUSTOM_COLORS['marker'], marker='o', 
                                      alpha=0.9, zorder=15,
                                      edgecolors=CUSTOM_COLORS['selection'], linewidth=2)
                    self.animation_markers.append(marker)
            
            # Canvas'ı güncelle
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.debug("Deger highlight hatas: %s", e)
    
    def clear_animation_highlights(self):
        """Tüm animasyon highlight'larını temizler"""
        try:
            # Marker'ları temizle
            for marker in self.animation_markers:
                marker.remove()
            self.animation_markers.clear()
            
            # Zaman çizgisini temizle
            self.hide_animation_marker()
            
            self.canvas.draw_idle()
            
        except Exception as e:
            logger.debug("Animasyon temizleme hatas: %s", e)
    
    def clear_plot(self):
        """Grafikleri temizler"""
        for ax in self.axes:
            ax.clear()
            ax.grid(True, alpha=0.3)
        
        self.plot_data.clear()
        self._clear_peaks()
        self._hide_all_tooltips()
        # Annotation'ları eksenlere göre yeniden kur
        self.hover_annotations = [self._create_annotation_for_axis(ax) for ax in self.axes]
        
        self.canvas.draw()
