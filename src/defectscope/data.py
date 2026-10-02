"""MVTec AD loading: train/good images for fitting, test images + ground-truth masks for evaluation."""
from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
IMG_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def image_transform(resize: int = 256, crop: int = 224) -> T.Compose:
    return T.Compose([
        T.Resize(resize, interpolation=T.InterpolationMode.BILINEAR),
        T.CenterCrop(crop),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def mask_transform(resize: int = 256, crop: int = 224) -> T.Compose:
    return T.Compose([
        T.Resize(resize, interpolation=T.InterpolationMode.NEAREST),
        T.CenterCrop(crop),
        T.ToTensor(),
    ])


def list_samples(root: str | Path, category: str, split: str) -> list[dict]:
    """Return [{path, label, mask, defect}] for one category/split. label 1 = defective."""
    base = Path(root) / category
    samples = []
    for defect_dir in sorted((base / split).iterdir()):
        if not defect_dir.is_dir():
            continue
        defect = defect_dir.name
        for img in sorted(p for p in defect_dir.iterdir() if p.suffix.lower() in IMG_EXTS):
            mask = None
            if defect != "good":
                mask = base / "ground_truth" / defect / f"{img.stem}_mask.png"
            samples.append({"path": str(img), "label": int(defect != "good"),
                            "mask": str(mask) if mask else None, "defect": defect})
    return samples


class MVTecDataset(Dataset):
    def __init__(self, root, category, split="train", resize=256, crop=224):
        self.samples = list_samples(root, category, split)
        self.crop = crop
        self.tf = image_transform(resize, crop)
        self.mtf = mask_transform(resize, crop)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        s = self.samples[i]
        img = self.tf(Image.open(s["path"]).convert("RGB"))
        if s["mask"]:
            mask = (self.mtf(Image.open(s["mask"]).convert("L")) > 0.5).float()
        else:
            mask = torch.zeros(1, self.crop, self.crop)
        return img, mask, s["label"], i
