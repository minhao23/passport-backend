# Passport Studio

A monorepo containing the Python/FastAPI image processor and a Next.js
App Router frontend. Image-processing calculations are unchanged; expected
photo failures now use typed exceptions and user-facing error codes.

## Repository

```text
frontend/          Next.js + React + TypeScript landing page
src/               FastAPI backend and image processing
best.pt            Trained YOLO checkpoint
requirements.txt   Existing Python dependencies
package.json       npm workspace and frontend scripts
```

## Local development

Use Node.js 20.9+ (a current LTS release is recommended) and Python 3.11.
Run all commands below from the repository root.

### 1. Start the Python backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm run dev:backend
```

Alternatively, with `uv` installed, create the environment with
`uv venv --python 3.11 .venv` and install with
`uv pip install --python .venv/bin/python -r requirements.txt`.
`npm run dev:backend` uses that local environment directly.
It stores downloaded models in `.venv/model-cache` and Ultralytics settings
in `.venv/ultralytics`, avoiding writes to global configuration directories.
Set `U2NET_HOME` or `YOLO_CONFIG_DIR` to use an existing cache instead.

The requirements include `rembg[cpu]` and Pillow. The first launch downloads
the approximately 1 GB BiRefNet portrait model and takes longer than subsequent launches. Keep
`best.pt` at the repository root; its path is resolved from the backend source,
independent of the working directory. Wait for application startup to finish before generating.
FastAPI's interactive API documentation is at http://127.0.0.1:8000/docs.
Once both models have loaded, http://127.0.0.1:8000/health returns
`{"status":"ready"}`.

### 2. Start Next.js in a second terminal

```bash
npm ci
cp frontend/.env.example frontend/.env.local
npm run dev
```

Open http://localhost:3000. Select a country, upload a JPG, PNG, or WebP
of up to 10 MB, generate a photo, and download the resulting JPEG.
The original upload is previewed separately from the generated result.
Changing the country or upload clears the previous result.

After selection, use **Change photo** below Generate or beside the original
preview to choose a replacement. Invalid replacements leave the current photo
intact. **Remove photo** returns to the upload state.

During generation, **Cancel processing** keeps the original photo available
for replacement or retry and discards any late response. The proxy forwards
the disconnect to FastAPI, which checks for cancellation between processing
stages. A native model inference already in progress finishes its current
call before stopping; cancellation does not forcibly kill the shared model.
Restart the backend after updating it to enable these cancellation checkpoints.

`BACKEND_URL` is server-only and defaults to `http://127.0.0.1:8000`.
Restart Next.js after changing it. The browser sends multipart requests to
`/api/process`; this Next.js route forwards the file to
`POST /images/process?country=...` and streams the JPEG back.
This avoids browser CORS configuration and keeps the backend address private.

### Frontend startup recovery

Run frontend commands from a branch containing the root `package.json`,
`package-lock.json`, and `frontend/package.json`. Generated folders left behind
after switching to a backend-only branch do not include the frontend source.

If `npm ls --workspace frontend --depth=0` reports missing or invalid packages,
stop the frontend server and run `npm ci` from the repository root. This
reinstalls the versions recorded in the lockfile.

If Next.js reports `TurbopackInternalError` with a missing `.sst` cache file,
stop the frontend server before moving its generated cache aside:

```bash
mv frontend/.next "$(mktemp -d /tmp/passport-next-cache.XXXXXX)/next"
npm run dev
```

Next.js rebuilds the cache on startup. Keep `node_modules/` and `.next/`
ignored by Git; neither belongs in a commit.

## Processing errors

FastAPI returns JSON with `code` and `detail` for processing failures:

| Code | Status | Meaning |
| --- | --- | --- |
| `PHOTO_ISSUE` | 400 or 422 | Invalid image, uncertain detection, or unusable subject mask |
| `PERSON_NOT_DETECTED` | 422 | No detection or the detected class is not the target subject |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected processing failure; details are logged server-side |
| `INVALID_COUNTRY` | 400 | Unsupported country |

The Next.js proxy keeps these categories and adds a display title. Connection,
timeout, unexpected response, and unknown server errors use
`INTERNAL_SERVER_ERROR` with status 502 or 504. Frontend file-size validation
uses `PHOTO_ISSUE` with status 413. Users receive photo guidance for input issues
and retry guidance for service issues, without private exception details.
Restart the Python backend to enable the new response codes. The proxy also
recognizes the original backend's known detection/decode error messages.

## Checks and production

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
npm run typecheck
npm run build
npm run start
```

Deploy the Next.js app as a Node.js service, not a static export. Deploy FastAPI
separately and set `BACKEND_URL` to its reachable address. Allow at least three
minutes for inference requests and configure infrastructure upload limits for
10 MB files plus multipart overhead. Hosted serverless providers may impose
smaller request limits or execution timeouts; use a long-running Node service
or adapt the upload architecture for those providers. This frontend validates
files but does not add authentication, rate limiting, or resource limits to
the Python service.

## Photo requirements and assets

Country names and dimensions in `frontend/lib/countries.ts` mirror
`src/utils/passport_sizes.py`; update both if the backend list changes.
The output uses a white background and the listed dimensions. The current
processor does not verify all country-specific passport rules or guarantee
acceptance. Always check the issuing authority's latest rules, including
restrictions on digitally edited photos.

User previews use local object URLs. Google Fonts supplies the page fonts, with local sans-serif
fallbacks if unavailable.
