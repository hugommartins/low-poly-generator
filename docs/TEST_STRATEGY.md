# Testing strategy

How `low-poly-generator` is tested, why, and what is not covered yet. Defects found so far are in [BUG_LOG.md](BUG_LOG.md). The pipeline that runs these checks is described in `.github/workflows/`.

**Status at a glance**

| Area | State |
|---|---|
| Automated suite | 67 tests in the current repo, all `unittest`/`pytest`-run checks with Hypothesis installed. |
| Coverage | Reported by the local CI run (`coverage.xml` is generated in the repo root). |
| Property-based tests | 21 tests in `tests/test_properties.py` (Hypothesis), 3 of them expected failures for BUG-010 to BUG-012. |
| Metamorphic tests | 10 tests in `tests/test_metamorphic.py` (Hypothesis): 6 exact relations, 4 with stated tolerances. |
| Differential test against the original script | `tests/test_differential.py`, 3 tests: 4 photos x 4 settings plus odd-sized images, byte-for-byte. |
| CI | Present in [.github/workflows/ci.yml](../.github/workflows/ci.yml); the suite is exercised by the project workflow. |

## 1. Scope

The product is a command-line tool and Python library that turns a photo into a low-poly SVG or PNG.

```text
              ┌─> Smooth (bilateral + saturation) ──────────┐
Photo ────────┤                                             ├─> Colour per triangle ─> SVG / PNG
              └─> Canny edges ─> Points ─> Delaunay ────────┘           │                  ^
                                (grid, snapped to edges,                └─> Relief shading ┘
                                 + border anchors)                          (optional)
```

**In scope:** correctness of the geometry, determinism, output files, input handling, the command-line interface, the relief shading, and behaviour across operating systems and dependency versions.

