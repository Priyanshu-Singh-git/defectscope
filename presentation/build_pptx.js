// Build deck.pptx (16:9, 13.333 x 7.5 in) from deck_data.json written by build_deck.py.
// Structured deck: light theme with warm accents, two layouts (cover, content), sections, speaker notes.
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const JSZip = require(require.resolve("jszip", { paths: [require.resolve("pptxgenjs")] }));

// pptxgenjs writes Office's stock palette into the theme; overwrite it with THEME's colors
// so scheme colors (and PowerPoint's own color picker) use the deck palette.
async function applyTheme(file, theme) {
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const part = "ppt/theme/theme1.xml";
  let xml = await zip.file(part).async("string");
  for (const [slot, hex] of Object.entries(theme.colors)) {
    if (!/^[0-9A-Fa-f]{6}$/.test(hex)) throw new Error(`theme color ${slot}=${hex} is not 6 hex digits`);
    xml = xml.replace(new RegExp("<a:" + slot + ">[\\s\\S]*?</a:" + slot + ">"), `<a:${slot}><a:srgbClr val="${hex}"/></a:${slot}>`);
  }
  xml = xml.replace(/<a:clrScheme name="[^"]*">/, `<a:clrScheme name="${theme.name}">`);
  zip.file(part, xml);
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
}

const D = JSON.parse(fs.readFileSync(path.join(__dirname, "deck_data.json"), "utf8"));

const THEME = {
  name: "DefectScope",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1F2937",   // headings (charcoal)
    lt1: "FFFFFF",   // slide background (white)
    dk2: "4B5563",   // body text
    lt2: "F6F5F4",   // card fill (soft light grey)
    accent1: "EA580C", // orange: the main accent
    accent2: "DC2626", // red: strong emphasis
    accent3: "F59E0B", // amber/yellow: fills only (too light for text on white)
    accent4: "B91C1C", // deep red: chart series 2
    accent5: "6B7280", // muted captions
    accent6: "E5E7EB", // card border / grid
    hlink: "EA580C",
    folHlink: "B91C1C",
  },
};
const H = THEME.colors; // hex-only options (chart grid lines etc.)

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.title = "DefectScope: label-free defect detection";
pres.author = "Priyanshu Singh";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, M = 0.6;

// ---------- image helpers ----------
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function fit(file, x, y, w, h) { // contain the image inside the box, centred
  const s = pngSize(file), r = Math.min(w / s.w, h / s.h);
  const iw = s.w * r, ih = s.h * r;
  return { path: file, x: x + (w - iw) / 2, y: y + (h - ih) / 2, w: iw, h: ih };
}

// ---------- layouts ----------
pres.defineSlideMaster({
  title: "COVER",
  background: { color: C.background1 },
  objects: [],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, M, 0.6, M],
  objects: [
    { placeholder: { options: { name: "kicker", type: "body", x: M, y: 0.42, w: 12.1, h: 0.4,
        fontFace: "Arial", fontSize: 13, bold: true, color: C.accent1, charSpacing: 2, margin: 0, valign: "middle" },
      text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: M, y: 0.82, w: 12.1, h: 0.95,
        fontFace: "Arial", fontSize: 34, bold: true, color: C.text1, margin: 0, valign: "top", align: "left" },
      text: "" } },
    { text: { text: "DefectScope · label-free defect detection",
        options: { x: M, y: 7.0, w: 8, h: 0.3, fontSize: 11, color: C.accent5, margin: 0 } } },
  ],
  slideNumber: { x: 12.1, y: 7.0, w: 0.63, h: 0.3, fontSize: 11, color: C.accent5, align: "right" },
});

