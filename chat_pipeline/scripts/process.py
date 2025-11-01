#!/usr/bin/env python3
import argparse, os, json, pathlib, datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    in_dir = pathlib.Path(args.inp)
    out_root = pathlib.Path(args.out)

    for p in sorted(in_dir.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        ai = data["source"]["ai"]
        # Use local date for folder buckets
        dt_local = datetime.datetime.strptime(data["timestamps"]["created_local"], "%Y-%m-%dT%H:%M:%S%z")
        yyyy, mm, dd = dt_local.strftime("%Y"), dt_local.strftime("%m"), dt_local.strftime("%d")
        chat_id = data["chat_id"]
        bundle = out_root / ai / yyyy / mm / dd / chat_id
        bundle.mkdir(parents=True, exist_ok=True)

        # Emit canonical files
        (bundle/"chat.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        (bundle/"chat.md").write_text(f"# {chat_id}\n\n*(placeholder)*\n", encoding="utf-8")
        meta = {
            "source": data.get("source", {}),
            "timestamps": data.get("timestamps", {}),
            "content_sha256": data.get("meta",{}).get("content_sha256",""),
            "provenance": {"detectors": ["process_stub"], "where_from": []}
        }
        (bundle/"meta.yaml").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        (bundle/"extracts").mkdir(exist_ok=True)

        print(bundle)

if __name__ == "__main__":
    main()
