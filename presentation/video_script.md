# Video script: DefectScope (60–80 s)

Record with OBS Studio, 1080p, cursor zoom on clicks, burned-in captions. Open the live demo first:
https://priyanshu-singh-git.github.io/defectscope/?product=metal_nut&sample=bent

| Time | On screen | Say (casually, like showing a friend) |
|---|---|---|
| 0–8 s | Demo already open on the bent metal nut: red heatmap on the bent edge, **DEFECT** badge | "This AI just found a bent part, and it has never seen a single defect photo." |
| 8–30 s | Switch product to **Bottle** → click *broken large*, then *good*. Then **Screw** → *scratch head* | "You set it up with photos of good parts only. Broken bottle: flagged, and it shows where. Good bottle: passes. Works on screws too." |
| 30–45 s | Click **…or upload your own photo** and pick a defective image saved on your desktop (e.g. one from `data/mvtec/bottle/test/`) | "You can upload your own photo. It runs right here in the browser, so the photo never leaves my laptop." |
| 45–60 s | Scroll to the **How good is it?** table | "On test parts it never saw, it caught 94% of defective parts and wrongly rejected 7% of good ones, at 50 milliseconds per part on a normal CPU." |
| 60–75 s | Back to the top, cursor on the heatmap | "The live demo is linked. If you want this on your production line, send me photos of your parts and I'll show you if it works." |

Tips
- The page loads the model on the first visit (~15 MB), so open it once before recording.
- Keep it honest: if a sample shows PASS on a defect (screw "manipulated front"), skip it or say "screws are the hardest case; on a real line I tune it on your parts".
