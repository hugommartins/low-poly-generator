# Test strategy

Test approach for `lowpoly`, design choices, and coverage gaps. The CI pipeline is defined in `.github/workflows/`. Defects will be tracked in `BUGS.md`.

## 1. Objectives and scope

The product is a command-line tool and Python library converting photos into low-poly SVGs or PNGs.

```text
              ┌─> Smooth (bilateral + saturation) ──────────┐
Photo ────────┤                                             ├─> Colour per triangle ─> SVG / PNG
              └─> Canny edges ─> Points ─> Delaunay ────────┘          │                  ^
                                (grid, snapped to edges,                └─> Relief shading ┘
                                 + border anchors)                          (optional)
```

**Quality objectives.** Testing validates:

1. **Fidelity:** Output matches the original script for identical settings.
2. **Geometry:** Mesh is a valid triangulation covering the entire canvas.
3. **Determinism:** Identical input and seed yield identical output.
4. **I/O Safety:** Files read/written safely; no data loss or overwrites.
5. **Usability:** Invalid input produces specific, readable errors (no tracebacks).
6. **Plausibility:** Relief shading mimics physical light on a surface.
7. **Portability:** Objectives hold across operating systems and dependency versions.

**In scope:** 
- Pipeline stages
- Rendering
- File handling
- CLI
- Relief shading

**Out of scope:** 
- Subjective output aesthetics (evaluate via README samples). 

## 2. Risks and priorities

Test effort scales with anticipated risk.

| Risk | Impact | Mitigation Strategy | Priority |
|---|---|---|---|
| Unintended output mutations post-refactor | Feature regression; breaks baseline fidelity | Enforce live differential testing against original script | High |
| Output data loss or file overwrites | Destructive data loss | Implement strict output-handling and permission tests | High |
| Application crashes on malformed input | Confusing user experience | Execute file-handling and boundary validation tests | High |
| Mesh geometry features gaps or overlaps | Holes or double-painted canvas areas | Validate bounds with coverage and canvas coordinate tests | High |
| Non-deterministic output across executions | Irreproducible results | Enforce fixed-seed determinism tests | Medium |
| Color drift via float-to-integer casting | Unintended color shifts in flat areas | Validate rounding algorithms via property tests | Medium |
| Environment-specific execution failures | Portability regressions | Validate across exhaustive CI OS/dependency matrix | Medium |
| Physically implausible relief shading | Lighting artifacts and visual inversions | Validate shading rules via directional relief tests | Medium |

## 3. Test approach

### 3.1 Levels

| Level | Scope | Location |
|---|---|---|
| Unit | Single stages on small synthetic images | `CoreTests`, `ReliefTests` |
| Integration | CLI file I/O using bundled sample photos | `FileTests` |
| Property | Image-agnostic rules checked on generated inputs | `tests/test_properties.py` |
| Differential | Match original script SVG output | `tests/test_differential.py` |
| System smoke | Installed wheel execution in a clean environment | CI `package` job |
| Environment | Cross-OS, Python, and NumPy combinations | CI `test` job matrix |

### 3.2 Techniques

| Technique | Application |
|---|---|
| Boundary values | 1px/2x2 images, non-multiple grid sizes, zero jitter. |
| Equivalence classes | Unreadable files: missing, empty, wrong format, damaged, permission denied. |
| Property-based | Invariants over generated images (sizes 2-120, grid 3-60). Failures shrink toward flat images. |
| Differential | Live comparison against original script output in the identical environment. |
| Metamorphic | Invert depth + rotate light 180 degrees yields identical shading. |
| Mutation | Alter code to verify suite failure (planned for nightly pipeline). |

### 3.3 Test oracles

- **Exact:** Determinism, identical output with relief off, flat surface retaining color, mean mode rounding to nearest integer.
- **Invariant:** Triangle areas sum to image area, corners act as points, free points within jitter window, point count follows `2n - 2 - b`, no points inside circumcircles.
- **Directional:** Rightward slope with left light brightens result; right light darkens result.
- **Reference output:** Byte-for-byte comparison against original script. Intentional schema differences (e.g., `viewBox` headers) are rewritten pre-comparison to isolate polygon matching.

