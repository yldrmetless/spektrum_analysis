"""
D75 & D95 — PEER Uyum Düzeltme Aracı

Kullanım:
    python -m src.utils.d75_d95_peer_alignment --proje proje.csv --peer _SearchResults.csv --out D75_D95_diff_report.csv

Kaynak kılavuz: Fix_D75_D95_PEER_Alignment.md

Bu araç, projedeki `D5-75 (s)` ve `D5-95 (s)` sürelerini PEER `_SearchResults.csv` ile
RSN (Record Sequence Number) üzerinden eşleyip fark raporu üretir ve bazı teşhis notları ekler.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

import pandas as pd


def _read_any_csv(path: Path) -> pd.DataFrame:
    """PEER/Proje CSV'lerini ayırıcıyı tahmin ederek okur."""
    for sep in [';', ',']:
        try:
            df = pd.read_csv(path, sep=sep)
            if df.shape[1] > 1:
                df.columns = [c.strip() for c in df.columns]
                return df
        except Exception:
            pass
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    return df


def _extract_rsn(text: Optional[str]) -> Optional[int]:
    """Serbest metinden RSN numarasını çıkarır (ör. "RSN68_SFERN_PEL" -> 68)."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    m = re.search(r"RSN\s*(\d+)|RSN(\d+)", str(text), flags=re.IGNORECASE)
    return int(m.group(1) or m.group(2)) if m else None


def build_alignment_report(project_csv: Path, peer_csv: Path) -> pd.DataFrame:
    df_proj = _read_any_csv(project_csv)
    df_peer = _read_any_csv(peer_csv)

    # Proje tarafı beklenen sütunlar (Türkçe şema)
    required_proj = ["Grup Adı", "D5-75 (s)", "D5-95 (s)", "Arias Şiddeti (m/s)"]
    for col in required_proj:
        if col not in df_proj.columns:
            raise ValueError(f"Proje CSV sütunu eksik: {col}")

    # PEER tarafı beklenen sütunlar
    peer_map_candidates = {
        "5-75% Duration (sec)": "PEER_D5_75",
        "5-95% Duration (sec)": "PEER_D5_95",
        "Arias Intensity (m/sec)": "PEER_Arias",
        "Arias Intensity (m/s)": "PEER_Arias",
    }
    # Zorunlu RSN ve dosya adları
    peer_required = ["Record Sequence Number", "Horizontal-1 Acc. Filename", "Horizontal-2 Acc. Filename"]
    for col in peer_required:
        if col not in df_peer.columns:
            raise ValueError(f"PEER CSV sütunu eksik: {col}")

    # PEER metrik sütunlarını normalize et
    keep_peer = {
        "Record Sequence Number": "RSN",
        "Horizontal-1 Acc. Filename": "H1_File",
        "Horizontal-2 Acc. Filename": "H2_File",
    }
    for src_col, dst_col in peer_map_candidates.items():
        if src_col in df_peer.columns:
            keep_peer[src_col] = dst_col

    df_peer_keep = df_peer[list(keep_peer.keys())].rename(columns=keep_peer)
    # RSN sayısallaştır
    df_peer_keep["RSN"] = pd.to_numeric(df_peer_keep["RSN"], errors="coerce")

    # Projede RSN çıkar ve daralt
    df_proj = df_proj.copy()
    df_proj["RSN"] = df_proj["Grup Adı"].map(_extract_rsn)
    df_proj_keep = df_proj[[
        "Grup Adı", "RSN", "D5-75 (s)", "D5-95 (s)", "Arias Şiddeti (m/s)"
    ]].rename(columns={
        "D5-75 (s)": "PROJ_D5_75",
        "D5-95 (s)": "PROJ_D5_95",
        "Arias Şiddeti (m/s)": "PROJ_Arias",
    })

    # Eşleştir
    cmp = df_proj_keep.merge(df_peer_keep, on="RSN", how="left")

    # Tür dönüştürmeleri
    for c in ["PROJ_D5_75", "PROJ_D5_95", "PROJ_Arias", "PEER_D5_75", "PEER_D5_95", "PEER_Arias"]:
        if c in cmp.columns:
            cmp[c] = pd.to_numeric(cmp[c], errors="coerce")

    # Farklar
    if "PEER_D5_75" in cmp.columns:
        cmp["ΔD5_75"] = cmp["PROJ_D5_75"] - cmp["PEER_D5_75"]
    else:
        cmp["ΔD5_75"] = pd.NA
    if "PEER_D5_95" in cmp.columns:
        cmp["ΔD5_95"] = cmp["PROJ_D5_95"] - cmp["PEER_D5_95"]
    else:
        cmp["ΔD5_95"] = pd.NA
    if "PEER_Arias" in cmp.columns:
        cmp["ΔArias"] = cmp["PROJ_Arias"] - cmp["PEER_Arias"]
    else:
        cmp["ΔArias"] = pd.NA

    # Teşhis notu
    def _diagnose_row(r: pd.Series) -> str:
        notes = []
        try:
            if pd.notna(r.get("ΔD5_75")) and pd.notna(r.get("ΔD5_95")):
                if abs(float(r["ΔD5_75"])) > 1.0 and abs(float(r["ΔD5_95"])) < 0.2:
                    notes.append("D5-75 bileşen/normalizasyon karışıklığı olası")
                if abs(float(r["ΔD5_95"])) > 1.0 and abs(float(r["ΔD5_75"])) < 0.2:
                    notes.append("D5-95 bileşen/normalizasyon karışıklığı olası")
            if pd.notna(r.get("ΔArias")) and pd.notna(r.get("PEER_Arias")):
                denom = abs(float(r["PEER_Arias"])) if float(r["PEER_Arias"]) != 0 else 1.0
                if abs(float(r["ΔArias"])) > 0.2 * denom:
                    notes.append("Arias farkı yüksek: dosya/birim/filtre kontrol et")
        except Exception:
            pass
        return "; ".join(notes)

    cmp["Not"] = cmp.apply(_diagnose_row, axis=1)

    # Çıktı sıralaması ve kolon düzeni
    cols = [
        "Grup Adı", "RSN",
        "PROJ_D5_75", "PEER_D5_75", "ΔD5_75",
        "PROJ_D5_95", "PEER_D5_95", "ΔD5_95",
        "PROJ_Arias", "PEER_Arias", "ΔArias",
        "H1_File", "H2_File", "Not"
    ]
    cols = [c for c in cols if c in cmp.columns]
    out = cmp[cols].sort_values(by="RSN", kind="stable")
    return out


def main():
    ap = argparse.ArgumentParser(description="D75/D95 sürelerini PEER ile hizalama raporu üretir.")
    ap.add_argument("--proje", required=True, help="proje.csv yolu")
    ap.add_argument("--peer", required=True, help="_SearchResults.csv yolu")
    ap.add_argument("--out", default="D75_D95_diff_report.csv", help="çıktı CSV yolu")
    args = ap.parse_args()

    report = build_alignment_report(Path(args.proje), Path(args.peer))
    report.to_csv(args.out, index=False)
    print(f"Yazıldı: {args.out}")


if __name__ == "__main__":
    main()


