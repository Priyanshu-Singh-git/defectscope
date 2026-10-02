// DefectScope browser demo: PatchCore scoring with ONNX Runtime Web, entirely client-side.
const MEAN = [0.485, 0.456, 0.406], STD = [0.229, 0.224, 0.225];
const $ = (id) => document.getElementById(id);
ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.2/dist/";

const state = { meta: null, session: null, banks: {}, product: null, results: {} };
window.defectscope = state; // exposed for automated checks

// ---- preprocessing: resize shorter side to 256, centre-crop 224, ImageNet-normalise ----
function preprocess(img) {
  const { resize, input } = state.meta;
  const s = resize / Math.min(img.naturalWidth, img.naturalHeight);
  const w = Math.round(img.naturalWidth * s), h = Math.round(img.naturalHeight * s);
  const big = document.createElement("canvas");
  big.width = w; big.height = h;
  const bctx = big.getContext("2d");
  bctx.imageSmoothingQuality = "high";
  bctx.drawImage(img, 0, 0, w, h);
  const crop = bctx.getImageData(Math.round((w - input) / 2), Math.round((h - input) / 2), input, input);
  const n = input * input, data = new Float32Array(3 * n);
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < 3; c++) data[c * n + i] = (crop.data[i * 4 + c] / 255 - MEAN[c]) / STD[c];
  }
  return { tensor: new ort.Tensor("float32", data, [1, 3, input, input]), crop };
}

// ---- heatmap: jet colour of score/threshold, shown only where clearly abnormal ----
function jet(t) {
  const r = Math.min(Math.max(1.5 - Math.abs(4 * t - 3), 0), 1);
  const g = Math.min(Math.max(1.5 - Math.abs(4 * t - 2), 0), 1);
  const b = Math.min(Math.max(1.5 - Math.abs(4 * t - 1), 0), 1);
  return [r * 255, g * 255, b * 255];
}
function drawResult(crop, patch, dims, thr) {
  const [gh, gw] = dims;
  const small = document.createElement("canvas");
  small.width = gw; small.height = gh;
  const sctx = small.getContext("2d");
  const im = sctx.createImageData(gw, gh);
  for (let i = 0; i < gh * gw; i++) {
    const r = patch[i] / thr;
    const [R, G, B] = jet(Math.min(Math.max((r - 0.7) / 0.6, 0), 1));
    const a = Math.min(Math.max((r - 0.75) / 0.35, 0), 1) * 0.65;
    im.data.set([R, G, B, a * 255], i * 4);
  }
  sctx.putImageData(im, 0, 0);
  for (const id of ["cIn", "cHeat"]) {
    const cv = $(id), ctx = cv.getContext("2d");
    const tmp = document.createElement("canvas");
    tmp.width = crop.width; tmp.height = crop.height;
    tmp.getContext("2d").putImageData(crop, 0, 0);
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(tmp, 0, 0, cv.width, cv.height);
    if (id === "cHeat") {
      ctx.save();
      ctx.filter = "blur(10px)";
      ctx.imageSmoothingEnabled = true;
      ctx.drawImage(small, 0, 0, cv.width, cv.height);
      ctx.restore();
    }
  }
}

async function loadBank(p) {
  if (!state.banks[p.key]) {
    const buf = await (await fetch(p.bank)).arrayBuffer();
    state.banks[p.key] = new ort.Tensor("float32", new Float32Array(buf), [p.n, p.dim]);
  }
  return state.banks[p.key];
}

async function analyse(img, sample) {
  const p = state.product;
  $("badge").className = "badge wait"; $("badge").textContent = "Checking…";
  try {
    const bank = await loadBank(p);
    const t0 = performance.now();
    const { tensor, crop } = preprocess(img);
    const out = await state.session.run({ image: tensor, bank });
    const ms = performance.now() - t0;
    const patch = out.patch_scores.data, score = out.score.data[0];
    drawResult(crop, patch, state.meta.grid, p.threshold);
    const ratio = score / p.threshold, defect = ratio > 1;
    $("badge").className = "badge " + (defect ? "defect" : "pass");
    $("badge").textContent = defect ? "⚠ DEFECT" : "✓ PASS";
    $("ratio").textContent = `Anomaly score ${ratio.toFixed(2)}× the pass/fail threshold (above 1.00× = defect)`;
    $("barFill").style.width = Math.min(ratio / 2, 1) * 100 + "%";
    $("timing").textContent = `${Math.round(ms)} ms in your browser`;
    if (sample) state.results[sample.file] = { score, py_score: sample.py_score, ms, defect };
  } catch (e) {
    $("badge").className = "badge wait";
    $("badge").innerHTML = `<span class="err">Error: ${e.message}</span>`;
    console.error(e);
  }
}

function loadImage(src) {
  return new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = src; });
}

function selectProduct(key, sampleLabel) {
  state.product = state.meta.products.find((p) => p.key === key) || state.meta.products[0];
  $("product").value = state.product.key;
  const box = $("thumbs"); box.innerHTML = "";
  state.product.samples.forEach((s, i) => {
    const b = document.createElement("button");
    b.className = "thumb"; b.type = "button";
    b.innerHTML = `<img src="${s.file}" alt="${s.label}">${s.label}`;
    b.onclick = async () => {
      box.querySelectorAll(".thumb").forEach((t) => t.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      await analyse(await loadImage(s.file), s);
    };
    box.appendChild(b);
  });
  const pick = state.product.samples.findIndex((s) => sampleLabel && s.label.startsWith(sampleLabel));
  const def = pick >= 0 ? pick : state.product.samples.findIndex((s) => s.label !== "good");
  box.children[Math.max(def, 0)].click();
}

async function main() {
  state.meta = await (await fetch("meta.json")).json();
  const sel = $("product");
  for (const p of state.meta.products) sel.add(new Option(p.name, p.key));
  $("stats").innerHTML = state.meta.products.map((p) => {
    const t = p.test, bad = t.test_defective, good = t.test_n - t.test_defective;
    return `<tr><td>${p.name}</td><td class="num">${Math.round(t.recall_defects * 100)}% (${Math.round(t.recall_defects * bad)} of ${bad})</td>` +
           `<td class="num">${Math.round(t.false_positive_rate * 100)}% (${Math.round(t.false_positive_rate * good)} of ${good})</td></tr>`;
  }).join("");
  state.session = await ort.InferenceSession.create("models/" + state.meta.model, { executionProviders: ["wasm"] });
  sel.onchange = () => selectProduct(sel.value);
  $("file").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > 15e6) { $("badge").textContent = "Image too large (max 15 MB)"; return; }
    $("thumbs").querySelectorAll(".thumb").forEach((t) => t.setAttribute("aria-pressed", "false"));
    await analyse(await loadImage(URL.createObjectURL(f)), null);
  };
  const q = new URLSearchParams(location.search);
  selectProduct(q.get("product") || state.meta.products[0].key, q.get("sample"));
}
main().catch((e) => { $("badge").innerHTML = `<span class="err">Failed to load: ${e.message}</span>`; });
