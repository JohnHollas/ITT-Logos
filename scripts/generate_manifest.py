import argparse, json, sys
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
LOGOS = REPO / "ITT-LogosForDesignSystem"
MANIFEST = REPO / "manifest.json"

VERSION_USE = {
    "full":  {"backgrounds": ["light"], "role": "primary",  "note": "Default. Color lockup for white/light surfaces."},
    "black": {"backgrounds": ["light"], "role": "mono",     "note": "Monochrome contexts on light surfaces (B&W print, grayscale layouts)."},
    "white": {"backgrounds": ["dark"],  "role": "reversed", "note": "White-on-transparent. Dark/navy/photo surfaces only."},
}
VERSION_ORDER = ["full", "black", "white"]

def slugify(name):
    return name.strip().lower().replace(" ", "-").replace("_", "-")

def scan_brand(brand_dir):
    versions = {}
    for f in sorted(brand_dir.glob("*.png")):
        stem = f.stem
        if "-" not in stem:
            print("  ! skipping " + f.name + ": expected <Brand>-Logo-<Version>.png", file=sys.stderr)
            continue
        version = stem.rsplit("-", 1)[-1].lower()
        if version not in VERSION_USE:
            print("  ! skipping " + f.name + ": unrecognized version '" + version + "'", file=sys.stderr)
            continue
        with Image.open(f) as im:
            w, h = im.size
        versions[version] = {
            "path": str(f.relative_to(REPO)).replace("\\", "/"),
            "dimensions": [w, h],
            "aspect_ratio": round(w / h, 3),
            **VERSION_USE[version],
        }
    fallbacks = {}
    if "black" not in versions and "full" in versions:
        fallbacks["black"] = "full"
    if "white" not in versions:
        fallbacks["white"] = None
    if "full" not in versions and "black" in versions:
        fallbacks["full"] = "black"
    return {
        "name": brand_dir.name,
        "slug": slugify(brand_dir.name),
        "folder": brand_dir.name,
        "versions": versions,
        "fallbacks": fallbacks,
        "missing": [v for v in VERSION_ORDER if v not in versions],
    }

def build():
    if not LOGOS.is_dir():
        sys.exit("no logo directory at " + str(LOGOS) + " - run this from the repo root.")
    brands = {}
    for brand_dir in sorted(p for p in LOGOS.iterdir() if p.is_dir()):
        info = scan_brand(brand_dir)
        if info["versions"]:
            brands[info["slug"]] = info
    return {
        "schema_version": 1,
        "description": "Index of brand logos. Pick a version by the background the logo sits on.",
        "root": LOGOS.name,
        "selection_rules": {
            "light_background": "full (default) - or black for monochrome contexts",
            "dark_background": "white",
            "photo_or_busy_background": "white over the darker area, with a scrim if needed",
            "never": "white logo on light bg (invisible); color/black logo on dark bg (disappears)",
        },
        "brand_count": len(brands),
        "brands": brands,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    data = build()
    rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        current = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else ""
        if current != rendered:
            sys.exit("manifest.json is stale - run: python scripts/generate_manifest.py")
        print("manifest.json is up to date.")
        return
    MANIFEST.write_text(rendered, encoding="utf-8")
    total = sum(len(b["versions"]) for b in data["brands"].values())
    print("Wrote " + MANIFEST.name + ": " + str(data["brand_count"]) + " brands, " + str(total) + " files.")
    for slug, b in data["brands"].items():
        if b["missing"]:
            line = "  - " + b["name"] + ": missing " + ", ".join(b["missing"])
            if b["fallbacks"]:
                line += " (fallbacks: " + str(b["fallbacks"]) + ")"
            print(line)

if __name__ == "__main__":
    main()
