# Framing Policy Comparison

Date: 2026-11-24

Status: **Implemented and verified** in the backend. The tables below preserve
the original comparison against the pre-fix rule.

Documentation refreshed: 2026-11-25. The frontend consolidation does not change
this policy or rerun the recorded matrix. User-facing off-center advice now
lives in `frontend/components/photo-studio/photo-framing-help.tsx`; automatic
face centering remains the last tie-breaker, not the primary crop objective.
Current architecture and commands are documented in `README.md`.

## Recommendation

Use **clean-edge-first selection with gap ranking**, while keeping the current
largest-crop-first search and head-protection constraints.

At each candidate crop width:

1. Prefer positions where both edges have at least 90% foreground coverage across
   the lower 5% of the frame.
2. When none qualify, retain the existing continuous-shoulder-slope fallback.
3. Within that eligible set, minimize the larger bottom-edge gap, then the sum of
   both gaps.
4. Break remaining ties by retaining the most headroom, then centering the face.

This selects positions from each image's matte and face bounds. There is no
hardcoded 103-pixel shift. The original comparison used an isolated prototype;
the recommended rule is now implemented in `src/services/photo_framing.py`.

## Test Coverage

- **1,742 distinct framing cases**, each evaluated under five policies:
  **8,710 policy evaluations**.
- **1,547 synthetic cases**: seven shoulder/body outlines, two body lengths, two
  head sizes, four amounts of added headroom, off-center subjects, silhouette-only
  head guidance, and deliberately unsuitable head/face cases.
- **195 real-matte variants** from **four distinct portraits**. Javier contributes
  two separately inferred input crops; three other portraits contribute one each.
  Each base matte is tested with three headroom amounts and 13 aspect ratios.
- The 13 unique aspect ratios cover every ratio in the app's country-size table.
  Added-headroom real variants are padded/resized existing mattes, not 195
  independently inferred photographs.
- All 52 deliberately unsuitable synthetic face/head cases were rejected by every
  policy. Additional rejection counts include geometries that cannot meet the
  existing framing constraints.
- Source masks were read-only during evaluation.

## Real-Matte Results

Here, a bottom gap is a run of bottom-row matte pixels with alpha below 128.
Strict support means at least 90% of each edge's lower 5% band has alpha at
least 128. These are framing metrics, not a JPEG color or matting-quality audit.

| Policy | Accepted / 195 | No Bottom Gaps | Strict Lower-Band Support | Additional Width Loss |
|---|---:|---:|---:|---:|
| Original, topmost relaxed position | 195 | 156 | 133 | 0% |
| Clean-edge-first, then topmost | 195 | 192 | 192 | 0% |
| **Clean-edge-first with gap ranking** | **195** | **195** | **192** | **0%** |
| Gap ranking with up to 2% additional width loss to seek strict edges | 195 | 195 | 192 | 0% |
| Strict edges only, then topmost | 192 | 192 | 192 | 0% |

The recommended rule removes the 39 nonzero bottom-gap results produced by the
original rule, without new rejections or additional cropping in this matrix.
The three accepted frames without strict lower-band support are square variants
of the curly-haired portrait: their shoulder slopes reach both bottom edges, but
leave natural corners higher in the lower band. Strict-only selection rejects
these three rather than finding a head-safe strict frame.

For Javier's high-headroom square input, the recommended result is a
**905 x 905 source crop at top 103**, rather than top 0. The working-matte gaps
change from 21 pixels per side to zero. This is the same position as the earlier
inspected, foreground-color-recovered reposition-only JPEG control, whose
exported bottom gaps are zero.

## Synthetic Results

| Policy | Accepted / 1,547 | No Bottom Gaps | Gaps Over 1% of Width | Max Additional Width Loss |
|---|---:|---:|---:|---:|
| Original rule | 1,455 | 1,026 | 424 | 0% |
| Clean-edge-first, then topmost | 1,455 | 1,138 | 315 | 0% |
| **Clean-edge-first with gap ranking** | **1,455** | **1,248** | **206** | **0%** |
| Gap ranking with up to 2% additional width loss | 1,455 | 1,248 | 206 | 1.68% |
| Strict edges only, then topmost | 1,291 | 1,244 | 47 | 25.66% |

The recommended rule removes 222 additional synthetic bottom-gap results,
without increasing any measured gap, changing rejection decisions, or shrinking
the accepted crop widths.

The bounded-extra-crop option improves lower-band support in 16 synthetic cases
but does not improve the bottom-gap counts. Strict-only selection creates
164 additional synthetic rejections and shrinks 123 accepted crops, with up to
25.66% additional width loss. It also fails one existing regression assertion
and raises an error in another subcase of the natural-shoulder test.

These results favor gap ranking over both unnecessary extra cropping and a
blanket strict-edge requirement.

## Comparison-stage Verification

