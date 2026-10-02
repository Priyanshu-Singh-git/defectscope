# Upwork portfolio entry: DefectScope

## Title
AI Defect Detection for Manufacturing: Set Up From Good-Part Photos Only

## Description
AI visual inspection that spots scratches, dents, cracks and contamination without a single defect photo.
It learns what a good part looks like and flags anything that doesn't match, with a heatmap showing exactly where.

On public benchmark parts it never saw, it caught 94% of defective parts while wrongly rejecting 7% of good ones,
at 50 ms per part on a normal CPU (no GPU). I re-implemented the PatchCore research method (CVPR 2022) from
scratch in PyTorch, benchmarked 4 backbones, and matched Intel's reference implementation (0.990 vs 0.988 image AUROC).

Try the live demo in your browser (photos never leave your device): https://priyanshu-singh-git.github.io/defectscope/

Want this on your line? Send me photos of your parts and I'll show you whether it works.

## Skills
Computer Vision · Anomaly Detection · PyTorch · Deep Learning · Quality Inspection · ONNX · Machine Vision

## Links
- Live demo: https://priyanshu-singh-git.github.io/defectscope/
- Code + benchmark: https://github.com/Priyanshu-Singh-git/defectscope
- Video: (add the YouTube link after recording)

## Images to upload (in this order)
`presentation/slides/slide_01.png` is the cover/thumbnail, then `slide_02.png` … `slide_09.png`.
