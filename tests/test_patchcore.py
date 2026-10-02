import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from defectscope import PatchCore, greedy_coreset, nearest_distance  # noqa: E402
from defectscope.metrics import image_auroc, pixel_auroc  # noqa: E402


def test_greedy_coreset_size_unique_and_covers_clusters():
    torch.manual_seed(0)
    centers = torch.tensor([[0.0, 0.0], [100.0, 0.0], [0.0, 100.0], [100.0, 100.0]])
    pts = torch.cat([c + torch.randn(50, 2) for c in centers])
    idx = greedy_coreset(pts, 4, proj_dim=0)
    assert len(idx) == 4 and len(set(idx.tolist())) == 4
    # farthest-point sampling must pick one point from each well-separated cluster
    assert sorted((idx // 50).tolist()) == [0, 1, 2, 3]


def test_nearest_distance_matches_bruteforce_and_chunks():
    q, b = torch.randn(30, 8), torch.randn(100, 8)
    expected = torch.cdist(q, b).min(1).values
    assert torch.allclose(nearest_distance(q, b, chunk=7), expected, atol=1e-5)


@pytest.mark.parametrize("backbone,grid", [("resnet18", (28, 28)), ("dinov2_vits14", (16, 16))])
def test_embed_shapes(backbone, grid):
    pc = PatchCore(backbone=backbone, pretrained=False, device="cpu")
    emb = pc.embed(torch.randn(2, 3, 224, 224))
    assert pc.grid == grid
    assert emb.shape[:2] == (2, grid[0] * grid[1])


def test_train_images_score_lower_than_corrupted():
    torch.manual_seed(0)
    pc = PatchCore(backbone="resnet18", pretrained=False, device="cpu", coreset_ratio=1.0)
    good = torch.zeros(4, 3, 224, 224) + 0.1 * torch.randn(4, 3, 224, 224)
    pc.fit([(good, None, None, None)])
    bad = good[:1].clone()
    bad[..., 80:140, 80:140] += 5.0
    s_good, maps = pc.predict(good[:1])
    s_bad, maps_bad = pc.predict(bad)
    assert maps.shape == (1, 224, 224)
    assert s_good.item() == pytest.approx(0.0, abs=1e-3)  # identical to bank entries
    assert s_bad.item() > s_good.item()
    # the anomaly map peaks inside the corrupted square
    peak = torch.nonzero(maps_bad[0] == maps_bad[0].max())[0]
    assert 60 <= peak[0] <= 160 and 60 <= peak[1] <= 160


def test_save_load_roundtrip(tmp_path):
    pc = PatchCore(backbone="resnet18", pretrained=False, device="cpu", coreset_ratio=0.5)
    pc.fit([(torch.randn(2, 3, 224, 224), None, None, None)])
    pc.save(tmp_path / "bank.pt")
    pc2 = PatchCore.load(tmp_path / "bank.pt", device="cpu", pretrained=False)
    assert pc2.bank.shape == pc.bank.shape and pc2.config == pc.config


def test_metrics():
    assert image_auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    m = torch.zeros(1, 4, 4); m[0, 0, 0] = 1
    s = torch.zeros(1, 4, 4); s[0, 0, 0] = 5
    assert pixel_auroc(m.numpy(), s.numpy()) == 1.0
