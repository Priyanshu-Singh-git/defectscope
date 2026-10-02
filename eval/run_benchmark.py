"""Fit PatchCore on MVTec AD train/good and evaluate on test, for a grid of configs.

Each (backbone, layers, coreset_ratio, category) result is appended as one JSON line
to eval/runs/<tag>.jsonl. Only measured values are written.

  python eval/run_benchmark.py --tag backbones --backbones resnet18 wide_resnet50 convnext_tiny dinov2_vits14
  python eval/run_benchmark.py --tag coreset --backbones wide_resnet50 --coreset 0.01 0.1 0.25
  python eval/run_benchmark.py --tag layers --backbones wide_resnet50 --layers layer2 --layers layer3 --layers layer2,layer3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from defectscope import BACKBONES, PatchCore  # noqa: E402
from defectscope.data import MVTecDataset  # noqa: E402
from defectscope.metrics import image_auroc, pixel_auroc  # noqa: E402

CATEGORIES = ["bottle", "screw", "carpet", "metal_nut", "transistor"]


def evaluate(model: PatchCore, ds: MVTecDataset, batch_size: int):
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=2)
    scores, maps, masks, labels = [], [], [], []
    if model.device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for img, mask, label, _ in loader:
        s, m = model.predict(img)
        scores.append(s); maps.append(m); masks.append(mask[:, 0]); labels.append(label)
    if model.device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    scores = torch.cat(scores).numpy()
    maps = torch.cat(maps).numpy()
    masks = torch.cat(masks).numpy()
    labels = torch.cat(labels).numpy()
    return {
        "image_auroc": image_auroc(labels, scores),
        "pixel_auroc": pixel_auroc(masks, maps),
        "ms_per_image": 1000 * elapsed / len(ds),
        "n_test": len(ds), "n_defective": int(labels.sum()),
    }, scores, maps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--data", default=str(ROOT / "data" / "mvtec"))
    ap.add_argument("--categories", nargs="+", default=CATEGORIES)
    ap.add_argument("--backbones", nargs="+", default=["wide_resnet50"])
    ap.add_argument("--layers", action="append", default=None,
                    help="comma-separated layer names; repeat flag for several configs")
    ap.add_argument("--coreset", nargs="+", type=float, default=[0.1])
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--save-banks", default=None, help="dir to save memory banks")
    ap.add_argument("--save-preds", default=None, help="dir to save test scores/maps (npz)")
    ap.add_argument("--device", default=None)
    ap.add_argument("--skip-done", action="store_true", help="skip configs already in <tag>.jsonl")
    args = ap.parse_args()

    out = ROOT / "eval" / "runs" / f"{args.tag}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    layer_cfgs = [tuple(l.split(",")) for l in args.layers] if args.layers else [None]
    done = set()
    if args.skip_done and out.exists():
        for l in out.read_text().splitlines():
            r = json.loads(l)
            done.add((r["backbone"], tuple(r["layers"]), r["coreset_ratio"], r["category"]))

    for backbone in args.backbones:
        for layers in layer_cfgs:
            for ratio in args.coreset:
                for cat in args.categories:
                    lay = tuple(layers or BACKBONES[backbone]["default"])
                    if (backbone, lay, ratio, cat) in done:
                        print(f"[{args.tag}] skip {backbone} {lay} {ratio} {cat} (done)", flush=True)
                        continue
                    torch.manual_seed(0)
                    model = PatchCore(backbone=backbone, layers=layers, coreset_ratio=ratio,
                                      device=args.device)
                    train = MVTecDataset(args.data, cat, "train")
                    test = MVTecDataset(args.data, cat, "test")
                    model.fit(DataLoader(train, batch_size=args.batch_size, num_workers=2))
                    res, scores, maps = evaluate(model, test, args.batch_size)
                    row = {"tag": args.tag, "category": cat, **model.config, **model.fit_stats, **res,
                           "device": str(model.device),
                           "gpu": torch.cuda.get_device_name(0) if model.device.type == "cuda" else None}
                    with open(out, "a", encoding="utf-8") as f:
                        f.write(json.dumps(row) + "\n")
                    print(f"[{args.tag}] {backbone:14s} {','.join(model.config['layers']):16s} "
                          f"cs={ratio:<5} {cat:11s} img={res['image_auroc']:.4f} "
                          f"pix={res['pixel_auroc']:.4f} bank={model.fit_stats['bank_size']} "
                          f"t_core={model.fit_stats['coreset_s']}s {res['ms_per_image']:.1f}ms/img",
                          flush=True)
                    name = f"{backbone}_{'-'.join(model.config['layers'])}_{ratio}_{cat}"
                    if args.save_banks:
                        Path(args.save_banks).mkdir(parents=True, exist_ok=True)
                        model.save(Path(args.save_banks) / f"{name}.pt")
                    if args.save_preds:
                        Path(args.save_preds).mkdir(parents=True, exist_ok=True)
                        np.savez_compressed(Path(args.save_preds) / f"{name}.npz",
                                            scores=scores, maps=maps.astype(np.float16),
                                            paths=np.array([s["path"] for s in test.samples]),
                                            labels=np.array([s["label"] for s in test.samples]))
                    del model
                    torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
