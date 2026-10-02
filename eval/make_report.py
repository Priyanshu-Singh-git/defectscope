"""Turn eval/runs/*.jsonl into eval/results.md + charts + a heatmap gallery.

Every number in results.md is read from the run logs; nothing is typed in by hand.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
RUNS = ROOT / "eval" / "runs"
FIG = ROOT / "assets" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# reference palette (light surface), fixed slot order
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BACKBONE_ORDER = ["wide_resnet50", "resnet18", "convnext_tiny", "dinov2_vits14"]
BACKBONE_LABEL = {"wide_resnet50": "WideResNet-50", "resnet18": "ResNet-18",
                  "convnext_tiny": "ConvNeXt-Tiny", "dinov2_vits14": "DINOv2 ViT-S/14"}
COLOR = {b: SERIES[i] for i, b in enumerate(BACKBONE_ORDER)}  # color follows the entity
CATS = ["bottle", "screw", "carpet", "metal_nut", "transistor"]

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"], "font.size": 11,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": INK2,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "axes.titlecolor": INK,
    "axes.titlesize": 13, "axes.titleweight": "bold",
})


def load(tag):
    p = RUNS / f"{tag}.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
    # if a config was run twice keep the latest row
    dedup = {}
    for r in rows:
        dedup[(r["backbone"], tuple(r["layers"]), r["coreset_ratio"], r["category"])] = r
    return list(dedup.values())


def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def fmt(x, d=3):
    return f"{x:.{d}f}"


# ---------------- backbone comparison ----------------
def backbone_section(rows):
    by = defaultdict(dict)
    for r in rows:
        by[r["backbone"]][r["category"]] = r
    bbs = [b for b in BACKBONE_ORDER if b in by and all(c in by[b] for c in CATS)]
    if not bbs:
        return "", None
    md = ["## 1. Backbone comparison (layers: default mid-level pair, coreset 10%)", "",
          "| Backbone | Layers | " + " | ".join(CATS) + " | **Mean** |",
          "|---|---|" + "---|" * (len(CATS) + 1)]
    for metric, name in (("image_auroc", "Image AUROC"), ("pixel_auroc", "Pixel AUROC")):
        md.append(f"| *{name}* | | " + " | " * len(CATS) + " |")
        for b in bbs:
            vals = [by[b][c][metric] for c in CATS]
            md.append(f"| {BACKBONE_LABEL[b]} | {'+'.join(by[b][CATS[0]]['layers'])} | "
                      + " | ".join(fmt(v) for v in vals) + f" | **{fmt(np.mean(vals))}** |")
    md += ["", "| Backbone | Feature dim | Mean bank size (patches) | Mean fit time (s) | "
               "GPU ms / test image |", "|---|---|---|---|---|"]
    for b in bbs:
        rs = [by[b][c] for c in CATS]
        md.append(f"| {BACKBONE_LABEL[b]} | {rs[0]['feat_dim']} | "
                  f"{int(np.mean([r['bank_size'] for r in rs])):,} | "
                  f"{np.mean([r['extract_s'] + r['coreset_s'] for r in rs]):.1f} | "
                  f"{np.mean([r['ms_per_image'] for r in rs]):.1f} |")
    md += ["", "GPU timings: " + str(rows[0].get("gpu")) + "; per-image time includes data loading, "
           "feature extraction, nearest-neighbour search and heatmap upsampling.", ""]

    # dot plot, two panels (small multiples, shared category axis)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    ylabels = CATS + ["Mean"]
    y = np.arange(len(ylabels))[::-1]
    for ax, (metric, title) in zip(axes, (("image_auroc", "Image AUROC (is the part defective?)"),
                                          ("pixel_auroc", "Pixel AUROC (where is the defect?)"))):
        lo = 1.0
        for i, b in enumerate(bbs):
            vals = [by[b][c][metric] for c in CATS]
            vals = vals + [np.mean(vals)]
            lo = min(lo, min(vals))
            off = (i - (len(bbs) - 1) / 2) * 0.16
            ax.scatter(vals, y + off, s=70, color=COLOR[b], edgecolor=SURFACE, linewidth=2,
                       zorder=3, label=BACKBONE_LABEL[b])
        ax.axhline(0.5, color=AXIS, linewidth=0.8)
        ax.set_xlim(max(0.0, np.floor(lo * 50) / 50 - 0.01), 1.003)
        ax.set_title(title, loc="left")
        style(ax)
    axes[0].set_yticks(y, ylabels)
    axes[0].get_yticklabels()[-1].set_fontweight("bold")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(bbs), frameon=False,
               labelcolor=INK2, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    out = FIG / "backbone_comparison.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    md.append(f"![Backbone comparison](../assets/figures/{out.name})\n")
    return "\n".join(md), bbs


# ---------------- layer ablation ----------------
def layer_section(rows, base_rows):
    rows = rows + [r for r in base_rows if r["backbone"] == "wide_resnet50"]
    by = defaultdict(dict)
    for r in rows:
        if r["backbone"] == "wide_resnet50" and r["coreset_ratio"] == 0.1:
            by["+".join(r["layers"])][r["category"]] = r
    cfgs = [k for k in ("layer2", "layer3", "layer2+layer3", "layer3+layer4") if k in by
            and all(c in by[k] for c in CATS)]
    if len(cfgs) < 2:
        return ""
    md = ["## 2. Which layers? (WideResNet-50, coreset 10%)", "",
          "| Layers | Image AUROC (mean) | Pixel AUROC (mean) | Worst category (image) |",
          "|---|---|---|---|"]
    for k in cfgs:
        im = [by[k][c]["image_auroc"] for c in CATS]
        px = [by[k][c]["pixel_auroc"] for c in CATS]
        worst = CATS[int(np.argmin(im))]
        md.append(f"| {k} | {fmt(np.mean(im))} | {fmt(np.mean(px))} | {worst} ({fmt(min(im))}) |")
    md.append("")
    return "\n".join(md)


# ---------------- coreset ablation ----------------
def coreset_section(rows, base_rows):
    rows = rows + base_rows
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["backbone"] in ("wide_resnet50", "resnet18") and \
                "+".join(r["layers"]) == "layer2+layer3":
            agg[r["backbone"]][r["coreset_ratio"]].append(r)
    md = ["## 3. Coreset size: accuracy vs memory vs speed", "",
          "| Backbone | Coreset | Image AUROC | Pixel AUROC | Bank size (patches) | "
          "Bank size fp16 (MB) | GPU ms / image |", "|---|---|---|---|---|---|---|"]
    series = {}
    for b in ("wide_resnet50", "resnet18"):
        pts = []
        for ratio in sorted(agg[b]):
            rs = agg[b][ratio]
            if len(rs) < len(CATS):
                continue
            bank = np.mean([r["bank_size"] for r in rs])
            mb = np.mean([r["bank_size"] * r["feat_dim"] * 2 / 1e6 for r in rs])
            im, px = np.mean([r["image_auroc"] for r in rs]), np.mean([r["pixel_auroc"] for r in rs])
            ms = np.mean([r["ms_per_image"] for r in rs])
            md.append(f"| {BACKBONE_LABEL[b]} | {ratio:.0%} | {fmt(im)} | {fmt(px)} | {int(bank):,} | "
                      f"{mb:.1f} | {ms:.1f} |")
            pts.append((ratio, im, px, mb))
        if pts:
            series[b] = pts
    md.append("")
    if any(len(p) > 1 for p in series.values()):
        fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
        for b, pts in series.items():
            r = [p[0] for p in pts]
            axes[0].plot(r, [p[1] for p in pts], "-o", color=COLOR[b], lw=2, ms=8,
                         mec=SURFACE, mew=2, label=BACKBONE_LABEL[b])
            axes[1].plot(r, [p[2] for p in pts], "-o", color=COLOR[b], lw=2, ms=8,
                         mec=SURFACE, mew=2, label=BACKBONE_LABEL[b])
            for ax, k in ((axes[0], 1), (axes[1], 2)):
                ax.annotate(BACKBONE_LABEL[b], (r[-1], pts[-1][k]), xytext=(6, 0),
                            textcoords="offset points", va="center", color=INK2, fontsize=10)
        for ax, t in zip(axes, ("Mean image AUROC", "Mean pixel AUROC")):
            ax.set_xscale("log")
            ax.set_xticks([0.01, 0.1, 0.25], ["1%", "10%", "25%"])
            ax.set_xlabel("Coreset size (% of training patches kept)")
            ax.set_title(t, loc="left")
            style(ax)
            ax.grid(axis="y", color=GRID, linewidth=0.8)
            ax.set_xlim(0.008, 0.45)
        fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=2,
                   frameon=False, labelcolor=INK2, bbox_to_anchor=(0.5, -0.02))
        fig.tight_layout(rect=(0, 0.08, 1, 1))
        out = FIG / "coreset_tradeoff.png"
        fig.savefig(out, dpi=200)
        plt.close(fig)
        md.append(f"![Coreset trade-off](../assets/figures/{out.name})\n")
    return "\n".join(md)


# ---------------- gallery ----------------
def gallery(dark: bool = False):
    from defectscope.data import image_transform, IMAGENET_MEAN, IMAGENET_STD
    preds = ROOT / "eval" / "preds"
    files = sorted(preds.glob("wide_resnet50_layer2-layer3_0.1_*.npz"))
    if not files:
        return ""
    tf = image_transform()
    m, s = np.array(IMAGENET_MEAN), np.array(IMAGENET_STD)
    picks = []
    for cat in CATS:
        f = preds / f"wide_resnet50_layer2-layer3_0.1_{cat}.npz"
        if not f.exists():
            continue
        d = np.load(f)
        bad = np.where(d["labels"] == 1)[0]
        # the defective image with the median score: representative, not cherry-picked best
        i = bad[np.argsort(d["scores"][bad])[len(bad) // 2]]
        picks.append((cat, str(d["paths"][i]), d["maps"][i].astype(np.float32),
                      float(d["scores"][i]), d["maps"].astype(np.float32)))
    bg, ink, ink2 = ("#131c2e", "#ffffff", "#cbd5e1") if dark else (SURFACE, INK, INK2)
    fig, axes = plt.subplots(2, len(picks), figsize=(3.0 * len(picks), 6.4), facecolor=bg)
    for j, (cat, path, amap, score, allmaps) in enumerate(picks):
        x = tf(Image.open(path).convert("RGB")).permute(1, 2, 0).numpy() * s + m
        x = x.clip(0, 1)
        gt_path = Path(path.replace("\\test\\", "\\ground_truth\\").replace("/test/", "/ground_truth/"))
        gt_path = gt_path.with_name(gt_path.stem + "_mask.png")
        axes[0, j].imshow(x)
        if gt_path.exists():
            from defectscope.data import mask_transform
            gt = mask_transform()(Image.open(gt_path).convert("L"))[0].numpy()
            axes[0, j].contour(gt, levels=[0.5], colors=["#e34948"], linewidths=1.5)
        vmin, vmax = np.percentile(allmaps, 1), np.percentile(allmaps, 99.9)
        axes[1, j].imshow(x)
        axes[1, j].imshow(amap, cmap="jet", alpha=0.5, vmin=vmin, vmax=vmax)
        defect = Path(path).parent.name
        axes[0, j].set_title(f"{cat}\n{defect.replace('_', ' ')}", fontsize=11, color=INK)
        for a in axes[:, j]:
            a.axis("off")
    axes[0, 0].text(-0.08, 0.5, "input + true\ndefect outline", transform=axes[0, 0].transAxes,
                    rotation=90, ha="right", va="center", color=ink2, fontsize=10)
    axes[1, 0].text(-0.08, 0.5, "PatchCore\nheatmap", transform=axes[1, 0].transAxes,
                    rotation=90, ha="right", va="center", color=ink2, fontsize=10)
    fig.tight_layout()
    out = FIG / ("heatmap_gallery_dark.png" if dark else "heatmap_gallery.png")
    fig.savefig(out, dpi=170, facecolor=bg)
    plt.close(fig)
    return ("## 4. Heatmap gallery (WideResNet-50)\n\nFor each category the defective test image with the "
            "**median** anomaly score is shown (representative, not the best case). Red outline = "
            f"ground-truth defect mask.\n\n![Gallery](../assets/figures/{out.name})\n")


def demo_section():
    p = ROOT / "eval" / "demo_threshold_results.json"
    if not p.exists():
        return ""
    d = json.loads(p.read_text())
    md = [f"## 5. Deployed demo model ({BACKBONE_LABEL.get(d['backbone'], d['backbone'])}, "
          f"coreset {d['coreset']:.0%}, CPU)", "",
          "Pass/fail threshold = the highest score among 10% of *good training images held out "
          "from the memory bank*. No test images were used to pick it. Metrics below are on the "
          "full MVTec AD test split at that fixed threshold.", "",
          "| Category | Test images (defective) | Image AUROC | Accuracy | Defects caught | "
          "False alarms on good parts |", "|---|---|---|---|---|---|"]
    for c, r in d["results"].items():
        md.append(f"| {c} | {r['test_n']} ({r['test_defective']}) | {fmt(r['image_auroc'])} | "
                  f"{r['accuracy']:.1%} | {r['recall_defects']:.1%} | {r['false_positive_rate']:.1%} |")
    cpu = ROOT / "eval" / "cpu_latency.json"
    if cpu.exists():
        c = json.loads(cpu.read_text())
        md += ["", f"CPU latency ({c['cpu']}, {c['threads']} threads, {c['n']} images, after warm-up): "
                   f"median **{c['median_ms']:.0f} ms**, p90 {c['p90_ms']:.0f} ms per image "
                   f"(backbone + nearest-neighbour search + heatmap)."]
    md.append("")
    return "\n".join(md)


def main():
    base = load("backbones")
    sec1, _ = backbone_section(base)
    parts = [
        "# DefectScope: evaluation results", "",
        "All numbers are measured by `eval/run_benchmark.py` on the official MVTec AD test split "
        "(5 of 15 categories: bottle, screw, carpet, metal_nut, transistor). Images are resized to 256 "
        "and center-cropped to 224. Generated by `eval/make_report.py` from `eval/runs/*.jsonl`. "
        "Nothing is hand-entered.", "",
        "Not measured: PRO / AUPRO (region-overlap metric) and the other 10 MVTec categories.", "",
        sec1, layer_section(load("layers"), base), coreset_section(load("coreset"), base),
        gallery(), demo_section(),
    ]
    gallery(dark=True)  # deck version
    (ROOT / "eval" / "results.md").write_text("\n".join(p for p in parts if p), encoding="utf-8")
    print("wrote eval/results.md and", sorted(x.name for x in FIG.glob("*.png")))


if __name__ == "__main__":
    main()
