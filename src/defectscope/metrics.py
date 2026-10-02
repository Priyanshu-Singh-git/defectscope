from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score


def image_auroc(labels, scores) -> float:
    return float(roc_auc_score(np.asarray(labels), np.asarray(scores)))


def pixel_auroc(masks, maps) -> float:
    """masks, maps: arrays of shape (N,H,W). AUROC over every pixel of the test set."""
    y = np.asarray(masks).astype(np.uint8).ravel()
    s = np.asarray(maps, dtype=np.float32).ravel()
    return float(roc_auc_score(y, s))
