# Bug log

Defects found while building and using `lowpoly`, with root cause, fix and the test that now guards each one.
Suite status at time of writing: 30 example-based tests (29 passed, 1 skipped as root) plus 21 property tests with 3 expected failures for BUG-010 to BUG-012.

Severity: **High** wrong or lost output, **Medium** wrong behaviour or misleading message, **Low** cosmetic or edge case.

## Summary

| ID | Title | Severity | Found by | Status | Guarded by |
|---|---|---|---|---|---|
| BUG-001 | Reimplementation diverged from the original script | High | Reviewer question | Fixed | Manual `cmp`; golden test proposed |
| BUG-002 | PNG write failed silently when output folder was missing | High | Found while testing | Fixed | `test_output_folder_is_created_for_png_and_svg` |
| BUG-003 | Folder mode overwrote files with the same name stem | High | Found while testing | Fixed | `test_folder_mode_same_stem_does_not_overwrite` |
| BUG-004 | Misleading error for a file that would not open | Medium | User report (macOS) | Fixed, not yet confirmed on the reporter's machine | Six tests, see entry |
| BUG-005 | `~` in paths was not expanded | Medium | User report (macOS) | Fixed | `test_tilde_is_expanded` |
| BUG-006 | Raw tracebacks shown for expected errors | Medium | Found while testing | Fixed | `test_cli_errors_are_clean_messages` |
| BUG-007 | Relief colours truncated instead of rounded | Medium | Test failure | Fixed | `test_flat_depth_keeps_colours` |
| BUG-008 | Coverage test crashed under NumPy 2 | Low | Test failure | Fixed | `test_triangles_cover_frame` |
| BUG-009 | Relief mode leaves dark and bright spikes at depth steps | Low | Visual inspection | Open, mitigated | None yet (see entry) |
| BUG-010 | PNG and SVG leave a one-pixel strip on the right and bottom edges | Medium | Property probe | Open | `test_a_flat_image_gives_a_flat_png` (expected failure) |
| BUG-011 | One-pixel-wide or tall image raises a raw `QhullError` | Low | Property probe | Open | `test_one_pixel_images_are_rejected_cleanly_or_rendered` (expected failure) |
| BUG-012 | Mean colour mode truncates instead of rounding | Medium | Property test run | Open | `test_a_flat_image_gives_triangles_of_that_one_colour_in_mean_mode` (expected failure) |

---

## BUG-001 Reimplementation diverged from the original script
- **Severity:** High. The "faithful" version did not produce the reference output.
- **Found by:** The reporter asked "Have you fully reverted the delaunay to the original script?"
- **Symptom:** Output differed from the original `border_uniform_low_poly`.
- **Root cause:** Five silent differences. Edge detection used a single-threshold Sobel instead of Canny with hysteresis. The bilateral filter was 5x5 instead of d=9, sigma 75/75. Saturation was scaled in luma space instead of HSV. Triangle colour was the mean of pixels instead of the centroid pixel. The default grid was 16 instead of 10.
- **Fix:** Rebuilt each stage to match the original. Verified byte-for-byte with `cmp` on the cat at grid 10 and 25 and on the portrait.
- **Regression guard:** Manual `cmp` only. An automated golden-master test is drafted but not yet in the repo.
- **Lesson:** A refactor needs an executable oracle, not a visual "looks the same".

## BUG-002 PNG output failed silently when the output folder was missing
- **Severity:** High. The command appeared to succeed and wrote nothing.
- **Root cause:** The return value of `cv2.imwrite` was not checked, and the parent folder was not created.
- **Fix:** Create the parent folder; raise an error if `imwrite` returns false.
- **Regression guard:** `test_output_folder_is_created_for_png_and_svg`.

## BUG-003 Folder mode overwrote files with the same stem
- **Severity:** High. Data loss.
- **Steps:** Put `a.jpg` and `a.png` in one folder and run folder mode.
- **Root cause:** Output name was built from the stem only, so both inputs wrote `a.svg`.
- **Fix:** On a collision, include the extension in the name (`a.png` becomes `a_png.svg`).
- **Regression guard:** `test_folder_mode_same_stem_does_not_overwrite`.

## BUG-004 Misleading error for a file that would not open
- **Severity:** Medium.
- **Found by:** The reporter, loading `~/Downloads/test.jpg` on macOS ("I know for sure that the image is there").
- **Symptom:** OpenCV printed a generic warning, then the tool claimed the file might be HEIC.
- **Root cause:** OpenCV uses one warning for "cannot open" and "unrecognised format", and the message assumed HEIC. The real cause on the reporter's machine has not been confirmed. Candidates: macOS privacy blocking Downloads, a different real format, or a 0-byte download.
- **Fix:** Read the bytes in Python and detect the format from the file content. Give a specific message for each case: missing, a folder, permission denied (with the macOS fix), empty, named unsupported format (HEIC/AVIF, with a `sips` hint), unrecognised content, damaged file. A wrong extension no longer matters when the content is supported.
- **Regression guard:** `test_missing_file`, `test_unrecognised_file_gives_clear_error`, `test_empty_file_is_named_as_empty`, `test_heic_by_content_is_reported_with_a_fix`, `test_extension_can_be_wrong_when_content_is_supported`, `test_truncated_jpeg_is_reported_as_damaged`, `test_permission_denied_message_mentions_macos_fix` (skipped as root).
- **Open:** The reporter has not said whether the file now loads. Needs confirmation on the original machine.

