# Quality baseline: design and validation

Report on test 6 of the [case study](CASE_STUDY.md): a stored-score check that fails when the sample photos' similarity to their source moves beyond a tolerance. It is built (`tests/test_quality_baseline.py`), fails the CI run on every environment, and was validated by injecting faults into the code. Terms such as SSIM, PSNR, baseline and noise floor are defined in the [glossary](CASE_STUDY.md#glossary).

## Result

Tolerance: 0.005 SSIM and 0.1 dB. Detection at this tolerance comes from a run of `scripts/validate_quality_baseline.py` at 0.005 SSIM / 0.1 dB (the script reads the tolerance from the same constants as the test). An earlier output of the same script, with the same score ranges, marked colours 1 level darker and the 1 and 2 px sampling offsets as missed; that matches the earlier tolerance of 0.01 SSIM / 0.3 dB, so it most likely predates the change.

- **Detects:** all 9 injected faults and all tested sizes. The smallest caught were colours 1 level darker (-0.19 dB, 1.9 times the tolerance), colour sampled 1 px off (+0.14 dB, 1.4 times) and 5 px of the right edge painted black. These thin margins are the weakest part of the result.
- **Two-sided:** a rise counts as well as a drop. Ignoring the saturation option raised SSIM on every photo and was caught only by the rise check.
- **False alarms:** 1 of 2 harmless changes. Changing the seed moved PSNR by +0.32 dB and by -0.11 dB across the 8 entries, both over the 0.1 dB tolerance. A bilateral window of 7 instead of 9 passes, by 0.001 SSIM and 0.02 dB.
- **In-sample:** the tolerance was tightened from 0.01 / 0.3 dB after the first validation missed the smallest sizes, so it is fitted to this injected set.
- **Existing tests:** without the differential test, they catch 3 of the 9 faults. The differential test fails on all 21 changes, harmless ones included (24 of its 24 cases for 20 changes, 23 of 24 for the 5 px black strip, where the portrait at grid 25 is unchanged). The 24 cases are the sample photos (4 photos at 4 grid and jitter settings) and noise images of odd sizes (4 sizes at 2 settings), and passes on the unmodified code.
- **Platform spread:** none between the stored baseline and Linux (Python 3.9 to 3.14), Windows or Intel macOS; Apple silicon differs by at most 0.0007 SSIM and 0.02 dB. The tolerance is 7 and 5 times larger. CI uploads the scores of every run.

## Design

| Item | Choice |
|---|---|
| Data | The four photos in `samples/inputs/`, loaded at 450 px, at the default seed |
| Settings | Default (grid 25) and grid 16: 8 entries |
| Stored | SSIM, PSNR and triangle count per entry, with the library versions that produced them (`tests/quality_baseline.json`) |
| Pass | Every SSIM within 0.005 and every PSNR within 0.1 dB of the stored value, in either direction |
| Tolerance source | Set from the fault-injection validation and the platform spread. It lies inside the seed noise range (SSIM sd 0.002 to 0.006, PSNR sd 0.1 to 0.3 dB), so it holds only with the seed pinned. A fixed-seed run repeats exactly on one machine, and the measured platform spread is smaller (see Platform spread). A change to random-number use or library versions can trip it |
| Triangle count | Stored and reported, not asserted. No injected fault was caught by it alone |
| Update | `python scripts/update_quality_baseline.py`, after reviewing the changed images |
| Without scikit-image | The scoring test is skipped; the comparison logic is still tested |
| CI | A failing comparison fails the test and the CI run on every leg. Each leg uploads its scores (`LOWPOLY_QUALITY_OUT`), and the `spread` job summarises them. Merge-blocking needs the `Required checks` job to be required in the repository's branch protection |

Baseline values (SSIM / PSNR in dB / triangles):

| Photo | Default (grid 25) | Grid 16 |
|---|---|---|
| cat | 0.464 / 20.30 / 485 | 0.513 / 21.29 / 1,109 |
| coffee | 0.391 / 16.50 / 490 | 0.435 / 17.89 / 1,131 |
| portrait | 0.468 / 15.42 / 717 | 0.529 / 16.96 / 1,652 |
| rocket | 0.711 / 22.83 / 489 | 0.727 / 23.55 / 1,126 |

Recorded on macOS 15.7 (Intel), Python 3.14.7, NumPy 2.5.3, OpenCV 5.0.0, SciPy 1.18.1 and scikit-image 0.26.0.

## Validation

