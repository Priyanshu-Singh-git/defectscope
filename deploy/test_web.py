"""Click every sample of every product in the browser demo (Edge, via Playwright) and compare
browser scores/verdicts with the PyTorch scores stored in meta.json. Writes eval/browser_check.json.

  python -m http.server 8600 --directory docs   # in another shell
  python deploy/test_web.py http://127.0.0.1:8600/
"""
import json, sys
from playwright.sync_api import sync_playwright
url = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1280, "height": 1000})
    logs = []
    pg.on("console", lambda m: logs.append(m.text) if m.type == "error" else None)
    pg.goto(url, wait_until="networkidle")
    pg.wait_for_function("window.defectscope && Object.keys(window.defectscope.results).length > 0", timeout=120000)
    products = pg.evaluate("window.defectscope.meta.products.map(p => [p.key, p.samples.length])")
    for key, n in products:
        pg.select_option("#product", key)
        pg.wait_for_timeout(800)
        for i in range(n):
            pg.locator("#thumbs .thumb").nth(i).click()
            pg.wait_for_function("document.getElementById('badge').textContent.match(/PASS|DEFECT|Error/)")
            pg.wait_for_timeout(200)
    res = pg.evaluate("window.defectscope.results")
    thr = {pk: t for pk, t in pg.evaluate("window.defectscope.meta.products.map(p => [p.key, p.threshold])")}
    worst, flips, ms = 0, 0, []
    for f, r in res.items():
        k = f.split("/")[1].rsplit("_", 1)[0]
        key = next(pk for pk in thr if f.startswith(f"samples/{pk}_"))
        rel = abs(r["score"] - r["py_score"]) / r["py_score"]
        worst = max(worst, rel); ms.append(r["ms"])
        flips += (r["score"] > thr[key]) != (r["py_score"] > thr[key])
        print(f"{f:45s} browser={r['score']:.3f} python={r['py_score']:.3f} diff={rel:.1%} {'DEFECT' if r['defect'] else 'PASS'}")
    ms.sort()
    print(f"samples={len(res)} max_score_diff={worst:.1%} verdict_flips={flips} median_ms={ms[len(ms)//2]:.0f} errors={logs[:3]}")
    from pathlib import Path
    Path(__file__).resolve().parents[1].joinpath("eval", "browser_check.json").write_text(json.dumps({
        "browser": "Microsoft Edge (Playwright), ONNX Runtime Web wasm", "samples": len(res),
        "max_score_rel_diff": worst, "verdict_flips": flips, "median_ms": ms[len(ms) // 2],
        "note": "ms includes preprocessing + ONNX inference, first run of each product includes warm-up"}, indent=2))
    b.close()