### 3.4 Test data

- **Synthetic images:** Predictable outputs (120x90 split, flat grey frame, horizontal ramp).
- **Sample photos:** Validation of execution and valid output generation.
- **Generated images:** Hypothesis profiles (`dev`: 200 examples; `ci`: 100 fixed-seed examples for reproducibility).

### 3.5 Test independence

Tests utilize fixed seeds, temporary directories, and zero network access. Tests isolate dependencies to `samples/` and `tests/reference/`.

## 4. Traceability: Requirements to tests

| ID | Requirement | Test Strategy |
|---|---|---|
| R1 | Output determined strictly by input, settings, and seed. | Determinism validation. |
| R2 | SVG is well-formed triangles. | Schema and geometry validation. |
| R3 | Mesh covers image without gaps/overlaps. | Boundary anchor and coverage checks. |
| R4 | Points land on detected edges. | Edge snapping validation. |
| R5 | PNG size and colors match specs. | Dimension and color checks. |
| R6 | Color modes execute safely; bad values rejected. | Color mode parameter validation. |
| R7 | Output matches original script (excluding `viewBox`). | Live differential comparison. |
| R8 | Specific errors for unreadable/invalid inputs. | Equivalence class file testing. |
| R9 | Safe file handling (folder creation, `~` expansion, no overwrite). | Output path and permission tests. |
| R10 | CLI processes formats correctly without tracebacks. | End-to-end CLI execution tests. |
| R11 | Default relief is off; causes zero change. | Baseline execution checks. |
| R12 | Relief obeys light direction, depth maps, and flags. | Physical shading validation. |
| R13 | Points stay within frame, unique, deterministic, bounded by jitter. | Point placement property tests. |
| R14 | Mesh remains a valid Delaunay triangulation. | Triangulation property tests. |
| R15 | One RGB color per triangle; files match dimensions. | Format consistency property tests. |
| R16 | Relief stays within bounds; inversions cancel out. | Metamorphic property tests. |
| R17 | Canvas coordinates equal mesh extents. | Coverage property tests. |
| R18 | Images under 2x2 pixels rejected clearly. | Minimum dimension boundary tests. |
| R19 | Mean color mode rounds to nearest integer. | Rounding strategy property tests. |

## 5. Environments and tooling

| Item | Detail |
|---|---|
| Operating systems | Linux, macOS (Apple Silicon/Intel), Windows |
| Python / NumPy | Python 3.9–3.13; NumPy 1.x and current |
| CI Jobs | `test` (matrix), `package` (build/smoke test), lint, dependency audit |
| Nightly job | Runs newest dependency releases to catch upstream breaks early |
| Tools | `unittest`, Hypothesis, `coverage`, mutation framework |

## 6. Defect handling and exit criteria

**Defect handling rules:**
- A fix requires a failing test prior to implementation and a passing test after.
- Intentional baseline output deviations require documentation and differential test updates.
- Post-fix, search the codebase for similar systemic patterns.

**Release exit criteria:**
- All tests pass across the CI matrix.
- Package installs cleanly and smoke test passes.
- Zero High-severity defects open.
- Lower-severity defects documented in `BUGS.md` and README limitations.

## 7. Planned work

1. **Relief Artefact Guard:** Implement strict failure thresholds for stepped depth maps.
2. **Coverage/Mutation Gates:** Enforce minimum CI thresholds.
3. **Expanded Metamorphic Tests:** Validate mirrored meshes and brightness-independent point placement.
4. **Input Fuzzing:** Expose edge cases (RGBA, 16-bit PNG, EXIF rotation, non-ASCII paths).
5. **Performance Benchmarking:** Validate runtime scaling against point counts.

## 8. Execution

```bash
pip install -e ".[test]"
python -m unittest discover -s tests -v
HYPOTHESIS_PROFILE=ci python -m unittest tests.test_properties -v

pip install coverage
coverage run --branch --source=src -m unittest discover -s tests
coverage report --show-missing
```