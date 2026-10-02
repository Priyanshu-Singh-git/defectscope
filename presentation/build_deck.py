"""Build the Upwork deck: measured numbers -> deck.pptx -> per-slide 1920x1080 PNGs + PDF.

  python presentation/build_deck.py --demo-url https://... --repo-url https://github.com/...

Steps
  1. read eval/ outputs, render hero.png and qr.png, write deck_data.json
  2. node build_pptx.js           -> deck.pptx (16:9, 13.333 x 7.5 in)
  3. export_slides.ps1 (PowerPoint) -> slides/slide_01.png ... (1920x1080) and deck.pdf
Every number on a slide is read from eval/ outputs; nothing is typed in.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation"
FIG = ROOT / "assets" / "figures"
sys.path.insert(0, str(ROOT / "src"))
CATS = ["bottle", "screw", "carpet", "metal_nut", "transistor"]
LABEL = {"wide_resnet50": "WideResNet-50", "resnet18": "ResNet-18",
         "convnext_tiny": "ConvNeXt-Tiny", "dinov2_vits14": "DINOv2 ViT-S/14"}


def load_rows(tag):
    p = ROOT / "eval" / "runs" / f"{tag}.jsonl"
    rows = {}
    for l in p.read_text().splitlines():
        r = json.loads(l)
        rows[(r["backbone"], "+".join(r["layers"]), r["coreset_ratio"], r["category"])] = r
    return list(rows.values())


def hero_image(category="metal_nut"):
    """Input | heatmap overlay of the median-score defective test image (representative)."""
    import matplotlib
    from defectscope.data import image_transform, IMAGENET_MEAN, IMAGENET_STD
    d = np.load(ROOT / "eval" / "preds" / f"wide_resnet50_layer2-layer3_0.1_{category}.npz")
    bad = np.where(d["labels"] == 1)[0]
    i = bad[np.argsort(d["scores"][bad])[len(bad) // 2]]
    x = image_transform()(Image.open(str(d["paths"][i])).convert("RGB")).permute(1, 2, 0).numpy()
    x = (x * np.array(IMAGENET_STD) + np.array(IMAGENET_MEAN)).clip(0, 1)
    allm = d["maps"].astype(np.float32)
    lo, hi = np.percentile(allm, 50), np.percentile(allm, 99.9)
    norm = ((d["maps"][i].astype(np.float32) - lo) / (hi - lo)).clip(0, 1)
    heat = matplotlib.colormaps["jet"](norm)[..., :3]
    a = (norm[..., None] ** 1.2) * 0.65
    over = (x * (1 - a) + heat * a).clip(0, 1)
    for name, arr in (("hero_input.png", x), ("hero_heatmap.png", over)):
        Image.fromarray((arr * 255).astype(np.uint8)).resize((672, 672), Image.LANCZOS).save(OUT / name)
    return Path(str(d["paths"][i])).parent.name


def qr(url):
    import qrcode
    q = qrcode.QRCode(border=2, box_size=12)
    q.add_data(url); q.make(fit=True)
    q.make_image(fill_color="#0b1220", back_color="white").convert("RGB").save(OUT / "qr.png")


def build(demo_url, repo_url):
    base = load_rows("backbones")
    by = defaultdict(dict)
    for r in base:
        by[r["backbone"]][r["category"]] = r
    mean = {b: (float(np.mean([by[b][c]["image_auroc"] for c in CATS])),
                float(np.mean([by[b][c]["pixel_auroc"] for c in CATS])))
            for b in by if len(by[b]) == len(CATS)}
    best = max(mean, key=lambda b: mean[b][0] + mean[b][1])
    demo = json.loads((ROOT / "eval" / "demo_threshold_results.json").read_text())
    dres = demo["results"].values()
    cpu = json.loads((ROOT / "eval" / "cpu_latency.json").read_text())
    fit_s = float(np.mean([by[demo["backbone"]][c]["extract_s"] + by[demo["backbone"]][c]["coreset_s"]
                           for c in CATS]))
    n_train = [len(list((ROOT / "data" / "mvtec" / c / "train" / "good").glob("*.png"))) for c in CATS]

    cs = defaultdict(list)
    for r in load_rows("coreset") + base:
        if "+".join(r["layers"]) == "layer2+layer3" and r["backbone"] in ("wide_resnet50", "resnet18"):
            cs[(r["backbone"], r["coreset_ratio"])].append(r)
    coreset_rows = [{
        "backbone": LABEL[b], "ratio": ratio,
        "image": float(np.mean([r["image_auroc"] for r in rs])),
        "pixel": float(np.mean([r["pixel_auroc"] for r in rs])),
        "bank_mb": float(np.mean([r["bank_size"] * r["feat_dim"] * 2 / 1e6 for r in rs])),
    } for (b, ratio), rs in sorted(cs.items(), key=lambda kv: (kv[0][0] != "wide_resnet50", kv[0][1]))
        if len(rs) == len(CATS)]

    hero_defect = hero_image()
    qr(demo_url)
    data = {
        "demo_url": demo_url, "repo_url": repo_url, "hero_defect": hero_defect,
        "backbones": [{"label": LABEL[b], "image": mean[b][0], "pixel": mean[b][1]}
                      for b in ["wide_resnet50", "resnet18", "convnext_tiny", "dinov2_vits14"] if b in mean],
        "best": {"label": LABEL[best], "image": mean[best][0], "pixel": mean[best][1]},
        "demo": {"backbone": LABEL[demo["backbone"]],
                 "recall": float(np.mean([r["recall_defects"] for r in dres])),
                 "fpr": float(np.mean([r["false_positive_rate"] for r in dres])),
                 "accuracy": float(np.mean([r["accuracy"] for r in dres]))},
        "cpu": cpu, "fit_s": fit_s, "n_train_min": min(n_train), "n_train_max": max(n_train),
        "coreset": coreset_rows,
        "assets": {"hero_input": str(OUT / "hero_input.png"), "hero_heatmap": str(OUT / "hero_heatmap.png"),
                   "shot": str(FIG / "demo_screenshot.png"), "gallery": str(FIG / "heatmap_gallery_dark.png"),
                   "qr": str(OUT / "qr.png")},
    }
    (OUT / "deck_data.json").write_text(json.dumps(data, indent=2))
    subprocess.run(["node", "build_pptx.js"], check=True, cwd=OUT)
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(OUT / "export_slides.ps1")], check=True, cwd=OUT)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-url", default="https://defectscope.streamlit.app")
    ap.add_argument("--repo-url", default="https://github.com/Priyanshu-Singh-git/defectscope")
    a = ap.parse_args()
    build(a.demo_url, a.repo_url)
