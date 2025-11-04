#!/usr/bin/env python3
import argparse, os, json, pathlib, time

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Build a tiny manifest of bundles discovered
    bundles = []
    for root, dirs, files in os.walk(args.inp):
        rootp = pathlib.Path(root)
        if "chat.json" in files:
            bundles.append(str(rootp))

    manifest = {
        "processing_run_id": int(time.time()),
        "bundle_count": len(bundles)
    }
    (out/"manifest.yaml").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
