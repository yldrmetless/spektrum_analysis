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
    """
    PEER CSV aktarım dialog'u — 3 mod:
      1. Varsayılan (çarpan = 1.0)
      2. Tümünü Çarp (tüm periyotlara tek çarpan)
      3. Aralık Çarp (T1–T2 arasına çarpan, dışı olduğu gibi)
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.title("PEER Spektrum Aktarım Ayarları")

        # --- Pencere boyut ve konum ---
        win_w, win_h = 480, 600
        try:
            parent.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw // 2) - (win_w // 2)
            y = py + (ph // 2) - (win_h // 2)
        except Exception:
            x = self.winfo_screenwidth() // 2 - win_w // 2
            y = self.winfo_screenheight() // 2 - win_h // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.resizable(False, False)

        self.transient(parent)
        self.grab_set()
        self.result = None

        # --- Renkler ---
        CARD_BG = "#FFFFFF"
        PANEL_BG = "#F8FAFC"
        BORDER = "#E5E7EB"
        TEXT = "#111827"
        MUTED = "#6B7280"
        PRIMARY = "#2563EB"
        DISABLED_BG = "#F3F4F6"

        self.configure(fg_color="#EEF2F7")

        # ===== Card =====
        card = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=16,
                            border_color=BORDER, border_width=1)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        # --- Başlık ---
        ctk.CTkLabel(content, text="PEER Spektrum Aktarım Ayarları",
                     text_color=TEXT, font=ctk.CTkFont(size=16, weight="bold")
                     ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(content, text="Spektral ivme değerlerine uygulanacak çarpan ayarlarını seçin.",
                     text_color=MUTED, font=ctk.CTkFont(size=11), justify="left"
                     ).pack(anchor="w", pady=(0, 16))

        # ===== MOD SEÇİMİ =====
        ctk.CTkLabel(content, text="ÇARPAN MODU",
                     text_color=MUTED, font=ctk.CTkFont(size=11, weight="bold")
                     ).pack(anchor="w")

        self.mode_var = tk.StringVar(value="default")

        mode_frame = ctk.CTkFrame(content, fg_color="transparent")
        mode_frame.pack(fill="x", pady=(8, 12))

        ctk.CTkRadioButton(
            mode_frame, text="Varsayılan (Çarpan = 1.0)",
            variable=self.mode_var, value="default",
            text_color=TEXT, fg_color=PRIMARY,
            command=self._on_mode_change
        ).pack(anchor="w", pady=3)

        ctk.CTkRadioButton(
            mode_frame, text="Tümünü Çarp",
            variable=self.mode_var, value="multiply_all",
            text_color=TEXT, fg_color=PRIMARY,
            command=self._on_mode_change
        ).pack(anchor="w", pady=3)

        ctk.CTkRadioButton(
            mode_frame, text="Belirli Periyot Aralığını Çarp",
            variable=self.mode_var, value="multiply_range",
            text_color=TEXT, fg_color=PRIMARY,
            command=self._on_mode_change
        ).pack(anchor="w", pady=3)

        # --- Ayırıcı ---
        ctk.CTkFrame(content, height=1, fg_color=BORDER).pack(fill="x", pady=(4, 12))

        # ===== ÇARPAN KATSAYISI =====
        ctk.CTkLabel(content, text="Çarpan Katsayısı",
                     text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(anchor="w")

        self.multiplier_entry = ctk.CTkEntry(
            content, placeholder_text="Örn: 1.5",
            height=38, fg_color=DISABLED_BG, border_color=BORDER,
            text_color=TEXT
        )
        self.multiplier_entry.pack(fill="x", pady=(4, 2))
        self.multiplier_entry.insert(0, "1.0")
        self.multiplier_entry.configure(state="disabled")

        self.multiplier_hint = ctk.CTkLabel(
            content, text="Varsayılan mod seçili — çarpan 1.0 olarak uygulanır.",
            text_color=MUTED, font=ctk.CTkFont(size=10)
        )
        self.multiplier_hint.pack(anchor="w", pady=(0, 12))

        # ===== PERİYOT ARALIĞI (sadece "multiply_range" modunda aktif) =====
        self.range_label = ctk.CTkLabel(
            content, text="Periyot Aralığı (s)",
            text_color=TEXT, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.range_label.pack(anchor="w")

        range_frame = ctk.CTkFrame(content, fg_color="transparent")
        range_frame.pack(fill="x", pady=(4, 2))
        range_frame.grid_columnconfigure(0, weight=1)
        range_frame.grid_columnconfigure(1, weight=0)
        range_frame.grid_columnconfigure(2, weight=1)

        self.t1_entry = ctk.CTkEntry(
            range_frame, placeholder_text="T₁ (başlangıç)",
            height=38, fg_color=DISABLED_BG, border_color=BORDER, text_color=TEXT
        )
        self.t1_entry.grid(row=0, column=0, sticky="ew")
        self.t1_entry.insert(0, "0.0")
        self.t1_entry.configure(state="disabled")

        ctk.CTkLabel(range_frame, text="  –  ", text_color=MUTED,
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=1)

        self.t2_entry = ctk.CTkEntry(
            range_frame, placeholder_text="T₂ (bitiş)",
            height=38, fg_color=DISABLED_BG, border_color=BORDER, text_color=TEXT
        )
        self.t2_entry.grid(row=0, column=2, sticky="ew")
        self.t2_entry.insert(0, "6.0")
        self.t2_entry.configure(state="disabled")

        self.range_hint = ctk.CTkLabel(
            content, text="Aralık dışındaki değerler olduğu gibi kalır.",
            text_color=MUTED, font=ctk.CTkFont(size=10)
        )
        self.range_hint.pack(anchor="w", pady=(0, 12))

        # ===== Butonlar =====
        ctk.CTkFrame(content, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 12))

        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x")

        ctk.CTkButton(
            btn_frame, text="İptal", fg_color="transparent", text_color=MUTED,
            hover_color="#F3F4F6", border_color=BORDER, border_width=1,
            corner_radius=10, width=80, height=36,
            command=self.destroy
        ).pack(side="right")

        ctk.CTkButton(
            btn_frame, text="Uygula", fg_color=PRIMARY, hover_color="#1D4ED8",
            text_color="#FFFFFF", corner_radius=10, width=100, height=36,
            command=self._on_apply
        ).pack(side="right", padx=(0, 10))

        # İlk state
        self._on_mode_change()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ────────────────────────────────────────────
    def _on_mode_change(self):
        """Mod değiştiğinde input alanlarını aktif/pasif yapar."""
        mode = self.mode_var.get()
        ENABLED_BG = "#FFFFFF"
        DISABLED_BG = "#F3F4F6"

        if mode == "default":
            self.multiplier_entry.configure(state="disabled", fg_color=DISABLED_BG)
            self.t1_entry.configure(state="disabled", fg_color=DISABLED_BG)
            self.t2_entry.configure(state="disabled", fg_color=DISABLED_BG)
            self.multiplier_hint.configure(
                text="Varsayılan mod seçili — çarpan 1.0 olarak uygulanır.")
            self.range_hint.configure(text="")

        elif mode == "multiply_all":
            self.multiplier_entry.configure(state="normal", fg_color=ENABLED_BG)
            self.t1_entry.configure(state="disabled", fg_color=DISABLED_BG)
            self.t2_entry.configure(state="disabled", fg_color=DISABLED_BG)
            self.multiplier_hint.configure(
                text="Tüm periyotlardaki ivme değerleri bu çarpanla çarpılır.")
            self.range_hint.configure(text="")

        elif mode == "multiply_range":
            self.multiplier_entry.configure(state="normal", fg_color=ENABLED_BG)
            self.t1_entry.configure(state="normal", fg_color=ENABLED_BG)
            self.t2_entry.configure(state="normal", fg_color=ENABLED_BG)
            self.multiplier_hint.configure(
                text="Sadece belirtilen aralıktaki ivme değerleri çarpılır.")
            self.range_hint.configure(
                text="Aralık dışındaki değerler olduğu gibi kalır.")

    def _on_apply(self):
        """Uygula butonuna basıldığında sonuçları doğrular ve pencereyi kapatır."""
        mode = self.mode_var.get()

        if mode == "default":
            self.result = {
                "mode": "default",
                "multiplier": 1.0,
            }
            self.destroy()
            return

        # Çarpan doğrulama
        try:
            multiplier = float(self.multiplier_entry.get())
        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli bir çarpan değeri giriniz.",
                                 parent=self)
            return

        if mode == "multiply_all":
            self.result = {
                "mode": "multiply_all",
                "multiplier": multiplier,
            }
            self.destroy()
            return

        if mode == "multiply_range":
            # Periyot aralığı doğrulama
            try:
                t1 = float(self.t1_entry.get())
                t2 = float(self.t2_entry.get())
            except ValueError:
                messagebox.showerror("Hata",
                                     "Lütfen geçerli periyot değerleri giriniz (T₁ ve T₂).",
                                     parent=self)
                return

            if t1 < 0 or t2 < 0:
                messagebox.showerror("Hata", "Periyot değerleri negatif olamaz.",
                                     parent=self)
                return

            if t1 >= t2:
                messagebox.showerror("Hata",
                                     f"T₁ ({t1}) değeri T₂ ({t2}) değerinden küçük olmalıdır.",
                                     parent=self)
                return

            self.result = {
                "mode": "multiply_range",
                "multiplier": multiplier,
                "t1": t1,
                "t2": t2,
            }
            self.destroy()
            return

    def get_result(self):
        """Dialog sonucunu döndürür. Eski API uyumluluğu için float da döndürülebilir."""
        self.wait_window()
        return self.result
