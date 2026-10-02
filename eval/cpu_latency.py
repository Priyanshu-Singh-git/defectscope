"""Measure CPU inference latency of the deployed demo model (models/demo/<category>.pt).

Writes eval/cpu_latency.json. Mirrors the app: 2 torch threads, one image at a time.
"""
from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from defectscope import PatchCore  # noqa: E402
from defectscope.data import image_transform, list_samples  # noqa: E402


def main(category="screw", n=30, threads=2):
    torch.set_num_threads(threads)
    model = PatchCore.load(ROOT / "models" / "demo" / f"{category}.pt", device="cpu")
    tf = image_transform()
    paths = [s["path"] for s in list_samples(ROOT / "data" / "mvtec", category, "test")][:n]
    xs = [tf(Image.open(p).convert("RGB"))[None] for p in paths]
    for x in xs[:3]:
        model.predict(x)  # warm-up
    times = []
    for x in xs:
        t0 = time.perf_counter()
        model.predict(x)
        times.append(1000 * (time.perf_counter() - t0))
    res = {"category": category, "bank_size": int(model.bank.shape[0]), "n": len(times),
           "threads": threads, "cpu": platform.processor() or platform.machine(),
           "median_ms": float(np.median(times)), "p90_ms": float(np.percentile(times, 90))}
    (ROOT / "eval" / "cpu_latency.json").write_text(json.dumps(res, indent=2))
    print(res)


if __name__ == "__main__":
    main(*sys.argv[1:2])
