#!/usr/bin/env python3
"""
Generate manifest.json for the ITT logo library.

Reads:  ITT-LogosForDesignSystem/<Brand>/<Brand>-Logo-<Version>[-Endorsed].png
  <Version>  = Full | White   (any case)
  -Endorsed  = optional; marks the endorsed lockup ("by Informa TechTarget")

Two axes per brand:
  endorsement form: normal | endorsed   (a brand may exist in one form or both)
  version:          full   | white

Each brand records the forms it actually comes in. Brands that exist in only one form
are correct as-is, not incomplete. If a caller asks for a form a brand doesn't have,
`fallbacks` points at the form that does exist.

Both hyphen and underscore separators are accepted. Nothing is renamed or moved.
Add logos -> re-run -> commit.

Usage:
    python scripts/generate_manifest.py
    python scripts/generate_manifest.py --check
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
LOGOS = REPO / "ITT-LogosForDesignSystem"
MANIFEST = REPO / "manifest.json"

VERSION_USE = {
    "full":  {"backgrounds": ["light"], "role": "primary",  "note": "Color lockup for white/light surfaces (default)."},
    "white": {"backgrounds": ["dark"],  "role": "reversed", "note": "White-on-transparent. Dark/navy/photo surfaces only."},
}
FILE_RE = re.compile(r"^(?P<brand>.+?)[-_]Logo[-_](?P<ver>Full|White)(?P<end>[-_]Endorsed)?\.png$", re.I)
FORMS = ["normal", "endorsed"]


def slugify(name: str) -> str:
    return name.strip().lower().replace(" ", "-").replace("_", "-")


def scan_brand(brand_dir: Path) -> dict:
    variants: dict[str, dict] = {"normal": {}, "endorsed": {}}
    for f in sorted(brand_dir.glob("*.png")):
        m = FILE_RE.match(f.name)
        if not m:
            print(f"  ! skipping {brand_dir.name}/{f.name}: unrecognized name", file=sys.stderr)
            continue
        ver = m.group("ver").lower()
        group = "endorsed" if m.group("end") else "normal"
        with Image.open(f) as im:
            w, h = im.size
        variants[group][ver] = {
            "path": str(f.relative_to(REPO)).replace("\\", "/"),
            "dimensions": [w, h],
            "aspect_ratio": round(w / h, 3),
            **VERSION_USE[ver],
        }

    # Which forms this brand actually comes in.
    forms = [g for g in FORMS if variants[g]]

    # If a form is absent, map each of its versions to the form that exists.
    fallbacks = {}
    for g, other in (("normal", "endorsed"), ("endorsed", "normal")):
        if not variants[g] and variants[other]:
            for v in variants[other]:
                fallbacks[f"{g}.{v}"] = f"{other}.{v}"

    variants = {g: vs for g, vs in variants.items() if vs}

    return {
        "name": brand_dir.name,
        "slug": slugify(brand_dir.name),
        "folder": brand_dir.name,
        "forms": forms,
        "variants": variants,
        "fallbacks": fallbacks,
    }


def build() -> dict:
    if not LOGOS.is_dir():
        sys.exit(f"no logo directory at {LOGOS} — run this from the repo root.")
    brands = {}
    for brand_dir in sorted((p for p in LOGOS.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
        info = scan_brand(brand_dir)
        if info["variants"]:
            brands[info["slug"]] = info
    total = sum(len(vs) for b in brands.values() for vs in b["variants"].values())
    return {
        "schema_version": 4,
        "description": "ITT brand logo index. Choose endorsement form (normal|endorsed), then version by background.",
        "root": LOGOS.name,
        "endorsement_legend": {
            "normal":   "brand lockup on its own",
            "endorsed": "lockup with the 'by Informa TechTarget' endorsement line",
        },
        "form_rule": "A brand may come in one form or both; see each brand's 'forms'. If a "
                     "requested form is absent, resolve via the brand's 'fallbacks' to the form "
                     "that exists.",
        "selection_rules": {
            "light_background": "full (default)",
            "dark_background": "white",
            "photo_or_busy_background": "white over the darker area, with a scrim if needed",
            "never": "white logo on a light background (invisible); color logo on a dark background (disappears)",
        },
        "brand_count": len(brands),
        "file_count": total,
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
            sys.exit("manifest.json is stale — run: python scripts/generate_manifest.py")
        print("manifest.json is up to date.")
        return
    MANIFEST.write_text(rendered, encoding="utf-8")
    print(f"Wrote {MANIFEST.name}: {data['brand_count']} brands, {data['file_count']} files.")
    single = {s: b["forms"][0] for s, b in data["brands"].items() if len(b["forms"]) == 1}
    if single:
        print(f"  {len(single)} brand(s) come in a single form (by design; fallbacks set):")
        for s, form in single.items():
            print(f"    - {data['brands'][s]['name']}: {form} only")


if __name__ == "__main__":
    main()
