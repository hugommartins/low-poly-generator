# Bug log

Defects found while building and using `lowpoly`: symptom, root cause, fix and the test that guards each one.

<div align="center">


## Status

| Severity | Open | Fixed | Total |
|---|---:|---:|---:|
| High | 0 | 3 | 3 |
| Medium | 0 | 6 | 6 |
| Low | 1 | 2 | 3 |
| **All** | **1** | **11** | **12** |


| Suite | Tests |
|---|---|
| Example-based | 33  |
| Differential | 3 |
| Property (Hypothesis) | 21 |

</div>

**Severity:** _High_ = wrong or lost output. _Medium_ = wrong behaviour or misleading message. _Low_ = cosmetic or edge case.

**Code map:** `pipeline.py` (stages, `Result`, `generate`), `relief.py` (depth and lighting), `io.py` (file reading and writing). `core.py` re-exports all three.

## All bugs

| ID | Title | Severity | Status | Date |
|---|---|---|---|---|
| [BUG-001](#bug-001) | Reimplementation diverged from the original script | High | Fixed | 2026 -10-03|
| [BUG-002](#bug-002) | PNG write failed silently when output folder was missing | High | Fixed | 2026 -10-03|
| [BUG-003](#bug-003) | Folder mode overwrote files with the same name stem | High | Fixed | 2026 -10-03|
| [BUG-004](#bug-004) | Misleading error for a file that would not open | Medium | Fixed | 2026 -10-03 |
| [BUG-005](#bug-005) | `~` in paths was not expanded | Medium | Fixed | 2026 -10-03 |
| [BUG-006](#bug-006) | Raw tracebacks shown for expected errors | Medium | Fixed |  2026 -10-03|
| [BUG-007](#bug-007) | Relief colours truncated instead of rounded | Medium | Fixed | 2026 -10-03|
| [BUG-008](#bug-008) | Coverage test crashed under NumPy 2 | Low | Fixed | 2026 -10-03|
| [BUG-009](#bug-009) | Relief mode leaves dark and bright spikes at depth steps | Low | **Open** | 2026 -10-03|
| [BUG-010](#bug-010) | PNG and SVG leave a one-pixel strip on the right and bottom edges | Medium | Fixed | 2026 -10-03|
| [BUG-011](#bug-011) | One-pixel-wide or tall image raises a raw `QhullError` | Low | Fixed | 2026 -10-03|
| [BUG-012](#bug-012) | Mean colour mode truncates instead of rounding | Medium | Fixed | 2026 -10-03|


## Open

<a id="bug-009"></a>

### BUG-009: Relief spikes at depth steps

**Low** · Open, mitigated · Found by: visual inspection

- **Symptom:** Dark and bright spikes where the depth map has a sharp step, for example the figure `relief_dome`.
- **Root cause:** Large height differences between neighbouring vertices give near-vertical facet normals.
- **Mitigation:** Tilt is capped at 60 degrees. The spikes are reduced, not removed.
- **Suggested guard:** An `xfail(strict=True)` test on a stepped depth map, so the defect is on record and the suite fails loudly if someone fixes it without updating the test.


## Fixed

<a id="bug-001"></a>

### BUG-001: Reimplementation diverged from the original script

**High** · Fixed · Found by: reviewer question ("Have you fully reverted the delaunay to the original script?")

- **Symptom:** Output differed from the original `border_uniform_low_poly`.
- **Root cause:** Five silent differences:
  1. Edge detection used a single-threshold Sobel instead of Canny with hysteresis.
  2. The bilateral filter was 5x5 instead of d=9, sigma 75/75.
  3. Saturation was scaled in luma space instead of HSV.
  4. Triangle colour was the mean of pixels instead of the centroid pixel.
  5. The default grid was 16 instead of 10.
- **Fix:** Rebuilt each stage to match the original. Verified byte for byte with `cmp` on the cat at grid 10 and 25 and on the portrait.
- **Guard:** `tests/test_differential.py` runs the original script (stored in `tests/reference/`) and the package on the same inputs and compares the SVGs byte for byte. Checked by changing saturation, a Canny threshold and the colour mode: each change failed the comparison. Since BUG-010, the comparison rewrites the original's `viewBox` header first; every polygon must still match.
- **Lesson:** A refactor needs an executable oracle, not a visual "looks the same".

<a id="bug-002"></a>

### BUG-002: PNG output failed silently when the output folder was missing

**High** · Fixed · Found by: testing

- **Symptom:** The command appeared to succeed and wrote nothing.
- **Root cause:** The return value of `cv2.imwrite` was not checked, and the parent folder was not created.
- **Fix:** Create the parent folder. Raise an error if `imwrite` returns false.
- **Guard:** `test_output_folder_is_created_for_png_and_svg`

<a id="bug-003"></a>

### BUG-003: Folder mode overwrote files with the same stem

**High** (data loss) · Fixed · Found by: testing

- **Symptom:** With `a.jpg` and `a.png` in one folder, folder mode wrote one `a.svg` and lost the other.
- **Root cause:** The output name was built from the stem only.
- **Fix:** On a collision, include the extension in the name (`a.png` becomes `a_png.svg`).
- **Guard:** `test_folder_mode_same_stem_does_not_overwrite`

<a id="bug-004"></a>

### BUG-004: Misleading error for a file that would not open

**Medium** · Fixed, not yet confirmed on the reporter's machine · Found by: user report (macOS), loading `~/Downloads/test.jpg` ("I know for sure that the image is there")

- **Symptom:** OpenCV printed a generic warning, then the tool claimed the file might be HEIC.
- **Root cause:** OpenCV uses one warning for "cannot open" and "unrecognised format", and the message assumed HEIC. The real cause on the reporter's machine has not been confirmed. Candidates: macOS privacy blocking Downloads, a different real format, or a 0-byte download.
- **Fix:** Read the bytes in Python and detect the format from the content. Each case gets its own message:
  - missing file
  - folder instead of a file
  - permission denied (with the macOS fix)
  - empty file
  - named unsupported format (HEIC/AVIF, with a `sips` hint)
  - unrecognised content
  - damaged file

  A wrong extension no longer matters when the content is supported.
- **Guard:**
  - `test_missing_file`
  - `test_unrecognised_file_gives_clear_error`
  - `test_empty_file_is_named_as_empty`
  - `test_heic_by_content_is_reported_with_a_fix`
  - `test_extension_can_be_wrong_when_content_is_supported`
  - `test_truncated_jpeg_is_reported_as_damaged`
  - `test_permission_denied_message_mentions_macos_fix` (skipped as root)
- **To do:** Ask the reporter whether the file now loads.

<a id="bug-005"></a>

### BUG-005: `~` in paths was not expanded

**Medium** · Fixed · Found by: user report (macOS), alongside BUG-004

- **Symptom:** A path starting with `~` that the shell had not expanded (for example inside quotes) was not found.
- **Root cause:** Paths were used as given, so `~` was treated as a literal folder name.
- **Fix:** Expand `~` for input and output.
- **Guard:** `test_tilde_is_expanded`

<a id="bug-006"></a>

### BUG-006: Raw tracebacks for expected errors

**Medium** · Fixed · Found by: testing

- **Symptom:** Expected failures printed a Python traceback.
- **Root cause:** `FileNotFoundError`, `ValueError` and `OSError` were not caught at the CLI.
- **Fix:** Catch them and print `lowpoly: error: <message>` with a non-zero exit code.
- **Guard:**
  - `test_cli_errors_are_clean_messages`
  - `test_bad_output_extension`
  - `test_missing_depth_map`

<a id="bug-007"></a>

### BUG-007: Relief colours truncated instead of rounded

**Medium** · Fixed · Found by: test failure (`test_flat_depth_keeps_colours`)

- **Symptom:** A flat surface changed colour.
- **Root cause:** Float colours were truncated when cast to `uint8`, so a flat surface came out slightly off its original colour.
- **Fix:** `np.rint` before the cast.
- **Guard:** `test_flat_depth_keeps_colours`

<a id="bug-008"></a>

### BUG-008: Coverage test crashed under NumPy 2

**Low** (test code, not product code) · Fixed · Found by: test failure

- **Root cause:** `np.cross` on 2D vectors is removed in NumPy 2.
- **Fix:** Explicit 2D determinant in the test.
- **Guard:** `test_triangles_cover_frame` (also checks that triangle areas sum to the image area).
- **Lesson:** Run the suite on NumPy 1 and 2 in CI.

<a id="bug-010"></a>

### BUG-010: PNG and SVG leave a one-pixel strip on the right and bottom edges

**Medium** · Fixed 2026-10-06 · Found by: random-image probe

- **Symptom:** On a flat image the PNG has a different colour in the last column and row. The SVG viewBox is `w x h` but points reach only `w-1` and `h-1`.
- **Root cause:** Points are pixel indices, so the mesh spans `(w-1) x (h-1)`. The canvas and viewBox were `w x h`. The frame-coverage property passed because it measures the mesh, not the canvas.
- **Inherited:** The original script has the same mesh and viewBox. The decision was that the original's header is no longer the standard.
- **Fix:**
  - `Result.to_svg` writes `viewBox="0 0 (w-1) (h-1)"`.
  - `Result.to_png` scales mesh coordinates by `w/(w-1)` and `h/(h-1)`.
  - Point placement and polygon coordinates are unchanged.
- **Guard:**
  - `test_a_flat_image_gives_a_flat_png` (`expectedFailure` marker removed)
  - `test_svg_view_box_is_exactly_what_the_mesh_covers`
  - `tests/test_differential.py` rewrites the original's `viewBox` header and still compares every polygon byte for byte.
  - `test_svg_has_one_polygon_per_triangle_inside_the_frame` now expects `0 0 {w-1} {h-1}`.
- **Note:** The viewBox aspect ratio now differs from the image's by one pixel. This is invisible at normal sizes.

<a id="bug-011"></a>

### BUG-011: One-pixel-wide or tall image raises a raw `QhullError`

**Low** · Fixed 2026-10-06 · Found by: random-image probe

- **Symptom:** A `1 x n` or `n x 1` image gave a traceback in the CLI instead of an error message.
- **Root cause:** All points are collinear, so Qhull cannot triangulate. The CLI catches only `FileNotFoundError`, `ValueError` and `OSError`; `QhullError` is none of these. The original script fails the same way.
- **Fix:** `generate` raises `ValueError("image must be at least 2x2 pixels, got WxH")` before any processing. The CLI already turns `ValueError` into a clean message (BUG-006).
- **Guard:**
  - `test_one_pixel_images_are_rejected_cleanly` (1x1, 1xN, Nx1)
  - `test_the_smallest_accepted_image_renders` (2x2)
  - `test_one_pixel_images_are_rejected_cleanly_or_rendered` (`expectedFailure` marker removed)

<a id="bug-012"></a>

### BUG-012: Mean colour mode truncates instead of rounding

**Medium** · Fixed 2026-10-06 · Found by: property test run (a flat image in mean mode came out one level darker)

- **Symptom:** Triangle colours in `mean` mode could be one level too dark.
- **Root cause:** `triangle_colors` wrote float means into a `uint8` array, which truncates. The mean of a flat colour 200 can come out 199. Same class as BUG-007, in a different function.
- **Fix:** `np.rint` before the cast.
- **Guard:**
  - `test_mean_mode_rounds_instead_of_truncating`
  - `test_a_flat_image_gives_triangles_of_that_one_colour_in_mean_mode` (`expectedFailure` marker removed, also in `test_regressions.py`)
- **Lesson:** A fix in one place (BUG-007) needs a search for the same pattern elsewhere.


## Observations that are not defects

- **Golden hashes depend on the environment.** Byte-exact SVG output can differ across OpenCV and SciPy builds, which is why the differential test runs the original script live instead of comparing with a stored file.
- **Neural depth was never tested.** The build environment had no model weights or package access, so that route was dropped. Facts about PyTorch wheels and Intel Mac support came from memory and are unverified.
- **Browser demo defects (demo removed).** Seams and corner spurs from stroke colour spilling past cell corners, and a duplicate `cols` identifier in the JavaScript. The reporter never confirmed the seam fix.
- **Subject-aware experiment (artifact, deleted).** A mask built from one median border colour classed a dark bird as background. A border-colour model plus a focus cue found the bird, but a pale belly close to the backdrop colour was still lost. A close-up cat photo with a white face against a white wall defeated the mask entirely. A colour-based mask cannot separate low-contrast, soft-edged subjects.