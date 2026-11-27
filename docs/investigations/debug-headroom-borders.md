# Debug Session: headroom-borders

Historical investigation: 2026-11-24. Documentation refreshed: 2026-11-25.
The frontend refactor does not change the backend fix or its recorded results.
Current crop guidance is in `frontend/components/photo-studio/photo-framing-help.tsx`;
startup and architecture are in `README.md`. Temporary evidence and service
states below describe the investigation, not current availability.

- **Status**: [RESOLVED]
- **progress_status**: verified
- **Issue**: The same portrait with extra space above the head produces lower side borders; a tighter input crop does not.
- **Project Root**: /Users/bytedance/Desktop/passport-backend
- **Evidence Source**: HTTP Debug Server; startup, health, and event probe succeeded
- **Debug Server (stopped)**: http://127.0.0.1:7777/event
- **Evidence Directory**: /tmp/passport-headroom-borders-20261124
- **Log File**: /tmp/passport-headroom-borders-20261124/trae-debug-log-headroom-borders.ndjson
- **Env File**: /tmp/passport-headroom-borders-20261124/headroom-borders.env

## Original Reproduction Steps
1. Run `/tmp/passport-headroom-borders-20261124/reproduce.py` with `PYTHONPATH=src`.
2. Compare a synthetic continuous shoulder silhouette at 400 x 560 with the identical mask cropped by 100 pixels at the top (400 x 460).
3. Trace the unchanged `plan_framing` function using `sys.settrace`; submit captured values to the external collector.
4. Export both to 602 x 602 JPEG, then export the high-headroom input with only its source crop repositioned downward by 38 pixels.
5. At this initial stage the original upload was unavailable. The continuation
   below used reconstructed crops from the matching JPG, not the exact PNG.

## Actual Portrait Continuation (Pre-fix)
- User supplied the filename `javier-cropped.png`.
- That filename was not found on Desktop or in a bounded Downloads search.
- Matching original found and visually inspected: `/Users/bytedance/Desktop/javier.jpg`, 960 x 1280, SHA-256 `a22b8cdbcbf1a85ea42c3464ffb9aeb58aba3b8b24e989542f6349bc7c7973de`.
- Replayed PNG crops from the matching JPG at `(0, 0, 960, 1086)` and `(0, 200, 960, 1086)`, approximating the screenshot proportions. These are reconstructed inputs, not the missing exact PNG.
- Used the actual trained YOLO, YuNet, MODNet, foreground-color recovery, framing, and JPEG export.
- Native replay wrote all outputs and log entries, but the command tool timed out afterward; a clean native command exit was not established.
- Both reconstructed inputs were subsequently submitted to the existing live backend. Both returned HTTP 200 and matched the traced native JPEGs byte-for-byte, providing clean end-to-end verification.
- No source image or backend behavior was modified.
- The comparison image was generated as an investigation artifact, not a
  shipping UI asset or mockup. See the temporary evidence directory for retained
  outputs; new verification captures must stay outside the repository.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Expected Signal | Conclusion |
|----|------------|------------|--------|-----------------|------------|
| A | Topmost-first selection keeps extra headroom and ends the crop at narrower shoulders. | High | Low | Lines 15, 17, 28-29: Javier's high input selects top 0; moving to top 103 at the same 905-pixel width removes the gaps. | CONFIRMED on matching portrait and synthetic control |
| B | The natural-slope exception permits visible lower side gaps. | High | Low | Lines 16, 18, 24, 26: high input accepted with 0% support and produces 12-pixel JPEG gaps; tight input has 100% support and no gaps. | CONFIRMED on matching portrait and synthetic control |
| C | Input cropping alters matting or face detection through bounded resizing, causing the borders. | Medium | Medium | Line 27: aligned masks have 99.695% opaque IoU; lines 28-29 remove gaps without changing the high-input matte or face guide. Small inference differences exist but are not needed to explain the borders. | REJECTED as the primary border cause for reconstructed Javier inputs |
| D | A stale or different local backend is serving the result. | Low | Low | Line 30: live high/tight JPEGs both match the current-source replay byte-for-byte. | REJECTED for the existing local backend and reconstructed inputs |

## Log Evidence
Source: `/tmp/passport-headroom-borders-20261124/trae-debug-log-headroom-borders.ndjson`.

