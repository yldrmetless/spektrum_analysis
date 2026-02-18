"""
Fix 3B Ölçeklendirme — PEER CSV ile proje tablosunu hizalama aracı

Kullanım (PowerShell/CMD):
    python -m src.utils.fix_3b_olceklendirme --proje proje.csv --peer _SearchResults.csv --out report_fix_3B.csv

Notlar:
- Kılavuz: Fix_3B_Olceklendirme.md
- İki yatay bileşene aynı ölçek katsayısı uygulanması varsayımıyla, PEER 'ScaleF/Scale Factor' ile
  proje tablosunu eşleştirir ve fark raporunu üretir.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

import pandas as pd


def _read_peer_csv(path: Path) -> pd.DataFrame:
    df = None
    try:
        df = pd.read_csv(path, sep=';')
    except Exception:
        df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def _read_proj_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def _basename_lower(s: str) -> str:
    return os.path.basename(str(s)).strip().lower()


def align_with_peer(project_csv: Path, peer_csv: Path) -> pd.DataFrame:
    proj = _read_proj_csv(project_csv)
    peer = _read_peer_csv(peer_csv)

    # Gerekli sütunları doğrula
    scale_col_candidates: List[str] = ["Scale Factor", "ScaleF"]
    luf_col_candidates: List[str] = [
        "Lowest Usable Frequency (Hz)",
        "Lowest Useable Frequency (Hz)",
    ]
    scale_col = next((c for c in scale_col_candidates if c in peer.columns), None)
    luf_col = next((c for c in luf_col_candidates if c in peer.columns), None)
    required_peer = [
        "Record Sequence Number",
        scale_col,
        "Horizontal-1 Acc. Filename",
        "Horizontal-2 Acc. Filename",
        luf_col,
    ]
    missing = [c for c in required_peer if c is None or c not in peer.columns]
    if missing:
        raise ValueError(f"PEER CSV beklenen sütunları içermiyor: {missing}")

    # Temel eşleştirme alanları
    peer = peer.copy()
    peer["h1_base"] = peer["Horizontal-1 Acc. Filename"].map(_basename_lower)
    peer["h2_base"] = peer["Horizontal-2 Acc. Filename"].map(_basename_lower)

    proj = proj.copy()
    key_col = 'Grup Adı' if 'Grup Adı' in proj.columns else proj.columns[0]
    proj['grp_base'] = proj[key_col].map(_basename_lower)

    # Önce H1 ile eşleştir
    merged = proj.merge(
        peer[["Record Sequence Number", scale_col, 'h1_base', 'h2_base', luf_col]],
        left_on='grp_base', right_on='h1_base', how='left'
    )

    # H1 eşleşmeyenleri H2 ile dene
    mask = merged[scale_col].isna()
    if mask.any():
        fill = proj.loc[mask].merge(
            peer[["Record Sequence Number", scale_col, 'h1_base', 'h2_base', luf_col]],
            left_on='grp_base', right_on='h2_base', how='left'
        )[["Record Sequence Number", scale_col, 'h1_base', 'h2_base', luf_col]]
        merged.loc[mask, ["Record Sequence Number", scale_col, 'h1_base', 'h2_base', luf_col]] = fill.values

    merged.rename(columns={scale_col: 'ScaleFactor_PEER', luf_col: 'LUF_Hz'}, inplace=True)

    # Proje ölçek sütununu bul ve delta oluştur
    proj_scale_col = 'Ölçek Katsayısı' if 'Ölçek Katsayısı' in merged.columns else None
    if proj_scale_col:
        merged['delta_scale'] = pd.to_numeric(merged[proj_scale_col], errors='coerce') - \
                                pd.to_numeric(merged['ScaleFactor_PEER'], errors='coerce')

    cols_out: List[str] = ["Record Sequence Number", key_col, 'ScaleFactor_PEER', 'LUF_Hz']
    if proj_scale_col:
        cols_out += [proj_scale_col, 'delta_scale']

    report = merged[cols_out].sort_values(by="Record Sequence Number")
    return report


def main():
    ap = argparse.ArgumentParser(description="PEER CSV ile proje ölçek katsayılarını hizalama raporu üretir.")
    ap.add_argument('--proje', required=True, help='proje.csv yolu')
    ap.add_argument('--peer', required=True, help='_SearchResults.csv yolu')
    ap.add_argument('--out', default='report_fix_3B.csv', help='çıktı CSV yolu')
    args = ap.parse_args()

    report = align_with_peer(Path(args.proje), Path(args.peer))
    out_path = Path(args.out)
    report.to_csv(out_path, index=False)
    print(f"Rapor yazıldı: {out_path}")


if __name__ == '__main__':
    main()


