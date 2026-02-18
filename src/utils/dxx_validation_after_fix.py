import argparse
import pandas as pd
import re


def read_any(path: str) -> pd.DataFrame:
    for sep in [';', ',']:
        try:
            df = pd.read_csv(path, sep=sep)
            if df.shape[1] > 1:
                return df
        except Exception:
            pass
    return pd.read_csv(path)


def rsn_from_grup(val: str) -> int | None:
    m = re.search(r"RSN\s*(\d+)|RSN(\d+)", str(val), flags=re.IGNORECASE)
    if not m:
        return None
    g1, g2 = m.groups()
    return int(g1 or g2) if (g1 or g2) else None


def build_validation(proj_path: str, peer_path: str, out_path: str, threshold: float) -> None:
    dfp = read_any(proj_path)
    dfp.columns = [c.strip() for c in dfp.columns]
    dfs = read_any(peer_path)
    dfs.columns = [c.strip() for c in dfs.columns]

    if "RSN" not in dfp.columns and "Grup Adı" in dfp.columns:
        dfp["RSN"] = dfp["Grup Adı"].map(rsn_from_grup)
    if "RSN" not in dfs.columns and "Record Sequence Number" in dfs.columns:
        dfs["RSN"] = pd.to_numeric(dfs["Record Sequence Number"], errors="coerce")

    peer_cols = [c for c in ["RSN", "5-75% Duration (sec)", "5-95% Duration (sec)"] if c in dfs.columns]
    peer = dfs[peer_cols].rename(columns={
        "5-75% Duration (sec)": "PEER_D5_75",
        "5-95% Duration (sec)": "PEER_D5_95",
    })
    proj_cols = [c for c in ["RSN", "D5-75 (s)", "D5-95 (s)"] if c in dfp.columns]
    proj = dfp[proj_cols].rename(columns={
        "D5-75 (s)": "PROJ_D5_75",
        "D5-95 (s)": "PROJ_D5_95",
    })

    cmp = proj.merge(peer, on="RSN", how="left")
    for c in ["PROJ_D5_75", "PROJ_D5_95", "PEER_D5_75", "PEER_D5_95"]:
        if c in cmp.columns:
            cmp[c] = pd.to_numeric(cmp[c], errors="coerce")

    cmp["ΔD5_75"] = cmp["PROJ_D5_75"] - cmp["PEER_D5_75"]
    cmp["ΔD5_95"] = cmp["PROJ_D5_95"] - cmp["PEER_D5_95"]

    cmp.to_csv(out_path, index=False)
    print(f"Yazıldı: {out_path}")

    viol = cmp[(cmp["ΔD5_75"].abs() > threshold) | (cmp["ΔD5_95"].abs() > threshold)]
    if not viol.empty:
        cols = [c for c in ["RSN", "ΔD5_75", "ΔD5_95"] if c in viol.columns]
        raise SystemExit(f"D‑süre farkları toleransı aşıyor (>{threshold}s):\n{viol[cols].to_string(index=False)}")


def main() -> int:
    ap = argparse.ArgumentParser(description="End-to-end Dxx validation after fix (PEER vs Project)")
    ap.add_argument("--proj", required=True, help="proje.csv path")
    ap.add_argument("--peer", required=True, help="_SearchResults.csv path")
    ap.add_argument("--out", default="Dxx_validation_after_fix.csv", help="output CSV path")
    ap.add_argument("--threshold", type=float, default=0.10, help="absolute seconds tolerance for ΔD5-75, ΔD5-95")
    args = ap.parse_args()
    build_validation(args.proj, args.peer, args.out, args.threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