`scripts/validate_quality_baseline.py` copies `src/`, `tests/` and `samples/` to a temporary directory, applies one change to the module under `src/lowpoly/` that contains the changed text, and records whether the existing tests fail and how far the 8 scores move. Ranges are the smallest and largest change over the 8 entries, from the run made at 0.01 SSIM / 0.3 dB. The Baseline column applies the current tolerance (0.005 / 0.1 dB) to those stored changes: a change counts as caught when any of the 8 scores moves by more than the tolerance.

**Faults** (the baseline fails; the output is wrong or has silently changed)

| Injected change | Existing tests, without the differential test | Baseline (0.005 / 0.1 dB) | SSIM change | PSNR change (dB) |
|---|---|---|---|---|
| Smoothing filter skipped | missed | caught (drop) | -0.019 to -0.005 | -0.76 to -0.10 |
| Red and blue swapped | missed | caught (drop) | -0.157 to -0.052 | -10.50 to -5.22 |
| Colour sampled at transposed coordinates | caught | caught (drop) | -0.281 to -0.083 | -9.56 to -4.91 |
| Points no longer search for an edge pixel | missed | caught (drop) | -0.050 to -0.008 | -1.45 to -0.43 |
| Canny run on the smoothed image | caught | caught (drop and rise) | -0.009 to +0.007 | -0.40 to +0.38 |
| Default Canny changed to 10/20 | missed | caught (drop) | -0.047 to -0.003 | -1.35 to -0.15 |
| Every other grid cell skipped | missed | caught (drop) | -0.091 to -0.017 | -2.96 to -1.58 |
| Border anchor points removed | caught | caught (drop) | -0.039 to -0.009 | -3.25 to -0.83 |
| Saturation option ignored | missed | caught (rise) | +0.015 to +0.120 | +0.49 to +1.90 |

**Smallest detectable size** (one fault at several sizes)

| Fault | Size | Baseline (0.005 / 0.1 dB) | SSIM change | PSNR change (dB) |
|---|---|---|---|---|
| Colours darker | 1 level | caught (-0.19 dB, 1.9 times) | -0.008 to -0.001 | -0.19 to -0.02 |
| | 2 levels | caught | -0.016 to -0.002 | -0.40 to -0.04 |
| | 4 levels | caught | -0.033 to -0.005 | -0.87 to -0.09 |
| | 8 levels | caught | -0.069 to -0.011 | -1.91 to -0.23 |
| Colour sampled off by | 1 px | caught (+0.14 dB, 1.4 times) | -0.001 to +0.002 | -0.08 to +0.14 |
| | 2 px | caught | -0.007 to +0.002 | -0.30 to +0.21 |
| | 3 px | caught | -0.024 to -0.000 | -0.57 to +0.18 |
| Right edge painted black | 5 px | caught | -0.002 to -0.001 | -0.34 to -0.04 |
| | 15 px | caught | -0.029 to -0.008 | -3.39 to -0.32 |
| | 30 px | caught | -0.048 to -0.022 | -4.85 to -1.02 |

**Harmless changes** (output differs, quality does not)

| Injected change | Baseline (0.005 / 0.1 dB) | SSIM change | PSNR change (dB) |
|---|---|---|---|
| Default seed 42 changed to 7 | flagged (PSNR +0.32 and -0.11 against 0.1) | +0.000 to +0.005 | -0.11 to +0.32 |
| Bilateral window 9 changed to 7 | not flagged (0.001 SSIM and 0.02 dB below the tolerance) | -0.004 to -0.001 | -0.08 to -0.01 |

Reading:
- The tolerance sets the smallest detectable fault: about 0.1 dB or 0.005 SSIM on a photo. Of the sizes tried, the smallest (1 level darker, 1 px sampling offset) are caught with margins of 1.9 and 1.4 times, so a slightly different platform or library could move them across the line. Sizes below those were not tried.
- Faults that act on the mesh or the colours move SSIM and PSNR together. The 2 px shift moves PSNR by -0.30 dB, 3 times the tolerance.
- A change that re-randomises the points (a new seed, or any change in how random numbers are used) moves scores by about the noise floor, so it trips the tolerance. Such a change alters the output anyway, so the baseline is reviewed and regenerated.
- A prototype of the relation checks (tests 1, 2 and 4 of the [case study](CASE_STUDY.md); not in the repository) caught 6 of 12 injected faults, all of which the baseline also caught. The list of 12 is not defined here, so the two counts are not comparable.
- The existing tests that are not the differential test (example, property and metamorphic tests, all run) catch 3 of the 9 faults: a transposed sample, Canny run on the smoothed image, and missing anchors. They also fail on colours 1 level darker and on every size of the black strip. They miss the smoothing, colour-order, edge-search, Canny-threshold, density and saturation faults. The differential test fails on every change but cannot tell a fault from an intended change; the baseline can, within the tolerance. The 21 differential results were produced by running `tests/test_differential.py` on each change; the other columns come from the validation run.