## BUG-005 `~` in paths was not expanded
- **Severity:** Medium. Found alongside BUG-004.
- **Root cause:** Paths were used as given, so a `~` that the shell did not expand (for example inside quotes) was treated as a literal folder name.
- **Fix:** Expand `~` for input and output.
- **Regression guard:** `test_tilde_is_expanded`.

## BUG-006 Raw tracebacks for expected errors
- **Severity:** Medium.
- **Root cause:** Expected failures (`FileNotFoundError`, `ValueError`, `OSError`) were not caught at the CLI.
- **Fix:** Catch them and print `lowpoly: error: <message>` with a non-zero exit code.
- **Regression guard:** `test_cli_errors_are_clean_messages`, `test_bad_output_extension`, `test_missing_depth_map`.

## BUG-007 Relief colours truncated instead of rounded
- **Severity:** Medium. A flat surface changed colour.
- **Found by:** `test_flat_depth_keeps_colours` failed.
- **Root cause:** Float colours were truncated when cast to `uint8` instead of rounded, so a flat surface came out slightly off its original colour.
- **Fix:** `np.rint` before the cast.
- **Regression guard:** `test_flat_depth_keeps_colours`.

## BUG-008 Coverage test crashed under NumPy 2
- **Severity:** Low. Test code, not product code.
- **Root cause:** `np.cross` on 2D vectors is removed in NumPy 2.
- **Fix:** Explicit 2D determinant in the test.
- **Regression guard:** `test_triangles_cover_frame` (also checks that triangle areas sum to the image area).
- **Lesson:** Run the suite on NumPy 1 and 2 in CI.

## BUG-009 Relief spikes at depth steps (open)
- **Severity:** Low. Visible artefact in `--relief` output.
- **Symptom:** Dark and bright spikes where the depth map has a sharp step, for example the figure `relief_dome`.
- **Root cause:** Large height differences between neighbouring vertices give near-vertical facet normals.
- **Mitigation:** Tilt is capped at 60 degrees. The spikes are reduced, not removed.
- **Suggested guard:** An `xfail(strict=True)` test on a stepped depth map, so the defect is on record and the suite fails loudly if someone fixes it without updating the test.

## BUG-010 PNG and SVG leave a one-pixel strip on the right and bottom edges (open)
- **Severity:** Medium. Every output has an unpainted strip.
- **Found by:** Random-image probe; the frame-coverage property passes because it measures the mesh, not the canvas.
- **Symptom:** On a flat image the PNG has a different colour in the last column and row. The SVG viewBox is `w x h` but points reach `w-1` and `h-1`.
- **Root cause:** Points are pixel indices, so the mesh spans `(w-1) x (h-1)`. The canvas and viewBox are `w x h`.
- **Suggested fix:** Scale the mesh to the canvas on output, or size the canvas `(w-1) x (h-1)`. Changing it alters output of the original script, so decide against BUG-001's oracle first.
- **Regression guard:** `test_a_flat_image_gives_a_flat_png`, marked `expectedFailure`. When the defect is fixed, the test "unexpectedly succeeds", which unittest reports as a failure; remove the marker then.

## BUG-011 One-pixel-wide or tall image raises a raw `QhullError` (open)
- **Severity:** Low. Edge case with a bad message.
- **Symptom:** A `1 x n` or `n x 1` image gives a traceback in the CLI instead of an error message.
- **Root cause:** All points are collinear, so Qhull cannot triangulate. The CLI catches only `FileNotFoundError`, `ValueError` and `OSError`; `QhullError` is none of these.
- **Suggested fix:** Reject images with a side under 2 pixels with a `ValueError` and a clear message (extends BUG-006).
- **Regression guard:** `test_one_pixel_images_are_rejected_cleanly_or_rendered` accepts either a clean `ValueError` or a rendered result, and marks the raw `QhullError` as `expectedFailure`.

## BUG-012 Mean colour mode truncates instead of rounding (open)
- **Severity:** Medium. Same class as BUG-007, in a different function.
- **Found by:** Property test run: a flat image in mean mode came out one level darker.
- **Root cause:** `triangle_colors` writes float means into a `uint8` array, which truncates. The mean of a flat colour 200 can come out 199.
- **Suggested fix:** `np.rint` before the cast, as in BUG-007.
- **Regression guard:** `test_a_flat_image_gives_triangles_of_that_one_colour_in_mean_mode`, marked `expectedFailure`.
- **Lesson:** A fix in one place (BUG-007) needs a search for the same pattern elsewhere.

---

## Observations that are not defects

- **Golden hashes depend on the environment.** Byte-exact SVG output can differ across OpenCV and SciPy builds. For CI on several platforms, compare point and triangle counts exactly, or keep one golden file per platform.
- **Neural depth was never tested.** No model weights or package access in the build environment, so that route was dropped from the project. Facts about PyTorch wheels and Intel Mac support came from memory and are unverified.
- **Browser demo defects (demo removed).** Seams and corner spurs from stroke colour spilling past cell corners, and a duplicate `cols` identifier in the JavaScript. The seam fix was never confirmed by the reporter.
- **Subject-aware experiment (artifact, deleted).** A mask built from one median border colour classed a dark bird as background. A border-colour model plus a focus cue found the bird, but a pale belly close to the backdrop colour was still lost. A close-up cat photo with a white face against a white wall defeated the mask entirely. Conclusion: a colour-based mask cannot separate low-contrast, soft-edged subjects.