| Case | Source crop | Headroom | Lower-edge coverage | Bottom gaps |
|------|-------------|----------|---------------------|-------------|
| High headroom | 400 x 400, top 0 | 140 pixels | 0%, 0% | 21, 21 pixels |
| Tight headroom | 400 x 400, top 0 | 40 pixels | 100%, 100% | 0, 0 pixels |
| Reposition-only control | 400 x 400, top 38 | 102 pixels | 90%, 90% | 0, 0 pixels |

- High-headroom JPEG bottom corners are pure white (line 4).
- Tight and reposition-only JPEG bottom corners are foreground RGB `[34, 55, 74]` (lines 7 and 8).
- The trace calls the existing source code without modifying any backend files.
- All 19 existing `test_photo_composition.py` tests pass. They cover headroom retention and slope acceptance but do not require strict-coverage alternatives to outrank relaxed candidates.

### Matching Javier Portrait
| Case | Working source crop | Working headroom | Strict lower-edge support | White pixels at each JPEG bottom edge |
|------|---------------------|------------------|---------------------------|---------------------------------------|
| High-headroom input | 905 x 905, top 0 | 225 pixels | 0%, 0% | 12, 12 |
| Tight input | 886 x 886, left 35, top 0 | 39 pixels | 100%, 100% | 0, 0 |
| Same-width reposition-only control | 905 x 905, top 103 | 122 pixels | At least 90%, 90% | 0, 0 |

- High-input face box: `(306, 346, 303, 368)`; head bounds `(272, 637, 225, 744)` (lines 13 and 15).
- High-input crop is accepted through the slope exception, which allows 91 pixels of gap at this width. Actual matte bottom gaps are 21 pixels per side; the exported near-white runs are 12 pixels per side (lines 16 and 18).
- Actual high-input matte supports a safer same-width crop at top 103. It preserves the full head and keeps 122 working pixels of headroom (lines 17 and 29).
- Mask comparison in original coordinates: opaque IoU `0.9969471626`; mean alpha difference `0.600937` on a 0-255 scale (line 27).
- Live JPEG SHA-256 parity:
  - High: `511812e3f09a8087f3868ed3e5eb7526f900696563c8a952d570ff01761ed64b`.
  - Tight: `c4f791a7a5895dcd311386757917309c821d47bc7720bf2161e5b1b57e1b211e`.
- The first live check used country as a form field and received request-validation HTTP 422. Correcting to the documented query parameter `/images/process?country=Brazil` produced HTTP 200 for both uploads. That initial 422 was a diagnostic request mistake, not a framing rejection.

## Pre-fix Verification Conclusion
Confirmed policy defect in both the synthetic control and reconstructed crops of the matching Javier original: `clean_left`/`clean_right` are relaxed by the natural-slope allowance (up to 10% of frame width), then `valid_tops[0]` picks the highest candidate. A cleaner same-width lower crop is not preferred.

This explains how empty space above the head can change visible shoulder corners without any change to the removal model. Keeping that headroom spends vertical frame space on background, so the bottom intersects narrower shoulder rows.

Recommended change at this stage: prefer positions satisfying strict edge support over slope-relaxed positions at each candidate width, then minimize the larger bottom gap and combined gaps before using headroom and face-centering tie-breakers. Retain relaxed corners only as a fallback when no strictly supported position exists at that width. The follow-up policy tests below refine the original strict-first recommendation.

No production fix or live post-fix verification had been performed at this stage. The repositioned export was a counterfactual control. The provided filename was not found, so source crops were reconstructed from `javier.jpg`; conclusions apply to those clearly identified inputs rather than claiming a byte-identical replay of the missing PNG. The user's subsequent request authorized a candidate test comparison, performed outside production code.

## Follow-up Policy Tests

