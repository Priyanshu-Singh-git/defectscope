"""PatchCore (Roth et al., CVPR 2022) — compact re-implementation.

fit:     good images -> mid-level patch features (locally aggregated, multi-layer)
         -> greedy k-center coreset -> memory bank
predict: test patch features -> distance to nearest bank entry = anomaly score
         image score = max patch score; pixel map = upsampled + Gaussian-smoothed patch scores

Simplification vs the paper: the paper pools each layer to a fixed dim and then
averages; here the layers are concatenated and channel-pooled once. The paper's
optional image-score reweighting is not used (image score = max patch distance).
"""
from __future__ import annotations

import math
import time

import torch
import torch.nn.functional as F
from torchvision.transforms.functional import gaussian_blur

from .backbones import FeatureExtractor


def greedy_coreset(feats: torch.Tensor, n: int, proj_dim: int = 128,
                   device="cpu", seed: int = 0) -> torch.Tensor:
    """Greedy k-center selection (farthest-point sampling) on a random projection.

    Returns indices (LongTensor, on CPU) of the n selected rows of `feats`.
    """
    N, D = feats.shape
    n = max(1, min(n, N))
    g = torch.Generator().manual_seed(seed)
    z = feats.float()
    if proj_dim and D > proj_dim:
        z = z @ (torch.randn(D, proj_dim, generator=g) / math.sqrt(proj_dim))
    z = z.to(device)
    sel = torch.empty(n, dtype=torch.long, device=device)
    sel[0] = int(torch.randint(N, (1,), generator=g))
    min_d = ((z - z[sel[0]]) ** 2).sum(1)
    for i in range(1, n):
        sel[i] = torch.argmax(min_d)
        min_d = torch.minimum(min_d, ((z - z[sel[i]]) ** 2).sum(1))
    return sel.cpu()


def nearest_distance(query: torch.Tensor, bank: torch.Tensor, chunk: int = 16384) -> torch.Tensor:
    """Euclidean distance from each query row to its nearest bank row."""
    best = torch.full((query.shape[0],), float("inf"), device=query.device)
    for s in range(0, bank.shape[0], chunk):
        d = torch.cdist(query, bank[s:s + chunk])
        best = torch.minimum(best, d.min(1).values)
    return best


class PatchCore:
    def __init__(self, backbone="wide_resnet50", layers=None, embed_dim=1024,
                 coreset_ratio=0.1, proj_dim=128, patch_size=3, img_size=224,
                 blur_sigma=4.0, device=None, seed=0, pretrained=True):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.extractor = FeatureExtractor(backbone, layers, img_size, pretrained).to(self.device)
        self.config = dict(backbone=backbone, layers=list(self.extractor.layers), embed_dim=embed_dim,
                           coreset_ratio=coreset_ratio, proj_dim=proj_dim, patch_size=patch_size,
                           img_size=img_size, blur_sigma=blur_sigma, seed=seed)
        self.bank = None
        self.grid = None
        self.fit_stats = {}

    # ---- features -------------------------------------------------------
    @torch.no_grad()
    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B,3,H,W) normalized -> (B, h*w, D) patch embeddings; sets self.grid=(h,w)."""
        p = self.config["patch_size"]
        feats = self.extractor(x.to(self.device))
        feats = [F.avg_pool2d(f, p, stride=1, padding=p // 2) for f in feats]  # local neighbourhood
        ref = feats[0].shape[-2:]
        feats = [f if f.shape[-2:] == ref else
                 F.interpolate(f, size=ref, mode="bilinear", align_corners=False) for f in feats]
        emb = torch.cat(feats, 1)
        B, C, h, w = emb.shape
        emb = emb.permute(0, 2, 3, 1).reshape(-1, 1, C)
        if C > self.config["embed_dim"]:
            emb = F.adaptive_avg_pool1d(emb, self.config["embed_dim"])
        self.grid = (h, w)
        return emb.reshape(B, h * w, -1)

    # ---- fit ------------------------------------------------------------
    @torch.no_grad()
    def fit(self, loader) -> "PatchCore":
        t0 = time.perf_counter()
        all_feats = []
        for batch in loader:
            e = self.embed(batch[0])
            all_feats.append(e.reshape(-1, e.shape[-1]).cpu())
        feats = torch.cat(all_feats)
        t1 = time.perf_counter()
        n = int(math.ceil(feats.shape[0] * self.config["coreset_ratio"]))
        if self.config["coreset_ratio"] >= 1.0:
            idx = torch.arange(feats.shape[0])
        else:
            idx = greedy_coreset(feats, n, self.config["proj_dim"], self.device, self.config["seed"])
        self.bank = feats[idx].to(self.device)
        t2 = time.perf_counter()
        self.fit_stats = dict(n_patches=int(feats.shape[0]), bank_size=int(self.bank.shape[0]),
                              feat_dim=int(self.bank.shape[1]),
                              extract_s=round(t1 - t0, 2), coreset_s=round(t2 - t1, 2))
        return self

    # ---- predict --------------------------------------------------------
    @torch.no_grad()
    def predict(self, x: torch.Tensor):
        """Returns (image_scores (B,), anomaly_maps (B,H,W)) on CPU."""
        if self.bank is None:
            raise RuntimeError("call fit() or load() first")
        emb = self.embed(x)
        B = emb.shape[0]
        h, w = self.grid
        patch = torch.stack([nearest_distance(e, self.bank) for e in emb]).reshape(B, 1, h, w)
        scores = patch.reshape(B, -1).max(1).values
        size = x.shape[-2:]
        maps = F.interpolate(patch, size=size, mode="bilinear", align_corners=False)
        sigma = self.config["blur_sigma"]
        if sigma > 0:
            k = 2 * int(round(4 * sigma)) + 1
            maps = gaussian_blur(maps, kernel_size=[k, k], sigma=[sigma, sigma])
        return scores.cpu(), maps[:, 0].cpu()

    # ---- persistence ----------------------------------------------------
    def save(self, path, extra: dict | None = None):
        torch.save({"config": self.config, "bank": self.bank.half().cpu(),
                    "fit_stats": self.fit_stats, "extra": extra or {}}, path)

    @classmethod
    def load(cls, path, device=None, pretrained=True) -> "PatchCore":
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        cfg = dict(ckpt["config"])
        obj = cls(**cfg, device=device, pretrained=pretrained)
        obj.bank = ckpt["bank"].float().to(obj.device)
        obj.fit_stats = ckpt.get("fit_stats", {})
        obj.extra = ckpt.get("extra", {})
        return obj
