"""Export the browser demo: ONNX scorer + per-product memory banks + samples -> docs/.

The ONNX graph takes (image, bank) and returns the 28x28 patch-score map and the image score,
so one model file serves every product line; each line only ships its small memory bank.
Parity with the PyTorch PatchCore is checked on every sample image before writing.

  python deploy/export_web.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
import torch.nn.functional as F
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from defectscope import PatchCore  # noqa: E402
from defectscope.data import image_transform  # noqa: E402

BANKS = ROOT / "models" / "web"
OUT = ROOT / "docs"
CATS = ["bottle", "screw", "carpet", "metal_nut", "transistor"]
LABELS = {"bottle": "Bottle", "screw": "Screw", "carpet": "Carpet", "metal_nut": "Metal nut",
          "transistor": "Transistor"}


class Scorer(torch.nn.Module):
    """PatchCore inference: features -> local aggregation -> nearest-bank-patch distance."""

    def __init__(self, pc: PatchCore):
        super().__init__()
        self.extractor = pc.extractor
        self.p = pc.config["patch_size"]

    def forward(self, x, bank):
        feats = [F.avg_pool2d(f, self.p, stride=1, padding=self.p // 2) for f in self.extractor(x)]
        ref = feats[0].shape[-2:]
        feats = [feats[0]] + [F.interpolate(f, size=ref, mode="bilinear", align_corners=False) for f in feats[1:]]
        emb = torch.cat(feats, 1)                       # 1,C,h,w
        q = emb.flatten(2).transpose(1, 2)[0]           # hw,C
        d2 = (q * q).sum(1, keepdim=True) + (bank * bank).sum(1)[None] - 2 * q @ bank.T
        dist = d2.clamp_min(0).min(1).values.sqrt()     # hw
        patch = dist.reshape(1, ref[0], ref[1])
        return patch, patch.max()


def main():
    OUT.mkdir(exist_ok=True)
    for sub in ("models", "banks", "samples"):
        shutil.rmtree(OUT / sub, ignore_errors=True)
        (OUT / sub).mkdir()
    pcs = {c: PatchCore.load(BANKS / f"{c}.pt", device="cpu") for c in CATS}
    first = pcs[CATS[0]]
    assert first.config["embed_dim"] >= first.bank.shape[1], "channel pooling not exported"
    scorer = Scorer(first).eval()
    onnx_path = OUT / "models" / "patchcore_resnet18.onnx"
    x0 = torch.randn(1, 3, 224, 224)
    torch.onnx.export(scorer, (x0, first.bank), str(onnx_path), opset_version=17,
                      input_names=["image", "bank"], output_names=["patch_scores", "score"],
                      dynamic_axes={"bank": {0: "n"}}, do_constant_folding=True)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    results = json.loads((ROOT / "eval" / "web_threshold_results.json").read_text())["results"]
    meta = {"model": onnx_path.name, "input": 224, "resize": 256, "grid": None, "products": []}
    tf = image_transform()
    worst = 0.0
    for c in CATS:
        pc = pcs[c]
        bank = pc.bank.float().numpy().astype(np.float32)
        (OUT / "banks" / f"{c}.bin").write_bytes(bank.tobytes())
        samples = []
        for f in sorted((ROOT / "assets" / "samples" / c).glob("*.png")):
            x = tf(Image.open(f).convert("RGB"))[None]
            with torch.no_grad():
                ref_patch, ref_score = scorer(x, pc.bank.float())
            got_patch, got_score = sess.run(None, {"image": x.numpy(), "bank": bank})
            err = abs(float(got_score) - float(ref_score)) / float(ref_score)
            worst = max(worst, err)
            meta["grid"] = list(got_patch.shape[1:])
            # web copy: 512px JPEG keeps the page light
            img = Image.open(f).convert("RGB")
            img.thumbnail((512, 512))
            name = f"{c}_{f.stem}.jpg"
            img.save(OUT / "samples" / name, quality=90)
            label = f.stem.rsplit("_", 1)[0].replace("_", " ")
            samples.append({"file": f"samples/{name}", "label": label, "py_score": float(ref_score)})
        meta["products"].append({
            "key": c, "name": LABELS[c], "bank": f"banks/{c}.bin", "n": int(bank.shape[0]),
            "dim": int(bank.shape[1]), "threshold": float(pc.extra["threshold"]), "samples": samples,
            "test": {k: results[c][k] for k in ("test_n", "test_defective", "recall_defects",
                                                 "false_positive_rate", "image_auroc")}})
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"ONNX vs PyTorch max relative score error: {worst:.2e}")
    assert worst < 1e-3, "ONNX export does not match PyTorch"
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file()) / 1e6
    print(f"wrote {OUT} ({size:.1f} MB)")


if __name__ == "__main__":
    main()
