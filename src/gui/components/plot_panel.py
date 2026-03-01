"""
Grafik çizim paneli bileşeni - TBDY_GUI.py özellikleri entegre edildi
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox, simpledialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from ...config.styles import CUSTOM_COLORS
import io
import logging
from ...utils.unit_converter import UnitConverter
import re
import customtkinter as ctk
from PIL import Image
from pathlib import Path
import sys
from src.gui.components.input_panel import RoundedButton
from tkinter import PhotoImage


logger = logging.getLogger(__name__)

class PlotPanel:
    """Grafik çizim paneli sınıfı"""

    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame

        # Matplotlib objeler
        self.figure = None
        self.canvas = None
        self.toolbar = None
        self.plotted_axes = {}

        # Hover annotation'ları
        self.hover_annotations = []
        self.plot_lines = []
        self.plot_data = []
        self.crosshair_lines = []  # (vline, hline) çiftleri
        self.status_label = None
        self.pinned_annotations = []
        self.controls_frame = None
         
        self._base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
        self._icons_dir = self._base_dir / "icons"

        # Arayüzü oluştur
        self._create_widgets()
        self.show_placeholder_plot()

    def _create_widgets(self):
        """Widget'ları oluşturur"""

        # Ana çerçeve zaten parent_frame olarak geliyor

        # Alt kısımda durum etiketi (hover okumaları için)
        try:
            status_frame = ttk.Frame(self.parent_frame)
            status_frame.pack(fill='x', side='bottom')

            self.status_label = ttk.Label(status_frame, text="Hazır", font=('Segoe UI', 9))
            self.status_label.pack(anchor='w', padx=6, pady=2)
        except Exception:
            self.status_label = None

        # Toolbar ve aksiyon butonları için ortak alt çerçeve
        try:
            self.controls_frame = ttk.Frame(self.parent_frame)
            self.controls_frame.pack(fill='x', side='bottom', pady=(0, 2))
        except Exception:
            self.controls_frame = self.parent_frame

        # Durum bayrakları
        self._grid_visible = True
        self._crosshair_visible = True
        self._ref_lines = []

        # Eksen ve çizgi yeniden kullanım durumları
        self.axes_map = {}
        self.line_map = {}
        self._aux_artists = {}

        # Blitting alt yapısı
        self._blit_enabled = True
        self._backgrounds = {}
        self._blit_need_recache = True

        self.action_bar = None

    def show_placeholder_plot(
        self,
        text="Hesaplama yapmak için lütfen\nveri setini içeren dosyayı yükleyin."
    ):
        """Placeholder grafik gösterir"""
        self._clear_canvas()
        self.figure, ax = plt.subplots(figsize=(10, 6))

        ax.text(
            0.5, 0.5, text,
            ha='center', va='center',
            fontsize=15, fontweight='medium',
            bbox=dict(
                boxstyle="round,pad=1.0",
                fc='white', alpha=0.8,
                ec=CUSTOM_COLORS['text']
            )
        )

        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        ax.set_facecolor('#FAFAFA')
        self._create_canvas()

    def plot_spectra(self, spectrum_result, spectrum_options):
        """
        Spektrum grafiklerini çizer - TBDY_GUI.py'den entegre edilmiş gelişmiş versiyon
        Args:
            spectrum_result (dict): Spektrum hesaplama sonuçları
            spectrum_options (dict): Hangi spektrumların çizileceği
        """
        if not spectrum_result or 'spectrum_info' not in spectrum_result:
            return

        # Eski referans çizgilerini kaldır (tekrar eklememek için)
        try:
            for ln in getattr(self, '_ref_lines', []) or []:
                try:
                    ln.remove()
                except Exception:
                    pass
        except Exception as e:
            logger.debug("_create_widgets status bar init failed: %s", e)

        self._ref_lines = []

        # Mevcut plot_data'yı güncellemek için sıfırla (axes korunur)
        self.plot_data = []

        spectrum_info = spectrum_result['spectrum_info']
        spectrum_count = sum([
            spectrum_options.get('horizontal', False),
            spectrum_options.get('vertical', False),
            spectrum_options.get('displacement', False)
        ])

        if spectrum_count == 0:
            self.show_placeholder_plot("Çizilecek bir spektrum türü seçilmedi.")
            return

        # Subplot düzeni hesapla - Tüm grafikler alt alta
        rows, cols = spectrum_count, 1

        # İlk kez oluşturuluyorsa eksenleri hazırla
        if not self.axes_map:
            try:
                self.figure.clear()
            except Exception:
                pass

            # try:
            #     # Legend içerde başlayacak; sağ kenarı geniş bırakmaya gerek yok
            #     self.figure.subplots_adjust(
            #         top=0.90, bottom=0.10, left=0.08, right=0.96, hspace=0.65
            #     )
            # except Exception:
            #     pass
            
            try:
                # constrained_layout=True modern ve otomatik bir yerleşim sağlar
                self.figure.set_constrained_layout(True)
                self.figure.set_constrained_layout_pads(
                    w_pad=0.1, 
                    h_pad=0.1,  # Grafikler arası iç boşluk
                    hspace=0.15, 
                    wspace=0.1
                )
            except Exception:
                # Eğer constrained_layout hata verirse manuel ayar (Değerleri güncelledim):
                self.figure.subplots_adjust(
                    top=0.85,    # 0.90 çok yüksekti, 0.85'e çekerek tavan boşluğu bıraktık
                    bottom=0.12, 
                    left=0.10, 
                    right=0.95, 
                    hspace=0.9   # 0.65 yetmemişti, 0.9 yaparak dikey boşluğu %40 daha artırdık
                )

            # Üç ekseni sabit oluştur (Yatay, Düşey, Yerdeğiştirme)
            ax1 = self.figure.add_subplot(3, 1, 1)
            ax2 = self.figure.add_subplot(3, 1, 2)
            ax3 = self.figure.add_subplot(3, 1, 3)

            self.axes_map = {'Yatay': ax1, 'Düşey': ax2, 'Yerdeğiştirme': ax3}

            for ax in [ax1, ax2, ax3]:
                try:
                    ax.margins(x=0.02, y=0.05)
                    ax.tick_params(labelsize=9)
                    ax.set_visible(False)
                except Exception:
                    pass

        current_plot = 0

        # Log T ekseni isteğe bağlı (geriye dönük uyum: 'log_t')
        use_log_t = bool(spectrum_options.get('log_period', spectrum_options.get('log_t', False)))

        # Kullanıcı referans periyotları (virgülle ayrılmış metin)
        user_ref_lines = []
        try:
            ref_text = spectrum_options.get('reference_periods', '')
            if isinstance(ref_text, str) and ref_text.strip():
                parts = [p.strip() for p in ref_text.replace(';', ',').split(',') if p.strip()]
                for p in parts:
                    try:
                        val = float(p)
                        if val >= 0:
                            user_ref_lines.append(val)
                    except Exception:
                        continue
        except Exception:
            user_ref_lines = []

        # Çizimde kullanılacak referans çizgilerini ayarla
        try:
            self._user_ref_lines = sorted(list(set(user_ref_lines))) if user_ref_lines else []
            self._user_ref_enabled = len(self._user_ref_lines) > 0
        except Exception:
            self._user_ref_lines = []
            self._user_ref_enabled = False

        # Hangi türler çizilecek ve sırayla
        selected_types = []
        if spectrum_options.get('horizontal', False) and 'horizontal' in spectrum_info:
            selected_types.append('Yatay')
        if spectrum_options.get('vertical', False) and 'vertical' in spectrum_info:
            selected_types.append('Düşey')
        if spectrum_options.get('displacement', False) and 'displacement' in spectrum_info:
            selected_types.append('Yerdeğiştirme')

        # Geometriyi ayarla ve görünürlükleri yönet
        total = len(selected_types)
        index_lookup = {'Yatay': None, 'Düşey': None, 'Yerdeğiştirme': None}
        for idx, gtype in enumerate(selected_types, start=1):
            index_lookup[gtype] = idx

        for gtype, ax in self.axes_map.items():
            if index_lookup[gtype] is not None:
                try:
                    ax.change_geometry(total, 1, index_lookup[gtype])
                except Exception:
                    pass
                ax.set_visible(True)
            else:
                ax.set_visible(False)

        # Görünür eksenleri eşit yüksekliğe yerleştir
        try:
            visible_axes = [self.axes_map[g] for g in selected_types]
            self._apply_equal_layout(visible_axes)

            # Blit arka planlarını güncellemek gerekecek
            self._blit_need_recache = True
        except Exception:
            pass

        # Yatay spektrum
        if 'Yatay' in selected_types:
            ax = self.axes_map['Yatay']
            h_info = spectrum_info['horizontal']
            period_array = spectrum_result['period_array']
            
            leg = ax.get_legend()
            if leg:
                leg.remove()
                
            if 'Yatay' in self._aux_artists:
                for artist in self._aux_artists['Yatay']:
                    artist.remove()
                self._aux_artists['Yatay'] = []

            self._plot_single_spectrum_advanced(
                ax,
                period_array,
                h_info['data'],
                'Yatay Elastik Tasarım Spektrum Grafiği',
                'Spektral İvme, Sₐₑ(T)',
                'Yatay Elastik Tasarım Spektrumu',
                CUSTOM_COLORS['yatay'],
                h_info.get('unit', 'g'),
                h_info,
                'Yatay',
                use_log_t
            )

            # Sağ üst özet kutusu (SDS, SD1, TA, TB, TL)
            try:
                TA = h_info.get('TA'); TB = h_info.get('TB'); TL = h_info.get('TL')
                SDS = h_info.get('SDS'); SD1 = h_info.get('SD1')

                text = []
                if SDS is not None: text.append(f"$S_{{DS}}$={SDS:.3f}")
                if SD1 is not None: text.append(f"$S_{{D1}}$={SD1:.3f}")
                if TA is not None: text.append(f"$T_{{A}}$={TA:.3f}s")
                if TB is not None: text.append(f"$T_{{B}}$={TB:.3f}s")
                if TL is not None: text.append(f"$T_{{L}}$={TL:.3f}s")

                if text:
                    # y koordinatı 0.98'den 0.75'e çekildi (Lejantın altına yerleşmesi için)
                    box = ax.text(
                        0.97, 0.75, "\n".join(text),
                        transform=ax.transAxes,
                        ha='right', va='top',
                        fontsize=8,
                        bbox=dict(
                            boxstyle='round,pad=0.3',
                            fc='white',
                            ec=CUSTOM_COLORS['grid'],
                            alpha=0.9
                        )
                    )
                    self._aux_artists['Yatay'].append(box)
            except Exception:
                pass

        
        # Düşey spektrum  
        if 'Düşey' in selected_types:
            ax = self.axes_map['Düşey']
            v_info = spectrum_info['vertical']
            period_array = spectrum_result['period_array']
            
            leg = ax.get_legend()
            if leg: leg.remove()
            if 'Düşey' in self._aux_artists:
                for artist in self._aux_artists['Düşey']:
                    artist.remove()
                self._aux_artists['Düşey'] = []
            
            
            self._plot_single_spectrum_advanced(
                ax, period_array, v_info['data'],
                'Düşey Elastik Tasarım Spektrum Grafiği', 
                'Spektral İvme, SₐₑD(T)',
                'Düşey Elastik Tasarım Spektrumuaa',
                CUSTOM_COLORS['dusey'],
                v_info.get('unit', 'g'),
                v_info,
                'Düşey',
                use_log_t
            )
            # Düşey grafikte x-limit: TLD
            try:
                TLD = v_info.get('T_LD')
                if TLD is not None and np.isfinite(TLD) and TLD > 0:
                    ax.set_xlim(left=0, right=float(TLD))
            except Exception:
                pass
            # Sağ üst özet kutusu (TAD, TBD, TLD)
            try:
                TAD = v_info.get('T_AD'); TBD = v_info.get('T_BD'); TLD = v_info.get('T_LD')
                text = []
                if TAD is not None: text.append(f"$T_{{AD}}$={TAD:.3f}s")
                if TBD is not None: text.append(f"$T_{{BD}}$={TBD:.3f}s")
                if TLD is not None: text.append(f"$T_{{LD}}$={TLD:.3f}s")
                
                if text:
                    # Lejant loc='upper right' (y=1.0) civarındadır. 
                    # Bu kutuyu y=0.75 koordinatına çekerek lejantın altına alıyoruz.
                    box = ax.text(0.97, 0.75, "\n".join(text), transform=ax.transAxes,
                                   ha='right', va='top', fontsize=8,
                                   bbox=dict(boxstyle='round,pad=0.3', fc='white', 
                                             ec=CUSTOM_COLORS['grid'], alpha=0.9))
                    self._aux_artists['Düşey'].append(box)
            except Exception:
                pass
        
        # Yerdeğiştirme spektrumu
        if 'Yerdeğiştirme' in selected_types:
            ax = self.axes_map['Yerdeğiştirme']
            d_info = spectrum_info['displacement']
            period_array = spectrum_result['period_array']
            
            leg = ax.get_legend()
            if leg: leg.remove()
            if 'Yerdeğiştirme' in self._aux_artists:
                for artist in self._aux_artists['Yerdeğiştirme']:
                    artist.remove()
                self._aux_artists['Yerdeğiştirme'] = []
            
            
            self._plot_single_spectrum_advanced(
                ax, period_array, d_info['data'],
                'Yerdeğiştirme Tasarım Spektrum Grafiği',
                'Spektral Yerdeğiştirme, Sₐₑ(T)',
                'Yatay Elastik Spektral Yerdeğiştirme', 
                CUSTOM_COLORS['yerdeğiştirme'],
                d_info.get('unit', 'cm'),
                d_info,
                'Yerdeğiştirme',
                use_log_t
            )
        
        # constrained_layout kullanılacak; ek ayar gereksiz
        
        # Canvas'ı yenile
        # self.canvas.draw()
        
        # # Hover annotations'ları oluştur
        # self._create_hover_annotations()
        # # Crosshair çizgilerini hazırla
        # self._create_crosshair_lines()
        
        # ── Referans periyot çizgilerini çiz ──
        if self._user_ref_lines:
            for gtype in selected_types:
                ax = self.axes_map[gtype]
                for t_val in self._user_ref_lines:
                    try:
                        ln = ax.axvline(
                            x=t_val,
                            color="#9CA3AF",
                            linestyle="--",
                            linewidth=0.8,
                            alpha=0.7,
                            zorder=1,
                        )
                        self._ref_lines.append(ln)
                        # Etiket (sadece en üstteki grafiğe)
                        if gtype == selected_types[0]:
                            txt = ax.annotate(
                                f"T={t_val}",
                                xy=(t_val, 0.98),
                                xycoords=("data", "axes fraction"),
                                ha="center",
                                va="bottom",
                                fontsize=7,
                                color="#6B7280",
                            )
                            self._ref_lines.append(txt)
                    except Exception:
                        continue
        
        self._create_hover_annotations()
        self._create_crosshair_lines()

        if self.canvas:
            if getattr(self, "_blit_enabled", False):
                self._blit_need_recache = True
                self._blit_redraw(force_full=True)
            else:
                self.canvas.draw_idle()
        
        if spectrum_count == 0:
            self.show_placeholder("Çizilecek bir spektrum türü seçilmedi.")
            return

    def _apply_equal_layout(self, axes_list):
        """Verilen eksenleri figür alanında eşit yüksekliklerle konumlandır."""
        try:
            if not axes_list:
                return
            # Kenar boşlukları (figure fraction)
            left = 0.07
            right = 0.99
            bottom = 0.08
            top = 0.96
            # Dikey aralık (iki eksen arası)
            vspace = 0.09
            n = len(axes_list)
            total_height = top - bottom
            height = (total_height - vspace * (n - 1)) / n if n > 0 else total_height
            width = right - left
            for idx, ax in enumerate(axes_list):
                y0 = top - (idx + 1) * height - idx * vspace
                ax.set_position([left, y0, width, height])
        except Exception as e:
            logger.debug("_apply_equal_layout failed: %s", e)
            
            
    def _plot_single_spectrum_advanced(
        self,
        ax,
        period_data,
        acceleration_values,
        title_text,
        ylabel_text,
        line_label,
        line_color_input,
        unit,
        spectrum_info_dict,
        graph_type,
        use_log_scale=False
    ):
        """Plots the spectrum graph with a fixed grid and modern dashboard aesthetics."""
        
        # --- 1. CLEANUP ---
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
        
        ax.cla() 
        
        ax.xaxis.set_major_locator(ticker.AutoLocator())
        ax.yaxis.set_major_locator(ticker.AutoLocator())
        ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        
        while ax.lines:
            ax.lines[0].remove()
        for collection in ax.collections:
            collection.remove()
            
        # --- MODERN DESIGN PARAMETERS ---
        MODERN_PALETTE = {
            'line': '#3B82F6', 'fill': '#3B82F6', 'text_main': '#1E293B',
            'text_sub': '#64748B', 'grid': '#F1F5F9', 'border': '#E2E8F0', 'bg': '#FFFFFF'
        }
        
        try:
            aux_artists_list = self._aux_artists.get(graph_type, [])
            for artist in aux_artists_list:
                try: artist.remove()
                except: pass
            self._aux_artists[graph_type] = []
        except:
            self._aux_artists[graph_type] = []

        self.plot_lines = [line for line in self.plot_lines if line.axes != ax]

        # 2. Axis and Spine Settings
        ax.set_facecolor(MODERN_PALETTE['bg'])
        for spine in ['top', 'right']: ax.spines[spine].set_visible(False)
        for spine in ['left', 'bottom']:
            ax.spines[spine].set_color(MODERN_PALETTE['border'])
            ax.spines[spine].set_linewidth(1.2)

        # 3. FIXED GRID SYSTEM (Independent of Units)
        ax.grid(False)
        # X Axis: Major grid line every 0.5 seconds
        ax.xaxis.set_major_locator(ticker.MultipleLocator(0.5))
        # Y Axis: Always roughly 6 horizontal divisions regardless of unit scale
        
        ax.grid(True, which='major', linestyle='-', linewidth=0.8, color=MODERN_PALETTE['grid'], zorder=0)
        ax.set_axisbelow(True)

        # 4. Spectrum Curve and Fill
        final_color = line_color_input if line_color_input else MODERN_PALETTE['line']
        main_line = ax.plot(period_data, acceleration_values, label=line_label, color=final_color, 
                            linewidth=2.8, alpha=1.0, zorder=3, antialiased=True)[0]
        
        self.line_map[graph_type] = main_line
        self.plot_lines.append(main_line)

        area_fill = ax.fill_between(period_data, acceleration_values, color=final_color, alpha=0.08, zorder=2)
        self._aux_artists[graph_type].append(area_fill)
        self.plot_data.append({'T': period_data, 'values': acceleration_values, 'ax': ax, 'type': graph_type, 'unit': unit})

        # 5. Titles and Labels
        main_font = {'fontname': 'Segoe UI', 'fontweight': 'bold', 'size': 13}
        sub_font = {'fontname': 'Segoe UI', 'fontweight': 'medium', 'size': 10}
        ax.set_title(title_text, color=MODERN_PALETTE['text_main'], pad=12, **main_font)
        
        dynamic_ylabel = self._get_dynamic_ylabel(ylabel_text, unit, graph_type)
        ax.set_ylabel(dynamic_ylabel, color=MODERN_PALETTE['text_sub'], labelpad=10, **sub_font)
        ax.set_xlabel('Periyot, T (saniye)', color=MODERN_PALETTE['text_sub'], labelpad=8, **sub_font)

        # 6. Scaling
        if use_log_scale:
            try:
                min_period = float(np.nanmin(period_data[period_data > 0])) if np.any(period_data > 0) else 1e-3
                ax.set_xscale('log')
                ax.set_xlim(left=max(1e-3, min_period))
            except: pass
        else:
            ax.set_xscale('linear')
            max_period = float(np.nanmax(period_data)) if np.size(period_data) > 0 else None
            ax.set_xlim(0, max_period) if max_period else ax.set_xlim(left=0)

        max_val = float(np.nanmax(acceleration_values)) if np.size(acceleration_values) > 0 else 1.0
        ax.set_ylim(0, max_val * 1.15)
        ax.tick_params(axis='both', which='major', labelsize=9, colors=MODERN_PALETTE['text_sub'])
        
        y_top = ax.get_ylim()[1]
        ax.yaxis.set_major_locator(ticker.MultipleLocator(y_top / 5))
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(
            lambda val, pos: f'{val:.2f}' if y_top <= 10 else f'{int(val)}'
        ))
        
        ax.tick_params(axis='both', which='major', labelsize=9, colors=MODERN_PALETTE['text_sub'])

        # 7. Design Parameters (TA, TB, TL)
        is_displacement = spectrum_info_dict.get('is_displacement', False)
        
        if graph_type == 'Düşey':
            pA, pB, pL = spectrum_info_dict.get('T_AD'), spectrum_info_dict.get('T_BD'), spectrum_info_dict.get('T_LD')
            sds_val = spectrum_info_dict.get('SDS_eff')
        else:
            pA, pB, pL = spectrum_info_dict.get('TA'), spectrum_info_dict.get('TB'), spectrum_info_dict.get('TL')
            sds_val = spectrum_info_dict.get('SDS')

        # 8. Vertical Parameter Lines (Dashed)
        critical_periods = [p for p in [pA, pB, pL] if p is not None and np.isfinite(p)]
        for p_val in critical_periods:
            ax.axvline(x=p_val, color=MODERN_PALETTE['border'], linestyle='--', linewidth=1, alpha=0.6, zorder=1)
            
            # Label logic
            tag = 'A' if p_val == pA else 'B' if p_val == pB else 'L'
            label_suffix = 'D' if graph_type == 'Düşey' else ''
            ax.text(p_val, ax.get_ylim()[1], f"$T_{{{tag}{label_suffix}}}$", 
                    ha='center', va='bottom', fontsize=8, color=MODERN_PALETTE['text_sub'])

        # X Tick Formatter for clean decimals
        ax.xaxis.set_major_formatter(ticker.FormatStrFormatter('%.1f'))

        # 9. SDS Summary Text and Legend
        if pA is not None and pB is not None and not is_displacement:
            unit_info = UnitConverter.get_unit_info('acceleration', unit)
            unit_symbol = unit_info.get('symbol', unit)
            summary_text = f"$S_{{DS}} = {sds_val:.2f}$ {unit_symbol}"
            
            y_offset = (ax.get_ylim()[1] - ax.get_ylim()[0]) * 0.04
            

            ax.text((pA + pB) / 2, sds_val + (y_offset * 0.5), summary_text, 
                    ha='center', va='bottom', fontsize=8, fontweight='bold', 
                    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec=MODERN_PALETTE['border'], alpha=0.9))

        try:
            chart_legend = ax.legend(loc='upper right', frameon=True, edgecolor=MODERN_PALETTE['border'], fontsize=8)
            chart_legend.get_frame().set_alpha(0.9)
        except: pass

        self.plotted_axes[graph_type] = ax
        
    def _get_dynamic_ylabel(self, base_ylabel, unit, graph_type):
        """Birime göre dinamik Y-label oluşturur (yalnızca birim bilgisi dahil)"""

        # Birim bilgisini al
        if 'İvme' in base_ylabel or graph_type in ['Yatay', 'Düşey']:
            unit_info = UnitConverter.get_unit_info('acceleration', unit)
            unit_symbol = unit_info.get('symbol', unit)

            # Temel ifadeyi birimle birlikte güncelle
            if graph_type == 'Yatay':
                return f'Spektral İvme, $S_{{ae}}$(T) [{unit_symbol}]'
            elif graph_type == 'Düşey':
                return f'Spektral İvme, $S_{{aeD}}$(T) [{unit_symbol}]'
            else:
                return f'Spektral İvme [{unit_symbol}]'

        elif 'Yerdeğiştirme' in base_ylabel or graph_type == 'Yerdeğiştirme':
            unit_info = UnitConverter.get_unit_info('displacement', unit)
            unit_symbol = unit_info.get('symbol', unit)
            return f'Spektral Yerdeğiştirme, $S_{{de}}$(T) [{unit_symbol}]'

        # Varsayılan durumda original ylabel'ı döndür (birim ekle)
        if unit:
            return f'{base_ylabel} [{unit}]'
        else:
            return f'{base_ylabel}'


    def _extract_symbol_from_ylabel(self, ax):
        """Y-etiketinden LaTeX sembolünü çıkar (örn: $S_{ae}$(T) gibi)"""
        try:
            ylabel = ax.get_ylabel()
            if not ylabel:
                return None

            # $...$ arasını yakala
            m = re.search(r"\$(.*?)\$", ylabel)
            if m:
                return m.group(1)

            # Alternatif: parantez öncesi metnin son kısmı
            m2 = re.search(r"([S][^\s,\(]+)", ylabel)
            return m2.group(1) if m2 else None
        except Exception:
            return None


    def _get_symbol_for_graph(self, graph_type):
        """Grafik türüne göre varsayılan sembol"""
        if graph_type == 'Yatay':
            return 'S_{ae}'
        if graph_type == 'Düşey':
            return 'S_{aeD}'
        if graph_type == 'Yerdeğiştirme':
            return 'S_{de}'
        return 'S'


    def _create_canvas(self):
        """Matplotlib canvas'ını oluşturur ve ikonları bozmadan değiştirir"""
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.parent_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

        self.canvas.mpl_connect('motion_notify_event', self._on_mouse_move)
        self.canvas.mpl_connect('key_press_event', self._on_key_press)
        self.canvas.mpl_connect('button_press_event', self._on_mouse_click)
        self.canvas.mpl_connect('draw_event', self._on_draw_event)

        controls_parent = getattr(self, 'controls_frame', None) or self.parent_frame

        try:
            self.toolbar = NavigationToolbar2Tk(self.canvas, controls_parent, pack_toolbar=False)
            self.toolbar.update()

            if not hasattr(self, "_toolbar_image_refs"):
                self._toolbar_image_refs = []
            self._toolbar_image_refs.clear()

            modern_icons_map = {
                "Home":     "home_gray.png",
                "Back":     "arrow_left.png",
                "Forward":  "arrow_right.png",
                "Pan":      "pan2.png",
                "Zoom":     "zoom2.png",
                "Subplots": "settings.png",
                "Save":     "save2.png",
            }

            for child in self.toolbar.winfo_children():
                widget_class = child.winfo_class()
                
                if widget_class in ('Button', 'Checkbutton'):
                    try:
                        btn_text = child.cget("text")
                        if btn_text in modern_icons_map:
                            img = self._load_icon2(self._icons_dir / modern_icons_map[btn_text])
                            if img:
                                self._toolbar_image_refs.append(img)
                                child._original_text = btn_text

                                if widget_class == 'Checkbutton':
                                    # Checkbutton: selectimage'ı da aynı ikon yap
                                    # böylece seçili/seçilmemiş hali aynı görünür
                                    child.configure(
                                        image=img,
                                        selectimage=img,
                                        indicatoron=False,
                                        text="",
                                        relief="flat",
                                        borderwidth=0,
                                        highlightthickness=0,
                                        compound="center",
                                        offrelief="flat",
                                        overrelief="flat",
                                        selectcolor=child.cget("bg")
                                    )
                                else:
                                    # Normal Button
                                    child.configure(
                                        image=img,
                                        text="",
                                        relief="flat",
                                        borderwidth=0,
                                        highlightthickness=0,
                                        compound="center"
                                    )
                                
                                child.configure(activebackground=child.cget("bg"))

                        elif btn_text in ["Subplots", "Customize"]:
                            child.pack_forget()
                    except Exception as e:
                        logger.debug(f"Button config error: {e}")
                        continue

            self.toolbar.pack(side="left", padx=(8, 0), pady=(2, 6))

        except Exception as e:
            logger.debug("Toolbar hatası: %s", e)

        try:
            self._create_action_bar()
        except Exception:
            pass
    
    def _clear_canvas(self):
        """Canvas'ı temizler"""
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.toolbar:
            self.toolbar.destroy()


    def _create_hover_annotations(self):
        """Hover annotation'larını oluşturur"""

        # Önce mevcut hover anotasyonlarını kaldır
        try:
            for ann in self.hover_annotations:
                try:
                    ann.remove()
                except Exception:
                    pass
        except Exception:
            pass

        self.hover_annotations.clear()

        for plot_data in self.plot_data:
            ax = plot_data['ax']

            # Her grafik için tek bir annotation oluştur
            annotation = ax.annotate(
                '',
                xy=(0, 0),
                xytext=(20, 20),
                textcoords="offset points",
                bbox=dict(
                    boxstyle="round,pad=0.5",
                    facecolor='#FFF8DC',
                    alpha=0.95,
                    edgecolor='#333333',
                    linewidth=0.5
                ),
                arrowprops=dict(
                    arrowstyle='->',
                    connectionstyle='arc3,rad=0.1',
                    color='#333333',
                    alpha=0.8
                ),
                fontsize=9,
                fontweight='normal',
                visible=False
            )

            try:
                annotation.set_clip_on(False)
                annotation.set_zorder(10)
            except Exception:
                pass

            self.hover_annotations.append(annotation)


    def _create_crosshair_lines(self):
        """Her eksende crosshair çizgileri oluşturur"""

        # Eski çizgileri kaldır
        for pair in self.crosshair_lines:
            try:
                v, h = pair
                v.remove()
                h.remove()
            except Exception:
                pass

        self.crosshair_lines.clear()

        # Yeni çizgiler
        for plot_data in self.plot_data:
            ax = plot_data['ax']
            vline = ax.axvline(
                x=0,
                color='#999999',
                linestyle='--',
                linewidth=0.8,
                alpha=0.5,
                visible=False
            )
            hline = ax.axhline(
                y=0,
                color='#999999',
                linestyle='--',
                linewidth=0.8,
                alpha=0.5,
                visible=False
            )
            self.crosshair_lines.append((vline, hline))

        # Arka plan önbelleğini yenile
        self._blit_need_recache = True


    def _toggle_grid(self):
        try:
            self._grid_visible = not getattr(self, '_grid_visible', True)
            for ax in self.figure.axes:
                ax.grid(self._grid_visible, which='both', linestyle='-', linewidth=0.5)

            if self.canvas:
                if self._blit_enabled:
                    self._blit_need_recache = True
                    self._blit_redraw(force_full=True)
                else:
                    self.canvas.draw_idle()
        except Exception as e:
            logger.debug("_toggle_grid failed: %s", e)


    def _toggle_log(self):
        try:
            for plot in self.plot_data:
                ax = plot['ax']
                is_log = (ax.get_xscale() == 'log')
                if is_log:
                    ax.set_xscale('linear')
                    ax.set_xlim(left=0)
                else:
                    # Güvenli sol sınır
                    T = np.asarray(plot['T']) if isinstance(plot['T'], np.ndarray) else np.array(plot['T'])
                    Tmin = float(np.nanmin(T[T > 0])) if np.any(T > 0) else 1e-3
                    ax.set_xscale('log')
                    ax.set_xlim(left=max(1e-3, Tmin))

            if self.canvas:
                if self._blit_enabled:
                    self._blit_need_recache = True
                    self._blit_redraw(force_full=True)
                else:
                    self.canvas.draw_idle()
        except Exception as e:
            logger.debug("_toggle_log failed: %s", e)


    def _toggle_ref_lines(self):
        try:
            if not hasattr(self, '_ref_lines'):
                self._ref_lines = []

            any_visible = any(getattr(ln, 'get_visible', lambda: False)() for ln in self._ref_lines)
            for ln in self._ref_lines:
                try:
                    ln.set_visible(not any_visible)
                except Exception:
                    continue

            if self.canvas:
                if self._blit_enabled:
                    self._blit_redraw()
                else:
                    self.canvas.draw_idle()
        except Exception as e:
            logger.debug("_toggle_ref_lines failed: %s", e)


    def _toggle_crosshair(self):
        try:
            self._crosshair_visible = not getattr(self, '_crosshair_visible', True)
            for v, h in self.crosshair_lines:
                v.set_visible(self._crosshair_visible)
                h.set_visible(False if not self._crosshair_visible else h.get_visible())

            if self.canvas:
                if self._blit_enabled:
                    self._blit_redraw()
                else:
                    self.canvas.draw_idle()
        except Exception as e:
            logger.debug("_toggle_crosshair failed: %s", e)


    def _on_key_press(self, event):
        try:
            if not event or not hasattr(event, 'key'):
                return

            key = str(event.key).lower()
            if key == 'g':
                self._toggle_grid()
            elif key == 'l':
                self._toggle_log()
            elif key == 'r':
                self._toggle_ref_lines()
            elif key == 'c':
                self._toggle_crosshair()
        except Exception as e:
            logger.debug("_on_key_press failed: %s", e)


    def _on_draw_event(self, event):
        """Blit arka planlarını yakala"""
        try:
            if not self._blit_enabled:
                return

            # Her axes için arka planı belleğe kaydet
            self._backgrounds.clear()
            for ax in self.figure.axes:
                try:
                    self._backgrounds[ax] = self.canvas.copy_from_bbox(ax.bbox)
                except Exception:
                    continue

            self._blit_need_recache = False
        except Exception:
            self._blit_enabled = False


    def _blit_redraw(self, force_full=False):
        """Sadece gerekli sanatçıları blit ile yeniden çiz"""
        try:
            if not self._blit_enabled:
                self.canvas.draw_idle()
                return

            if force_full or self._blit_need_recache or not self._backgrounds:
                # Tam çizim yapılır, arka planlar draw_event ile güncellenir
                self.canvas.draw_idle()
                return

            # Her eksen için arka planı geri yükle ve sadece değişen sanatçıları çiz
            for ax in self.figure.axes:
                if ax not in self._backgrounds:
                    continue

                try:
                    self.canvas.restore_region(self._backgrounds[ax])
                except Exception:
                    continue

                # Crosshair çizgileri ve hover annotation'ı bu eksende ise çiz

                # Crosshair'lar
                for (v, h), plot in zip(self.crosshair_lines, self.plot_data):
                    if plot['ax'] is ax:
                        try:
                            v.draw(ax.figure.canvas.get_renderer())
                            h.draw(ax.figure.canvas.get_renderer())
                        except Exception:
                            pass

                # Hover anotasyonu
                for ann, plot in zip(self.hover_annotations, self.plot_data):
                    if plot['ax'] is ax and ann.get_visible():
                        try:
                            ann.draw(ax.figure.canvas.get_renderer())
                        except Exception:
                            pass

                # Ekrana it
                try:
                    self.canvas.blit(ax.bbox)

                    # Hover annotation eksen sınırlarını aşıyorsa tam çizim yap
                    for ann, plot in zip(self.hover_annotations, self.plot_data):
                        if plot['ax'] is ax and ann.get_visible():
                            renderer = ax.figure.canvas.get_renderer()
                            bbox = ann.get_window_extent(renderer=renderer)
                            if not ax.bbox.contains(bbox.x0, bbox.y0) or not ax.bbox.contains(bbox.x1, bbox.y1):
                                self.canvas.draw_idle()
                                break
                except Exception:
                    try:
                        self.canvas.draw_idle()
                    except Exception:
                        pass

        except Exception as e:
            # Hata olursa blit'i kapatıp normal draw'a dön
            logger.debug("_blit_redraw failed, disabling blit: %s", e)
            try:
                self._blit_enabled = False
                self.canvas.draw_idle()
            except Exception:
                pass


    def _on_mouse_move(self, event):
        """Mouse hareket ettiğinde hover değerlerini göster"""
        if not event.inaxes or not self.plot_data:
            # Mouse grafik alanından çıktığında tüm annotations'ları gizle
            for annotation in self.hover_annotations:
                annotation.set_visible(False)

            # Crosshair'ları gizle
            for v, h in self.crosshair_lines:
                v.set_visible(False)
                h.set_visible(False)

            # Status bar'ı sıfırla
            if self.status_label:
                try:
                    self.status_label.config(text="Hazır")
                except Exception:
                    pass

            if self.canvas:
                if self._blit_enabled:
                    self._blit_redraw()
                else:
                    self.canvas.draw_idle()
            return

        try:
            # Her plot verisi için kontrol et
            for i, plot_data in enumerate(self.plot_data):
                if event.inaxes == plot_data['ax']:
                    # Hover annotations listesi yeterince uzun mu kontrol et
                    if i < len(self.hover_annotations):
                        # İlgili eksen için enterpole edilmis y değeri
                        y_interp = None
                        try:
                            if event.xdata is not None:
                                T_arr = np.asarray(plot_data['T'])
                                V_arr = np.asarray(plot_data['values'])
                                y_interp = float(np.interp(event.xdata, T_arr, V_arr))
                        except Exception:
                            y_interp = event.ydata

                        self._show_hover_value(event, plot_data, self.hover_annotations[i])

                        # Senkronize crosshair: tüm alt eksenlerde aynı x konumu
                        if event.xdata is not None:
                            for j, pair in enumerate(self.crosshair_lines):
                                try:
                                    v, h = pair
                                    v.set_xdata([event.xdata, event.xdata])
                                    v.set_visible(True)

                                    # Yatay çizgi sadece aktif eksende görünür
                                    if j == i and y_interp is not None:
                                        h.set_ydata([y_interp, y_interp])
                                        h.set_visible(True)
                                    else:
                                        h.set_visible(False)
                                except Exception:
                                    continue

                        # Status bar text
                        if self.status_label and event.xdata is not None:
                            try:
                                unit = plot_data.get('unit', '')
                                val_for_status = y_interp if y_interp is not None else event.ydata
                                if val_for_status is not None:
                                    self.status_label.config(
                                        text=f"T={event.xdata:.3f} s, Değer={val_for_status:.4f} {unit}"
                                    )
                            except Exception:
                                pass

                        # Diğer annotations'ları gizle
                        for j, annotation in enumerate(self.hover_annotations):
                            if j != i:
                                annotation.set_visible(False)

                        if self.canvas:
                            if self._blit_enabled:
                                self._blit_redraw()
                            else:
                                self.canvas.draw_idle()
                        break
            else:
                # Hiçbir plot area'sında değilse tümünü gizle
                for annotation in self.hover_annotations:
                    annotation.set_visible(False)

                # Tüm crosshair çizgilerini gizle
                for v, h in self.crosshair_lines:
                    v.set_visible(False)
                    h.set_visible(False)

                if self.canvas:
                    if self._blit_enabled:
                        self._blit_redraw()
                    else:
                        self.canvas.draw_idle()

        except (IndexError, AttributeError, ValueError):
            # Hata durumunda sessizce geç
            for annotation in self.hover_annotations:
                annotation.set_visible(False)


    def _show_hover_value(self, event, plot_data, annotation):
        """Hover değerini gösterir - TBDY_GUI.py'den entegre"""
        try:
            if event.inaxes != plot_data['ax']:
                annotation.set_visible(False)
                return

            # Enterpolasyon ile hover değeri
            T_data = np.asarray(plot_data['T'])
            values_data = np.asarray(plot_data['values'])

            if event.xdata is None:
                annotation.set_visible(False)
                return

            interp_value = float(np.interp(event.xdata, T_data, values_data))
            closest_T = float(event.xdata)
            closest_value = interp_value

            # Annotation metnini ayarla
            unit_code = plot_data.get('unit', '')
            graph_type = plot_data.get('type', '')

            # Doğru birim simgesini al
            if graph_type == 'Yerdeğiştirme':
                unit_info = UnitConverter.get_unit_info('displacement', unit_code)
            else:
                unit_info = UnitConverter.get_unit_info('acceleration', unit_code)
            unit_symbol = unit_info.get('symbol', unit_code)

            symbol = plot_data.get('symbol') or self._get_symbol_for_graph(graph_type)
            hover_text = f'T={closest_T:.3f}s\n${symbol}$={closest_value:.4f} {unit_symbol}'

            annotation.set_text(hover_text)
            annotation.xy = (closest_T, closest_value)
            annotation.set_visible(True)

            # Canvas'ı güncelle
            if self.canvas:
                try:
                    self.figure.canvas.draw_idle()
                except Exception:
                    if self._blit_enabled:
                        self._blit_redraw()
                    else:
                        self.canvas.draw_idle()

        except Exception as e:
            # Hata durumunda annotation'ı gizle
            annotation.set_visible(False)


    def get_figure(self):
        """Mevcut figure'ı döndürür"""
        return self.figure


    def get_plotted_axes(self):
        """Çizilmiş axes'leri döndürür"""
        return self.plotted_axes


    def clear_plot(self):
        """Mevcut grafikleri ve verileri temizler"""
        self.plot_lines.clear()
        self.plot_data.clear()
        self.plotted_axes.clear()
        self.hover_annotations.clear()  # Hover annotations'ı da temizle

        # Pin'lenen anotasyonları kaldır
        try:
            for ann, marker in self.pinned_annotations:
                try:
                    ann.remove()
                except Exception:
                    pass
                try:
                    marker.remove()
                except Exception:
                    pass
        except Exception:
            pass

        self.pinned_annotations.clear()
        self.figure.clear()


    def _on_mouse_click(self, event):
        """Sol tık: hover bilgisini pin'le; Sağ tık: son pini kaldır"""
        try:
            if not event or not event.inaxes:
                return
            
            try:
                if self.toolbar and str(self.toolbar.mode) != "":
                    return
            except Exception:
                pass
            ax = event.inaxes

            # İlgili plot_data'yı bul
            target_idx = None
            for i, plot_data in enumerate(self.plot_data):
                if plot_data['ax'] is ax:
                    target_idx = i
                    break

            if target_idx is None:
                return

            plot_data = self.plot_data[target_idx]

            # Sol tık: pin ekle
            if event.button == 1:
                if event.xdata is None:
                    return

                T_arr = np.asarray(plot_data['T'])
                V_arr = np.asarray(plot_data['values'])
                try:
                    y_val = float(np.interp(event.xdata, T_arr, V_arr))
                except Exception:
                    y_val = event.ydata

                # Anotasyonu oluştur
                unit_code = plot_data.get('unit', '')
                graph_type = plot_data.get('type', '')

                if graph_type == 'Yerdeğiştirme':
                    unit_info = UnitConverter.get_unit_info('displacement', unit_code)
                else:
                    unit_info = UnitConverter.get_unit_info('acceleration', unit_code)

                unit_symbol = unit_info.get('symbol', unit_code)
                symbol = plot_data.get('symbol') or self._get_symbol_for_graph(graph_type)

                text = f"T={event.xdata:.3f}s\n${symbol}$={y_val:.4f} {unit_symbol}"
                ann = ax.annotate(
                    text,
                    xy=(event.xdata, y_val),
                    xytext=(15, 15),
                    textcoords="offset points",
                    bbox=dict(
                        boxstyle="round,pad=0.5",
                        facecolor="#E8F6FF",
                        alpha=0.97,
                        edgecolor="#2266AA",
                        linewidth=0.6
                    ),
                    arrowprops=dict(
                        arrowstyle='->',
                        color='#2266AA',
                        alpha=0.8,
                        linewidth=0.8
                    ),
                    fontsize=9,
                    visible=True
                )

                # Nokta işareti
                marker, = ax.plot(
                    [event.xdata],
                    [y_val],
                    marker='o',
                    color=CUSTOM_COLORS.get('nokta', '#d35400'),
                    markersize=4,
                    alpha=0.9
                )

                self.pinned_annotations.append((ann, marker))

                # Aynı eksendeki hover anotasyonunu gizle (mavi ve sarı üst üste görünmesin)
                try:
                    if target_idx is not None and target_idx < len(self.hover_annotations):
                        self.hover_annotations[target_idx].set_visible(False)
                except Exception:
                    pass

                if self.canvas:
                    if self._blit_enabled:
                        self._blit_need_recache = True
                        self._blit_redraw(force_full=True)
                    else:
                        self.canvas.draw_idle()

            # Sağ tık: bu eksendeki son pini kaldır
            elif event.button == 3:
                # Sondan geriye doğru ilk aynı eksene ait olanı bul
                for idx in range(len(self.pinned_annotations) - 1, -1, -1):
                    ann, marker = self.pinned_annotations[idx]
                    try:
                        if ann.axes is ax:
                            try:
                                ann.remove()
                            except Exception:
                                pass
                            try:
                                marker.remove()
                            except Exception:
                                pass

                            del self.pinned_annotations[idx]

                            if self.canvas:
                                if self._blit_enabled:
                                    self._blit_need_recache = True
                                    self._blit_redraw(force_full=True)
                                else:
                                    self.canvas.draw_idle()
                            break
                    except Exception:
                        continue

        except Exception:
            pass


    def show_placeholder(self, text="Hesaplama yapmak için lütfen\nveri setini içeren dosyayı yükleyin."):
        """Placeholder grafik gösterir"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            text,
            ha='center',
            va='center',
            fontsize=15,
            fontweight='medium',
            bbox=dict(boxstyle="round,pad=1.0", fc='white', alpha=0.8, ec=CUSTOM_COLORS['text'])
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        ax.set_facecolor('#FAFAFA')
        self.canvas.draw()


    def _add_custom_toolbar_buttons(self):
        """NavigationToolbar'a özel butonlar ekler"""
        return
    
    
    def _load_icon(self, path: Path):
        from PIL import Image, ImageTk
        try:
            img = Image.open(str(path)).convert("RGBA")
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"İkon yüklenemedi: {path} -> {e}")
            return None
        
    def _load_icon2(self, path: Path):
        from PIL import Image, ImageTk
        try:
            img = Image.open(str(path)).convert("RGBA")
            img = img.resize((24, 24), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(img)
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

        # ✅ GERÇEK spacer (width artık çalışır)
        spacer = ttk.Frame(bar, width=30)   # 🔧 BURAYI DEĞİŞTİR
        spacer.pack(side="left", fill="y")
        spacer.pack_propagate(False)

        BTN_H = 34
        R = 8
        CANVAS_BG = "#FFFFFF"
        W14 = 140

        if not hasattr(self, "_action_icons"):
            self._action_icons = {
                "pan":  self._load_icon(self._icons_dir / "pan.png"),
                "zoom": self._load_icon(self._icons_dir / "zoom.png"),
                "home": self._load_icon(self._icons_dir / "reset.png"),
                "copy": self._load_icon(self._icons_dir / "image.png"),
                "csv2": self._load_icon(self._icons_dir / "csv2.png"),
            }

        f = getattr(self, "font", None)

        def btn(text, icon, cmd, padx=2):
            b = RoundedButton(
                bar, text=text,
                image=self._action_icons.get(icon),
                on_click=cmd,
                height=BTN_H, radius=R,
                canvas_bg=CANVAS_BG, font=f
            )
            b.pack(side="left", padx=padx)
            b.config(width=W14)

        btn("Pan", "pan", lambda: self._toolbar_action("pan"))
        btn("Zoom", "zoom", lambda: self._toolbar_action("zoom"))
        btn("Reset", "home", lambda: self._toolbar_action("home"))
        btn("PNG Kopyala", "copy", self._copy_png_to_clipboard, padx=6)
        btn("CSV Dışa Aktar", "csv2", self._export_csv)
        
        try:
            if hasattr(self, "toolbar") and hasattr(self.toolbar, "_message_label"):
                self.toolbar._message_label.configure(width=30, anchor="w")
        except Exception:
            pass

    def _restore_toolbar_icons(self):
        """Zoom/Pan sonrası toolbar ikonlarını orijinal hallerine zorla döndürür."""
        try:
            modern_icons_map = {
                "Home":     "home_gray.png",
                "Back":     "arrow_left.png",
                "Forward":  "arrow_right.png",
                "Pan":      "pan2.png",
                "Zoom":     "zoom2.png",
                "Save":     "save2.png",
            }
            for child in self.toolbar.winfo_children():
                if "button" in str(child).lower():
                    try:
                        btn_text = getattr(child, '_original_text', '')
                        if btn_text in modern_icons_map:
                            img = self._load_icon2(self._icons_dir / modern_icons_map[btn_text])
                            if img:
                                if not hasattr(self, '_toolbar_image_refs'):
                                    self._toolbar_image_refs = []
                                self._toolbar_image_refs.append(img)
                                child.configure(image=img, text="", compound="center")
                    except Exception:
                        continue
        except Exception:
            pass

    def _toolbar_action(self, action: str):
        """Matplotlib toolbar aksiyonlarını tetikler ve durumu günceller."""
        if not self.toolbar:
            return
        try:
            if action == "pan":
                self.toolbar.pan()
                status = "Pan modu"
            elif action == "zoom":
                self.toolbar.zoom()
                status = "Zoom kutusu"
            elif action == "home":
                self.toolbar.home()
                status = "Görünüm sıfırlandı"
            else:
                return

            if self.status_label:
                self.status_label.config(text=status)
        except Exception as e:
            logger.debug("Toolbar action failed (%s): %s", action, e)

    def _copy_png_to_clipboard(self):
        """Figure'ı PNG olarak panoya kopyalar (Windows'ta CF_DIB; aksi halde kaydet)"""
        try:
            try:
                import win32clipboard, win32con  # type: ignore
                from PIL import Image
                self.figure.canvas.draw()
                width, height = self.figure.canvas.get_width_height()
                rgb = self.figure.canvas.tostring_rgb()
                img = Image.frombytes('RGB', (width, height), rgb)
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
                if self.status_label:
                    self.status_label.config(text='PNG panoya kopyalandı')
                return
            except Exception:
                pass
            file_path = filedialog.asksaveasfilename(
                defaultextension='.png',
                filetypes=[('PNG dosyası', '*.png')],
                title='PNG olarak kaydet'
            )
            if file_path:
                self.figure.savefig(file_path, format='png', dpi=300)
                if self.status_label:
                    self.status_label.config(text=f'PNG kaydedildi: {file_path}')
        except Exception as e:
            try:
                messagebox.showerror('Hata', f'PNG kopyalanamadı/kaydedilemedi.\n{e}')
            except Exception:
                pass

    def _export_csv(self):
        """Grafik verilerini tek bir CSV'ye dışa aktarır"""
        if not self.plot_data:
            try:
                messagebox.showinfo('Bilgi', 'Dışa aktarılacak veri yok.')
            except Exception:
                pass
            return
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV dosyası', '*.csv')],
                title='CSV dışa aktar'
            )
            if not file_path:
                return
            base_T = np.asarray(self.plot_data[0]['T'], dtype=float)
            columns = [base_T]
            headers = ['T']
            for plot in self.plot_data:
                values = np.asarray(plot['values'], dtype=float)
                T_vals = np.asarray(plot['T'], dtype=float)
                if len(T_vals) != len(base_T) or np.any(T_vals != base_T):
                    values = np.interp(base_T, T_vals, values)
                unit = plot.get('unit', '')
                gtype = plot.get('type', 'Seri')
                headers.append(f'{gtype} ({unit})')
                columns.append(values)
            data = np.column_stack(columns)
            header_line = ','.join(headers)
            np.savetxt(file_path, data, delimiter=',', header=header_line, comments='', fmt='%.10g')
            if self.status_label:
                self.status_label.config(text=f'CSV kaydedildi: {file_path}')
        except Exception as e:
            try:
                messagebox.showerror('Hata', f'CSV dışa aktarımı başarısız.\n{e}')
            except Exception:
                pass

    def _show_ref_menu(self):
        """Referans çizgileri için menü"""
        try:
            if not hasattr(self, '_ref_menu') or self._ref_menu is None:
                # Menü kökünü top-level'e bağla; toolbar GC/odak sorunlarını önler
                root = self.parent_frame.winfo_toplevel()
                self._ref_menu = tk.Menu(root, tearoff=0)
                self._ref_menu.add_command(label='Ref. çizgi ekle...', command=self._add_reference_line_dialog)
                self._ref_menu.add_command(label='Referans çizgiyi göster', command=self._toggle_ref_lines)
                self._ref_menu.add_command(label='Son ref. çizgiyi kaldır', command=self._remove_last_reference_line)
            x = self.toolbar.winfo_pointerx(); y = self.toolbar.winfo_pointery()
            try:
                if hasattr(self._ref_menu, 'tk_popup'):
                    self._ref_menu.tk_popup(x, y)
                else:
                    self._ref_menu.post(x, y)
            finally:
                try:
                    self._ref_menu.grab_release()
                except Exception:
                    pass
        except Exception:
            try:
                self._add_reference_line_dialog()
            except Exception:
                pass

    def _add_reference_line_dialog(self):
        """Kullanıcıdan T değeri(leri) alıp ref. çizgisi ekle"""
        try:
            parent = None
            try:
                parent = self.parent_frame.winfo_toplevel()
            except Exception:
                parent = None
            text = simpledialog.askstring('Ref. çizgi ekle', 'Periyot T değer(ler)i (virgülle):', parent=parent)
            if not text:
                return
            parts = [p.strip() for p in text.replace(';', ',').split(',') if p.strip()]
            t_values = []
            for p in parts:
                try:
                    val = float(p)
                    if val >= 0:
                        t_values.append(val)
                except Exception:
                    continue
            if not t_values:
                return
            for t_val in t_values:
                for ax in self.figure.axes:
                    try:
                        color = CUSTOM_COLORS.get('ref', '#455A64')
                        ln = ax.axvline(
                            x=float(t_val), color=color, linestyle='-.',
                            linewidth=1.1, alpha=0.95, zorder=6
                        )
                        try:
                            ln.set_gid('ref_line')
                        except Exception:
                            pass
                        self._ref_lines.append(ln)
                    except Exception:
                        continue
            if self.canvas:
                if getattr(self, '_blit_enabled', False):
                    try:
                        self._blit_need_recache = True
                        self._blit_redraw(force_full=True)
                    except Exception:
                        self.canvas.draw_idle()
                else:
                    self.canvas.draw_idle()
        except Exception:
            pass

    def _remove_last_reference_line(self):
        """Eklenen son referans çizgisini kaldır"""
        try:
            for idx in range(len(self._ref_lines) - 1, -1, -1):
                ln = self._ref_lines[idx]
                try:
                    ln.remove()
                except Exception:
                    pass
                del self._ref_lines[idx]
                break
            if self.canvas:
                self.canvas.draw_idle()
        except Exception:
            pass
