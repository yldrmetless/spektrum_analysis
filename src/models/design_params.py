from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk


@dataclass
class DesignParamsModel:
    sds_var: tk.StringVar
    sd1_var: tk.StringVar
    tl_var: tk.StringVar

    @classmethod
    def create(cls, master=None, sds: float = 0.8, sd1: float = 0.4, tl: float = 6.0) -> "DesignParamsModel":
        return cls(
            sds_var=tk.StringVar(master, value=str(float(sds))),
            sd1_var=tk.StringVar(master, value=str(float(sd1))),
            tl_var=tk.StringVar(master, value=str(float(tl))),
        )

    def get_values(self) -> tuple[float, float, float]:
        try:
            sds = float(self.sds_var.get())
        except Exception:
            sds = 0.0
        try:
            sd1 = float(self.sd1_var.get())
        except Exception:
            sd1 = 0.0
        try:
            tl = float(self.tl_var.get())
        except Exception:
            tl = 6.0
        return sds, sd1, tl


