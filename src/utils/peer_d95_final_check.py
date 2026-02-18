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


def build_final_check(proj_path: str, peer_path: str, out_path: str) -> None:
    dfp = read_any(proj_path)
    dfp.columns = [c.strip() for c in dfp.columns]
    dfs = read_any(peer_path)
    dfs.columns = [c.strip() for c in dfs.columns]

    if "RSN" not in dfp.columns and "Grup Adı" in dfp.columns:
        dfp["RSN"] = dfp["Grup Adı"].map(rsn_from_grup)
    if "RSN" not in dfs.columns and "Record Sequence Number" in dfs.columns:
        dfs["RSN"] = pd.to_numeric(dfs["Record Sequence Number"], errors="coerce")

    peer = dfs[["RSN", "5-95% Duration (sec)"]].rename(columns={"5-95% Duration (sec)": "PEER_D5_95"})
    proj = dfp[["RSN", "D5-95 (s)"]].rename(columns={"D5-95 (s)": "PROJ_D5_95"})

    cmp = proj.merge(peer, on="RSN", how="left")
    for c in ["PROJ_D5_95", "PEER_D5_95"]:
        cmp[c] = pd.to_numeric(cmp[c], errors="coerce")
    cmp["ΔD5_95"] = cmp["PROJ_D5_95"] - cmp["PEER_D5_95"]
    cmp.to_csv(out_path, index=False)
    print(f"Yazıldı: {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="PEER D5-95 final comparison report")
    ap.add_argument("--proj", required=True, help="proje.csv path")
    ap.add_argument("--peer", required=True, help="_SearchResults.csv path")
    ap.add_argument("--out", default="D95_final_check.csv", help="output CSV path")
    args = ap.parse_args()
    build_final_check(args.proj, args.peer, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


