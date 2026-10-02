"""DefectScope — label-free visual defect detection (PatchCore), CPU demo."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib
import numpy as np
import streamlit as st
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from defectscope import PatchCore  # noqa: E402
from defectscope.data import IMAGENET_MEAN, IMAGENET_STD, image_transform  # noqa: E402

MODELS = ROOT / "models" / "web"
SAMPLES = ROOT / "assets" / "samples"
RESULTS = ROOT / "eval" / "web_threshold_results.json"
CONTACT_URL = "https://github.com/Priyanshu-Singh-git"  # swap for the Upwork profile URL when available
MAX_UPLOAD_MB = 8
LABELS = {"bottle": "Bottle", "screw": "Screw", "carpet": "Carpet (texture)",
          "metal_nut": "Metal nut", "transistor": "Transistor"}

st.set_page_config(page_title="DefectScope", page_icon="🔍", layout="wide")
torch.set_num_threads(2)


@st.cache_resource(show_spinner="Loading backbone and memory bank…")
def load_model(category: str) -> PatchCore:
    return PatchCore.load(MODELS / f"{category}.pt", device="cpu")


@st.cache_data
def load_results() -> dict:
    return json.loads(RESULTS.read_text())["results"] if RESULTS.exists() else {}


def overlay(img: np.ndarray, amap: np.ndarray, thr: float) -> np.ndarray:
    """Jet heatmap of score/threshold, blended where the map is elevated."""
    r = amap / thr  # 1.0 = the pass/fail threshold
    norm = np.clip((r - 0.7) / 0.6, 0, 1)  # colour range 0.7x..1.3x threshold
    heat = matplotlib.colormaps["jet"](norm)[..., :3]
    alpha = np.clip((r - 0.75) / 0.35, 0, 1)[..., None] * 0.65  # only clearly abnormal areas
    return (img * (1 - alpha) + heat * alpha).clip(0, 1)


def denorm(x: torch.Tensor) -> np.ndarray:
    m = torch.tensor(IMAGENET_MEAN)[:, None, None]
    s = torch.tensor(IMAGENET_STD)[:, None, None]
    return (x * s + m).clamp(0, 1).permute(1, 2, 0).numpy()


# ---------------- sidebar ----------------
st.sidebar.title("🔍 DefectScope")
st.sidebar.caption("Finds defects after seeing only good parts.")
cats = [c for c in LABELS if (MODELS / f"{c}.pt").exists()]
if not cats:
    st.error("No memory banks found in models/web. Run train/build_demo_banks.py --coreset 0.01 --out models/web first.")
    st.stop()
qp = st.query_params  # deep links, e.g. ?product=metal_nut&sample=bent
category = st.sidebar.selectbox("Product line", cats, format_func=LABELS.get,
                                index=cats.index(qp["product"]) if qp.get("product") in cats else 0)
sample_files = sorted((SAMPLES / category).glob("*.png"))
source = st.sidebar.radio("Input", ["Sample image", "Upload your own"])
img_pil = None
if source == "Sample image" and sample_files:
    want = qp.get("sample", "")
    start = next((i for i, f in enumerate(sample_files) if want and f.stem.startswith(want)), 0)
    pick = st.sidebar.selectbox("Sample", sample_files, index=start,
                                format_func=lambda p: p.stem.rsplit("_", 1)[0].replace("_", " ")
                                .replace("good", "good (no defect)"))
    img_pil = Image.open(pick).convert("RGB")
else:
    up = st.sidebar.file_uploader("Image (PNG/JPG, max 8 MB)", type=["png", "jpg", "jpeg"])
    if up is not None:
        if up.size > MAX_UPLOAD_MB * 1024 * 1024:
            st.sidebar.error(f"File too large (> {MAX_UPLOAD_MB} MB).")
        else:
            img_pil = Image.open(up).convert("RGB")
            img_pil.thumbnail((1024, 1024))
    st.sidebar.caption("Upload a photo of the same product type; the model only knows the "
                       "selected line's normal appearance.")

# ---------------- main ----------------
st.title("DefectScope: spots defects, no defect photos needed")
st.write("Set up from photos of **good parts only**. It flags anything that doesn't look like a "
         "normal part and shows where. Pick a sample or upload your own photo.")

if img_pil is None:
    st.info("Pick a sample or upload an image in the sidebar.")
else:
    model = load_model(category)
    thr = float(model.extra["threshold"])
    x = image_transform()(img_pil)[None]
    t0 = time.perf_counter()
    score, amap = model.predict(x)
    ms = 1000 * (time.perf_counter() - t0)
    score, amap = float(score[0]), amap[0].numpy()
    ratio = score / thr
    defective = score > thr

    c1, c2, c3 = st.columns([1, 1, 0.8])
    base = denorm(x[0])
    c1.image(base, caption="Input (224×224 centre crop)", use_container_width=True)
    c2.image(overlay(base, amap, thr), caption="Anomaly heatmap", use_container_width=True)
    with c3:
        if defective:
            st.error("### ⚠️ DEFECT")
        else:
            st.success("### ✅ PASS")
        st.metric("Anomaly score / threshold", f"{ratio:.2f}×",
                  help="Image score is the largest patch distance to the memory bank of normal "
                       "patches. Above 1.0× = defect.")
        st.progress(min(ratio / 2, 1.0))
        st.caption(f"CPU inference: {ms:.0f} ms · memory bank: {model.bank.shape[0]:,} patches "
                   f"× {model.bank.shape[1]} dims · backbone: {model.config['backbone']}")

    res = load_results().get(category)
    if res:
        with st.expander("How good is this model on the held-out test set?"):
            st.write(
                f"MVTec AD `{category}` test set ({res['test_n']} images, {res['test_defective']} "
                f"defective), threshold fixed from held-out *good* images only:")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Image AUROC", f"{res['image_auroc']:.3f}")
            m2.metric("Accuracy", f"{res['accuracy']:.1%}")
            m3.metric("Defects caught", f"{res['recall_defects']:.1%}")
            m4.metric("False alarms", f"{res['false_positive_rate']:.1%}")

with st.expander("How it works"):
    st.markdown(
        "1. A frozen ImageNet backbone extracts mid-level features (layer 2 + layer 3).\n"
        "2. Each feature is averaged with its 3×3 neighbourhood, giving one embedding per image patch.\n"
        "3. Embeddings from all good training images are compressed with greedy **coreset** sampling "
        "into a memory bank.\n"
        "4. At test time, each patch's distance to its nearest normal patch is its anomaly score. "
        "The max is the image score, and the upsampled map is the heatmap.\n\n"
        "Full benchmark (WideResNet-50, ConvNeXt, DINOv2, layer and coreset ablations) is in the repo.")

st.divider()
st.caption(f"Built by **Priyanshu Singh** · [Contact / hire me]({CONTACT_URL}) · "
           "Demo data: MVTec AD (CC BY-NC-SA 4.0, non-commercial); for production, "
           "the model is fitted on your own good parts.")