**Out of scope:**
- Whether an output looks good. That is a judgement call made by looking at the samples in the README. ([but that does not mean I won't try it](CASE_STUDY.md))

## 2. Risk-based priorities

| Risk | Impact | Where it is checked |
|---|---|---|
| Output changes silently after a refactor | The tool no longer does what the original script did | Differential test against the original script (`tests/test_differential.py`) |
| Mesh has gaps or overlaps | Holes or double-painted areas in the picture | `test_triangles_cover_frame`, `test_frame_corners_present`; property tests (areas tile the frame, Euler count, empty circumcircle) |
| Output differs between runs | Cannot reproduce a result | `test_deterministic`, `test_seed_changes_output` |
| Bad input crashes or misleads | Confusing failures, as in BUG-004 | The file-handling tests (R8, R9) |
| Output is lost or overwritten | Data loss, as in BUG-002 and BUG-003 | Output-folder and same-stem tests |
| Works on one machine only | Fails for other users (NumPy 2, Intel Mac, Windows) | CI matrix |
| Relief shading is wrong | Artefacts or inverted lighting | The relief tests (R11, R12) and relief properties (R15); BUG-009 is open |

## 3. Test levels

| Level | What it covers | Where |
|---|---|---|
| Unit | Single stages with small synthetic images: edges, point placement, colours, relief maths | `CoreTests`, `ReliefTests` in `tests/test_core.py` |
| Integration | File in, file out through `render_file` and the CLI, using the bundled sample photos | `FileTests` |
| Property | Rules that hold for any image, checked on generated images and sizes | `tests/test_properties.py` |
| Metamorphic | How the output must change when the input changes in a known way (see section 6) | `tests/test_metamorphic.py` |
| Differential | Same SVG as the original script for the same settings | `tests/test_differential.py` |
| System smoke | The installed wheel in a clean environment runs the real command and rejects bad input cleanly | `package` job in CI |
| Environment | Same suite on several OS, Python and NumPy combinations | `test` job matrix in CI |

Synthetic images (a 120x90 black and white split, a flat grey frame, a horizontal ramp) are used where the right answer can be worked out. The sample photos in `samples/inputs/` are used where only "it runs and produces valid output" can be asserted.

## 4. How correctness is judged (test oracles)

Image output has no single right answer, so the checks use different kinds of oracle:

- **Exact:** determinism, identical output with relief off, a flat surface keeping its colour.
- **Invariant:** the triangle areas sum to the image area; the four frame corners are always points; every point lies on an edge pixel or within the jitter window.
- **Directional:** with a slope rising to the right, light from the left brightens the result and light from the right darkens it.
- **Relational (metamorphic):** two related runs must produce related outputs, for example mirroring the scene and the light mirrors the shading. No expected output is needed. See section 6.
- **Reference output:** the original script, kept in `tests/reference/` and run in the same environment as the package, compared byte for byte (differential test).

## 5. Requirements to tests

| ID | Requirement | Tests |
|---|---|---|
| R1 | Same input and settings give the same output; a different seed changes it | `test_deterministic`, `test_seed_changes_output` |
| R2 | The SVG is well-formed and made of triangles | `test_svg_is_valid_triangles` |
| R3 | The mesh covers the whole image with no gap or overlap | `test_frame_corners_present`, `test_triangles_cover_frame` |
| R4 | Points land on detected edges | `test_points_snap_to_edges` |
| R5 | PNG output has the right size and colours | `test_png_matches_size_and_colours` |
| R6 | Colour modes work and bad values are rejected | `test_mean_mode_runs`, `test_bad_color_mode` |
| R7 | Output equals the original script's for the same grid size and jitter | `test_samples_match_the_original_script`, `test_odd_sizes_match_the_original_script`, `test_the_comparison_can_fail` |
| R8 | Unreadable input gives a specific message: missing, empty, unrecognised, HEIC, truncated, permission denied, wrong extension | `test_missing_file`, `test_empty_file_is_named_as_empty`, `test_unrecognised_file_gives_clear_error`, `test_heic_by_content_is_reported_with_a_fix`, `test_truncated_jpeg_is_reported_as_damaged`, `test_permission_denied_message_mentions_macos_fix`, `test_extension_can_be_wrong_when_content_is_supported` |
| R9 | Output handling is safe: folder created, `~` expanded, no overwrite, bad extension rejected | `test_output_folder_is_created_for_png_and_svg`, `test_tilde_is_expanded`, `test_folder_mode_same_stem_does_not_overwrite`, `test_bad_output_extension` |
| R10 | The CLI writes SVG, PNG and whole folders, and reports errors without tracebacks | `test_cli_svg_png_and_folder`, `test_cli_errors_are_clean_messages` |
| R11 | Relief is off by default and changes nothing then | `test_off_by_default_and_identical` |
| R12 | Relief behaves physically: light direction matters, flat depth keeps colours, zero strength has no effect, depth maps are resized, flags are validated | `test_light_direction_matters`, `test_flat_depth_keeps_colours`, `test_shading_zero_is_no_effect`, `test_brightness_depth_runs_and_changes_colours`, `test_depth_map_file_is_resized`, `test_cli_relief_png_and_flag_checks`, `test_missing_depth_map` |
| R13 | Point placement obeys its rules for any image: inside the frame, unique, corners present, deterministic, within the jitter of a cell centre, no more than one per cell plus anchors | `PlacePointsProperties` (6 tests) |
| R14 | The triangulation is a valid Delaunay mesh: areas tile the frame exactly, no zero-area triangle, every point used, `2n - 2 - b` triangles, no point inside a circumcircle | `TriangulationProperties` (5 tests) |
| R15 | Colours and files are consistent: one RGB colour per triangle, a flat image gives one colour, SVG and PNG have the right shape | `OutputProperties` (7 passing tests) |
| R16 | Relief stays within its lighting bounds, zero shading changes nothing, inverted depth with the light turned 180 degrees gives the same shading | `ReliefProperties` (3 tests) |
| R17 | Open defects stay on record: edge strip, one-pixel images, mean-mode rounding | Three `expectedFailure` tests in `OutputProperties` (BUG-010, 011, 012) |
| R18 | Relief is the same picture under changes that must not matter: light angle plus 360 degrees, depth scaled and offset, a mirrored scene with a mirrored light | `ExactRelations` (3 tests) |
| R19 | Shading strength is linear; brightening a photo by a constant keeps the edges, points and triangles; transposing a photo transposes its edge map | `ExactRelations` (3 tests) |
| R20 | Under changes that preserve the content only approximately, the output stays within a stated tolerance: flips, red and blue swapped, image and grid doubled | `ToleratedRelations` (4 tests) |

## 6. Metamorphic tests

### What they are

A metamorphic test changes the input in a way whose effect on the output is known, runs the program on both, and checks that the two outputs are related in that way. It never needs to know the correct output. Example: mirror the scene and the light, and the shading of every triangle must mirror too.

### Why they matter for this product

- **There is no answer key.** For a photo nobody can say which mesh is right. Example tests only work on tiny synthetic images where the answer can be worked out by hand. Property tests check rules on one output at a time. The differential test only covers what the original script did, and the original has no relief mode. Relations are the one way to test relief and the whole pipeline on arbitrary images.
- **They catch defects that stay inside the rules.** A shading bug can leave every colour inside the lighting bounds and the mesh perfectly valid, and the picture is still wrong. The relation "mirror scene and light, get mirrored shading" fails on it. The same goes for a depth map that is no longer normalised, an edge threshold that drifts with brightness, shading that is not linear in its strength, and an angle that stops wrapping past 360.
- **They need no stored outputs.** There are no golden files to regenerate, and nothing depends on the OpenCV or SciPy build, so they run the same on every CI platform.
- **They state product intent in plain terms.** "Brightening a photo must not move the triangles" is a sentence a user or reviewer can check. Together the relations read as a specification of behaviour the product promises but never wrote down.
- **They scale with Hypothesis.** Every generated image is another test of the relation, including ones nobody would write by hand.

### The relations

| Relation | Kind | Tolerance and reason |
|---|---|---|
| Mirror points and depth left to right, light angle `a` becomes `360 - a`: shading mirrors | Exact | 1 colour level (rounding) |
| Light angle plus 360 degrees: same picture | Exact | 1 level |
| Depth `d` replaced by `k * d + c`: same picture | Exact | 1 level |
| Shading `s` lies on the line from shading 0 to shading 1 | Exact | 1 level. Dark images only, because the final clip at 255 would bend the line |
| Add a constant to every pixel: same edges, points and triangles | Exact | None. OpenCV's grey conversion weights sum to exactly 1, so every gradient is unchanged |
| Transpose the photo: the edge map transposes | Exact | None |
| Flip left to right or top to bottom: the edge map flips | Tolerated | Every edge pixel needs a partner within 1 px, with at most 1% (and at least 8 pixels) unmatched. OpenCV breaks ties between equal gradients by scan order, so a two-pixel-wide edge can land one column over |
| Swap blue and red: `smooth()` swaps | Tolerated | 12 colour levels (worst seen 9). Hue is stored in 8 bits, so the HSV round trip rounds differently |
| Double the image and the grid: triangle count stays close | Tolerated | 15% (worst seen 11%). The count follows the grid, not the content |

The tolerances were set by measuring the worst deviation over about 1,500 random images and adding margin. The reason sits next to each constant in the test file.

### Writing a new one

1. Pick a change to the input whose effect you can state in one sentence.
2. Try it on a few real inputs before writing the test.
3. Decide when it holds, and generate only those inputs. Leave a case out when the relation is meaningless there, instead of widening the tolerance.
4. Measure the worst deviation over many random inputs. Set the tolerance just above it and write the reason beside the constant.
5. Break the code on purpose and confirm that the test fails.

### Limits

- A bug that affects both runs the same way is invisible. If the light's y component had the wrong sign everywhere, the mirror relation would still hold. The directional example test (`test_light_direction_matters`) covers that, which is why the methods are used together.
- A tolerance can hide small real drift. The tolerated relations catch faults larger than the stated error, not smaller ones.
- The tests have not run with the real Hypothesis package yet. Only the stand-in was used here.

## 7. Gaps and planned work

1. **Golden file.** Not needed for the original script, because the differential test compares live output in one environment. A stored golden file would only add protection for features the original never had (relief, mean colour mode), and its bytes would differ across OpenCV and SciPy builds, so compare counts or keep one file per platform.
2. **Property-based tests: extend.** Done: point placement, triangulation (empty circumcircle, `2n - 2 - b` triangles, exact area), output (colour per triangle, SVG and PNG shape) and relief (bounds, inversion symmetry). Next: a stateful test of the CLI.
3. **Metamorphic tests: extend.** Ten exist (section 6). Candidates not built: larger `grid_size` gives fewer points (held on three images but is not guaranteed, because merged points can break it); a different seed gives a different mesh that still passes every structural property; a shifted crop of a photo gives the same edges away from the border.
4. **Input fuzzing.** 1x1 image, grayscale, RGBA, 16-bit PNG, EXIF-rotated, very large, non-ASCII path, read-only output folder.
5. **Known defects on record.** BUG-010 to BUG-012 have `expectedFailure` property tests. BUG-009 (relief spikes) has none yet; it needs a stepped depth map and a threshold on the shading range.
6. **Performance.** Time against point count, to confirm the run time grows sensibly.

## 8. How to run

```bash
pip install -e ".[test]"                      # adds hypothesis and coverage
python -m unittest discover -s tests -v        # the whole suite, including the differential test
HYPOTHESIS_PROFILE=ci python -m unittest tests.test_properties -v   # property tests, 100 fixed examples

pip install coverage
coverage run --branch --source=src -m unittest discover -s tests
coverage report --show-missing
```

Without installing the package, prefix the commands with `PYTHONPATH=src`. Without Hypothesis, `test_properties.py` and `test_metamorphic.py` are skipped as whole modules.

### Property-test profiles

`HYPOTHESIS_PROFILE` selects how the property and metamorphic tests run (defined in `tests/test_properties.py`; `test_metamorphic.py` imports it):

| Profile | Examples per test | Inputs | Used by |
|---|---|---|---|
| `dev` (default) | 200 | Random, different every run | Local runs |
| `ci` | 100 | Fixed (`derandomize`), same every run | CI |

CI uses fixed inputs so that a red build always means the code changed, and a failure reproduces on the next run. The count of 100 is Hypothesis's default and keeps the run short across the CI matrix. The 100 was chosen, not derived; raise it if the run stays fast.

The consequence is that CI re-checks the same cases and does not look for new bugs. Exploration happens locally with the default profile. Hypothesis saves a failing example in `.hypothesis/` (ignored by git) and replays it on the next run, so a failure found locally stays reproducible until fixed.

## 9. Environments

CI runs the suite on Linux (Python 3.9 to 3.13, NumPy 1.x and current), macOS on Apple silicon, macOS on Intel, and Windows. CI also runs a lint check and a dependency audit (both advisory), and builds the wheel for the smoke test. Each run installs the newest release of every dependency, so an upstream break shows up on the next push; the NumPy 2 failure in BUG-008 was found this way. There is no scheduled run: a break is seen only when something is pushed.

## 10. Defect handling

Each defect is recorded in [BUG_LOG.md](BUG_LOG.md) with severity, root cause, fix and the test that guards it. A fix is not finished until a test fails without it and passes with it.

## 11. Exit criteria for a release

- All tests pass on every CI matrix leg.
- The packaged wheel installs in a clean environment and the smoke test passes.
- No open defect rated High.
- Open defects of lower severity are listed in `BUG_LOG.md` and in the README's limitations section (BUG-009 to BUG-012 are today).