## Platform spread

The baseline test ran on nine CI environments, and each leg's scores were compared with the stored baseline, which was recorded on macOS 15.7 (Intel).

| Environment | Libraries | Difference from the baseline |
|---|---|---|
| Linux, Python 3.9, 3.10, 3.11, 3.12, 3.13 and 3.14 | NumPy 1.26 to 2.5, OpenCV 4.11 and 5.0, SciPy 1.13 to 1.18, scikit-image 0.24 to 0.26 | None: every SSIM, PSNR and triangle count is equal |
| Windows, Python 3.12 | NumPy 2.5, OpenCV 5.0, SciPy 1.18, scikit-image 0.26 | None |
| macOS 15, Intel, Python 3.12 | Same as Windows | None |
| macOS, Apple silicon, Python 3.12 | Same as Windows | Up to 0.0007 SSIM and 0.02 dB |

Apple silicon against the baseline (SSIM / PSNR in dB):

| Photo | Default (grid 25) | Grid 16 |
|---|---|---|
| cat | +0.0001 / +0.01 | -0.0001 / 0.00 |
| coffee | -0.0002 / -0.01 | +0.0001 / -0.01 |
| portrait | 0.0000 / 0.00 | -0.0007 / -0.01 |
| rocket | 0.0000 / 0.00 | +0.0004 / +0.02 |

- **Equality:** "equal" means the stored scores match to 4 decimals for SSIM and 2 for dB.
- **Triangle counts** are equal everywhere. This suggests point placement does not depend on the platform and the difference is in the colours; point coordinates were not compared, so it is an inference.
- **Libraries:** the six Linux legs differ in Python, NumPy, OpenCV, SciPy and scikit-image versions and give identical scores, and the Apple silicon leg uses the same library versions as the Windows and Intel macOS legs. The only leg that differs is Apple silicon, so the difference is attributed to the build; this is inferred from library versions, not tested.
- **Margin:** the largest difference is 0.0007 SSIM and 0.02 dB, against tolerances of 0.005 SSIM and 0.1 dB, 7 and 5 times larger.

**What the tolerance could be.** The tolerance was first set at 0.01 SSIM / 0.3 dB from the seed noise floor, before the platform spread was known, then tightened after the validation missed the smallest sizes. Applying other tolerances to the validation above (a change counts as caught when any of the 8 scores moves by more than the tolerance):

| SSIM / PSNR tolerance | Faults and sizes missed | Harmless changes flagged | Margin over the spread |
|---|---|---|---|
| 0.01 / 0.3 dB (before) | colours 1 level darker, shifts of 1 and 2 px | seed | 14 / 15 times |
| 0.005 / 0.1 dB (now) | none | seed | 7 / 5 times |
| 0.003 / 0.05 dB | none | seed, bilateral window | 4 / 2.5 times |

The seed change is flagged by every setting, because it changes the output. The measurement covers nine environments and one run each; the CI installs the newest release of every dependency, so a later release can move the scores.

## Limits

- Nine faults, three faults at several sizes (10 variants) and two harmless changes, chosen by the author who knows the code. The tolerance was tightened after the first validation missed some of them, so the detection is in-sample and the detection rate is not a general estimate.
- Detection at 0.005 SSIM / 0.1 dB comes from a single run of the validation script. The other tolerances in the table above are applied to the same score ranges, not re-run.
- Four photos, one machine, one library version set for the baseline values and the validation numbers (see the environment under Design). The platform comparison covers nine environments, one run each.
- The test that fails on colours 1 level darker was not identified; the validation records how many existing tests fail, not which.
- The check sees what SSIM and PSNR see. Faults smaller than the smallest tested sizes (1 level, 1 px, 5 px of black edge) were not tried.
- It says nothing about which output looks better.

## Using it

```bash
pip install -e ".[test]"                                   # adds scikit-image
python -m unittest tests.test_quality_baseline -v          # run the check
python scripts/update_quality_baseline.py                  # regenerate after a reviewed output change
python scripts/validate_quality_baseline.py --markdown     # repeat the fault-injection validation
```

To compare the platforms again, download the `quality-scores-*` artifacts of a CI run (`gh run download RUN_ID --pattern 'quality-scores-*' -D scores`) and run `python scripts/quality_spread.py scores`. Each CI leg also prints its scores in the run summary, and the `spread` job tabulates them across the legs. To run the test without failing on a mismatch, set `LOWPOLY_QUALITY_MODE=report` locally.