function content(section, kicker, title) {
  const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
  s.addText(kicker.toUpperCase(), { placeholder: "kicker" });
  s.addText(title, { placeholder: "title" });
  return s;
}
function card(s, x, y, w, h, name) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.12,
    fill: { color: C.background2 }, line: { color: C.accent6, width: 1 }, objectName: name });
}
function numBadge(s, x, y, n, name) {
  s.addShape(pres.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: C.accent1 }, line: { type: "none" }, objectName: name });
  s.addText(String(n), { x, y, w: 0.5, h: 0.5, fontSize: 15, bold: true, color: C.background1, align: "center",
    valign: "middle", margin: 0, isTextBox: true });
}
const pct = (v) => `${Math.round(v * 100)}%`;
const f3 = (v) => v.toFixed(3);

// ================= 1. thumbnail cover =================
// Doubles as the Upwork portfolio thumbnail: product name huge, one USP line, one visual.
pres.addSection({ title: "Hook" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Hook" });
  const img = 5.4, ix = W - img - 0.5, iy = (7.5 - img) / 2;
  s.addImage({ path: D.assets.hero_heatmap, x: ix, y: iy, w: img, h: img, objectName: "Hero heatmap",
    altText: `Metal nut with a ${D.hero_defect} defect, heatmap glowing over the defect` });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ix + 0.25, y: iy + img - 0.8, w: 3.1, h: 0.5, rectRadius: 0.1,
    fill: { color: C.background1, transparency: 10 }, line: { type: "none" } });
  s.addText([{ text: "● ", options: { color: C.accent2 } }, { text: "Defect found here", options: { color: C.text1 } }],
    { x: ix + 0.25, y: iy + img - 0.8, w: 3.1, h: 0.5, fontSize: 16, bold: true, align: "center", valign: "middle",
      margin: 0, isTextBox: true });
  const tw = ix - M - 0.35;
  s.addText("AI VISUAL INSPECTION", { x: M, y: 1.2, w: tw, h: 0.45, fontFace: "Arial", fontSize: 18, bold: true,
    color: C.accent2, charSpacing: 3, margin: 0, isTextBox: true });
  s.addText("DefectScope", { x: M, y: 1.75, w: tw, h: 1.15, fontFace: "Arial", fontSize: 66, bold: true,
    color: C.text1, margin: 0, valign: "top", isTextBox: true, objectName: "Product name" });
  s.addText([
    { text: "Spots scratches and dents.", options: { color: C.text1, breakLine: true } },
    { text: "No defect photos needed.", options: { color: C.accent1 } },
  ], { x: M, y: 3.1, w: tw, h: 1.7, fontFace: "Arial", fontSize: 28, bold: true, margin: 0, valign: "top",
       isTextBox: true, objectName: "USP" });
  const chips = ["No defect labels", "Pixel heatmap", "Runs on CPU"];
  let cx = M;
  chips.forEach((t) => {
    const cw = 0.1 * t.length + 0.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 5.0, w: cw, h: 0.55, rectRadius: 0.27,
      fill: { color: C.background2 }, line: { color: C.accent1, width: 1.25 } });
    s.addText(t, { x: cx, y: 5.0, w: cw, h: 0.55, fontSize: 17, bold: true, color: C.text1,
      align: "center", valign: "middle", margin: 0, isTextBox: true });
    cx += cw + 0.15;
  });
  s.addNotes("0-10s: upload a defective part; the heatmap lights up exactly on the defect. " +
    "Say: it was never shown a single defect, only good parts.");
}

