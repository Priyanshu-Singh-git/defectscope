"""Build the 8-slide Upwork deck (16:9) from measured results.

Outputs (presentation/):
  deck.html, deck.pdf, slides/slide_01.png ... slide_08.png, diagram.png, hero.png
Every number on a slide is read from eval/ outputs; nothing is typed in.

  python presentation/build_deck.py --demo-url https://... --repo-url https://github.com/...
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation"
FIG = ROOT / "assets" / "figures"
sys.path.insert(0, str(ROOT / "src"))
CATS = ["bottle", "screw", "carpet", "metal_nut", "transistor"]
LABEL = {"wide_resnet50": "WideResNet-50", "resnet18": "ResNet-18",
         "convnext_tiny": "ConvNeXt-Tiny", "dinov2_vits14": "DINOv2 ViT-S/14"}


def b64(path_or_img, fmt="PNG"):
    if isinstance(path_or_img, (str, Path)):
        data = Path(path_or_img).read_bytes()
        mime = "image/png" if str(path_or_img).endswith(".png") else "image/jpeg"
    else:
        buf = io.BytesIO(); path_or_img.save(buf, fmt); data = buf.getvalue(); mime = "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def load_rows(tag):
    p = ROOT / "eval" / "runs" / f"{tag}.jsonl"
    rows = {}
    for l in p.read_text().splitlines():
        r = json.loads(l)
        rows[(r["backbone"], "+".join(r["layers"]), r["coreset_ratio"], r["category"])] = r
    return list(rows.values())


def hero_image(category="metal_nut"):
    """Large heatmap overlay of a representative (median-score) defective image."""
    import matplotlib
    from defectscope.data import image_transform, IMAGENET_MEAN, IMAGENET_STD
    d = np.load(ROOT / "eval" / "preds" / f"wide_resnet50_layer2-layer3_0.1_{category}.npz")
    bad = np.where(d["labels"] == 1)[0]
    i = bad[np.argsort(d["scores"][bad])[len(bad) // 2]]
    x = image_transform()(Image.open(str(d["paths"][i])).convert("RGB")).permute(1, 2, 0).numpy()
    x = (x * np.array(IMAGENET_STD) + np.array(IMAGENET_MEAN)).clip(0, 1)
    amap = d["maps"][i].astype(np.float32)
    allm = d["maps"].astype(np.float32)
    lo, hi = np.percentile(allm, 50), np.percentile(allm, 99.9)
    norm = ((amap - lo) / (hi - lo)).clip(0, 1)
    heat = matplotlib.colormaps["jet"](norm)[..., :3]
    a = (norm[..., None] ** 1.2) * 0.65
    over = (x * (1 - a) + heat * a).clip(0, 1)
    both = np.concatenate([x, np.ones((224, 8, 3)), over], axis=1)
    img = Image.fromarray((both * 255).astype(np.uint8)).resize((1104 * 2 // 2, 504), Image.LANCZOS)
    img.save(OUT / "hero.png")
    return img, str(Path(str(d["paths"][i])).parent.name)


def qr(url):
    import qrcode
    q = qrcode.QRCode(border=1, box_size=10)
    q.add_data(url); q.make(fit=True)
    return q.make_image(fill_color="#0b1220", back_color="white").convert("RGB")


CSS = """
@page { size: 1920px 1080px; margin: 0; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0b1220; font-family: "Segoe UI", system-ui, sans-serif; color: #e5e7eb; }
.slide { width: 1920px; height: 1080px; position: relative; overflow: hidden;
         background: #0b1220; padding: 96px 112px; page-break-after: always; display: flex;
         flex-direction: column; }
.kicker { color: #14b8a6; font-weight: 700; font-size: 26px; letter-spacing: .12em; text-transform: uppercase; }
h1 { font-size: 92px; line-height: 1.04; font-weight: 800; color: #fff; letter-spacing: -.02em; }
h2 { font-size: 64px; line-height: 1.08; font-weight: 800; color: #fff; margin-top: 14px; letter-spacing: -.01em; }
p.lead { font-size: 32px; line-height: 1.4; color: #cbd5e1; margin-top: 24px; max-width: 1500px; }
.accent { color: #f59e0b; }
.teal { color: #14b8a6; }
.foot { position: absolute; left: 112px; right: 112px; bottom: 48px; display: flex;
        justify-content: space-between; color: #64748b; font-size: 22px; }
.row { display: flex; gap: 40px; margin-top: 48px; flex: 1; min-height: 0; }
.card { background: #131c2e; border: 1px solid #22304a; border-radius: 20px; padding: 36px 40px; flex: 1; }
.card h3 { font-size: 34px; color: #fff; margin-bottom: 14px; }
.card p { font-size: 27px; line-height: 1.45; color: #cbd5e1; }
.big { font-size: 96px; font-weight: 800; color: #fff; line-height: 1; }
.big small { font-size: 36px; color: #94a3b8; font-weight: 600; }
.cap { font-size: 24px; color: #94a3b8; margin-top: 12px; line-height: 1.4; }
.imgwrap { background: #fcfcfb; border-radius: 16px; padding: 18px; display: flex; align-items: center;
           justify-content: center; }
.imgwrap img { max-width: 100%; max-height: 100%; }
.pipe { display: flex; align-items: stretch; gap: 0; margin-top: 70px; }
.box { flex: 1; background: #131c2e; border: 2px solid #22304a; border-radius: 20px; padding: 32px 26px; }
.box .n { color: #14b8a6; font-weight: 800; font-size: 26px; }
.box h3 { color: #fff; font-size: 33px; margin: 10px 0 12px; line-height: 1.15; }
.box p { color: #cbd5e1; font-size: 24px; line-height: 1.4; }
.box.hl { border-color: #14b8a6; }
.arrow { width: 56px; display: flex; align-items: center; justify-content: center; color: #14b8a6; font-size: 44px; }
.tag { display: inline-block; background: #14b8a61f; color: #5eead4; border: 1px solid #14b8a655;
       border-radius: 999px; padding: 6px 18px; font-size: 22px; margin: 6px 8px 0 0; }
"""


def foot(n):
    return f'<div class="foot"><span>DefectScope · label-free defect detection</span><span>{n} / 8</span></div>'


def build(demo_url, repo_url):
    OUT.mkdir(exist_ok=True)
    base = load_rows("backbones")
    by = defaultdict(dict)
    for r in base:
        by[r["backbone"]][r["category"]] = r
    mean = {b: (np.mean([by[b][c]["image_auroc"] for c in CATS]),
                np.mean([by[b][c]["pixel_auroc"] for c in CATS])) for b in by if len(by[b]) == len(CATS)}
    best = max(mean, key=lambda b: mean[b][0] + mean[b][1])
    demo = json.loads((ROOT / "eval" / "demo_threshold_results.json").read_text())
    dres = demo["results"]
    d_acc = np.mean([r["accuracy"] for r in dres.values()])
    d_rec = np.mean([r["recall_defects"] for r in dres.values()])
    d_fpr = np.mean([r["false_positive_rate"] for r in dres.values()])
    cpu = json.loads((ROOT / "eval" / "cpu_latency.json").read_text())
    fit_s = np.mean([by[demo["backbone"]][c]["extract_s"] + by[demo["backbone"]][c]["coreset_s"] for c in CATS])
    n_train = [len(list((ROOT / "data" / "mvtec" / c / "train" / "good").glob("*.png"))) for c in CATS]

    hero, hero_defect = hero_image()
    shot = FIG / "demo_screenshot.png"
    qr_img = qr(demo_url)

    s = []
    # 1 hook
    s.append(f"""<section class="slide" style="padding-top:110px">
      <div class="kicker">Industrial vision · PatchCore re-implementation</div>
      <h1 style="margin-top:26px;max-width:1700px">It finds defects it has never seen.<br>
      <span class="teal">It was only ever shown good parts.</span></h1>
      <div style="margin-top:56px;display:flex;gap:48px;align-items:flex-end">
        <img src="{b64(hero)}" style="height:500px;border-radius:18px;border:2px solid #22304a">
        <div style="padding-bottom:10px">
          <div class="big">{mean[best][0]:.3f}</div>
          <div class="cap" style="font-size:28px">mean image AUROC<br>5 MVTec AD categories<br>({LABEL[best]})</div>
        </div>
      </div>{foot(1)}</section>""")
    # 2 problem
    s.append(f"""<section class="slide"><div class="kicker">The problem</div>
      <h2>Defects are rare, so labelled defect data barely exists.</h2>
      <div class="row" style="flex:0;margin-top:70px">
        <div class="card"><h3>Supervised models need examples</h3>
          <p>A classic detector needs many labelled images of every defect type before it works.
          On a good line, those images barely exist.</p></div>
        <div class="card"><h3>New defects appear</h3>
          <p>A new scratch, crack or contamination nobody labelled yet goes straight past a supervised model.</p></div>
        <div class="card"><h3>Manual inspection doesn't scale</h3>
          <p>Human inspectors get tired, disagree with each other, and can't watch every part at line speed.</p></div>
      </div>
      <p class="lead" style="margin-top:64px">What every line <i>does</i> have: thousands of photos of
      <span class="accent">good</span> parts.</p>{foot(2)}</section>""")
    # 3 trick + demo
    s.append(f"""<section class="slide"><div class="kicker">The trick</div>
      <h2>Learn what “normal” looks like. Flag everything else.</h2>
      <div class="row">
        <div style="flex:1.55" class="imgwrap"><img src="{b64(shot)}"></div>
        <div style="flex:1;display:flex;flex-direction:column;gap:26px">
          <div class="card" style="flex:0"><h3><span class="teal">①</span> Zero defect labels</h3>
            <p>Fitted only on {min(n_train)}–{max(n_train)} good images per product line.</p></div>
          <div class="card" style="flex:0"><h3><span class="teal">②</span> Shows <i>where</i></h3>
            <p>Pixel heatmap localises the defect for the operator.</p></div>
          <div class="card" style="flex:0"><h3><span class="teal">③</span> Pass / fail</h3>
            <p>Threshold set from held-out good parts, never from test data.</p></div>
        </div></div>{foot(3)}</section>""")
    # 4 pipeline
    pipe = f"""<div class="pipe">
        <div class="box"><div class="n">01</div><h3>Good images</h3><p>Only defect-free photos of the product. No annotation.</p></div>
        <div class="arrow">→</div>
        <div class="box hl"><div class="n">02</div><h3>Frozen backbone</h3><p>Mid-level CNN features (layer 2 + 3): local texture and shape, not ImageNet classes.</p></div>
        <div class="arrow">→</div>
        <div class="box"><div class="n">03</div><h3>Patch embeddings</h3><p>3×3 neighbourhood pooling, multi-scale concat: one vector per image patch.</p></div>
        <div class="arrow">→</div>
        <div class="box hl"><div class="n">04</div><h3>Coreset memory bank</h3><p>Greedy k-center sampling keeps 1–10% of patches while still covering “normal”.</p></div>
        <div class="arrow">→</div>
        <div class="box"><div class="n">05</div><h3>Nearest-neighbour score</h3><p>Distance to the closest normal patch gives the heatmap; its max is the image score.</p></div>
      </div>"""
    s.append(f"""<section class="slide"><div class="kicker">How it works · PatchCore (Roth et al., CVPR 2022)</div>
      <h2>Five steps, no training loop, no labels.</h2>{pipe}
      <p class="lead" style="margin-top:60px"><b style="color:#fff">For experts:</b> locally aware patch
      features from a pretrained backbone, a greedy-coreset memory bank, and max-of-patch kNN distance for the
      image score. Re-implemented from the paper in PyTorch + timm.</p>{foot(4)}</section>""")
    # 5 results / backbones
    rows_html = "".join(
        f"<tr><td>{LABEL[b]}</td><td>{mean[b][0]:.3f}</td><td>{mean[b][1]:.3f}</td></tr>"
        for b in ["wide_resnet50", "resnet18", "convnext_tiny", "dinov2_vits14"] if b in mean)
    s.append(f"""<section class="slide"><div class="kicker">Results · MVTec AD benchmark</div>
      <h2>Which backbone? I measured four.</h2>
      <div class="row">
        <div class="imgwrap" style="flex:1.75"><img src="{b64(FIG / 'backbone_comparison.png')}"></div>
        <div class="card" style="flex:0.75">
          <h3>Mean over 5 categories</h3>
          <table style="font-size:27px;width:100%;border-collapse:collapse;margin-top:10px;color:#e5e7eb">
            <tr style="color:#94a3b8;text-align:left"><th style="padding:8px 0">Backbone</th><th>Image</th><th>Pixel</th></tr>
            {rows_html}</table>
          <p class="cap" style="margin-top:22px">AUROC on the official test split. Same pipeline, only the
          feature extractor changes. Full ablations (layers, coreset) are in the repo.</p>
        </div></div>{foot(5)}</section>""")
    # 6 gallery
    s.append(f"""<section class="slide"><div class="kicker">Detections</div>
      <h2>Representative, not cherry-picked.</h2>
      <p class="lead" style="margin-top:14px;font-size:28px">Each column shows the defective test image with the
      <b>median</b> score for that category. Red outline = ground-truth defect.</p>
      <div class="row" style="margin-top:30px"><div class="imgwrap" style="flex:1">
      <img src="{b64(FIG / 'heatmap_gallery.png')}"></div></div>{foot(6)}</section>""")
    # 7 deployment
    s.append(f"""<section class="slide"><div class="kicker">Deployment</div>
      <h2>Runs on a normal CPU. A new product line takes minutes.</h2>
      <div class="row" style="flex:0;margin-top:56px">
        <div class="card"><div class="big">{cpu['median_ms']:.0f}<small> ms</small></div>
          <p class="cap">median CPU time per image, {cpu['threads']} threads ({LABEL[demo['backbone']]}, live demo model)</p></div>
        <div class="card"><div class="big">{fit_s:.0f}<small> s</small></div>
          <p class="cap">mean time to fit a new product line from good images (laptop RTX 3050)</p></div>
        <div class="card"><div class="big">{d_rec:.0%}</div>
          <p class="cap">of defects caught at a fixed threshold, with {d_fpr:.0%} false alarms on good parts
          (demo model, mean of 5 lines)</p></div>
      </div>
      <div class="row" style="margin-top:40px">
        <div class="imgwrap" style="flex:1.3"><img src="{b64(FIG / 'coreset_tradeoff.png')}"></div>
        <div class="card"><h3>Adding a new line</h3><p>1. Photograph good parts under production lighting<br>
          2. Fit the memory bank (no labels, no GPU training run)<br>3. Set threshold on held-out good parts<br>
          4. Deploy as an API, an edge box, or this app</p></div>
      </div>{foot(7)}</section>""")
    # 8 CTA
    s.append(f"""<section class="slide" style="justify-content:center">
      <div class="kicker">Try it</div>
      <h1 style="margin-top:22px;max-width:1300px">I can build this for <span class="teal">your</span> production line.</h1>
      <div style="display:flex;gap:64px;align-items:center;margin-top:64px">
        <img src="{b64(qr_img)}" style="width:300px;height:300px;border-radius:16px">
        <div style="font-size:34px;line-height:1.7;color:#cbd5e1">
          <div><b style="color:#fff">Live demo</b> · {demo_url}</div>
          <div><b style="color:#fff">Code + benchmark</b> · {repo_url}</div>
          <div style="margin-top:18px"><span class="tag">PyTorch</span><span class="tag">Anomaly detection</span>
          <span class="tag">Computer vision</span><span class="tag">Quality inspection</span><span class="tag">Edge deployment</span></div>
        </div></div>
      <p class="cap" style="margin-top:56px;font-size:24px">Priyanshu Singh · Freelance AI / ML Engineer · Demo trained on MVTec AD
      (non-commercial license); client systems are fitted on your own parts.</p>{foot(8)}</section>""")

    html = f"<!doctype html><html><head><meta charset='utf-8'><title>DefectScope deck</title><style>{CSS}</style></head><body>{''.join(s)}</body></html>"
    (OUT / "deck.html").write_text(html, encoding="utf-8")

    # standalone pipeline diagram
    diag = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS} body{{background:#0b1220}}</style></head><body><div style='width:1920px;padding:40px 60px 60px'>{pipe}</div></body></html>"

    from playwright.sync_api import sync_playwright
    (OUT / "slides").mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
        pg.set_content(html, wait_until="load")
        for i, el in enumerate(pg.query_selector_all("section.slide"), 1):
            el.screenshot(path=str(OUT / "slides" / f"slide_{i:02d}.png"))
        pg.pdf(path=str(OUT / "deck.pdf"), width="1920px", height="1080px", print_background=True)
        pg.set_content(diag, wait_until="load")
        pg.query_selector("div").screenshot(path=str(OUT / "diagram.png"))
        b.close()
    print("deck written:", sorted(x.name for x in (OUT / "slides").glob("*.png")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-url", default="https://defectscope.streamlit.app")
    ap.add_argument("--repo-url", default="https://github.com/Priyanshu-Singh-git/defectscope")
    a = ap.parse_args()
    build(a.demo_url, a.repo_url)
