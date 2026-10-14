# Output-quality metrics

> Research note: this page is an exploratory study. It is not part of the public CLI docs or the project’s active acceptance checks. The canonical user guidance is in [README.md](../README.md), and the current testing status is in [TEST_STRATEGY.md](TEST_STRATEGY.md).

Exploration of how to measure output quality against the source photo. Only the stored-score baseline test ([BASELINE_REPORT.md](BASELINE_REPORT.md)) uses these metrics; `scikit-image` is a test dependency, not a package dependency. Data: the four sample photos at 450 px; method and tables in [PARAMETER_STUDY.md](PARAMETER_STUDY.md). Separate from [TESTING.md](TESTING.md), which covers what the project tests today. Terms such as SSIM, PSNR, edge lift and jitter are defined in the [glossary](CASE_STUDY.md#glossary).

## Result

- **Relative checks work; absolute thresholds do not.** SSIM against the photo is 0.32 to 0.78 across settings, so no fixed gate such as 0.85 can pass.
- **Two relations hold:** a photo's output scores higher against its own photo than against another (margins 0.17 to 0.45 against a limit of 0.10), and SSIM rises across a large density step (0.074 to 0.225 against 0.05, thin on the rocket photo). In fault injection they caught gross faults only.
- **SSIM and PSNR detect different faults**, so both are used.
- **A baseline** (stored scores, fail on a move in either direction) is the second check, and it is built. Its tolerance depends on the spread across platforms, which is not measured.

## Metrics

| Metric | Measures | Blind to |
|---|---|---|
| SSIM | Local luminance, contrast and structure against the photo | Uniform brightness changes |
| PSNR | Mean squared pixel error against the photo | Structure |
| Edge lift | Share of the photo's Canny edge pixels within 2 px of a mesh edge, minus the share of all pixels within 2 px of a mesh edge (chance). This is boundary recall, as used for superpixels, with chance subtracted | Appearance |

Chance is subtracted because a mesh covers the image densely: at grid 16, 0.69 of all pixels are near a mesh edge with no edge-following at all.

Not used: LPIPS (needs PyTorch and downloaded weights), ImageMagick `compare` (same SSIM and PSNR), OpenCV `matchShapes` (compares closed shapes).

## What the metrics detect

One output (cat photo, grid 16, SSIM 0.513, PSNR 21.1 dB) was damaged in known ways and scored against the photo:

| Damage | SSIM change | PSNR change (dB) |
|---|---|---|
| Different photo, same size | -0.310 | -10.43 |
| Output mirrored | -0.179 | -6.49 |
| Red and blue swapped | -0.073 | -9.12 |
| Output shifted 6 px | -0.069 | -1.78 |
| Colours 20% too saturated | -0.031 | -2.37 |
| Colours 20% darker | -0.008 | -4.05 |
| Last column and row black | -0.001 | -0.61 |
| Colours 1 level darker | -0.001 | -0.15 |

Gross faults register on both metrics. SSIM barely reacts to brightness. The two small faults register only in PSNR.

## Strategy

1. **Baseline** (built; design and validation in [BASELINE_REPORT.md](BASELINE_REPORT.md)). Store SSIM, PSNR and triangle count per sample photo and setting at the default seed. Fail when SSIM or PSNR moves, up or down, by more than the tolerance. Update the baseline by reviewed change only. A rise has to fail because ignoring the saturation option raised both scores.
2. **Relations** (not built). Own photo above another photo by 0.10 (at grid 16: own 0.44 to 0.73, other 0.16 to 0.35). SSIM higher at grid 9 than at grid 40 by 0.05 (measured gain 0.074 to 0.225). Adjacent coarse grids are not monotone, so the step must be large.
3. **Report.** Fidelity against triangle count, produced on demand: [PARAMETER_STUDY.md](PARAMETER_STUDY.md) and [GRID_RATIO_STUDY.md](GRID_RATIO_STUDY.md).

Seed noise (SSIM sd 0.002 to 0.006, PSNR sd 0.1 to 0.3 dB) matters when comparing settings, not for a fixed-seed baseline. `scikit-image` is in the test extra. The baseline tolerance is the noise floor; the spread across the CI matrix is not measured.

## Limits

- Fidelity rises with every added triangle (+0.044 SSIM per doubling above about 500 triangles, no elbow), so it cannot choose the best-looking density.
- A whole-image average hides local losses such as text or a thin line. None of the sample photos has text.
- Colour error per triangle was not measured.