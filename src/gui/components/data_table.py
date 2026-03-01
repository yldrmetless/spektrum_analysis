"""
Veri tablosu bileşeni
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ...utils.file_utils import FileUtils
import customtkinter as ctk

class DataTable:
    """Veri tablosu bileşeni sınıfı"""

    # Tasarım sabitleri – 2. resim: tamamen beyaz, minimal, satır çizgili
    _HEADER_BG = "#FFFFFF"
    _HEADER_FG = "#1F2937"
    _ROW_BG_EVEN = "#FFFFFF"
    _ROW_BG_ODD = "#F8F9FB"
    _ROW_HEIGHT = 32
    _SEPARATOR_COLOR = "#E5E7EB"
    _HEADER_FONT = ('Poppins', 10, 'bold')
    _CELL_FONT = ('Poppins', 9)
    _SELECTED_BG = "#DBEAFE"
    _SELECTED_FG = "#1E3A5F"

    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        self.tree = None
        self.vsb = None
        self.hsb = None
        self._style_configured = False

        # Arayüzü oluştur
        self._create_widgets()
        self.show_placeholder()

    def _create_widgets(self):
        """Widget'ları oluşturur"""
        # Ana çerçeve zaten parent_frame olarak geliyor
        pass

    def _configure_table_style(self):
        """Tablo için özel ttk stilini yapılandırır"""
        if self._style_configured:
            return
        try:
            style = ttk.Style()
            # Treeview gövdesi
            style.configure("DataTable.Treeview",
                        background=self._ROW_BG_EVEN,
                        fieldbackground=self._ROW_BG_EVEN,
                        foreground="#374151",
                        rowheight=self._ROW_HEIGHT,
                        font=self._CELL_FONT,
                        borderwidth=1,
                        relief="flat",
                        bordercolor=self._SEPARATOR_COLOR)
            # Başlık
            style.configure("DataTable.Treeview.Heading",
                        background=self._HEADER_BG,
                        foreground=self._HEADER_FG,
                        font=self._HEADER_FONT,
                        relief="flat",
                        borderwidth=1,
                        bordercolor=self._SEPARATOR_COLOR,
                        padding=(12, 8))
            style.map("DataTable.Treeview.Heading",
                    background=[('active', '#F9FAFB')],
                    relief=[('active', 'flat')])
            style.map("DataTable.Treeview",
                    background=[('selected', self._SELECTED_BG)],
                    foreground=[('selected', self._SELECTED_FG)])
            
            # Dış border'ı kaldır
            style.layout("DataTable.Treeview", [
                ('Treeview.treearea', {'sticky': 'nswe'})
            ])

            # Modern dikey scrollbar stili
            style.configure("Modern.Vertical.TScrollbar",
                        background="#E5E7EB",
                        troughcolor="#F9FAFB",
                        borderwidth=0,
                        relief="flat",
                        width=8)
            style.map("Modern.Vertical.TScrollbar",
                    background=[('active', '#CBD5E1'), ('pressed', '#94A3B8')])

            self._style_configured = True
        except Exception:
            pass

    def _apply_row_striping(self):
        """Satır arası çizgi efekti için çok hafif alternatif renklendirme uygular"""
        if not self.tree:
            return
        try:
            self.tree.tag_configure('even_row', background=self._ROW_BG_EVEN)
            self.tree.tag_configure('odd_row', background=self._ROW_BG_ODD)
            for i, item in enumerate(self.tree.get_children()):
                tag = 'even_row' if i % 2 == 0 else 'odd_row'
                self.tree.item(item, tags=(tag,))
        except Exception:
            pass

    def _create_icon_button(self, parent, icon_text, icon_color, label_text, command):
        """2. resimdeki gibi renkli ikon + metin buton oluşturur"""
        btn_frame = tk.Frame(parent, bg="#FFFFFF", cursor="hand2",
                            highlightbackground="#E5E7EB", highlightthickness=1,
                            padx=10, pady=6)

        icon_lbl = tk.Label(btn_frame, text=icon_text, fg=icon_color,
                           bg="#FFFFFF", font=('Poppins', 10))
        icon_lbl.pack(side='left', padx=(0, 4))

        text_lbl = tk.Label(btn_frame, text=label_text, fg="#374151",
                           bg="#FFFFFF", font=('Poppins', 9))
        text_lbl.pack(side='left')

        # Tüm child widget'lara tıklama ve hover bağla
        def on_click(e):
            command()
        def on_enter(e):
            btn_frame.configure(bg="#F9FAFB")
            icon_lbl.configure(bg="#F9FAFB")
            text_lbl.configure(bg="#F9FAFB")
        def on_leave(e):
            btn_frame.configure(bg="#FFFFFF")
            icon_lbl.configure(bg="#FFFFFF")
            text_lbl.configure(bg="#FFFFFF")

        for w in (btn_frame, icon_lbl, text_lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return btn_frame

    def show_placeholder(self, text="Verileri görmek için önce bir hesaplama yapın."):
        """Placeholder mesajı gösterir"""
        self._clear_widgets()

        placeholder_label = ttk.Label(
            self.parent_frame,
            text=text,
            font=('Poppins', 12)
        )
        placeholder_label.pack(expand=True)

    def update_data(self, dataframe):
        """Veri tablosunu günceller"""
        self._clear_widgets()

        if dataframe is None or dataframe.empty or len(dataframe.columns) <= 1:
            self.show_placeholder()
            return

        # Özel tablo stilini yapılandır
        self._configure_table_style()

        # Tablo container'ı oluştur
        table_container = ttk.Frame(self.parent_frame)
        table_container.pack(fill="both", expand=True)

        # Tüm sütunları hazırla (index + columns)
        # Not: Index adı, sütunlar içinde zaten varsa TEKRAR EKLEME.
        all_columns = []
        index_name = dataframe.index.name if dataframe.index.name else None
        include_index = bool(index_name) and (index_name not in dataframe.columns)
        if include_index:
            all_columns.append(index_name)
        all_columns.extend(dataframe.columns.tolist())

        # Treeview container (scrollbar düzeni için)
        tree_frame = ttk.Frame(table_container)
        tree_frame.pack(fill="both", expand=True)

        # Treeview oluştur
        self.tree = ttk.Treeview(tree_frame, columns=all_columns, show='headings',
                                style="DataTable.Treeview")

        # Sütun başlıklarını ayarla – ortaya hizalı
        for col in all_columns:
            self.tree.heading(col, text=col, anchor='center')
            self.tree.column(col, width=250, anchor='center')

        # Verileri ekle - profesyonel format ile
        from src.config.styles import format_table_value
        for index, row in dataframe.iterrows():
            formatted_values = []

            # Index değerini ekle (sadece include_index True ise)
            if include_index:
                if isinstance(index, (int, float)):
                    # Periyot için time formatını kullan
                    if index_name and 'periyot' in index_name.lower():
                        formatted_values.append(format_table_value(index, "time"))
                    else:
                        formatted_values.append(format_table_value(index, "general"))
                else:
                    formatted_values.append(str(index))

            # Diğer sütunları ekle
            for col_name, val in zip(dataframe.columns, row):
                if isinstance(val, (int, float)):
                    # Sütun adına göre veri türünü belirle
                    if 'time' in col_name.lower() or 'zaman' in col_name.lower():
                        formatted_values.append(format_table_value(val, "time"))
                    elif 'accel' in col_name.lower() or 'ivme' in col_name.lower():
                        formatted_values.append(format_table_value(val, "acceleration"))
                    elif 'vel' in col_name.lower() or 'hız' in col_name.lower():
                        formatted_values.append(format_table_value(val, "velocity"))
                    elif 'disp' in col_name.lower() or 'yerdeğiştirme' in col_name.lower():
                        formatted_values.append(format_table_value(val, "displacement"))
                    else:
                        formatted_values.append(format_table_value(val, "general"))
                else:
                    formatted_values.append(str(val))
            self.tree.insert("", "end", values=formatted_values)

        # Satır arası çizgi efekti için hafif renklendirme uygula
        self._apply_row_striping()

        # Scrollbar'ları oluştur
        self.vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                                  command=self.tree.yview,
                                  style="Modern.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=self.vsb.set)

        # Layout
        self.vsb.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

        # CTRL+A ile tümünü seçme özelliği
        self.tree.bind("<Control-a>", lambda event: self._select_all())
        self.tree.bind("<Control-A>", lambda event: self._select_all())

        # Butonları oluştur
        self._create_buttons()

    def _create_buttons(self):
        """Butonları oluşturur"""
        button_bar = tk.Frame(self.parent_frame, bg="#FFFFFF", pady=10, padx=4)
        button_bar.pack(fill='x', pady=(6, 0))

        # Verileri kopyala butonu
        copy_button = self._create_icon_button(
            button_bar, "\U0001F4CB", "#3B82F6", "Verileri Kopyala",
            self._copy_data_to_clipboard
        )
        copy_button.pack(side='left', padx=(0, 6))

        # Excel'e aktar butonu
        export_button = self._create_icon_button(
            button_bar, "\U0001F4CA", "#10B981", "Excel'e Aktar",
            self._export_data_to_excel
        )
        export_button.pack(side='left', padx=(0, 6))

        # CSV'ye aktar butonu
        csv_button = self._create_icon_button(
            button_bar, "\U0001F4C4", "#F59E0B", "CSV'ye Aktar",
            self.export_to_csv
        )
        csv_button.pack(side='left', padx=(0, 6))

    def _clear_widgets(self):
        """Widget'ları temizler"""
        for widget in self.parent_frame.winfo_children():
            widget.destroy()

    def _select_all(self):
        """Tüm satırları seçer"""
        if self.tree:
            self.tree.selection_set(self.tree.get_children())

    def _copy_data_to_clipboard(self):
        """Verileri panoya kopyalar"""
        if hasattr(self, 'current_dataframe') and self.current_dataframe is not None:
            FileUtils.copy_dataframe_to_clipboard(self.current_dataframe)
        else:
            messagebox.showwarning("Veri Yok", "Kopyalanacak veri bulunmuyor.")

    def _export_data_to_excel(self):
        """Verileri Excel'e aktarır"""
        if hasattr(self, 'current_dataframe') and self.current_dataframe is not None:
            FileUtils.export_dataframe_to_excel(self.current_dataframe)
        else:
            messagebox.showwarning("Veri Yok", "Dışarı aktarılacak veri bulunmuyor.")

    def set_dataframe(self, dataframe):
        """
        DataFrame'i tabloda gösterir

        Args:
            dataframe (pd.DataFrame): Gösterilecek DataFrame
        """
        if dataframe is None or dataframe.empty:
            self.show_placeholder()
            return

        self.dataframe = dataframe

        # Mevcut widget'ları temizle
        self._clear_widgets()

        # Özel tablo stilini yapılandır
        self._configure_table_style()

        # Tablo container
        table_container = ttk.Frame(self.parent_frame)
        table_container.pack(fill="both", expand=True)

        unit_info_text = self._get_unit_info_from_dataframe(dataframe)
        if unit_info_text:
            import tkinter as tk
            
            try:
                parent_bg_color = table_container.cget("bg")
            except Exception:
                parent_bg_color = "#F0F0F0" 

            unit_info_label = tk.Label(
                table_container,
                text=f"\U0001F4CA {unit_info_text}",
                font=('Poppins', 9),
                fg="#565656",
                bg=parent_bg_color
            )
            unit_info_label.pack(anchor='w', pady=(0, 4), padx=4)

        # Tüm sütunları hazırla (index + columns)
        # Not: Index adı, sütunlar içinde zaten varsa TEKRAR EKLEME.
        all_columns = []
        index_name = dataframe.index.name if dataframe.index.name else None
        include_index = bool(index_name) and (index_name not in dataframe.columns)
        if include_index:
            all_columns.append(index_name)
        all_columns.extend(dataframe.columns.tolist())

        # Treeview container (scrollbar düzeni için)
        tree_frame = ttk.Frame(table_container)
        tree_frame.pack(fill="both", expand=True)

        # Treeview oluştur
        self.tree = ttk.Treeview(tree_frame, columns=all_columns, show='headings',
                                style="DataTable.Treeview")

        # Sütun başlıklarını ayarla – ortaya hizalı
        for col in all_columns:
            self.tree.heading(col, text=col, anchor='center')
            # Index sütunu için genişlik ayarı
            if index_name and col == index_name:
                max_width = max(len(str(col)),
                              dataframe.index.astype(str).str.len().max() if len(dataframe) > 0 else 10)
            else:
                max_width = max(len(str(col)),
                              dataframe[col].astype(str).str.len().max() if len(dataframe) > 0 else 10)
            self.tree.column(col, width=min(max_width * 10 + 30, 280), anchor='center')

        # Verileri ekle - profesyonel format ile
        from src.config.styles import format_table_value
        for index, row in dataframe.iterrows():
            values = []

            # Index değerini ekle (sadece include_index True ise)
            if include_index:
                if isinstance(index, (int, float)):
                    # Periyot için time formatını kullan
                    if index_name and 'periyot' in index_name.lower():
                        values.append(format_table_value(index, "time"))
                    else:
                        values.append(format_table_value(index, "general"))
                else:
                    values.append(str(index))

            # Diğer sütunları ekle
            for col_name, val in zip(dataframe.columns, row):
                if isinstance(val, (int, float)):
                    # Sütun adına göre veri türünü belirle
                    if 'time' in col_name.lower() or 'zaman' in col_name.lower():
                        values.append(format_table_value(val, "time"))
                    elif 'accel' in col_name.lower() or 'ivme' in col_name.lower():
                        values.append(format_table_value(val, "acceleration"))
                    elif 'vel' in col_name.lower() or 'hız' in col_name.lower():
                        values.append(format_table_value(val, "velocity"))
                    elif 'disp' in col_name.lower() or 'yerdeğiştirme' in col_name.lower():
                        values.append(format_table_value(val, "displacement"))
                    else:
                        values.append(format_table_value(val, "general"))
                else:
                    values.append(str(val))
            self.tree.insert("", "end", values=values)

        # Satır arası çizgi efekti için hafif renklendirme uygula
        self._apply_row_striping()

        # Scrollbar'lar ekle
        # Sadece modern dikey scrollbar (yatay scrollbar kaldırıldı)
        v_scrollbar = ctk.CTkScrollbar(tree_frame, orientation="vertical",
                                        command=self.tree.yview,
                                        width=16,
                                        button_color="#C0C0C0",
                                        button_hover_color="#A0A0A0",
                                        fg_color="transparent",
                                        corner_radius=4)
        self.tree.configure(yscrollcommand=v_scrollbar.set)

        # Layout
        v_scrollbar.pack(side='right', fill='y')
        self.tree.pack(fill='both', expand=True)

        # Alt buton çubuğu
        button_bar = tk.Frame(self.parent_frame, bg="#FFFFFF", pady=10, padx=4)
        button_bar.pack(fill='x', pady=(6, 0))

        # Sol taraf butonları
        left_btns = tk.Frame(button_bar, bg="#FFFFFF")
        left_btns.pack(side='left')

        # Kopyala butonu – mavi ikon
        copy_btn = self._create_icon_button(left_btns, "\U0001F4CB", "#3B82F6",
                                            "Verileri Kopyala", self.copy_to_clipboard)
        copy_btn.pack(side='left', padx=(0, 6))

        # Excel'e aktar butonu – yeşil ikon
        excel_btn = self._create_icon_button(left_btns, "\U0001F4CA", "#10B981",
                                             "Excel'e Aktar", self.export_to_excel)
        excel_btn.pack(side='left', padx=(0, 6))

        # CSV'ye aktar butonu – turuncu ikon
        csv_btn = self._create_icon_button(left_btns, "\U0001F4C4", "#F59E0B",
                                           "CSV'ye Aktar", self.export_to_csv)
        csv_btn.pack(side='left', padx=(0, 6))

        # Sağ taraf butonları
        right_btns = tk.Frame(button_bar, bg="#FFFFFF")
        right_btns.pack(side='right')

        # Tümünü seç butonu – mavi ikon
        select_all_btn = self._create_icon_button(right_btns, "\u2611", "#3B82F6",
                                                  "Tümünü Seç", self.select_all)
        select_all_btn.pack(side='left', padx=(0, 6))

        # Seçimi temizle butonu – kırmızı/mor ikon
        clear_btn = self._create_icon_button(right_btns, "\u2715", "#8B5CF6",
                                             "Seçimi Temizle", self.clear_selection)
        clear_btn.pack(side='left')

        # Klavye kısayollarını bağla
        self.tree.bind('<Control-a>', lambda e: self.select_all())
        self.tree.bind('<Control-c>', lambda e: self.copy_to_clipboard())

        # Kök widget'a focus ver (klavye kısayolları için)
        self.tree.focus_set()

    def _get_unit_info_from_dataframe(self, dataframe):
        """DataFrame sütunlarından birim bilgisini çıkarır"""
        units_found = []

        for column in dataframe.columns:
            column_lower = column.lower()

            # İvme birimlerini tespit et
            if '(g)' in column_lower:
                units_found.append('İvme: g')
            elif '(m/s²)' in column_lower or 'm/s²' in column_lower:
                units_found.append('İvme: m/s²')
            elif '(cm/s²)' in column_lower or 'cm/s²' in column_lower:
                units_found.append('İvme: cm/s²')

            # Yerdeğiştirme birimlerini tespit et
            elif '(cm)' in column_lower and 'yerdeğiştirme' in column_lower:
                units_found.append('Yerdeğiştirme: cm')
            elif '(m)' in column_lower and 'yerdeğiştirme' in column_lower:
                units_found.append('Yerdeğiştirme: m')
            elif '(mm)' in column_lower and 'yerdeğiştirme' in column_lower:
                units_found.append('Yerdeğiştirme: mm')

        if units_found:
            unique_units = list(set(units_found))
            return f"Veri birimler: {', '.join(unique_units)}"

        return "Varsayılan birimler: İvme (g), Yerdeğiştirme (cm)"

    def get_selected_data(self):
        """Seçili verileri döndürür"""
        if not self.tree:
            return None

        selected_items = self.tree.selection()
        if not selected_items:
            return None

        # Seçili satırları al
        selected_data = []
        for item in selected_items:
            values = self.tree.item(item)['values']
            selected_data.append(values)

        return selected_data

    def clear_data(self):
        """Verileri temizler"""
        self.current_dataframe = None
        self.show_placeholder()

    def copy_to_clipboard(self):
        """Seçili verileri panoya kopyalar"""
        try:
            if self.tree and self.dataframe is not None:
                # Seçili satırları al
                selected_items = self.tree.selection()

                if selected_items:
                    # Seçili satırları kopyala
                    selected_data = []

                    # Başlıkları ekle (index + columns)
                    headers = []
                    index_name = self.dataframe.index.name if self.dataframe.index.name else None
                    include_index = bool(index_name) and (index_name not in self.dataframe.columns)
                    if include_index:
                        headers.append(index_name)
                    headers.extend(self.dataframe.columns.tolist())
                    selected_data.append('\t'.join(headers))

                    # Seçili satırları ekle
                    for item in selected_items:
                        values = self.tree.item(item)['values']
                        selected_data.append('\t'.join(str(v) for v in values))

                    # Panoya kopyala
                    clipboard_text = '\n'.join(selected_data)
                    self.tree.clipboard_clear()
                    self.tree.clipboard_append(clipboard_text)

                    messagebox.showinfo("Başarılı", f"{len(selected_items)} satır panoya kopyalandı.")
                else:
                    # Hiçbir şey seçili değilse tüm veriyi kopyala
                    include_index = bool(self.dataframe.index.name) and (self.dataframe.index.name not in self.dataframe.columns)
                    clipboard_text = self.dataframe.to_csv(sep='\t', index=include_index)
                    self.tree.clipboard_clear()
                    self.tree.clipboard_append(clipboard_text)

                    messagebox.showinfo("Başarılı", "Tüm veriler panoya kopyalandı.")

        except Exception as e:
            messagebox.showerror("Kopyalama Hatası", f"Veriler kopyalanırken hata: {str(e)}")

    def export_to_excel(self):
        """Verileri Excel dosyasına aktarır"""
        try:
            if self.dataframe is not None:
                # Kaydetme dialogu
                file_path = FileUtils.save_file_dialog(
                    title="Excel'e Aktar",
                    filetypes=[("Excel dosyası", "*.xlsx")],
                    default_extension=".xlsx",
                    parent=self.parent_frame.winfo_toplevel() if hasattr(self.parent_frame, "winfo_toplevel") else None
                )

                if file_path:
                    # Index'i yalnızca ayrı bir sütun YOKSA dahil et
                    include_index = bool(self.dataframe.index.name) and (self.dataframe.index.name not in self.dataframe.columns)
                    self.dataframe.to_excel(file_path, index=include_index)
                    messagebox.showinfo("Başarılı", f"Veriler Excel'e aktarıldı:\n{file_path}")
            else:
                messagebox.showwarning("Uyarı", "Aktarılacak veri yok.")

        except Exception as e:
            messagebox.showerror("Aktarma Hatası", f"Excel'e aktarırken hata: {str(e)}")

    def export_to_csv(self):
        """Verileri CSV dosyasına aktarır"""
        try:
            df = getattr(self, 'dataframe', None) or getattr(self, 'current_dataframe', None)
            if df is not None:
                # Kaydetme dialogu
                file_path = filedialog.asksaveasfilename(
                    title="CSV'ye Aktar",
                    filetypes=[("CSV dosyası", "*.csv")],
                    defaultextension=".csv",
                    parent=self.parent_frame.winfo_toplevel() if hasattr(self.parent_frame, "winfo_toplevel") else None
                )

                if file_path:
                    # Index'i yalnızca ayrı bir sütun YOKSA dahil et
                    include_index = bool(df.index.name) and (df.index.name not in df.columns)
                    df.to_csv(file_path, index=include_index, encoding='utf-8-sig')
                    messagebox.showinfo("Başarılı", f"Veriler CSV'ye aktarıldı:\n{file_path}")
            else:
                messagebox.showwarning("Uyarı", "Aktarılacak veri yok.")

        except Exception as e:
            messagebox.showerror("Aktarma Hatası", f"CSV'ye aktarırken hata: {str(e)}")

    def clear_selection(self):
        """Tablo seçimini temizler"""
        if self.tree:
            self.tree.selection_remove(self.tree.selection())

    def select_all(self):
        """Tablodaki tüm satırları seçer"""
        if self.tree:
            all_items = self.tree.get_children()
            self.tree.selection_set(all_items)
