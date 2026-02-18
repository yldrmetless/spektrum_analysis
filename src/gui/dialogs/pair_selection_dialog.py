import tkinter as tk
from tkinter import ttk


class PairSelectionDialog(tk.Toplevel):
    """
    Kullanıcının mevcut deprem kayıtları listesinden iki bileşen seçmesini
    sağlayan bir Tkinter Toplevel diyalog penceresi.
    """

    def __init__(self, parent, record_names):
        super().__init__(parent)
        self.title("Deprem Çifti Seçin")
        self.transient(parent)
        self.grab_set()

        self.record_names = list(record_names or [])
        self.result = None

        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="1. Yatay Bileşen (X):").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.combo1 = ttk.Combobox(main_frame, values=self.record_names, width=40, state="readonly")
        self.combo1.grid(row=0, column=1, padx=5, pady=5)
        if self.record_names:
            self.combo1.current(0)

        ttk.Label(main_frame, text="2. Yatay Bileşen (Y):").grid(
            row=1, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.combo2 = ttk.Combobox(main_frame, values=self.record_names, width=40, state="readonly")
        self.combo2.grid(row=1, column=1, padx=5, pady=5)
        if len(self.record_names) > 1:
            self.combo2.current(1)
        elif self.record_names:
            self.combo2.current(0)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10, sticky=tk.E)

        self.ok_button = ttk.Button(button_frame, text="Tamam", command=self.on_ok)
        self.ok_button.pack(side=tk.LEFT, padx=5)

        self.cancel_button = ttk.Button(button_frame, text="İptal", command=self.on_cancel)
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.wait_window()

    def on_ok(self):
        """
        Kullanıcı 'Tamam'a bastığında seçilen değerleri saklar.
        """
        selected_comp1 = self.combo1.get()
        selected_comp2 = self.combo2.get()

        if selected_comp1 and selected_comp2:
            self.result = (selected_comp1, selected_comp2)
            self.destroy()

    def on_cancel(self):
        """
        Kullanıcı 'İptal'e bastığında pencereyi kapatır.
        """
        self.result = None
        self.destroy()

    def get_selected_pair(self):
        """
        Seçilen çifti döndürür.
        """
        return self.result

