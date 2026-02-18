from __future__ import annotations

from typing import Iterable, Optional, Sequence

import numpy as np


def solve_lp_scaling(
    S_list: Sequence[np.ndarray],
    S_target: np.ndarray,
    T: np.ndarray,
    mask: np.ndarray,
    alpha: float = 1.3,
    weights: Optional[Iterable[float]] = None,
    max_scale: Optional[float] = None,
    min_scale: float = 0.1,
) -> np.ndarray:
    """
    Kayıt-bazlı ölçekleme için lineer programlama çözümü (Kısıt-Tatmin Modu).
    
    NOT: Bu mod PGMD'nin MSE minimizasyonu ile aynı amaç değildir.
    "En az artırma" mantığı ile TBDY uygun kısıt tatmini sağlar.

    Amaç: min sum(w_i * f_i)
    Kısıtlar:
      - (1/n) * sum_i f_i * S_i(T_j) >= alpha * S_target(T_j),  tüm j mask içinde
      - f_i >= 0,  ve opsiyonel olarak f_i <= max_scale

    Args:
        S_list: Her kayıt için SRSS spektrumu (g), shape (n_records, n_T)
        S_target: Tasarım spektrumu Sae(T) (g), shape (n_T,)
        T: Periyot dizisi (s), shape (n_T,)
        mask: Pencere maskesi (örn. [0.2*Tp, 1.5*Tp])
        alpha: 1B/2B=1.0, 3B=1.3 tipik
        weights: Kayıt başına ağırlıklar (varsayılan 1)
        max_scale: f_i üst sınırı (opsiyonel, varsayılan None → sınırsız)
        min_scale: f_i alt sınırı (varsayılan 0.1; negatif/çok küçük katsayıları engeller)

    Returns:
        f: Kayıt başına ölçek katsayıları, shape (n_records,)
    """
    try:
        from scipy.optimize import linprog
    except Exception as exc:  # pragma: no cover - import hatası durumunda net mesaj
        raise RuntimeError("LP çözücü için scipy gereklidir: pip install scipy") from exc

    n = len(S_list)
    if n == 0:
        return np.array([], dtype=float)

    W = np.ones(n, dtype=float) if weights is None else np.asarray(list(weights), dtype=float)
    if W.shape[0] != n:
        raise ValueError("weights uzunluğu kayıt sayısı ile aynı olmalıdır.")

    # A matrisi: (m, n)  m=mask içindeki T_j sayısı
    S_mat = np.vstack([np.asarray(Si, dtype=float) for Si in S_list])  # (n, n_T)
    A = (S_mat[:, mask].T) / float(n)  # (m, n)
    b = float(alpha) * np.asarray(S_target, dtype=float)[mask]

    # linprog standardı: minimize c^T f, A_ub f <= b_ub, A_eq f == b_eq
    # Bizde A f >= b -> -A f <= -b
    c = W
    A_ub = -A
    b_ub = -b
    min_bound = float(min_scale) if min_scale is not None else 0.0
    if min_bound < 0.0:
        raise ValueError("min_scale negatif olamaz.")
    bounds = [
        (min_bound, (None if max_scale is None else float(max_scale)))
        for _ in range(n)
    ]

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"LP scaling failed: {res.message}")
    return np.asarray(res.x, dtype=float)


