"""Frozen pretrained backbones that return intermediate feature maps (NCHW).

Layer names are mapped to timm indices so CNNs and ViTs share one interface:
  CNN  -> timm features_only=True, out_indices
  ViT  -> forward_intermediates(...) patch tokens reshaped to a grid
"""
from __future__ import annotations

import timm
import torch
from torch import nn

BACKBONES = {
    "resnet18": {
        "timm": "resnet18.tv_in1k", "kind": "cnn",
        "layers": {"layer1": 1, "layer2": 2, "layer3": 3, "layer4": 4},
        "default": ("layer2", "layer3"),
    },
    "wide_resnet50": {
        "timm": "wide_resnet50_2.tv_in1k", "kind": "cnn",
        "layers": {"layer1": 1, "layer2": 2, "layer3": 3, "layer4": 4},
        "default": ("layer2", "layer3"),
    },
    "convnext_tiny": {
        "timm": "convnext_tiny.fb_in1k", "kind": "cnn",
        "layers": {"stage0": 0, "stage1": 1, "stage2": 2, "stage3": 3},
        "default": ("stage1", "stage2"),
    },
    "dinov2_vits14": {
        "timm": "vit_small_patch14_dinov2.lvd142m", "kind": "vit",
        "layers": {f"block{i}": i for i in range(12)},
        "default": ("block7", "block10"),
    },
}


class FeatureExtractor(nn.Module):
    def __init__(self, name: str, layers=None, img_size: int = 224, pretrained: bool = True):
        super().__init__()
        if name not in BACKBONES:
            raise ValueError(f"unknown backbone {name!r}; choose from {list(BACKBONES)}")
        spec = BACKBONES[name]
        self.name = name
        self.kind = spec["kind"]
        self.layers = tuple(layers or spec["default"])
        self.indices = [spec["layers"][l] for l in self.layers]
        if self.kind == "cnn":
            self.model = timm.create_model(spec["timm"], pretrained=pretrained,
                                           features_only=True, out_indices=self.indices)
        else:
            self.model = timm.create_model(spec["timm"], pretrained=pretrained,
                                           img_size=img_size, num_classes=0)
        self.model.eval().requires_grad_(False)

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        if self.kind == "cnn":
            return list(self.model(x))
        return list(self.model.forward_intermediates(
            x, indices=self.indices, output_fmt="NCHW", intermediates_only=True, norm=False))