- Full report: [framing-policy-test-results.md](../experiments/framing-policy-test-results.md).
- Five policies were evaluated on 1,742 framing cases: 1,547 synthetic cases and 195 real-matte variants from four source photos, across all 13 configured aspect ratios.
- Actual-model mattes for three additional portraits were written successfully, along with face metadata and collection-complete evidence at NDJSON lines 31-35.
- The native collection process subsequently exited nonzero with the sandbox restriction on `/var/lib/libuuid/clock.txt`. The framing matrices, regression suites, and independent oracle all exited 0.
- Recommended policy: strict-edge-first with bottom-gap ranking, retaining the largest accepted crop width and existing head safeguards.
- Original-rule real-matrix bottom-gap-free results: 156/195. Recommended prototype: 195/195, with no additional crop-width loss, new rejections, or detected-head constraint violations.
- Recommended synthetic bottom-gap-free results: 1,248/1,455 accepted, compared with 1,026/1,455 under the original rule.
- Remaining limitation: 206 accepted synthetic cases retain bottom gaps greater than 1% of frame width. The policy is not a universal border-free guarantee.
- Strict-only selection caused 164 additional synthetic rejections and three real-matrix rejections, with up to 25.66% additional crop-width loss among accepted synthetic cases.
- The up-to-2% extra-crop policy did not improve bottom-gap counts over the recommendation.
- Comparison-stage backend suite: 105 passed on the original code and 105 passed with the recommended prototype patched into the test process. Independent scalar oracle: 102 checks passed.
- Prototype and detailed results: `/tmp/passport-headroom-borders-20261124/candidate_framing.py`, `matrix-synthetic.json`, `matrix-real.json`, `check_oracle.py`, and `run_candidate_suite.py`.
- Temporary-script Ruff checks were unavailable during the comparison because Ruff was not installed.
- No tracked production files were modified during the comparison. Implementation followed the user's explicit request below.

## Implemented Fix and Post-fix Verification

- User authorized implementation of the recommended policy with "just implement them".
- `src/services/photo_framing.py` now saves strict lower-edge eligibility before applying the existing shoulder-slope fallback. At the largest accepted crop width, it prefers strict positions, then ranks by maximum bottom gap, combined gaps, retained headroom, and face centering.
- Empty bottom rows receive full-width gap penalties instead of being mistaken for filled edges by `argmax`.
- Models, proportional resizing, country dimensions, head safeguards, and slope-acceptance thresholds are unchanged. No extra-zoom policy or synthetic shoulder filling was introduced.
- Three regressions were added to `tests/test_photo_composition.py`, covering excess headroom, gap-ranked slope fallback, and strict-band positions with narrow or empty final rows. The regressions failed against the original behavior.
- Full implemented backend suite: **108 passed**.
- Production outcomes match the recorded recommended policy in **all 1,742 matrix cases**, including accepted dimensions, positions, gaps, strict support, and constraint checks. Source masks remained read-only.
- Ruff lint and format checks passed for both changed Python files using isolated `uvx ruff`; project dependencies were not changed.
- The verified project backend on port 8000 was restarted to activate the fix. Health returned `{"status":"ready"}`.
- Both reconstructed Javier inputs returned HTTP 200 with 602 x 602 JPEG output:
  - High headroom: bottom gaps `[0, 0]`, SHA-256 `0fa963dd714abd1cd1ecc3ae3d5c8cf71c42471d334200efe6400e8103ba0466`, byte-identical to the earlier same-width reposition-only control.
  - Tight input: bottom gaps `[0, 0]`, SHA-256 `c4f791a7a5895dcd311386757917309c821d47bc7720bf2161e5b1b57e1b211e`, byte-identical to the original live tight result.
- The high-headroom fixed JPEG was opened and visually inspected. The lower shoulder borders are absent.
- Verification files: `implemented-verification.json`, `live-fixed-verification.json`, `verify_implemented.py`, `verify_live_fixed.py`, and `javier-{high,tight}-fixed-live.jpg` in the evidence directory. Post-fix live evidence is recorded at NDJSON line 36.
- The temporary collector was stopped with SIGTERM after ownership verification.
  Evidence files were retained and the app backend was left running at that time.
- Limitations above remain: the exact requested PNG was unavailable, and the tested ranking is not a universal border-free or official-acceptance guarantee.

## Final Evidence Gate
- **Evidence Sources**: User screenshots; matching original JPG; external NDJSON lines 1-36; implemented `src/services/photo_framing.py`; original and post-fix live HTTP 200 responses with JPEG SHA-256 parity; inspected source portraits, comparison outputs, and fixed high-headroom JPEG; 1,742-case candidate matrix and implementation parity; 108 implemented backend tests; passing Ruff lint/format checks; 102 scalar-oracle checks
- **progress_status**: verified
- **Hypothesis Conclusions**: A CONFIRMED; B CONFIRMED; C REJECTED as primary cause; D REJECTED for the current local replay
- **Cleanup State**: No instrumentation was added to business code. Investigation
  resolved and temporary collector stopped; evidence retained. Backend was left
  running on port 8000 at verification time. Temporary assets may not survive
  cleanup or be available on other checkouts.
