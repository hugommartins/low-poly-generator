# Grid size by image type and size, and which parameters matter most

Exploration of the best grid size across image types and sizes, and of which parameters move the result most at a fixed grid size. Follows [PARAMETER_STUDY.md](PARAMETER_STUDY.md) (four photos, one size). Metrics: [QUALITY_METRICS.md](QUALITY_METRICS.md). Terms such as SSIM, PSNR, edge lift and jitter are defined in the [glossary](CASE_STUDY.md#glossary).

## Result

- **Best grid size:** with jitter at half the grid, about 16 cells across the long side for every image type tested. The band within 90% of the peak differs by type: 16 only for portrait and texture, 16 to 24 for animal, 8 to 16 for object, 12 to 24 for text and sky (section 1). That is a grid of about 20 px at 256 px, 24 px at 384 px and 24 to 28 px at 512 px.
- **Jitter rule:** the package default is a fixed 12 px, not half the grid. With it, 16 px is the best grid at 384 and 512 px, and 24 px gives 16% and 13% less edge lift (0.016 and 0.013, near the 0.02 noise threshold) for about half the triangles. Not adopted; 256 px was not tested (section 6).
- **Size:** the coarse side of the curve follows cells across; the dense side follows grid pixels.
- **Parameters by effect:** on edge lift, jitter then Canny; smoothing and saturation change only colours, so their lift effect is zero by construction, and they are ranked by SSIM and PSNR (section 3). Grid size outweighs all of them.
- **Jitter:** `max(12, grid / 2)` leaves grids up to 25 px unchanged and improves coarser ones by 0.020 to 0.026 lift, near the noise threshold. Not adopted.
- **Canny:** 100/200 has the highest edge lift at 256, 384 and 512 px against Canny reference edges. On four photos it also ranks first against Sobel and Laplacian-of-Gaussian reference edges, but its lead over the runner-up there is 0.008 to 0.009 lift, below the 0.02 noise threshold. Provisional ([PARAMETER_STUDY.md](PARAMETER_STUDY.md), section 2).
- **Types:** texture and text gain little fidelity from the first doublings of density.
- **Complexity:** on 36 images, the busier the image (share of Canny edge pixels), the finer the best grid and the lower the edge lift. Grid 25 is in the best band for sparse images and about 16% (0.0055) below the peak on packed ones at 384 px (section 5).
- **Contact sheet:** 24 px is the coarsest of three grids where the subject stays readable; 12 px stays low-poly and is closer to the photo.

## Method

"Best" grid size is the grid where the mesh follows the photo's edges most (edge lift), because SSIM and PSNR rise with every added triangle. Other parameters are compared at a fixed grid size, so density cannot explain an effect.

- **Images:** 14 images bundled with scikit-image, not added to the repository. Grayscale images are stacked to three channels.

| Type | Images | Note |
|---|---|---|
| portrait | astronaut, camera | `camera` is grayscale |
| animal | chelsea | |
| object | coffee, rocket, coins | `coins` is grayscale |
| texture | brick, grass, gravel | grayscale; fine, even detail |
| text | page, text | grayscale |
| sky | hubble_deep_field, moon | mostly dark background; `moon` is grayscale |
| graphic | colorwheel | smooth gradients, no edge at default Canny |

- **Sizes:** long side 256, 384 and 512 px, and 800 px for one image (hubble). Images are resized with area averaging and never enlarged, so small originals have fewer sizes.
- **Grid size** is set as cells across the long side `N` = 6, 8, 12, 16, 24, 32, 48, 64; `grid_size` in pixels is long side / `N`. Triangle count then depends on `N` and the aspect ratio only.
- **Settings:** defaults (Canny 100/200, saturation 1.3, smoothing 75, centroid colours), with jitter at half the grid size. The package default is a fixed 12 px; section 6 compares the two rules.
- **Metrics:** SSIM, PSNR and edge lift as defined in [PARAMETER_STUDY.md](PARAMETER_STUDY.md), against the photo's own default-Canny edges within 2 px.
- **Seeds:** 3 per setting. Seed noise, from 12 seeds on 13 images: SSIM sd 0.004 to 0.005, lift sd 0.005 to 0.010. Differences under about 0.01 SSIM or 0.02 lift are not read as real when settings are compared across seeds; the quality baseline pins the seed, so its tolerance is tighter.
- **Parameter screening:** `N` = 16 and 32, 384 px, 13 images (all with a 384 px version). Smoothing is varied by replacing `smooth` in the script.
- The scripts for sections 1 to 4 are not in the repository. `scripts/grid_sweep.py` runs the extended sweep of section 5 and writes `grid_sweep.csv`; `scripts/grid_jitter.py` runs section 6 and writes `grid_jitter.csv`.

## 1. Grid size by image type

Edge lift (mean over the type's images and sizes), by cells across the long side:

| Type | N=8 | N=12 | N=16 | N=24 | N=32 | N=48 | Peak | Within 90% of peak (N) | Same, in grid px |
|---|---|---|---|---|---|---|---|---|---|
| portrait | 0.053 | 0.063 | **0.079** | 0.067 | 0.051 | 0.024 | 16 | 16 | 14 to 32 |
| animal | 0.054 | 0.071 | **0.082** | 0.076 | 0.044 | 0.011 | 16 | 16 to 24 | 14 to 24 |
| object | 0.103 | 0.110 | **0.112** | 0.089 | 0.060 | 0.026 | 16 | 8 to 16 | 18 to 32 |
| texture | 0.014 | 0.034 | **0.047** | 0.039 | 0.028 | 0.014 | 16 | 16 | 14 to 24 |
| text | 0.032 | 0.079 | **0.085** | 0.081 | 0.050 | 0.013 | 16 | 12 to 24 | 14 to 24 |
| sky | 0.127 | 0.147 | **0.156** | 0.146 | 0.117 | 0.069 | 16 | 12 to 24 | 14 to 48 |

- Types differ in level, not in position: sky has the highest lift (0.156) and texture the lowest (0.047).
- Past the peak the mesh is too dense to follow edges: at N=64 nearly every pixel is within 2 px of a mesh edge (chance 0.96 or more), so lift is near zero.
- Graphic has no edges at default Canny on the one image tested, so lift is undefined. Its SSIM is the highest of all types: 0.72 at N=16, 0.90 at N=64.

Fidelity by type: SSIM at N=16, and gain per doubling of triangles at coarse (N 6 to 16) and dense (N 32 to 64) grids:

| Type | SSIM at N=16 | Gain per doubling, coarse | Gain per doubling, dense |
|---|---|---|---|
| graphic | 0.720 | 0.041 | 0.045 |
| sky | 0.647 | 0.003 | 0.023 |
| object | 0.526 | 0.026 | 0.042 |
| portrait | 0.521 | 0.031 | 0.055 |
| text | 0.435 | 0.015 | 0.067 |
| animal | 0.423 | 0.029 | 0.078 |
| texture | 0.232 | 0.012 | 0.100 |

Texture and text gain little from the first doublings and most from the last; grass and gravel score 0.07 to 0.10 at N=16. Sky starts high (0.64 at N=6) because most of the image is a flat dark background.

## 2. Grid size by image size

![Edge lift against cells across the long side, and against grid size in pixels, for three image sizes](images/study_ratio.png)

Nine images that exist at all three sizes, mean edge lift:

| N | 256 px | 384 px | 512 px |
|---|---|---|---|
| 6 | 0.065 | 0.059 | 0.052 |
| 8 | 0.079 | 0.082 | 0.063 |
| 12 | 0.088 | 0.092 | 0.088 |
| 16 | 0.087 | 0.107 | 0.103 |
| 24 | 0.057 | 0.090 | 0.099 |
| 32 | 0.021 | 0.065 | 0.092 |
| 48 | 0.000 | 0.022 | 0.062 |
| 64 | 0.000 | 0.004 | 0.022 |

- The peak is at N = 12 to 16 at 256 px, 16 at 384 px and 16 to 24 at 512 px: a grid of about 21, 24 and 21 to 32 px.
- The coarse side lines up by cells across. The dense side lines up by pixels: at an 8 px grid all three sizes give a lift of 0.022. Lift collapses under a grid of about 10 to 14 px; the 2 px tolerance of the metric contributes to this.
- Single images vary more than the pooled curve (the peak `N` moved up to a factor of six with size, for example gravel 8, 32, 48), because each image's curve is flat near its peak.
- Sizes above 512 px were run on one image: hubble peaks at N=32 at 800 px, a grid of 25 px.

| Long side | Grid size that follows edges best (px) | Cells across | Typical best |
|---|---|---|---|
| 256 px | 14 to 21 | 12 to 18 | about 20 |
| 384 px | 16 to 32 | 12 to 24 | about 24 |
| 512 px | 21 to 32 | 16 to 24 | about 24 to 28 |

The default grid of 25 is in the band for 384 and 512 px. At N = 12 to 24 the triangle count runs from about 150 to 1,250, depending on the image.

## 3. Parameters by effect

At a fixed grid size (N = 16 and 32, 384 px, 13 images). Effect is the difference between the best and worst tested value, in the mean over all images.

| Rank | Parameter | Values | SSIM effect (N=16 / 32) | PSNR effect, dB | Lift effect (N=16 / 32) | Changes |
|---|---|---|---|---|---|---|
| 1 | Jitter (share of grid) | 0, 0.25, 0.5, 0.75, 1.0 | 0.029 / 0.027 | 0.5 / 0.6 | **0.138 / 0.109** | Point positions |
| 2 | Canny low/high | 25/50, 50/100, 100/200, 200/400 | 0.009 / 0.013 | 0.4 / 0.6 | 0.061 / 0.036 | Point positions |
| 3 | Smoothing (bilateral sigma) | 0, 75, 150 | 0.015 / 0.021 | 0.7 / 0.9 | 0 | Colours |
| 4 | Saturation | 1.0, 1.15, 1.3 | 0.014 / 0.017 | 0.3 / 0.5 | 0 | Colours |

For scale, going from N=8 to N=32 moves the mean SSIM by 0.124. Smoothing and saturation leave the mesh alone, so edge lift cannot change.

**Jitter** (N=16):

| Jitter (share of grid) | SSIM | Lift | Triangles |
|---|---|---|---|
| 0 | 0.432 | -0.004 | 475 |
| 0.25 | 0.448 | 0.050 | 473 |
| 0.5 | 0.461 | 0.102 | 471 |
| 0.75 | 0.459 | 0.114 | 467 |
| 1.0 | 0.458 | 0.134 | 466 |

- Jitter 0 is the worst setting: no edge-following and 0.03 SSIM lost.
- SSIM is flat from 0.5. Lift keeps rising while the triangle count falls, because neighbouring points merge.
- The package default is a fixed 12 px, which is 0.48 of the default grid (25), 0.75 at grid 16 and 0.3 at grid 40.

**Canny:** 100/200 gives the highest edge lift at every size (0.079 at 256 px, 0.102 at 384 px, 0.103 at 512 px; the other three settings 0.033 to 0.073). It has the best SSIM in portrait, sky, text and texture; in animal and object another pair is higher by 0.008 to 0.010. The reference edges are the photo's own Canny 100/200 edges, so the lift comparison is partly circular. Against Sobel and Laplacian-of-Gaussian reference edges on four photos, 100/200 still ranks first, with a lead of 0.008 to 0.009 lift over the runner-up, below the 0.02 noise threshold ([PARAMETER_STUDY.md](PARAMETER_STUDY.md), section 2). Provisional.

**Smoothing:** sigma 75 gains +0.013 SSIM at N=16 and +0.021 at N=32 over no filter; sigma 150 adds at most 0.002. There is no optimum between 50 and 150 (settings differ by under 0.002 SSIM on colour images), so 75 is on a plateau. The gain is similar at 256, 384 and 512 px (+0.017, +0.013, +0.012). The window (d=9) was not varied.

**Saturation:** 1.3 costs 0.014 to 0.017 SSIM against 1.0 on average over these 13 images (object 0.047, animal 0.013, portrait 0.012). The mean is diluted: eight of the 13 images are greyscale, which saturation cannot change. On colour images only (`scripts/colour_options.py`, 384 px, 16 cells across, jitter 12, 3 seeds) the cost is 0.044 SSIM on the four sample photos and 0.033 on 25 colour photos, with 1.0 higher on every image ([PARAMETER_STUDY.md](PARAMETER_STUDY.md), section 4). The smoothing and saturation effects in the table above are therefore understated for colour photos.


## 4. Checks

### Jitter: default 12 px against half the grid size

Paired runs on 13 images at 384 px, 5 seeds each, at five grid sizes. Only the jitter differs. Differences are half-grid minus default, mean over images; the count is images with a higher value.

| Grid (px) | Jitter, default / half grid | Lift: default | Lift: half grid | Lift difference (images higher) | SSIM difference (images higher) |
|---|---|---|---|---|---|
| 12 | 12 / 6 | 0.108 | 0.066 | -0.042 (0 of 13) | -0.002 (9 of 13) |
| 16 | 12 / 8 | 0.111 | 0.089 | -0.022 (1 of 13) | +0.001 (7 of 13) |
| 25 | 12 / 12 | 0.093 | 0.093 | 0 | 0 |
| 40 | 12 / 20 | 0.059 | 0.079 | +0.020 (11 of 13) | +0.001 (7 of 13) |
| 60 | 12 / 30 | 0.020 | 0.046 | +0.026 (10 of 13) | +0.005 (12 of 13) |

At fine grids the fixed 12 px is already 0.75 to 1.0 of the grid and halving it lowers lift. At coarse grids it is 0.3 or less and half the grid helps. `max(12, grid / 2)` is the larger of the two rules at every grid tested: it equals the default up to 25 px and equals half the grid above. SSIM changes by at most 0.005.

### Grid size: contact sheet

![Three photos at a coarse, the recommended and a dense grid](images/contact_sheet.png)

Three images at 384 px, jitter at half the grid, other settings default.

| Image | Grid 48 px: triangles, SSIM, lift | Grid 24 px: triangles, SSIM, lift | Grid 12 px: triangles, SSIM, lift |
|---|---|---|---|
| astronaut | 158, 0.36, 0.058 | 573, 0.45, **0.075** | 2,156, 0.56, 0.062 |
| rocket | 106, 0.68, 0.156 | 402, 0.70, **0.157** | 1,441, 0.74, 0.080 |
| coffee | 105, 0.33, 0.058 | 403, 0.38, **0.082** | 1,442, 0.46, 0.066 |

- **48 px:** the subject is lost in the astronaut and the coffee; only the rocket's tower is readable.
- **24 px:** the face, flag and suit, the cup and saucer, and the rocket with one side tower are recognisable, and the image reads as low-poly. Edge lift is highest or tied here.
- **12 px:** closer to the photo (the second tower, the spoon and the cup handle appear), and still low-poly.

## 5. Grid size by image complexity

Extended sweep: 36 images, the 21 CC0 photos in `samples/study/` (sources in `samples/study/SOURCES.md`) and the 14 scikit-image and 2 scikit-learn sample images (`colorwheel` has no Canny edges, so lift is undefined and it is left out). Sizes 256, 384 and 512 px (never enlarged), N = 6 to 64, jitter at half the grid, 3 seeds. `python scripts/grid_sweep.py run`, then `analyze`; per-run rows are in `grid_sweep.csv`. Seed sd of lift is 0.004 (median) to 0.006 (mean).

**Complexity measure:** edge density, the share of pixels that are Canny 100/200 edges at 384 px on the long side. It runs from 0.005 (ladder against a wall) to 0.33 (grass). Flat share (pixels with a gradient under 4) tracks it, from 0.95 to 0.07.

| Bin (edge density) | Images | N=6 | 8 | 12 | 16 | 24 | 32 | 48 | 64 | Best N | Within 90% (N) | SSIM at N=16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Minimal (<0.06) | 15 | 0.078 | 0.094 | 0.104 | 0.107 | 0.093 | 0.066 | 0.029 | 0.010 | 16 | 12 to 16 | 0.660 |
| Middle (0.06 to 0.12) | 11 | 0.032 | 0.039 | 0.060 | 0.071 | 0.065 | 0.049 | 0.021 | 0.007 | 16 | 16 to 24 | 0.510 |
| Packed (>0.12) | 10 | 0.009 | 0.013 | 0.024 | 0.027 | 0.029 | 0.025 | 0.013 | 0.005 | 24 | 16 to 24 | 0.271 |

Edge lift by bin, mean over sizes. Density moves the level far more than the position: lift at the peak falls from 0.107 to 0.029 and SSIM at N=16 from 0.66 to 0.27, while the best N moves from 16 to 24.

![Edge-following lift against grid size in pixels for minimal, middle and packed images at 256, 384 and 512 px](images/study_density.png)

*Edge lift against grid size for the three density bins. The dashed line is the default 25 px. Packed images peak at 16 to 21 px and reach less than a third of the lift of minimal ones.*

![One minimal, one middle and one packed photo at grid sizes 32, 24 and 16 px](images/study_density_sheet.png)

*One photo per bin at 384 px, jitter at half the grid. The lorikeet and hedgehog stay readable at 24 px; the packed street scene is not readable at any of the three grids (SSIM 0.32 to 0.38).*

By image size, where the best grid is in pixels:

| Bin | 256 px: best N, band in grid px | 384 px | 512 px |
|---|---|---|---|
| Minimal | 8, 16 to 32 | 16, 24 to 32 | 24, 21 to 32 |
| Middle | 16, 16 to 21 | 16, 16 to 24 | 24, 16 to 32 |
| Packed | 12, 21 | 24, 16 | 32, 16 to 21 |

- Minimal images tolerate a coarse grid (about 24 to 32 px). Packed images want 16 to 21 px at every size. Middle images sit between.
- The default grid of 25 is in the band for minimal images at all three sizes, at the coarse edge for middle images, and coarser than the band for packed ones. At 384 px the lift at 24 px is 84% of the packed peak.
- Mean SSIM per image at N=16 and 384 px (3 seeds, `grid_sweep.csv`) runs from 0.09 (grass) to 0.89 (bread-plate); at 512 px, from 0.07 to 0.90.
- Per image, 22 of 36 keep at least 90% of their own peak lift at N=16 (median 96%). The worst are gravel, fern, salad, grass and street-dense (45 to 56%), whose peaks are at N = 24 to 32. Fern, grass and gravel peak under 0.01 lift, which is noise, so their peak position is not read.
- Spearman correlation across images: edge density with the fitted peak N +0.60 (pooled over sizes; per size +0.42 to +0.59; p < 0.001), with peak lift -0.76, and flat share with the fitted peak N -0.46 (p = 0.005). Density predicts how much the mesh can follow edges better than where the peak lies.
- The very sparse images peak at N = 6 to 9 (ladder, moon, rocket); with three of them this is an indication.
- Bands use the tested N, which step by 1.33 to 2 times, so a band edge is accurate to one step. Bins hold 9 to 15 images per size (small originals have no 512 px version).

## 6. Jitter rule and grid size

Sections 1, 2 and 5 set the jitter to half the grid. The package default is a fixed 12 px, which at fine grids is 0.75 to 1.0 of the grid and snaps more points to edges. The images of the extended sweep (36 at 384 px, 32 at 512 px; `colorwheel` left out, 256 px not run) were generated with both rules at grids of 40, 32, 24, 16 and 12 px, 3 seeds each (`python scripts/grid_jitter.py run`, then `analyze`; 680 rows in `grid_jitter.csv`). Mean edge lift:

| Image size | Jitter | 40 px | 32 px | 24 px | 16 px | 12 px |
|---|---|---|---|---|---|---|
| 384 px | 12 px (default) | 0.041 | 0.060 | 0.079 | **0.095** | 0.092 |
| 384 px | Half the grid | 0.064 | 0.072 | **0.079** | 0.074 | 0.056 |
| 512 px | 12 px (default) | 0.046 | 0.066 | 0.084 | **0.097** | 0.093 |
| 512 px | Half the grid | 0.073 | 0.080 | **0.084** | 0.077 | 0.058 |

- With half-grid jitter the best grid is 24 px; with the default 12 px it is 16 px at both sizes. At 25 px both rules use a jitter of 12 and agree.
- Under `max(12, grid / 2)` the current default of 25 px is best; under the fixed default 16 px is best.
- Under the fixed default, 16 px is the best grid or within 0.006 of it in all three density bins at both sizes (table below; the largest gap is 0.0052, packed images at 512 px). Against 24 px it adds 0.016 lift at 384 px (16%) and 0.013 at 512 px (13%), near the 0.02 noise threshold, for about twice the triangles.
Mean edge lift under the fixed 12 px jitter, by edge-density bin (bins as in section 5; `python scripts/grid_jitter.py analyze` prints this table for both rules):

| Image size | Bin (images) | 40 px | 32 px | 24 px | 16 px | 12 px | Best | 16 px below best by |
|---|---|---|---|---|---|---|---|---|
| 384 px | Minimal (15) | 0.065 | 0.088 | 0.113 | **0.126** | 0.119 | 16 px | 0 |
| 384 px | Middle (11) | 0.033 | 0.055 | 0.079 | **0.097** | 0.095 | 16 px | 0 |
| 384 px | Packed (10) | 0.015 | 0.024 | 0.029 | 0.046 | **0.048** | 12 px | 0.002 |
| 512 px | Minimal (14) | 0.071 | 0.099 | 0.120 | **0.134** | 0.120 | 16 px | 0 |
| 512 px | Middle (9) | 0.036 | 0.059 | 0.080 | 0.091 | **0.094** | 12 px | 0.003 |
| 512 px | Packed (9) | 0.017 | 0.023 | 0.033 | 0.046 | **0.051** | 12 px | 0.005 |

- The conclusion about where the best grid lies therefore depends on the jitter rule. The sections above hold for half-grid jitter.

## 7. Suggested starting settings

For an image of 256 to 512 px on the long side.

| Setting | Start | Basis |
|---|---|---|
| Grid size | With half-grid jitter: about 20 px at 256, 24 at 384, 24 to 28 at 512; 16 to 21 px for packed scenes (edge density above 0.12). With the package's fixed 12 px jitter: 16 px at 384 and 512 px (256 px not tested). Not adopted | Sections 2, 5 and 6 |
| Jitter | `max(12, grid / 2)` equals the default up to 25 px and adds 0.020 to 0.026 lift at 40 and 60 px, near the noise threshold. Not adopted | Sections 3, 4 and 6 |
| Canny | 100/200 | Section 3; provisional |
| Smoothing | 75 | Section 3; on a plateau from 50 to 150 |
| Saturation | 1.0 for fidelity (0.033 to 0.044 SSIM above 1.3 on colour photos); 1.3 for a stronger look | Section 3 |

Texture and text will not resemble the photo closely at any grid size. Graphic has one image and no setting is suggested.

## 8. Limits

- Sections 1 to 4: fourteen images, one to three per type; animal and graphic have one each. Per-type rows are indications. Section 5 adds 23 images and groups by edge density instead of type.
- Eight of the 14 images are grayscale, which raises their SSIM and PSNR and dilutes the mean effect of saturation and smoothing (section 3).
- Sizes stop at 512 px apart from one image at 800 px. The fixed-jitter comparison (section 6) covers 384 and 512 px only.
- The grid sweeps use half-grid jitter, which is not the package default, so their grid recommendations do not carry over to the default without section 6.
- The 2 px tolerance of edge lift shapes the dense side of every curve, and the reference edges depend on image size.
- Edge density is one measure of complexity; fur and foliage raise it without adding structure. Its bin limits (0.06, 0.12) were set by eye to give bins of 10 to 15 images.
- The 21 photos have no types assigned, so the type rows and the density bins are not crossed.
- Edge-following is not appeal. The contact sheet covers three images.
- One machine, `scikit-image` 0.26.0.