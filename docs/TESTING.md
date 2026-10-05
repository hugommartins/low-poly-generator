# Testing strategy

How `low-poly-generator` is tested and why. Defects found so far are in [BUG_LOG.md](BUG_LOG.md).

## 1. Scope

The project is a command-line tool and Python library that turns a photo into a low-poly SVG or PNG. The pipeline is: bilateral smoothing, saturation boost, Canny edges, one point per grid cell snapped to an edge, border anchors, Delaunay triangulation, one colour per triangle. An optional relief mode shades triangles as if they had height.

**In scope:** correctness of the geometry, determinism, output files, input handling, the command-line interface, the relief shading, and behaviour across operating systems and dependency versions.

**Out of scope:**
- Whether an output looks good. That is a judgement call made by looking at the samples in the README.

## 2. Risk-based priorities

| Risk | Impact | Where it is checked |
|---|---|---|
| Output changes silently after a refactor | The tool no longer does what the original script did | Golden-master and differential test (planned), manual `cmp` (done once) |
| Mesh has gaps or overlaps | Holes or double-painted areas in the picture | `test_triangles_cover_frame`, `test_frame_corners_present`; property tests (areas tile the frame, Euler count, empty circumcircle) |
| Output differs between runs | Cannot reproduce a result | `test_deterministic`, `test_seed_changes_output` |
| Bad input crashes or misleads | Confusing failures, as in BUG-004 | The file-handling tests (R8, R9) |
| Output is lost or overwritten | Data loss, as in BUG-002 and BUG-003 | Output-folder and same-stem tests |
| Works on one machine only | Fails for other users (NumPy 2, Intel Mac, Windows) | CI matrix |
| Relief shading is wrong | Artefacts or inverted lighting | The relief tests (R11, R12); BUG-009 is open |

## 3. Test levels

| Level | What it covers | Where |
|---|---|---|
| Unit | Single stages with small synthetic images: edges, point placement, colours, relief maths | `CoreTests`, `ReliefTests` in `tests/test_core.py` |
| Integration | File in, file out through `render_file` and the CLI, using the bundled sample photos | `FileTests` |
| System smoke | The installed wheel in a clean environment runs the real command and rejects bad input cleanly | `package` job in CI |
| Environment | Same suite on several OS, Python and NumPy combinations | `test` job matrix in CI |

Synthetic images (a 120x90 black and white split, a flat grey frame, a horizontal ramp) are used where the right answer can be worked out. The sample photos in `samples/inputs/` are used where only "it runs and produces valid output" can be asserted.

## 4. How correctness is judged

Image output has no single right answer, so the checks use different kinds of oracle:

- **Exact:** determinism, identical output with relief off, a flat surface keeping its colour.
- **Invariant:** the triangle areas sum to the image area; the four frame corners are always points; every point lies on an edge pixel or within the jitter window.
- **Directional:** with a slope rising to the right, light from the left brightens the result and light from the right darkens it.
- **Reference output:** the original script, via a byte-for-byte comparison (golden master, planned as an automatic test).

## 5. Requirements to tests

| ID | Requirement | Tests |
|---|---|---|
| R1 | Same input and settings give the same output; a different seed changes it | `test_deterministic`, `test_seed_changes_output` |
| R2 | The SVG is well-formed and made of triangles | `test_svg_is_valid_triangles` |
| R3 | The mesh covers the whole image with no gap or overlap | `test_frame_corners_present`, `test_triangles_cover_frame` |
| R4 | Points land on detected edges | `test_points_snap_to_edges` |
| R5 | PNG output has the right size and colours | `test_png_matches_size_and_colours` |
| R6 | Colour modes work and bad values are rejected | `test_mean_mode_runs`, `test_bad_color_mode` |
| R7 | Default output equals the original script's | Manual `cmp` on 3 cases; automatic golden test planned |
| R8 | Unreadable input gives a specific message: missing, empty, unrecognised, HEIC, truncated, permission denied, wrong extension | `test_missing_file`, `test_empty_file_is_named_as_empty`, `test_unrecognised_file_gives_clear_error`, `test_heic_by_content_is_reported_with_a_fix`, `test_truncated_jpeg_is_reported_as_damaged`, `test_permission_denied_message_mentions_macos_fix`, `test_extension_can_be_wrong_when_content_is_supported` |
| R9 | Output handling is safe: folder created, `~` expanded, no overwrite, bad extension rejected | `test_output_folder_is_created_for_png_and_svg`, `test_tilde_is_expanded`, `test_folder_mode_same_stem_does_not_overwrite`, `test_bad_output_extension` |
| R10 | The CLI writes SVG, PNG and whole folders, and reports errors without tracebacks | `test_cli_svg_png_and_folder`, `test_cli_errors_are_clean_messages` |
| R11 | Relief is off by default and changes nothing then | `test_off_by_default_and_identical` |
| R12 | Relief behaves physically: light direction matters, flat depth keeps colours, zero strength has no effect, depth maps are resized, flags are validated | `test_light_direction_matters`, `test_flat_depth_keeps_colours`, `test_shading_zero_is_no_effect`, `test_brightness_depth_runs_and_changes_colours`, `test_depth_map_file_is_resized`, `test_cli_relief_png_and_flag_checks`, `test_missing_depth_map` |

## 6. Gaps and planned work

1. **Golden master.** An automatic comparison with the original script's output. Hash comparison is fragile across OpenCV and SciPy builds, so on CI compare point and triangle counts exactly, or keep one golden file per platform.
2. **Property-based tests: extend.** Done: point placement, triangulation (empty circumcircle, `2n - 2 - b` triangles, exact area), output (colour per triangle, SVG and PNG shape) and relief (bounds, inversion symmetry). Next: mirrored-image and brightness metamorphic relations, and a stateful test of the CLI.
3. **Metamorphic tests.** A mirrored image gives a mirrored mesh; a larger `grid_size` gives fewer points; brightening the image keeps the points and changes only the colours.
4. **Input fuzzing.** 1x1 image, grayscale, RGBA, 16-bit PNG, EXIF-rotated, very large, non-ASCII path, read-only output folder.
5. **Known defects on record.** BUG-010 to BUG-012 have `expectedFailure` property tests. BUG-009 (relief spikes) has none yet; it needs a stepped depth map and a threshold on the shading range.
6. **Performance.** Time against point count, to confirm the run time grows sensibly.
7. **Coverage threshold and mutation score.** Set both after the first measured run.

## 7. How to run

```bash
pip install -e ".[test]"                       # adds hypothesis and coverage
python -m unittest discover -s tests -v        # the whole suite
HYPOTHESIS_PROFILE=ci python -m unittest tests.test_properties -v   # property tests, 100 fixed examples

pip install coverage
coverage run --branch --source=src -m unittest discover -s tests
coverage report --show-missing
```

Without installing the package, prefix the commands with `PYTHONPATH=src`.

## 8. Environments

CI runs the suite on Linux (Python 3.9 to 3.13, NumPy 1.x and current), macOS on Apple silicon, macOS on Intel, and Windows. A nightly job runs the newest release of every dependency to catch upstream breaks early; the NumPy 2 failure in BUG-008 is the kind of problem it exists for.

## 9. Defect handling

Each defect is recorded in [BUG_LOG.md](BUG_LOG.md) with severity, root cause, fix and the test that guards it. A fix is not finished until a test fails without it and passes with it.

## 10. Exit criteria for a release

- All tests pass on every CI matrix leg.
- The packaged wheel installs in a clean environment and the smoke test passes.
- No open defect rated High.
- Open defects of lower severity are listed in `BUG_LOG.md` and in the README's limitations section.