- Existing complete backend suite: **105 passed**.
- Complete backend suite with the recommended prototype patched into the test
  process: **105 passed**.
- Existing composition regressions under the recommended prototype: **19 passed**.
- Independent scalar position-search oracle: **102 checks passed**.
- Zero source-coverage, aspect-rounding, detected-head margin, headroom, or
  below-chin constraint violations across accepted matrix results.
- No new rejection decisions or increased bottom-gap fractions under the
  recommended policy.
- Recommended real-matrix framing time: approximately **4.3 ms p95** on this
  local run. This is not full inference latency or deployment performance.
- Production tracked-file diff remained empty during the comparison. No models,
  dependency versions, export settings, frontend code, or live backend behavior
  were changed at that stage.

## Implementation Verification

- Implemented strict-edge-first selection and bottom-gap ranking, preserving
  largest-crop-first search, head safeguards, and existing slope eligibility.
- Added explicit full-width penalties for empty bottom rows so their `argmax`
  boundaries cannot incorrectly indicate filled edges.
- Added three targeted regression tests. They failed against the original rule;
  the complete implemented backend suite now has **108 passing tests**.
- The production implementation matches the recorded winner in **all 1,742
  framing cases**, including crop dimensions, positions, acceptance, strict
  support, gaps, and constraint checks. Source masks remained read-only.
- Ruff lint and format checks passed for both changed Python files through
  isolated `uvx ruff`. No project dependency changes were needed.
- Restarted the confirmed project backend on port 8000. Both reconstructed
  Javier uploads returned HTTP 200, `image/jpeg`, and 602 x 602 dimensions.
- The high-headroom live JPEG has **zero bottom side gaps** and is byte-identical
  to the earlier safe same-width reposition control. The tight live JPEG remains
  byte-identical to its pre-fix output. The fixed high JPEG was visually inspected.
- Models, export settings, proportional scaling, and frontend code are unchanged.
  No bounded-extra-crop or strict-only alternative was implemented.
- At verification time, the collector was stopped and evidence retained. The
  backend was left running; this historical report does not assert current
  service availability.

## Limitations

This is a best fit for the stated preference to reposition before adding zoom,
not proof of border-free output on every photograph.

The recommended rule still leaves gaps greater than 1% of frame width in
206 accepted synthetic cases: 76 asymmetric, 75 slow-sloping, 47 tapered, and
8 ordinary sloping cases. Achieving stronger guarantees for these geometries
would require different cropping/rejection tradeoffs; this experiment does not
silently introduce them.

Head safety here means preserving the bounds reported by the existing detector
and matte heuristics. The tests do not establish anatomical completeness, valid
pose, official country acceptance, or correct masks for arbitrary uploads.
Matting accuracy, input quality, and cases with missing source pixels remain
separate limitations.

The three additional native portrait mattes and metadata were successfully
written, and collection-complete evidence was logged. However, that collection
process exited with the sandbox restriction on `/var/lib/libuuid/clock.txt`.
The subsequent framing matrices, regression suites, and oracle checks completed
with exit code 0. No new complete native JPEG-pipeline verification is claimed
for all 195 real-matte variants.

Ruff was not installed during the original comparison, so linting the temporary
comparison scripts was unavailable. The implemented production changes and
regression tests subsequently passed Ruff lint and format checks via `uvx`.

## Reproducibility

Temporary scripts, masks, and detailed JSON results are under:

`/tmp/passport-headroom-borders-20261124`

These are local, temporary evidence assets, not tracked reproduction fixtures;
they may not exist on another checkout or after temporary-directory cleanup.

- `candidate_framing.py`: isolated candidate implementation.
- `collect_portraits.py`: actual-model matte collection.
- `benchmark_policies.py`: matrices, metrics, and composition compatibility checks.
- `check_oracle.py`: independent scalar position-search checks.
- `run_candidate_suite.py`: complete backend regressions with the prototype.
- `matrix-synthetic.json` and `matrix-real.json`: per-case results and summaries.
- `verify_implemented.py` and `implemented-verification.json`: production parity
  against all recorded recommended-policy outcomes.
- `verify_live_fixed.py` and `live-fixed-verification.json`: post-fix live JPEG
  checks and byte parity.
- `javier-high-fixed-live.jpg` and `javier-tight-fixed-live.jpg`: live fixed outputs.
- `portrait-metadata.json`: source hashes, face bounds, and collection status.
- `trae-debug-log-headroom-borders.ndjson`: original investigation and collection
  evidence.

Run scripts with the repository's `.venv/bin/python`, `PYTHONPATH=src`, and the
repository as the working directory. The comparison runs require the recorded
temporary evidence assets to remain available. The original baseline is preserved
in the recorded matrix JSON; rerunning `benchmark_policies.py` now would use the
implemented rule as its production baseline, not recreate the original one.