// ================= 2. problem =================
pres.addSection({ title: "Problem" });
{
  const s = content("Problem", "The problem", "Defects are rare, so labelled defect data barely exists.");
  const items = [
    ["Supervised models need examples", "A classic detector needs many labelled images of every defect type. On a good production line those images barely exist."],
    ["New defects appear", "A new scratch, crack or contamination that nobody labelled yet goes straight past a supervised model."],
    ["Manual inspection doesn't scale", "Inspectors get tired, disagree with each other, and can't check every part at line speed."],
  ];
  const cw = (12.13 - 2 * 0.35) / 3;
  items.forEach(([h, p], i) => {
    const x = M + i * (cw + 0.35), y = 2.2;
    card(s, x, y, cw, 3.15, `Problem card ${i + 1}`);
    numBadge(s, x + 0.35, y + 0.35, i + 1, `Badge ${i + 1}`);
    s.addText(h, { x: x + 0.35, y: y + 1.0, w: cw - 0.7, h: 0.75, fontFace: "Arial", fontSize: 18, bold: true,
      color: C.text1, margin: 0, valign: "top", isTextBox: true });
    s.addText(p, { x: x + 0.35, y: y + 1.85, w: cw - 0.7, h: 1.2, fontSize: 15, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
  });
  s.addText([
    { text: "What every line does have: ", options: { color: C.text2 } },
    { text: "plenty of photos of good parts.", options: { color: C.accent1, bold: true } },
  ], { x: M, y: 5.8, w: 12.1, h: 0.7, fontSize: 24, margin: 0, isTextBox: true });
  s.addNotes("Defects are rare by design, so you can't collect hundreds of labelled examples. " +
    "Flip the problem: learn what good looks like.");
}

// ================= 3. the trick + demo =================
pres.addSection({ title: "Solution" });
{
  const s = content("Solution", "The trick", "Learn what “normal” looks like. Flag everything else.");
  const box = { x: M, y: 1.95, w: 7.6, h: 4.85 };
  card(s, box.x, box.y, box.w, box.h, "Screenshot frame");
  s.addImage({ ...fit(D.assets.shot, box.x + 0.15, box.y + 0.15, box.w - 0.3, box.h - 0.3),
    objectName: "Demo screenshot", altText: "DefectScope web app flagging a defect with a heatmap" });
  const pts = [
    ["Zero defect labels", `Fitted only on ${D.n_train_min}–${D.n_train_max} good images per product line.`],
    ["Shows where", "A pixel heatmap points the operator to the defect."],
    ["Pass / fail", "Threshold set from held-out good parts, never from test data."],
  ];
  const x = M + box.w + 0.35, w = W - M - x;
  pts.forEach(([h, p], i) => {
    const y = 1.95 + i * 1.7;
    card(s, x, y, w, 1.45, `Point ${i + 1}`);
    numBadge(s, x + 0.25, y + 0.25, i + 1, `Point badge ${i + 1}`);
    s.addText(h, { x: x + 0.95, y: y + 0.22, w: w - 1.15, h: 0.45, fontFace: "Arial", fontSize: 17, bold: true,
      color: C.text1, margin: 0, isTextBox: true });
    s.addText(p, { x: x + 0.95, y: y + 0.68, w: w - 1.15, h: 0.65, fontSize: 13.5, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
  });
  s.addNotes("Show the live demo: pick a product line, choose a sample, and the verdict plus heatmap appear in about a second.");
}

// ================= 4. pipeline =================
{
  const s = content("Solution", "How it works · PatchCore (Roth et al., CVPR 2022)", "Five steps, no training loop, no labels.");
  const steps = [
    ["Good images", "Defect-free photos only. No annotation."],
    ["Frozen backbone", "Mid-level CNN features (layers 2 + 3): texture and shape, not ImageNet classes."],
    ["Patch embeddings", "3×3 neighbourhood pooling, multi-scale concat: one vector per image patch."],
    ["Coreset memory", "Greedy k-center sampling keeps 1–10% of patches while still covering “normal”."],
    ["kNN anomaly score", "Distance to the closest normal patch gives the heatmap; its max is the image score."],
  ];
  const gap = 0.32, bw = (12.13 - 4 * gap) / 5, y = 2.25, bh = 3.0;
  steps.forEach(([h, p], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, rectRadius: 0.12,
      fill: { color: C.background2 }, line: { color: (i === 1 || i === 3) ? C.accent1 : C.accent6, width: (i === 1 || i === 3) ? 2 : 1 },
      objectName: `Step ${i + 1}` });
    s.addText(`0${i + 1}`, { x: x + 0.25, y: y + 0.25, w: 1, h: 0.35, fontSize: 14, bold: true, color: C.accent1,
      margin: 0, isTextBox: true });
    s.addText(h, { x: x + 0.25, y: y + 0.65, w: bw - 0.5, h: 0.75, fontFace: "Arial", fontSize: 16.5, bold: true,
      color: C.text1, margin: 0, valign: "top", isTextBox: true });
    s.addText(p, { x: x + 0.25, y: y + 1.5, w: bw - 0.5, h: 1.4, fontSize: 13, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
    if (i < 4) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + bw + 0.05, y: y + bh / 2 - 0.12, w: gap - 0.1, h: 0.24,
      fill: { color: C.accent1 }, line: { type: "none" } });
  });
  s.addText([
    { text: "For experts: ", options: { bold: true, color: C.text1 } },
    { text: "locally aware patch features from a frozen pretrained backbone, a greedy-coreset memory bank, and max-of-patch kNN distance as the image score. Re-implemented from the paper in PyTorch + timm.",
      options: { color: C.text2 } },
  ], { x: M, y: 5.65, w: 12.1, h: 0.9, fontSize: 15, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Technical peek. Key point for clients: nothing is trained, so a new product line needs only good photos and minutes of compute.");
}

// ================= 5. results: backbone comparison (native chart) =================
pres.addSection({ title: "Results" });
{
  const s = content("Results", "Results · MVTec AD benchmark", "Which backbone? I measured four.");
  const labels = D.backbones.map((b) => b.label);
  const lo = Math.min(...D.backbones.flatMap((b) => [b.image, b.pixel]));
  const minV = Math.max(0, Math.floor((lo - 0.01) * 50) / 50);
  card(s, M, 1.95, 7.9, 4.85, "Chart frame");
  s.addChart(pres.charts.BAR, [
    { name: "Image AUROC", labels, values: D.backbones.map((b) => +b.image.toFixed(3)) },
    { name: "Pixel AUROC", labels, values: D.backbones.map((b) => +b.pixel.toFixed(3)) },
  ], {
    x: M + 0.15, y: 2.05, w: 7.6, h: 4.65, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: [H.accent1, H.accent4], valAxisMinVal: minV, valAxisMaxVal: 1.0, valAxisLabelFormatCode: "0.00",
    valAxisMajorUnit: 0.02,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", dataLabelFontSize: 10,
    dataLabelColor: H.dk2, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: H.dk2, valAxisLabelColor: H.accent5, catAxisLabelFontSize: 12, valAxisLabelFontSize: 10,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: H.accent6, size: 0.75 }, catGridLine: { style: "none" },
    catAxisLineShow: false, valAxisLineShow: false,
    showLegend: true, legendPos: "t", legendColor: H.dk2, legendFontSize: 12, legendFontFace: "+mn-lt",
    showTitle: true, title: "Mean AUROC over 5 categories (higher is better)", titleColor: H.dk1,
    titleFontSize: 14, titleFontFace: "+mn-lt",
    objectName: "Backbone comparison chart",
  });
  const x = M + 8.25, w = W - M - x;
  card(s, x, 1.95, w, 4.85, "Takeaway card");
  s.addText("Best overall", { x: x + 0.3, y: 2.2, w: w - 0.6, h: 0.4, fontSize: 14, color: C.accent5, margin: 0, isTextBox: true });
  s.addText(D.best.label, { x: x + 0.3, y: 2.55, w: w - 0.6, h: 0.55, fontFace: "Arial", fontSize: 24, bold: true,
    color: C.text1, margin: 0, isTextBox: true });
  s.addText([
    { text: `${f3(D.best.image)}`, options: { bold: true, color: C.accent1 } },
    { text: " image AUROC", options: { color: C.text2, breakLine: true } },
    { text: `${f3(D.best.pixel)}`, options: { bold: true, color: C.accent1 } },
    { text: " pixel AUROC", options: { color: C.text2 } },
  ], { x: x + 0.3, y: 3.2, w: w - 0.6, h: 0.9, fontSize: 18, margin: 0, isTextBox: true });
  s.addText("Same pipeline, only the feature extractor changes. Official MVTec AD test split: bottle, screw, carpet, metal nut, transistor. Layer and coreset ablations are in the repo.",
    { x: x + 0.3, y: 4.35, w: w - 0.6, h: 2.2, fontSize: 13.5, color: C.text2, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("One number that proves it works: read the best backbone's image AUROC. Mention you benchmarked CNNs, ConvNeXt and a DINOv2 ViT, not just one model.");
}

// ================= 6. gallery =================
{
  const s = content("Results", "Detections", "Representative, not cherry-picked.");
  s.addText("For each category: the defective test image with the median score. Red outline = ground-truth defect.",
    { x: M, y: 1.65, w: 12.1, h: 0.4, fontSize: 14, color: C.text2, margin: 0, isTextBox: true });
  const box = { x: M, y: 2.2, w: 12.13, h: 4.6 };
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { ...box, rectRadius: 0.12, fill: { color: C.background2 }, line: { color: C.accent6, width: 1 },
    objectName: "Gallery frame" });
  s.addImage({ ...fit(D.assets.gallery, box.x + 0.15, box.y + 0.1, box.w - 0.3, box.h - 0.2),
    objectName: "Heatmap gallery", altText: "Input images with true defect outlines above PatchCore heatmaps" });
  s.addNotes("Run three categories live: screw, bottle, carpet. Then show a good part scoring low.");
}

// ================= 7. deployment =================
pres.addSection({ title: "Deployment" });
{
  const s = content("Deployment", "Deployment", "Runs on a CPU. A new product line takes minutes.");
  const stats = [
    [`${Math.round(D.cpu.median_ms)} ms`, `median CPU time per image (${D.cpu.threads} threads, ${D.demo.backbone}, live demo model)`],
    [`${Math.round(D.fit_s)} s`, "mean time to fit a new product line from good images (laptop RTX 3050)"],
    [pct(D.demo.recall), `of defects caught at a fixed threshold, with ${pct(D.demo.fpr)} false alarms on good parts (demo model, mean of 5 lines)`],
  ];
  const cw = (12.13 - 2 * 0.35) / 3;
  stats.forEach(([v, c], i) => {
    const x = M + i * (cw + 0.35), y = 1.95;
    card(s, x, y, cw, 2.0, `Stat ${i + 1}`);
    s.addText(v, { x: x + 0.3, y: y + 0.2, w: cw - 0.6, h: 0.85, fontFace: "Arial", fontSize: 40, bold: true,
      color: C.accent1, margin: 0, isTextBox: true });
    s.addText(c, { x: x + 0.3, y: y + 1.05, w: cw - 0.6, h: 0.85, fontSize: 12.5, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
  });
  // coreset trade-off table (native)
  const hdr = ["Backbone", "Coreset", "Image AUROC", "Pixel AUROC", "Bank (MB)"].map((t) => ({ text: t,
    options: { bold: true, color: C.accent1, fill: { color: C.background2 } } }));
  const rows = D.coreset.map((r) => [r.backbone, pct(r.ratio), f3(r.image), f3(r.pixel), r.bank_mb.toFixed(1)]
    .map((t) => ({ text: t, options: { color: C.text2, fill: { color: C.background1 } } })));
  s.addText("Coreset size: accuracy vs memory", { x: M, y: 4.2, w: 7, h: 0.4, fontFace: "Arial", fontSize: 15, bold: true,
    color: C.text1, margin: 0, isTextBox: true });
  s.addTable([hdr, ...rows], { x: M, y: 4.65, w: 7.4, colW: [1.9, 1.1, 1.5, 1.5, 1.4], fontSize: 12,
    fontFace: "Calibri", border: { type: "solid", pt: 0.75, color: H.accent6 }, rowH: 0.3, margin: 0.05,
    objectName: "Coreset table" });
  const x = M + 7.75, w = W - M - x;
  card(s, x, 4.2, w, 2.6, "New line card");
  s.addText("Adding a new product line", { x: x + 0.3, y: 4.38, w: w - 0.6, h: 0.4, fontFace: "Arial", fontSize: 15,
    bold: true, color: C.text1, margin: 0, isTextBox: true });
  s.addText([
    { text: "Photograph good parts under production lighting", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Fit the memory bank (no labels, no training run)", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Set the threshold on held-out good parts", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Ship as an API, an edge box, or this app", options: { bullet: { type: "number" } } },
  ], { x: x + 0.3, y: 4.85, w: w - 0.6, h: 1.8, fontSize: 13.5, color: C.text2, margin: 0,
       paraSpaceAfter: 6, valign: "top", isTextBox: true });
  s.addNotes("Deployment notes: CPU speed, and how fast a new product line can be added.");
}

// ================= 8. CTA =================
pres.addSection({ title: "Call to action" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Call to action" });
  s.addText("TRY IT", { x: M, y: 0.9, w: 6, h: 0.4, fontFace: "Arial", fontSize: 14, bold: true, color: C.accent1,
    charSpacing: 2, margin: 0, isTextBox: true });
  s.addText([
    { text: "I can build this for ", options: { color: C.text1 } },
    { text: "your", options: { color: C.accent1 } },
    { text: " production line.", options: { color: C.text1 } },
  ], { x: M, y: 1.35, w: 12.1, h: 1.7, fontFace: "Arial", fontSize: 44, bold: true, margin: 0, valign: "top",
       isTextBox: true, objectName: "CTA headline" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 3.4, w: 2.9, h: 2.9, rectRadius: 0.12, fill: { color: "FFFFFF" },
    line: { type: "none" } });
  s.addImage({ path: D.assets.qr, x: M + 0.15, y: 3.55, w: 2.6, h: 2.6, objectName: "QR code",
    altText: "QR code to the live demo" });
  const x = M + 3.4;
  s.addText([
    { text: "Live demo", options: { bold: true, color: C.text1, breakLine: true } },
    { text: D.demo_url, options: { color: C.accent1, hyperlink: { url: D.demo_url }, breakLine: true } },
    { text: " ", options: { fontSize: 8, breakLine: true } },
    { text: "Code + benchmark", options: { bold: true, color: C.text1, breakLine: true } },
    { text: D.repo_url, options: { color: C.accent1, hyperlink: { url: D.repo_url } } },
  ], { x, y: 3.45, w: 8.6, h: 1.9, fontSize: 20, margin: 0, valign: "top", isTextBox: true });
  const tags = ["PyTorch", "Anomaly detection", "Computer vision", "Quality inspection", "Edge deployment"];
  let tx = x, ty = 5.35;
  tags.forEach((t) => {
    const tw = 0.085 * t.length + 0.5;
    if (tx + tw > W - M) { tx = x; ty += 0.55; }
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: tx, y: ty, w: tw, h: 0.42, rectRadius: 0.2,
      fill: { color: C.background2 }, line: { color: C.accent1, width: 1 } });
    s.addText(t, { x: tx, y: ty, w: tw, h: 0.42, fontSize: 13, color: C.text1, align: "center",
      valign: "middle", margin: 0, isTextBox: true });
    tx += tw + 0.15;
  });
  s.addText("Priyanshu Singh · Freelance AI / ML Engineer · Demo fitted on MVTec AD (non-commercial license); client systems are fitted on your own parts.",
    { x: M, y: 6.75, w: 12.1, h: 0.4, fontSize: 12, color: C.accent5, margin: 0, isTextBox: true });
  s.addNotes("The live demo is linked. If you want this built into your production line, message me.");
}

(async () => {
  const out = path.join(__dirname, "deck.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
