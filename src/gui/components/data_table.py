"""
Veri tablosu bileşeni
"""

from tkinter import ttk, messagebox
from ...utils.file_utils import FileUtils

class DataTable:
    """Veri tablosu bileşeni sınıfı"""
    
    def __init__(self, parent_frame):
        """
        Args:
            parent_frame: Ana çerçeve
        """
        self.parent_frame = parent_frame
        self.tree = None
        self.vsb = None
        self.hsb = None
        
        # Arayüzü oluştur
        self._create_widgets()
        self.show_placeholder()
    
    def _create_widgets(self):
        """Widget'ları oluşturur"""
        # Ana çerçeve zaten parent_frame olarak geliyor
        pass
    
    def show_placeholder(self, text="Verileri görmek için önce bir hesaplama yapın."):
        """Placeholder mesajı gösterir"""
        self._clear_widgets()
        
        placeholder_label = ttk.Label(
            self.parent_frame, 
            text=text, 
            font=('Segoe UI', 12)
        )
        placeholder_label.pack(expand=True)
    
    def update_data(self, dataframe):
        """Veri tablosunu günceller"""
        self._clear_widgets()
        
        if dataframe is None or dataframe.empty or len(dataframe.columns) <= 1:
            self.show_placeholder()
            return
        
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
        
        # Treeview oluştur
        self.tree = ttk.Treeview(table_container, columns=all_columns, show='headings')
        
        # Sütun başlıklarını ayarla
        for col in all_columns:
            self.tree.heading(col, text=col)
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
        
        # Scrollbar'ları oluştur
        self.vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        
        # Treeview'ı scrollbar'larla bağla
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)
        
        # Widget'ları yerleştir
        self.vsb.pack(side='right', fill='y')
        self.hsb.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)
        
        # CTRL+A ile tümünü seçme özelliği
        self.tree.bind("<Control-a>", lambda event: self._select_all())
        self.tree.bind("<Control-A>", lambda event: self._select_all())
        
        # Butonları oluştur
        self._create_buttons()
    
    def _create_buttons(self):
        """Butonları oluşturur"""
        button_frame = ttk.Frame(self.parent_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        # Verileri kopyala butonu
        copy_button = ttk.Button(
            button_frame, 
            text="Verileri Kopyala", 
            command=self._copy_data_to_clipboard
        )
        copy_button.pack(side='left', padx=5)
        
        # Excel'e aktar butonu
        export_button = ttk.Button(
            button_frame, 
            text="Excel'e Aktar (.xlsx)", 
            command=self._export_data_to_excel
        )
        export_button.pack(side='left', padx=5)
    
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
        
        # Tablo container
        table_container = ttk.Frame(self.parent_frame)
        table_container.pack(fill="both", expand=True)
        
        # Birim bilgisi etiketi
        unit_info_text = self._get_unit_info_from_dataframe(dataframe)
        if unit_info_text:
            unit_info_label = ttk.Label(table_container, 
                                       text=f"📊 {unit_info_text}",
                                       font=('Segoe UI', 9),
                                       foreground='blue')
            unit_info_label.pack(pady=(0, 5))
        
        # Tüm sütunları hazırla (index + columns)
        # Not: Index adı, sütunlar içinde zaten varsa TEKRAR EKLEME.
        all_columns = []
        index_name = dataframe.index.name if dataframe.index.name else None
        include_index = bool(index_name) and (index_name not in dataframe.columns)
        if include_index:
            all_columns.append(index_name)
        all_columns.extend(dataframe.columns.tolist())
        
        # Treeview oluştur
        self.tree = ttk.Treeview(table_container, columns=all_columns, show='headings')
        
        # Sütun başlıklarını ayarla
        for col in all_columns:
            self.tree.heading(col, text=col)
            # Index sütunu için genişlik ayarı
            if index_name and col == index_name:
                max_width = max(len(str(col)), 
                              dataframe.index.astype(str).str.len().max() if len(dataframe) > 0 else 10)
            else:
                max_width = max(len(str(col)), 
                              dataframe[col].astype(str).str.len().max() if len(dataframe) > 0 else 10)
            self.tree.column(col, width=min(max_width * 8 + 20, 250), anchor='center')
        
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
        
        # Scrollbar'lar ekle
        v_scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_container, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Layout
        v_scrollbar.pack(side='right', fill='y')
        h_scrollbar.pack(side='bottom', fill='x')
        self.tree.pack(fill='both', expand=True)
        
        # Buton çerçevesi
        button_frame = ttk.Frame(self.parent_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        # Kopyala butonu
        copy_btn = ttk.Button(button_frame, text="📋 Verileri Kopyala", command=self.copy_to_clipboard)
        copy_btn.pack(side='left', padx=(0, 5))
        
        # Excel'e aktar butonu
        excel_btn = ttk.Button(button_frame, text="📊 Excel'e Aktar", command=self.export_to_excel)
        excel_btn.pack(side='left', padx=5)
        
        # Seçimi temizle butonu
        clear_btn = ttk.Button(button_frame, text="🔄 Seçimi Temizle", command=self.clear_selection)
        clear_btn.pack(side='right')
        
        # Tümünü seç butonu  
        select_all_btn = ttk.Button(button_frame, text="✅ Tümünü Seç", command=self.select_all)
        select_all_btn.pack(side='right', padx=(5, 0))
        
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
    
    def clear_selection(self):
        """Tablo seçimini temizler"""
        if self.tree:
            self.tree.selection_remove(self.tree.selection())
    
    def select_all(self):
        """Tablodaki tüm satırları seçer"""
        if self.tree:
            all_items = self.tree.get_children()
            self.tree.selection_set(all_items) 
