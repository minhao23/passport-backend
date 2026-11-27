# Debug Session: iphone-heif-decode

- **Status**: [OPEN]
- **progress_status**: analyzed
- **Experiment Date**: 2026-11-28
- **Issue**: An iPhone 16 Plus photo previews in the browser but processing reports that the backend cannot open it.
- **Project Root**: /Users/bytedance/Desktop/passport-backend
- **Evidence Directory**: /tmp/passport-iphone-heif-decode-20261127
- **Debug Server**: http://127.0.0.1:7777/event; healthy, metadata-only evidence collected.
- **Log File**: /tmp/passport-iphone-heif-decode-20261127/trae-debug-log-iphone-heif-decode.ndjson
- **Env File**: /tmp/passport-iphone-heif-decode-20261127/iphone-heif-decode.env

## Known Evidence

- Apple Photos labels the original HEIF, 3024 x 4032, approximately 1.4 MB.
- These reported original dimensions and size are below the application's limits.
- The original failing file and a captured failing HTTP request are unavailable.
- A Photos format label does not establish the bytes or MIME type submitted by the browser.
- The displayed message matches the backend's InvalidPhotoError.
- The user reports successful frontend preview and failure only after Generate.
- The user cannot reproduce the failure on an iPad.

## Experiment Setup

- Production application code was not changed.
- Temporary instrumentation wrapped the real decoder in an isolated Python process.
- The isolated service used the real FastAPI route, multipart handling, request limits,
  queue lifecycle, and image decoder. Only inference was replaced with decoded-image
  JPEG encoding; YOLO/MODNet and passport framing were not exercised.
- A separate Next.js production server forwarded browser requests to that service.
- All photo bytes stayed on this machine. Production access was limited to public
  page and JavaScript GET requests.
- Browser files were constructed by automation, not selected through a physical
  iPhone Photos/iCloud picker.

| Runtime                                         | Version                 |
| ----------------------------------------------- | ----------------------- |
| Chrome                                          | 158.0.8127.37           |
| Playwright WebKit on macOS                      | 27.2                    |
| Current Pillow / pillow-heif / libheif          | 13.0.0 / 1.9.0 / 1.23.7 |
| Minimum-supported pillow-heif / bundled libheif | 1.3.0 / 1.21.2          |

The seven real HEIF samples ranged from 12.2 to 18.0 megapixels. Two controlled
64 x 96 HEIFs had verified 10-bit and 12-bit depth with HDR/PQ color-profile
parameters. A JPEG control was also included. These controlled files are not
a substitute for an iPhone 16 photo with its actual auxiliary/gain-map metadata.

## Reproduction Steps

1. Inspect the publicly deployed frontend without uploading any personal photos.
2. Instrument frontend format decisions and backend decoder stages with metadata-only events.
3. Exercise available real HEIF samples, including correctly typed and misleadingly typed selections.
4. Compare local evidence with deployed code and documented decoder limitations.
5. Do not label the tester's root cause confirmed without its request or decoder exception.

## Hypotheses & Verification

| ID  | Hypothesis                                                                        | Likelihood | Effort | Expected Evidence                                                                                                                                        | Conclusion   |
| --- | --------------------------------------------------------------------------------- | ---------- | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| A   | The deployed HEIF codec cannot decode this file's encoding or auxiliary metadata. | Medium     | Medium | Both local decoder versions passed all intact samples; the failing file and deployed decoder exception remain unavailable.                               | INCONCLUSIVE |
| B   | A MIME/extension mismatch bypasses frontend HEIF conversion.                      | Medium     | Low    | WebKit previewed HEIF mislabeled JPEG/PNG/WebP and uploaded unchanged HEIF bytes. This is confirmed for controlled inputs, not for the tester's request. | CONFIRMED    |
| C   | The deployed frontend/backend differs from the current HEIF-capable source.       | Medium     | Low    | Current public frontend contains the converter; deployed backend versions and the tester's cached frontend remain unknown.                               | INCONCLUSIVE |
| D   | Upload/export altered or truncated the image bytes.                               | Low        | Medium | All 35 controlled requests arrived unchanged. Intentional JPEG truncation reproduced the message, but no real upload corruption was observed.            | INCONCLUSIVE |

## Results

### Browser Matrix

42 application cases completed, 21 in each engine.

| Outcome                                               | Chrome | WebKit |
| ----------------------------------------------------- | ------ | ------ |
| Successful preview, upload, and decoder-only response | 15     | 18     |
| Expected frontend rejection                           | 5      | 2      |
| Expected backend failure after deliberate truncation  | 1      | 1      |

- All seven real HEIFs and both controlled high-bit-depth HEIFs converted to real
  JPEG bytes and decoded successfully when labeled correctly.
- Empty MIME with a HEIF extension, uppercase extension, and HEIF MIME with a
  `.jpg` filename also converted successfully.
- HEIF bytes mislabeled as JPEG, PNG, or WebP failed before preview in Chrome.
- Those same mislabeled bytes previewed in WebKit and bypassed conversion.
  Generate submitted the original HEIF bytes with the misleading MIME type.
