from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from .pair_manager import infer_axis


class PairingDialog(tk.Toplevel):
    def __init__(self, master, pair_manager, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.title("Deprem Kayıtlarını Eşleştir - Yeni Arayüz")
        try:
            self.minsize(900, 600)
        except Exception:
            pass
        self.pm = pair_manager
        self.result_saved = False

        # modal
        try:
            self.transient(master.winfo_toplevel())
            self.grab_set()
        except Exception:
            pass

        self._build_ui()
        self._load_data()

    def _build_ui(self):
        try:
            self.columnconfigure(0, weight=1)
            self.rowconfigure(1, weight=1)  # Ana içerik alanı
        except Exception:
            pass

        # Üst: Yeni çift oluşturma bölümü
        top_frame = ttk.LabelFrame(self, text="🆕 Yeni Çift Oluştur")
        top_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8,4))
        try:
            top_frame.columnconfigure(1, weight=1)
        except Exception:
            pass
        
        # Grup adı girişi
        ttk.Label(top_frame, text="Grup Adı:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.var_group_name = tk.StringVar()
        self.entry_group_name = ttk.Entry(top_frame, textvariable=self.var_group_name, width=30)
        self.entry_group_name.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Button(top_frame, text="Yeni Grup Oluştur", command=self._create_new_group).grid(row=0, column=2, padx=5, pady=5)

        # Orta: Ana eşleştirme alanı
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)

        # Sol: Mevcut gruplar
        frm_groups = ttk.Labelframe(paned, text="📋 Mevcut Çiftler")
        try:
            frm_groups.columnconfigure(0, weight=1)
            frm_groups.rowconfigure(0, weight=1)
        except Exception:
            pass
        self.tv_groups = ttk.Treeview(frm_groups, columns=("pairs",), show="tree headings", selectmode="browse")
        self.tv_groups.heading("#0", text="Grup Adı")
        self.tv_groups.heading("pairs", text="X | Y Bileşenleri")
        self.tv_groups.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tv_groups.bind("<<TreeviewSelect>>", self._on_group_select)

        # Sağ: Kayıt seçimi
        frm_selection = ttk.Labelframe(paned, text="🎯 Bileşen Seçimi")
        try:
            frm_selection.columnconfigure(0, weight=1)
            frm_selection.rowconfigure(2, weight=1)
        except Exception:
            pass
        
        # Seçili grup bilgisi
        info_frame = ttk.Frame(frm_selection)
        info_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        ttk.Label(info_frame, text="Seçili Grup:").pack(side="left")
        self.var_selected_group = tk.StringVar(value="(Grup seçilmedi)")
        ttk.Label(info_frame, textvariable=self.var_selected_group, font=("TkDefaultFont", 9, "bold")).pack(side="left", padx=(5,0))
        
        # X ve Y seçimi
        selection_frame = ttk.Frame(frm_selection)
        selection_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        try:
            selection_frame.columnconfigure(1, weight=1)
            selection_frame.columnconfigure(3, weight=1)
        except Exception:
            pass
        
        ttk.Label(selection_frame, text="X Bileşeni:").grid(row=0, column=0, sticky="w")
        self.var_x_component = tk.StringVar()
        self.combo_x = ttk.Combobox(selection_frame, textvariable=self.var_x_component, state="readonly", width=25)
        self.combo_x.grid(row=0, column=1, sticky="ew", padx=(5,10))
        
        ttk.Label(selection_frame, text="Y Bileşeni:").grid(row=0, column=2, sticky="w")
        self.var_y_component = tk.StringVar()
        self.combo_y = ttk.Combobox(selection_frame, textvariable=self.var_y_component, state="readonly", width=25)
        self.combo_y.grid(row=0, column=3, sticky="ew", padx=5)
        
        # Butonlar
        btn_frame = ttk.Frame(frm_selection)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        ttk.Button(btn_frame, text="✅ Eşleştir", command=self._apply_pairing).pack(side="left")
        ttk.Button(btn_frame, text="🔄 Otomatik Eşle", command=self._auto_pair_selected).pack(side="left", padx=(5,0))
        ttk.Button(btn_frame, text="🗑️ Temizle", command=self._clear_selected_group).pack(side="left", padx=(5,0))

        # Mevcut kayıtlar listesi
        records_frame = ttk.LabelFrame(frm_selection, text="📁 Tüm Kayıtlar")
        records_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=(10,5))
        try:
            records_frame.columnconfigure(0, weight=1)
            records_frame.rowconfigure(0, weight=1)
        except Exception:
            pass
        
        self.tv_records = ttk.Treeview(
            records_frame,
            columns=("axis","dt","n"),
            show="tree headings",
            selectmode="browse"
        )
        self.tv_records.heading("#0", text="Kayıt Adı")
        self.tv_records.heading("axis", text="Tahmin")
        self.tv_records.heading("dt", text="dt [s]")
        self.tv_records.heading("n", text="N")
        self.tv_records.column("axis", width=60, anchor="center")
        self.tv_records.column("dt", width=80, anchor="center")
        self.tv_records.column("n", width=60, anchor="center")
        self.tv_records.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.tv_records.bind("<Double-1>", self._on_record_double_click)

        try:
            paned.add(frm_groups, weight=1)
            paned.add(frm_selection, weight=2)
        except Exception:
            paned.add(frm_groups)
            paned.add(frm_selection)

        # Alt: Seçenekler ve butonlar
        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", padx=8, pady=(4,8))
        try:
            bottom.columnconfigure(2, weight=1)
        except Exception:
            pass
        
        # Seçenekler
        self.var_crop = tk.BooleanVar(value=True)
        self.var_swap = tk.BooleanVar(value=False)
        ttk.Checkbutton(bottom, text="📏 Kısa olanı kullan", variable=self.var_crop, command=self._on_option_change).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(bottom, text="🔄 X↔Y Değiştir", variable=self.var_swap, command=self._on_option_change).grid(row=0, column=1, sticky="w", padx=(10,0))
        
        # Ana butonlar
        ttk.Button(bottom, text="💾 Kaydet ve Kapat", command=self._on_save).grid(row=0, column=3, sticky="e", padx=(5,0))
        ttk.Button(bottom, text="❌ İptal", command=self._on_close).grid(row=0, column=4, sticky="e", padx=(5,0))

    def _load_data(self):
        try:
            self.suggestions, self.name_to_rr = self.pm.suggest_pairs()
        except Exception:
            self.suggestions, self.name_to_rr = {}, {}
        self.current_core: Optional[str] = None
        
        # Grupları doldur
        self._refresh_groups()
        
        # Tüm kayıtları doldur
        self._refresh_records()
        
        # Combobox'ları doldur
        self._refresh_combos()

    def _refresh_groups(self):
        """Grup listesini yeniler."""
        try:
            # Mevcut grupları temizle
            for item in self.tv_groups.get_children():
                self.tv_groups.delete(item)
            
            # Eşleştirilmiş grupları ekle
            for gid, sel in sorted(self.suggestions.items()):
                x_name = sel.get('X', '-')
                y_name = sel.get('Y', '-')
                label = f"{x_name} | {y_name}"
                self.tv_groups.insert("", "end", iid=gid, text=gid, values=(label,))
            
            # Manuel grupları ekle (override'lardan)
            for gid, overrides in getattr(self.pm, '_overrides', {}).items():
                if gid not in self.suggestions:  # Sadece yeni manuel grupları
                    x_name = overrides.get('X', '-')
                    y_name = overrides.get('Y', '-')
                    label = f"{x_name} | {y_name}"
                    display_name = gid.replace('MANUAL_', 'Manuel: ').replace('NEW_GROUP_', 'Yeni: ')
                    self.tv_groups.insert("", "end", iid=gid, text=display_name, values=(label,))
                    
        except Exception:
            pass

    def _refresh_records(self):
        """Tüm kayıtlar listesini yeniler."""
        try:
            # Mevcut kayıtları temizle
            for item in self.tv_records.get_children():
                self.tv_records.delete(item)
            
            # Tüm kayıtları ekle
            for name, record in sorted(self.name_to_rr.items()):
                try:
                    # Eksen tahmini
                    axis_guess = infer_axis(name) or "?"
                    
                    # dt ve N bilgisi
                    dt = float(record.get('processed_data', {}).get('params', {}).get('time_step', 0.0))
                    if not dt and record.get('processed_data', {}).get('time') is not None:
                        t = record['processed_data']['time']
                        dt = float(t[1]-t[0]) if len(t) >= 2 else 0.0
                    n = int(len(record.get('processed_data', {}).get('acceleration', [])))
                    
                    self.tv_records.insert("", "end", iid=name, text=name, 
                                         values=(axis_guess, f"{dt:.5f}", n))
                except Exception:
                    self.tv_records.insert("", "end", iid=name, text=name, 
                                         values=("?", "0.00000", 0))
        except Exception:
            pass

    def _refresh_combos(self):
        """Combobox'ları günceller."""
        try:
            # Tüm kayıt adlarını al
            record_names = list(self.name_to_rr.keys())
            record_names.sort()
            
            # Combobox'ları güncelle
            self.combo_x['values'] = [""] + record_names
            self.combo_y['values'] = [""] + record_names
            
        except Exception:
            pass

    def _create_new_group(self):
        """Yeni grup oluşturur."""
        group_name = self.var_group_name.get().strip()
        if not group_name:
            messagebox.showwarning("Uyarı", "Lütfen grup adı girin.")
            return
        
        # Grup adını temizle
        import re
        clean_name = re.sub(r'[^A-Za-z0-9_\-]', '_', group_name)
        group_id = f"MANUAL_{clean_name}"
        
        # Aynı isimde grup var mı kontrol et
        existing_groups = [self.tv_groups.item(child)["text"] for child in self.tv_groups.get_children()]
        if group_id in existing_groups or f"Manuel: {clean_name}" in existing_groups:
            messagebox.showwarning("Uyarı", "Bu isimde bir grup zaten mevcut.")
            return
        
        # Yeni grubu ekle
        try:
            display_name = f"Manuel: {clean_name}"
            self.tv_groups.insert("", "end", iid=group_id, text=display_name, values=("- | -",))
            
            # Yeni grubu seç
            self.tv_groups.selection_set(group_id)
            self._on_group_select()
            
            # Grup adı alanını temizle
            self.var_group_name.set("")
            
            messagebox.showinfo("Başarılı", f"'{display_name}' grubu oluşturuldu. Şimdi X ve Y bileşenlerini seçin.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Grup oluşturulamadı: {e}")

    def _on_group_select(self, *args):
        """Grup seçildiğinde çalışır."""
        sel = self.tv_groups.selection()
        if not sel:
            self.current_core = None
            self.var_selected_group.set("(Grup seçilmedi)")
            self.var_x_component.set("")
            self.var_y_component.set("")
            return
        
        group_id = sel[0]
        self.current_core = group_id
        
        # Grup adını göster
        group_text = self.tv_groups.item(group_id)["text"]
        self.var_selected_group.set(group_text)
        
        # Mevcut X ve Y seçimlerini göster
        try:
            overrides = getattr(self.pm, '_overrides', {}).get(group_id, {})
            suggestions = self.suggestions.get(group_id, {})
            
            x_name = overrides.get('X') or suggestions.get('X', '')
            y_name = overrides.get('Y') or suggestions.get('Y', '')
            
            self.var_x_component.set(x_name)
            self.var_y_component.set(y_name)
            
        except Exception:
            self.var_x_component.set("")
            self.var_y_component.set("")

    def _apply_pairing(self):
        """Seçilen X ve Y bileşenlerini uygular."""
        if not self.current_core:
            messagebox.showwarning("Uyarı", "Lütfen önce bir grup seçin.")
            return
        
        x_name = self.var_x_component.get().strip()
        y_name = self.var_y_component.get().strip()
        
        if not x_name or not y_name:
            messagebox.showwarning("Uyarı", "Lütfen hem X hem de Y bileşenini seçin.")
            return
        
        if x_name == y_name:
            messagebox.showwarning("Uyarı", "X ve Y bileşenleri farklı olmalıdır.")
            return
        
        # Kayıtların mevcut olduğunu kontrol et
        if x_name not in self.name_to_rr or y_name not in self.name_to_rr:
            messagebox.showerror("Hata", "Seçilen kayıtlardan biri bulunamadı.")
            return
        
        try:
            # Eşleştirmeyi uygula
            self.pm.set_override(self.current_core, 'X', x_name)
            self.pm.set_override(self.current_core, 'Y', y_name)
            
            # Grup listesini güncelle
            label = f"{x_name} | {y_name}"
            self.tv_groups.set(self.current_core, "pairs", label)
            
            messagebox.showinfo("Başarılı", f"Eşleştirme uygulandı:\nX: {x_name}\nY: {y_name}")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Eşleştirme uygulanamadı: {e}")

    def _auto_pair_selected(self):
        """Seçili grup için otomatik eşleştirme yapar."""
        if not self.current_core:
            messagebox.showwarning("Uyarı", "Lütfen önce bir grup seçin.")
            return
        
        try:
            # Mevcut kayıtları al
            record_names = list(self.name_to_rr.keys())
            
            # X ve Y adaylarını bul
            x_candidates = []
            y_candidates = []
            
            for name in record_names:
                axis_guess = infer_axis(name)
                if axis_guess == 'X':
                    x_candidates.append(name)
                elif axis_guess == 'Y':
                    y_candidates.append(name)
            
            # En iyi eşleştirmeyi bul
            if x_candidates and y_candidates:
                self.var_x_component.set(x_candidates[0])
                self.var_y_component.set(y_candidates[0])
                messagebox.showinfo("Otomatik Eşleştirme", 
                                  f"Önerilen eşleştirme:\nX: {x_candidates[0]}\nY: {y_candidates[0]}\n\n'Eşleştir' butonuna tıklayarak uygulayın.")
            else:
                messagebox.showwarning("Uyarı", "Otomatik eşleştirme için uygun kayıtlar bulunamadı.")
                
        except Exception as e:
            messagebox.showerror("Hata", f"Otomatik eşleştirme başarısız: {e}")

    def _clear_selected_group(self):
        """Seçili grubun eşleştirmesini temizler."""
        if not self.current_core:
            messagebox.showwarning("Uyarı", "Lütfen önce bir grup seçin.")
            return
        
        try:
            self.pm.set_override(self.current_core, 'X', None)
            self.pm.set_override(self.current_core, 'Y', None)
            
            self.var_x_component.set("")
            self.var_y_component.set("")
            
            # Grup listesini güncelle
            self.tv_groups.set(self.current_core, "pairs", "- | -")
            
            messagebox.showinfo("Başarılı", "Grup eşleştirmesi temizlendi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Temizleme başarısız: {e}")

    def _on_record_double_click(self, event):
        """Kayıt listesinde çift tıklandığında çalışır."""
        sel = self.tv_records.selection()
        if not sel:
            return
        
        record_name = sel[0]
        axis_guess = infer_axis(record_name)
        
        # Tahmine göre X veya Y'ye ata
        if axis_guess == 'X':
            self.var_x_component.set(record_name)
        elif axis_guess == 'Y':
            self.var_y_component.set(record_name)
        else:
            # Tahmin yoksa boş olana ata
            if not self.var_x_component.get():
                self.var_x_component.set(record_name)
            elif not self.var_y_component.get():
                self.var_y_component.set(record_name)

    def _on_option_change(self):
        """Seçenekler değiştiğinde çalışır."""
        if self.current_core:
            try:
                self.pm.set_option(self.current_core, 'crop_min', bool(self.var_crop.get()))
                self.pm.set_option(self.current_core, 'swap_xy', bool(self.var_swap.get()))
            except Exception:
                pass

    def _on_save(self):
        """Değişiklikleri kaydeder ve dialog'u kapatır."""
        try:
            self.result_saved = True
            messagebox.showinfo("Başarılı", "Eşleştirmeler kaydedildi.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme başarısız: {e}")

    def _on_close(self):
        """Dialog'u kapatır."""
        try:
            if not self.result_saved:
                result = messagebox.askyesnocancel("Çıkış", "Değişiklikleri kaydetmek istiyor musunuz?")
                if result is True:  # Evet
                    self._on_save()
                    return
                elif result is None:  # İptal
                    return
            self.destroy()
        except Exception:
            self.destroy()