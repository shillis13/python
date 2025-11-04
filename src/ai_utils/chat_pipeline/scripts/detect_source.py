#!/usr/bin/env python3
import argparse, subprocess, json, os, re, sys

def where_froms(path:str)->str:
    try:
        out = subprocess.check_output(["xattr","-p","com.apple.metadata:kMDItemWhereFroms",path], stderr=subprocess.DEVNULL)
        return out.decode("utf-8","ignore")
    except Exception:
        return ""

def classify(path:str, exporter_map:dict):
    wf = where_froms(path)
    ai = None
    exporter = None
    # Domain hints
    if "chat.openai.com" in wf: ai="chatgpt"
    if "claude.ai" in wf: ai= "claude" if not ai else ai
    # Chrome extension mapping
    m = re.search(r"chrome-extension://([a-z]{32})", wf)
    if m:
        exporter = exporter_map.get("chrome_extensions", {}).get(m.group(1), exporter)
    # Filename patterns
    name = os.path.basename(path)
    for rule in exporter_map.get("filename_patterns", []):
        if re.search(rule["pattern"], name):
            exporter = rule.get("exporter", exporter)
    # Light content sniff
    try:
        with open(path, "rb") as f:
            head = f.read(4096).decode("utf-8","ignore")
            if "anthropic" in head or "claude-" in head:
                ai = ai or "claude"
            if '"mapping"' in head and '"current_node"' in head:
                ai = ai or "chatgpt"
    except Exception:
        pass

    return {"ai": ai or "unknown", "exporter": exporter or "unknown", "where_froms": wf}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=False, help="Queue file to append ready items")
    ap.add_argument("--out", required=False, help="Optional output directory for classifier JSON")
    ap.add_argument("--exporter-map", default="50_automation/schemas/exporter_map.yaml")
    args = ap.parse_args()

    target = os.environ.get("HAZEL_FILE") or os.environ.get("FILE") or ""
    if not target or not os.path.exists(target):
        print(json.dumps({"error":"No target file (set HAZEL_FILE)"}))
        sys.exit(0)

    # naive YAML read without PyYAML: accept empty map
    exporter_map = {}
    try:
        import yaml  # if available, great
        with open(args.exporter_map,"r") as f: exporter_map = yaml.safe_load(f) or {}
    except Exception:
        exporter_map = {}

    info = classify(target, exporter_map)

    if args.queue:
        os.makedirs(os.path.dirname(args.queue), exist_ok=True)
        with open(args.queue, "a") as q:
            q.write(target + "\n")

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        outp = os.path.join(args.out, os.path.basename(target)+".detect.json")
        with open(outp, "w") as f: json.dump(info, f, indent=2)

    print(json.dumps(info))

if __name__ == "__main__":
    main()