- The local backend correctly sniffed and decoded those HEIF bytes anyway.
  Therefore, conversion bypass alone did not reproduce the tester's full failure.
- `application/octet-stream` and `image/heif-sequence` were rejected during
  selection in both engines, which does not match the reported failure timing.
- Direct capability probes confirmed that Chrome could not natively open the
  sample, while WebKit could open it under both HEIF and JPEG MIME labels.

### Decoder And Transport

- Current and minimum-supported HEIF versions each decoded all seven real HEIFs,
  both verified high-bit-depth HEIFs, and the JPEG control.
- SHA-256 and byte counts matched between browser submission and backend input
  for all 35 Generate requests.
- Keeping the full preview but deliberately submitting only the first 32 JPEG
  bytes produced the exact displayed error in both engines. The underlying
  exception was `OSError: Truncated File Read`.
- Two separate HEIF truncations remained decodable to expected dimensions.
  Pixel equivalence was not checked; not every truncation produces this error.
- These results do not establish the behavior of the deployed Linux codec.

### Deployment Check

The current public frontend exposes HEIF/HEIC in its picker and includes the
HEIF preflight, opening state, JPEG encoding, and lazy fallback converter.
Constants and conversion logic are in different JavaScript chunks. An initial
probe requiring both tokens in one chunk returned no matches; this was a probe
limitation, not evidence that conversion was absent. The corrected inventory
confirmed both pieces.

This excludes a blanket claim that the current live frontend has no converter.
It does not identify the tester's cached version or deployed backend version.

## Log Evidence

The authoritative evidence is
`/tmp/passport-iphone-heif-decode-20261127/trae-debug-log-iphone-heif-decode.ndjson`.

| Lines   | Observation                                                                                           |
| ------- | ----------------------------------------------------------------------------------------------------- |
| 1-29    | Current codec versions and successful real HEIF decoding.                                             |
| 30-37   | Verified 10/12-bit input headers and successful RGB decoding.                                         |
| 240-246 | Correct HEIF label produces JPEG preview and uploaded JPEG bytes.                                     |
| 261-268 | Same file labeled JPEG previews as HEIF, skips conversion, uploads HEIF, and is decoded successfully. |
| 269-284 | PNG/WebP mislabels reproduce the same bypass.                                                         |
| 303-308 | Full preview, controlled 32-byte upload, underlying truncation exception, and exact public error.     |
| 309-319 | Minimum-supported HEIF codec versions and successful decoding.                                        |
| 320-323 | Native Chrome failure versus native WebKit success, including the JPEG mislabel.                      |
| 328     | Corrected public asset inventory confirms HEIF constants and converter in separate bundles.           |

Detailed case outputs and executable experiment harnesses are in the same
external evidence directory. No photo contents or EXIF were written to NDJSON.

## Comparative Conclusion

Changing only the declared MIME of the same intact HEIF demonstrates the gap:

| Controlled Input                   | WebKit Preview | Generate Payload | Local Decoder |
| ---------------------------------- | -------------- | ---------------- | ------------- |
| HEIF bytes, `image/heif`           | Converted JPEG | JPEG bytes       | Success       |
| Identical HEIF bytes, `image/jpeg` | Original HEIF  | HEIF bytes       | Success       |

The reproducible weakness is format detection, not a proven iPhone-specific
decoder root cause. There is no post-fix claim: this was an investigation, and
no production behavior was changed.

## Recommended Next Steps

1. Detect supported HEIF from file contents before choosing conversion, rather
   than trusting MIME/filename. Do not treat arbitrary MP4/AVIF `ftyp` containers
   as supported HEIF. Preserve dimension preflight and existing limits.
2. Record safe backend decoder diagnostics: actual format, byte count, codec
   versions, stage, and exception class/message. Exclude photo data, names, EXIF,
   and public stack traces.
3. Obtain one retry from the affected iPhone with its iOS version and browser.
   Compare Photos versus Files selection if feasible. The photo itself does not
   need to be shared when the decoder error and format diagnostics are available.

## Cleanup And Scope

- Temporary Next.js port 3120 and decoder port 8120 services are stopped.
- Browser contexts were closed; no experiment application process remains.
- No production source, dependencies, models, or limits changed.
- Temporary scripts, generated test images, runtime packages, and evidence stay
  outside the repository.
- The metadata collector and this record remain open because the original
  failing request has not been observed; no fix or resolution is claimed.

## Final Evidence Gate

- **Evidence Sources**: User screenshots and reported timing; source inspection;
  NDJSON lines 1-328; browser/direct/minimum-codec result files; public deployment assets.
- **progress_status**: analyzed
- **Hypothesis Conclusions**: A INCONCLUSIVE; B CONFIRMED for controlled inputs;
  C INCONCLUSIVE (current frontend absence excluded); D INCONCLUSIVE
  (no corruption observed in controlled requests).
- **Scope**: Investigation only. No behavioral fix is authorized or claimed.
