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
    { text: { text: "DefectScope · AI visual inspection",
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

// ================= 2. problem (business wording) =================
pres.addSection({ title: "Problem" });
{
  const s = content("Problem", "The problem", "Rare defects make AI inspection hard.");
  const items = [
    ["Normal AI needs defect photos", "A standard AI model must see hundreds of examples of every defect type. A good production line simply doesn't have them."],
    ["New defects slip through", "A scratch, crack or contamination nobody planned for goes straight past a model that was never shown it."],
    ["Manual checks don't scale", "People get tired, disagree with each other, and can't check every part at line speed."],
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
    { text: "What you do have: photos of good parts. ", options: { color: C.text2 } },
    { text: "That's all DefectScope needs.", options: { color: C.accent1, bold: true } },
  ], { x: M, y: 5.8, w: 12.1, h: 0.7, fontSize: 24, margin: 0, isTextBox: true });
  s.addNotes("Defects are rare by design, so you can't collect hundreds of labelled examples. Flip the problem: learn what good looks like.");
}

// ================= 3. live demo =================
pres.addSection({ title: "Solution" });
{
  const s = content("Solution", "Try it yourself", "Upload a photo. See pass/fail and where.");
  const box = { x: M, y: 1.95, w: 7.6, h: 4.85 };
  card(s, box.x, box.y, box.w, box.h, "Screenshot frame");
  s.addImage({ ...fit(D.assets.shot, box.x + 0.15, box.y + 0.15, box.w - 0.3, box.h - 0.3),
    objectName: "Demo screenshot", altText: "DefectScope web app flagging a defect with a heatmap" });
  const pts = [
    ["Set up from good parts only", `Each product line was set up from ${D.n_train_min}–${D.n_train_max} photos of good parts. No defect photos, no labelling.`],
    ["Shows the operator where", "A heatmap marks the exact spot, so people can check it in seconds."],
    ["A pass/fail line you can trust", "The reject threshold is set on good parts the model never saw, not tuned on the test set."],
  ];
  const x = M + box.w + 0.35, w = W - M - x;
  pts.forEach(([h, p], i) => {
    const y = 1.95 + i * 1.7;
    card(s, x, y, w, 1.45, `Point ${i + 1}`);
    numBadge(s, x + 0.25, y + 0.25, i + 1, `Point badge ${i + 1}`);
    s.addText(h, { x: x + 0.95, y: y + 0.2, w: w - 1.15, h: 0.45, fontFace: "Arial", fontSize: 16, bold: true,
      color: C.text1, margin: 0, isTextBox: true });
    s.addText(p, { x: x + 0.95, y: y + 0.65, w: w - 1.15, h: 0.72, fontSize: 13, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
  });
  s.addNotes("Live demo: pick a product line, choose a sample or upload a photo; verdict and heatmap appear in about a second.");
}

// ================= 4. results in plain numbers =================
pres.addSection({ title: "Results" });
{
  const s = content("Results", "Results in plain numbers", "What it caught, what it wrongly rejected, how fast.");
  const ppm = (Math.round(60000 / D.cpu.median_ms / 100) * 100).toLocaleString("en-US");
  const stats = [
    [pct(D.demo.recall), "of defective parts caught", "average over 5 product types"],
    [pct(D.demo.fpr), "of good parts wrongly rejected", "the false alarms that cost you money"],
    [`${Math.round(D.cpu.median_ms)} ms`, `per part on a normal CPU (≈${ppm} parts/min)`, `${D.cpu.threads} CPU threads, no GPU`],
  ];
  const cw = (12.13 - 2 * 0.35) / 3;
  stats.forEach(([v, c1, c2], i) => {
    const x = M + i * (cw + 0.35), y = 1.95;
    card(s, x, y, cw, 1.95, `Stat ${i + 1}`);
    s.addText(v, { x: x + 0.3, y: y + 0.2, w: cw - 0.6, h: 0.85, fontFace: "Arial", fontSize: 42, bold: true,
      color: C.accent1, margin: 0, isTextBox: true });
    s.addText([{ text: c1, options: { bold: true, color: C.text1, breakLine: true } },
               { text: c2, options: { color: C.accent5 } }],
      { x: x + 0.3, y: y + 1.08, w: cw - 0.6, h: 0.75, fontSize: 13.5, margin: 0, valign: "top", isTextBox: true });
  });
  const hdr = ["Product", "Defective parts caught", "Good parts wrongly rejected"].map((t) => ({ text: t,
    options: { bold: true, color: C.accent1, fill: { color: C.background2 } } }));
  const rows = D.per_product.map((r) => [r.name,
    `${pct(r.recall)}  (${Math.round(r.recall * r.n_bad)} of ${r.n_bad})`,
    `${pct(r.fpr)}  (${Math.round(r.fpr * r.n_good)} of ${r.n_good})`]
    .map((t) => ({ text: t, options: { color: C.text2, fill: { color: C.background1 } } })));
  s.addTable([hdr, ...rows], { x: M, y: 4.2, w: 7.9, colW: [1.9, 3.0, 3.0], fontSize: 13, fontFace: "Calibri",
    border: { type: "solid", pt: 0.75, color: H.accent6 }, rowH: 0.34, margin: 0.06, objectName: "Per-product table" });
  const x = M + 8.25, w = W - M - x;
  card(s, x, 4.2, w, 2.6, "Honesty note");
  s.addText("How this was measured", { x: x + 0.3, y: 4.4, w: w - 0.6, h: 0.4, fontFace: "Arial", fontSize: 15,
    bold: true, color: C.text1, margin: 0, isTextBox: true });
  s.addText("Public MVTec AD test images the model never saw, with one fixed pass/fail threshold per product. " +
    "On your parts, the feasibility step measures these same numbers before you commit.",
    { x: x + 0.3, y: 4.85, w: w - 0.6, h: 1.8, fontSize: 13, color: C.text2, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("One number that proves it works: read the defects-caught and false-alarm numbers.");
}

// ================= 5. how it works (simple) =================
{
  const s = content("Results", "How it works", "Three steps. No labelling project.");
  const steps = [
    ["Photos of good parts", "A few hundred photos of normal parts, taken at the line."],
    ["It learns “normal”", "A pretrained vision network memorises what every small patch of a good part looks like."],
    ["It flags anything else", "Any patch that doesn't match normal is marked on a heatmap. Too far from normal means reject."],
  ];
  const gap = 0.55, bw = (12.13 - 2 * gap) / 3, y = 2.25, bh = 2.9;
  steps.forEach(([h, p], i) => {
    const x = M + i * (bw + gap);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: bw, h: bh, rectRadius: 0.12,
      fill: { color: C.background2 }, line: { color: i === 2 ? C.accent1 : C.accent6, width: i === 2 ? 2 : 1 },
      objectName: `Step ${i + 1}` });
    numBadge(s, x + 0.3, y + 0.3, i + 1, `Step badge ${i + 1}`);
    s.addText(h, { x: x + 0.3, y: y + 1.0, w: bw - 0.6, h: 0.5, fontFace: "Arial", fontSize: 20, bold: true,
      color: C.text1, margin: 0, isTextBox: true });
    s.addText(p, { x: x + 0.3, y: y + 1.6, w: bw - 0.6, h: 1.2, fontSize: 15, color: C.text2,
      margin: 0, valign: "top", isTextBox: true });
    if (i < 2) s.addShape(pres.shapes.RIGHT_ARROW, { x: x + bw + 0.12, y: y + bh / 2 - 0.15, w: gap - 0.24, h: 0.3,
      fill: { color: C.accent1 }, line: { type: "none" } });
  });
  s.addText([
    { text: "For engineers: ", options: { bold: true, color: C.text1 } },
    { text: "a from-scratch re-implementation of PatchCore (Roth et al., CVPR 2022) in PyTorch: mid-level features from a frozen backbone, a greedy-coreset memory bank, and nearest-neighbour patch scoring. Benchmarks are in the appendix.",
      options: { color: C.text2 } },
  ], { x: M, y: 5.6, w: 12.1, h: 0.9, fontSize: 14, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("Technical peek, kept simple. Key point for clients: nothing to label; a new product needs only good photos.");
}

// ================= 6. gallery =================
{
  const s = content("Results", "Real detections", "Representative, not cherry-picked.");
  s.addText("Per product: the defective test photo with the median score. Red outline = where the real defect is.",
    { x: M, y: 1.65, w: 12.1, h: 0.4, fontSize: 14, color: C.text2, margin: 0, isTextBox: true });
  const box = { x: M, y: 2.2, w: 12.13, h: 4.6 };
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { ...box, rectRadius: 0.12, fill: { color: "FCFCFB" },
    line: { color: C.accent6, width: 1 }, objectName: "Gallery frame" });
  s.addImage({ ...fit(D.assets.gallery, box.x + 0.15, box.y + 0.1, box.w - 0.3, box.h - 0.2),
    objectName: "Heatmap gallery", altText: "Input images with true defect outlines above heatmaps" });
  s.addNotes("Run three products live: screw, bottle, carpet. Then show a good part passing.");
}

// ================= 7. how we'd work together =================
pres.addSection({ title: "Working together" });
{
  const s = content("Working together", "How we'd work together", "Start small. See it work on your parts first.");
  const steps = [
    ["Send photos", `A few hundred photos of good parts from your line (this demo used ${D.n_train_min}–${D.n_train_max}), plus any defective ones you have.`],
    ["Feasibility report", "I set it up on your parts and report the real numbers: defects caught, false rejects, speed."],
    ["Deploy at the line", "Runs on a PC or edge box next to your camera, with a pass/fail signal your line can act on."],
  ];
  const cw = (12.13 - 2 * 0.35) / 3;
  steps.forEach(([h, p], i) => {
    const x = M + i * (cw + 0.35), y = 2.2;
    card(s, x, y, cw, 2.75, `Work step ${i + 1}`);
    s.addText(`STEP ${i + 1}`, { x: x + 0.35, y: y + 0.3, w: 2, h: 0.35, fontSize: 13, bold: true, color: C.accent1,
      charSpacing: 2, margin: 0, isTextBox: true });
    s.addText(h, { x: x + 0.35, y: y + 0.7, w: cw - 0.7, h: 0.5, fontFace: "Arial", fontSize: 20, bold: true,
      color: C.text1, margin: 0, isTextBox: true });
    s.addText(p, { x: x + 0.35, y: y + 1.3, w: cw - 0.7, h: 1.35, fontSize: 15, color: C.text2, margin: 0,
      valign: "top", isTextBox: true });
  });
  card(s, M, 5.25, 12.13, 1.45, "What you get");
  s.addText([
    { text: "What you get:  ", options: { bold: true, color: C.text1 } },
    { text: "the trained inspector for your product · an operator app or API · source code you own · setup docs so your team can add new products themselves.",
      options: { color: C.text2 } },
  ], { x: M + 0.35, y: 5.4, w: 11.4, h: 1.15, fontSize: 16, margin: 0, valign: "middle", isTextBox: true });
  s.addNotes("Lower the client's risk: a small first step on their own parts before any big commitment.");
}

// ================= 8. CTA =================
pres.addSection({ title: "Call to action" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Call to action" });
  s.addText("NEXT STEP", { x: M, y: 0.9, w: 6, h: 0.4, fontFace: "Arial", fontSize: 14, bold: true, color: C.accent2,
    charSpacing: 2, margin: 0, isTextBox: true });
  s.addText([
    { text: "Send me photos of your parts.", options: { color: C.text1, breakLine: true } },
    { text: "I'll show you if it works.", options: { color: C.accent1 } },
  ], { x: M, y: 1.35, w: 12.1, h: 1.9, fontFace: "Arial", fontSize: 42, bold: true, margin: 0, valign: "top",
       isTextBox: true, objectName: "CTA headline" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 3.55, w: 2.9, h: 2.9, rectRadius: 0.12, fill: { color: "FFFFFF" },
    line: { color: C.accent6, width: 1 } });
  s.addImage({ path: D.assets.qr, x: M + 0.15, y: 3.7, w: 2.6, h: 2.6, objectName: "QR code",
    altText: "QR code to the live demo" });
  const x = M + 3.4;
  const links = [["Try the live demo", D.demo_url]];
  if (D.video_url) links.push(["Watch the 75-second walkthrough", D.video_url]);
  links.push(["Code and full benchmark", D.repo_url]);
  const runs = [];
  links.forEach(([label, url], i) => {
    runs.push({ text: label, options: { bold: true, color: C.text1, breakLine: true } });
    runs.push({ text: url.replace(/^https:\/\//, ""), options: { color: C.accent1, hyperlink: { url }, breakLine: i < links.length - 1 } });
    if (i < links.length - 1) runs.push({ text: " ", options: { fontSize: 6, breakLine: true } });
  });
  s.addText(runs, { x, y: 3.55, w: 8.6, h: 2.9, fontSize: 18, margin: 0, valign: "top", isTextBox: true });
  s.addText("Priyanshu Singh · Freelance AI / ML Engineer · Demo set up on the public MVTec AD dataset (non-commercial licence); client systems are set up on your own parts.",
    { x: M, y: 6.75, w: 12.1, h: 0.4, fontSize: 12, color: C.accent5, margin: 0, isTextBox: true });
  s.addNotes("The live demo is linked. If you want this on your production line, message me.");
}

// ================= 9. appendix: engineering depth =================
pres.addSection({ title: "Appendix" });
{
  const s = content("Appendix", "Appendix · for engineers", "Benchmarked, not guessed.");
  const labels = D.backbones.map((b) => b.label);
  const lo = Math.min(...D.backbones.flatMap((b) => [b.image, b.pixel]));
  const minV = Math.max(0, Math.floor((lo - 0.01) * 50) / 50);
  card(s, M, 1.95, 6.3, 4.85, "Chart frame");
  s.addChart(pres.charts.BAR, [
    { name: "Image AUROC", labels, values: D.backbones.map((b) => +b.image.toFixed(3)) },
    { name: "Pixel AUROC", labels, values: D.backbones.map((b) => +b.pixel.toFixed(3)) },
  ], {
    x: M + 0.1, y: 2.05, w: 6.1, h: 4.65, barDir: "col", barGrouping: "clustered", barGapWidthPct: 60,
    chartColors: [H.accent1, H.accent4], valAxisMinVal: minV, valAxisMaxVal: 1.0, valAxisLabelFormatCode: "0.00",
    valAxisMajorUnit: 0.02, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000",
    dataLabelFontSize: 9, dataLabelColor: H.dk2, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: H.dk2, valAxisLabelColor: H.accent5, catAxisLabelFontSize: 10, valAxisLabelFontSize: 9,
    catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
    valGridLine: { color: H.accent6, size: 0.75 }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "t", legendColor: H.dk2, legendFontSize: 11, legendFontFace: "+mn-lt",
    showTitle: true, title: "4 backbones, same pipeline (mean over 5 MVTec AD categories)", titleColor: H.dk1,
    titleFontSize: 12, titleFontFace: "+mn-lt", objectName: "Backbone comparison chart",
  });
  const x = M + 6.6, w = W - M - x;
  s.addText("Versus published reference implementations", { x, y: 1.95, w, h: 0.4, fontFace: "Arial", fontSize: 14,
    bold: true, color: C.text1, margin: 0, isTextBox: true });
  const hdr = ["Method", "Image", "Pixel", "Screw"].map((t) => ({ text: t,
    options: { bold: true, color: C.accent1, fill: { color: C.background2 } } }));
  const rows = D.compare.map((r) => [r.name, f3(r.image), f3(r.pixel), f3(r.screw)].map((t) => ({ text: t,
    options: { color: r.mine ? C.text1 : C.text2, bold: r.mine, fill: { color: C.background1 } } })));
  s.addTable([hdr, ...rows], { x, y: 2.4, w, colW: [w - 2.4, 0.8, 0.8, 0.8], fontSize: 11, fontFace: "Calibri",
    border: { type: "solid", pt: 0.75, color: H.accent6 }, rowH: 0.3, margin: 0.05, objectName: "Comparison table" });
  const c1 = D.coreset.find((r) => r.backbone === "WideResNet-50" && r.ratio === 0.01);
  const c10 = D.coreset.find((r) => r.backbone === "WideResNet-50" && Math.abs(r.ratio - 0.1) < 1e-9);
  const notes = [{ text: "Same 5 categories, image/pixel AUROC. Source: " + D.compare_src + ".",
    options: { color: C.accent5, breakLine: !!(c1 && c10) } }];
  if (c1 && c10) notes.push({ text: `Keeping 1% of the memory bank (${c1.bank_mb.toFixed(0)} MB instead of ${c10.bank_mb.toFixed(0)} MB) costs ${(c10.image - c1.image).toFixed(3)} image AUROC.`,
    options: { color: C.text2 } });
  s.addText(notes, { x, y: 5.15, w, h: 1.6, fontSize: 12, margin: 0, valign: "top", isTextBox: true });
  s.addNotes("For technical buyers: four backbones measured, compared with Intel anomalib on the same categories.");
}

(async () => {
  const out = path.join(__dirname, "deck.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
