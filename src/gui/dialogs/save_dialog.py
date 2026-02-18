"""
Grafik kaydetme seçenekleri dialog'u (CustomTkinter tasarım)
İşlev değişmez: vars/save_mode/result/toggle/on_save aynı.
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox


class SaveDialog(ctk.CTkToplevel):
    """Grafik kaydetme seçenekleri için web-benzeri dialog penceresi."""

    FRIENDLY_NAMES = {
        "Yatay": "Yatay Elastik Tasarım Spektrumu",
        "Düşey": "Düşey Elastik Tasarım Spektrumu",
        "Yerdeğiştirme": "Yatay Yerdeğiştirme Elastik Tasarım Spektrumu",
    }

    def __init__(self, parent, available_graphs):
        super().__init__(parent)
        self.title("Grafik Kaydetme Seçenekleri")

        # --- Konum (seninkiyle aynı mantık, sade) ---
        try:
            parent.update_idletasks()
            parent_x = parent.winfo_rootx()
            parent_y = parent.winfo_rooty()
            parent_w = parent.winfo_width()
            parent_h = parent.winfo_height()
        except Exception:
            parent_w, parent_h = 800, 600
            parent_x = self.winfo_screenwidth() // 2 - parent_w // 2
            parent_y = self.winfo_screenheight() // 2 - parent_h // 2

        win_w, win_h = 560, 520
        x = parent_x + (parent_w // 2) - (win_w // 2)
        y = parent_y + (parent_h // 2) - (win_h // 2)
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(520, 480)

        self.transient(parent)
        self.grab_set()
        self.result = None

        # --- Renkler (2. görsel hissi) ---
        APP_BG = "#EEF2F7"
        CARD_BG = "#FFFFFF"
        PANEL_BG = "#F8FAFC"
        BORDER = "#E5E7EB"
        TEXT = "#111827"
        MUTED = "#6B7280"
        PRIMARY = "#2563EB"

        self.configure(fg_color=APP_BG)

        # --- State ---
        self.vars = {}
        self.checkboxes = []

        # ===== Card =====
        card = ctk.CTkFrame(
            self,
            fg_color=CARD_BG,
            corner_radius=16,
            border_color=BORDER,
            border_width=1
        )
        card.pack(fill="both", expand=True, padx=14, pady=14)

        # İç padding alanı
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=16)

        # Başlık + açıklama
        ctk.CTkLabel(
            content,
            text="Grafik Kaydetme Seçenekleri",
            text_color=TEXT,
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            content,
            text="Kaydedilecek grafikleri seçin ve kaydetme yöntemini belirleyin.",
            text_color=MUTED,
            font=ctk.CTkFont(size=12),
            justify="left"
        ).pack(anchor="w", pady=(4, 14))

        # ===== KAYDEDİLECEK GRAFİKLER =====
        ctk.CTkLabel(
            content,
            text="KAYDEDİLECEK GRAFİKLER",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w")

        graphs_box = ctk.CTkFrame(
            content,
            fg_color=PANEL_BG,
            corner_radius=14,
            border_color=BORDER,
            border_width=1
        )
        graphs_box.pack(fill="x", pady=(8, 14))

        graphs_in = ctk.CTkFrame(graphs_box, fg_color="transparent")
        graphs_in.pack(fill="x", padx=12, pady=10)

        # Checkbox listesi (aynı vars mantığı)
        for graph_name in available_graphs:
            var = tk.BooleanVar(value=True)
            self.vars[graph_name] = var

            label_text = self.FRIENDLY_NAMES.get(graph_name, graph_name)

            cb = ctk.CTkCheckBox(
                graphs_in,
                text=label_text,
                variable=var,
                onvalue=True,
                offvalue=False,
                text_color=TEXT,
                fg_color=PRIMARY,          # seçili kutu rengi
                border_color="#CBD5E1",    # boş kutu border
                hover_color="#1D4ED8",
                checkbox_width=18,
                checkbox_height=18,
                corner_radius=9
            )
            cb.pack(anchor="w", fill="x", pady=6)
            self.checkboxes.append(cb)

        # Divider
        ctk.CTkFrame(graphs_in, height=1, fg_color=BORDER).pack(fill="x", pady=(6, 8))

        # Link-like aksiyonlar
        links = ctk.CTkFrame(graphs_in, fg_color="transparent")
        links.pack(fill="x")

        ctk.CTkButton(
            links,
            text="✓  Tümünü Seç",
            fg_color="transparent",
            hover_color="#E7EEF9",
            text_color=PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
            width=0,
            command=self.select_all
        ).pack(side="left")

        ctk.CTkButton(
            links,
            text="✕  Hiçbirini Seçme",
            fg_color="transparent",
            hover_color="#E7EEF9",
            text_color=PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
            width=0,
            command=self.clear_all
        ).pack(side="left", padx=(14, 0))

        # ===== KAYDETME YÖNTEMİ =====
        ctk.CTkLabel(
            content,
            text="KAYDETME YÖNTEMİ",
            text_color=MUTED,
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(anchor="w")

        method_box = ctk.CTkFrame(content, fg_color="transparent")
        method_box.pack(fill="x", pady=(8, 8))

        self.save_mode = tk.StringVar(value="birlikte")

        self.rb1 = ctk.CTkRadioButton(
            method_box,
            text="Tümünü Tek Dosyaya Kaydet",
            variable=self.save_mode,
            value="birlikte",
            text_color=TEXT,
            fg_color=PRIMARY,
            command=self.toggle_checkboxes
        )
        self.rb1.pack(anchor="w", pady=4)

        self.rb2 = ctk.CTkRadioButton(
            method_box,
            text="Seçilenleri Ayrı Dosyalara Kaydet",
            variable=self.save_mode,
            value="ayri",
            text_color=TEXT,
            fg_color=PRIMARY,
            command=self.toggle_checkboxes
        )
        self.rb2.pack(anchor="w", pady=4)

        # Alt çizgi
        ctk.CTkFrame(content, height=1, fg_color=BORDER).pack(fill="x", pady=(8, 12))

        # ===== Butonlar =====
        btns = ctk.CTkFrame(content, fg_color="transparent")
        btns.pack(fill="x")

        ctk.CTkButton(
            btns,
            text="İptal",
            fg_color="transparent",
            hover_color="#F3F4F6",
            text_color=TEXT,
            border_color=BORDER,
            border_width=1,
            corner_radius=12,
            width=110,
            height=40,
            command=self.destroy
        ).pack(side="right")

        ctk.CTkButton(
            btns,
            text="Kaydet",
            fg_color=PRIMARY,
            hover_color="#1D4ED8",
            text_color="#FFFFFF",
            corner_radius=12,
            width=120,
            height=40,
            command=self.on_save
        ).pack(side="right", padx=(10, 10))

        # İlk state ayarı
        self.toggle_checkboxes()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.wait_window(self)

    # ==== İŞLEV AYNI ====

    def toggle_checkboxes(self):
        """Kaydetme moduna göre checkbox'ları aktif/pasif yapar."""
        if self.save_mode.get() == "birlikte":
            for cb in self.checkboxes:
                cb.configure(state="disabled")
        else:
            for cb in self.checkboxes:
                cb.configure(state="normal")

    def select_all(self):
        """Tüm grafikleri seçer."""
        for var in self.vars.values():
            var.set(True)

    def clear_all(self):
        """Tüm seçimleri temizler."""
        for var in self.vars.values():
            var.set(False)

    def on_save(self):
        """Kaydet butonuna basıldığında sonuçları ayarlar ve pencereyi kapatır."""
        selected_graphs = [name for name, var in self.vars.items() if var.get()]
        if self.save_mode.get() == "ayri" and not selected_graphs:
            messagebox.showwarning("Seçim Yapılmadı", "Lütfen en az bir grafik seçin.", parent=self)
            return

        self.result = {"graphs": selected_graphs, "mode": self.save_mode.get()}
        self.destroy()

    def get_result(self):
        """Dialog sonucunu döndürür"""
        return self.result



class PeerExportDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Çarpan Katsayısı Ayarları")
        
        # Pencere Boyutu ve Ortalama
        win_w, win_h = 400, 350
        self.geometry(f"{win_w}x{win_h}")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        self.result = None
        self.configure(fg_color="#FFFFFF")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=30, pady=30)

        ctk.CTkLabel(
            content, text="Çarpan Katsayısı Ayarları",
            text_color="#111827", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", pady=(0, 20))

        # Varsayılanı Kullan Checkbox
        self.use_default_var = tk.BooleanVar(value=True)
        self.check = ctk.CTkCheckBox(
            content, text="Varsayılanı Kullan",
            variable=self.use_default_var,
            command=self.toggle_entry,
            checkbox_width=18, checkbox_height=18, corner_radius=6
        )
        self.check.pack(anchor="w", pady=(0, 15))

        ctk.CTkLabel(
            content, text="Çarpan Katsayısı (Y)",
            text_color="#374151", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w")

        self.multiplier_entry = ctk.CTkEntry(
            content, placeholder_text="Değer giriniz...",
            height=40, fg_color="#F3F4F6", border_color="#E5E7EB",
            text_color="#111827"
        )
        self.multiplier_entry.pack(fill="x", pady=(5, 5))
        self.multiplier_entry.insert(0, "1.0")
        self.multiplier_entry.configure(state="disabled")

        ctk.CTkLabel(
            content, text="Sismik çarpan faktörünü manuel olarak girin.",
            text_color="#6B7280", font=ctk.CTkFont(size=11)
        ).pack(anchor="w")

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", side="bottom")

        self.apply_btn = ctk.CTkButton(
            btn_frame, text="Uygula", fg_color="#2563EB", hover_color="#1D4ED8",
            command=self.on_apply, height=35
        )
        self.apply_btn.pack(side="right", padx=(10, 0))

        self.cancel_btn = ctk.CTkButton(
            btn_frame, text="İptal", fg_color="transparent", text_color="#6B7280",
            hover_color="#F3F4F6", command=self.destroy, width=60
        )
        self.cancel_btn.pack(side="right")

    def toggle_entry(self):
        if self.use_default_var.get():
            self.multiplier_entry.configure(state="disabled", fg_color="#F3F4F6")
        else:
            self.multiplier_entry.configure(state="normal", fg_color="#FFFFFF")

    def on_apply(self):
        try:
            if self.use_default_var.get():
                self.result = 1.0
            else:
                self.result = float(self.multiplier_entry.get())
            self.destroy()
        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli bir sayı giriniz.", parent=self)

    def get_result(self):
        self.wait_window()
        return self.result