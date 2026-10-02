"""Build the small CPU-friendly memory banks shipped with the Streamlit demo.

Per category:
  1. split train/good 90/10 (fixed seed)
  2. fit PatchCore (ResNet-18) on the 90%
  3. threshold = max anomaly score over the held-out 10% good images
     (no test images are used to choose it)
  4. report accuracy / recall / false-positive rate on the untouched test set at that threshold
Writes models/demo/<category>.pt and eval/demo_threshold_results.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from defectscope import PatchCore  # noqa: E402
from defectscope.data import MVTecDataset  # noqa: E402
from defectscope.metrics import image_auroc  # noqa: E402

CATEGORIES = ["bottle", "screw", "carpet", "metal_nut", "transistor"]


def scores_of(model, ds, bs=8):
    out = []
    for img, *_ in DataLoader(ds, batch_size=bs, num_workers=2):
        out.append(model.predict(img)[0])
    return torch.cat(out).numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "mvtec"))
    ap.add_argument("--backbone", default="resnet18")
    ap.add_argument("--coreset", type=float, default=0.1)
    ap.add_argument("--holdout", type=float, default=0.1)
    ap.add_argument("--out", default=str(ROOT / "models" / "demo"))
    ap.add_argument("--samples", type=int, default=3, help="sample test images to copy per category")
    ap.add_argument("--results", default=str(ROOT / "eval" / "demo_threshold_results.json"))
    args = ap.parse_args()
    Path(args.out).mkdir(parents=True, exist_ok=True)
    report = {}
    for cat in CATEGORIES:
        torch.manual_seed(0)
        train = MVTecDataset(args.data, cat, "train")
        test = MVTecDataset(args.data, cat, "test")
        perm = np.random.default_rng(0).permutation(len(train))
        n_hold = max(5, int(round(len(train) * args.holdout)))
        hold_idx, fit_idx = perm[:n_hold].tolist(), perm[n_hold:].tolist()

        model = PatchCore(backbone=args.backbone, coreset_ratio=args.coreset)
        model.fit(DataLoader(Subset(train, fit_idx), batch_size=8, num_workers=2))
        hold = scores_of(model, Subset(train, hold_idx))
        thr = float(hold.max())

        s = scores_of(model, test)
        y = np.array([x["label"] for x in test.samples])
        pred = s > thr
        res = {
            "threshold": thr, "holdout_good_n": n_hold,
            "holdout_score_mean": float(hold.mean()), "holdout_score_std": float(hold.std()),
            "test_n": int(len(y)), "test_defective": int(y.sum()),
            "image_auroc": image_auroc(y, s),
            "accuracy": float((pred == y).mean()),
            "recall_defects": float(pred[y == 1].mean()),
            "false_positive_rate": float(pred[y == 0].mean()),
            "bank_size": model.fit_stats["bank_size"],
        }
        report[cat] = res
        model.save(Path(args.out) / f"{cat}.pt",
                   extra={"threshold": thr, "category": cat,
                          "holdout_score_mean": res["holdout_score_mean"]})
        print(cat, json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()}),
              flush=True)

        # copy a few sample test images for one-click trial: 1 good + defects of different types
        sdir = ROOT / "assets" / "samples" / cat
        sdir.mkdir(parents=True, exist_ok=True)
        goods = [x for x in test.samples if x["label"] == 0]
        seen, bads = set(), []
        for x in test.samples:
            if x["label"] == 1 and x["defect"] not in seen:
                seen.add(x["defect"]); bads.append(x)
        for x in goods[:1] + bads[: args.samples - 1]:
            shutil.copy(x["path"], sdir / f"{x['defect']}_{Path(x['path']).name}")

    out_json = Path(args.results)
    out_json.write_text(json.dumps({"backbone": args.backbone, "coreset": args.coreset,
                                    "results": report}, indent=2))
    print("wrote", out_json)


if __name__ == "__main__":
    main()
