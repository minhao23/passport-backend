# Passport Studio

A monorepo containing the Python/FastAPI image processor and a Next.js
App Router frontend. Uploads and processing capacity are bounded; expected
photo failures use typed exceptions and user-facing error codes.

## Repository

```text
frontend/          Next.js + React + TypeScript landing page
src/               FastAPI backend and image processing
best.pt            Trained YOLO checkpoint
requirements.txt   Existing Python dependencies
package.json       npm workspace and frontend scripts
Dockerfile.backend Backend-only production image
Dockerfile.frontend Frontend-only production image
```

### Frontend structure

`frontend/app/page.tsx` delegates to the Server Component
`components/passport-page.tsx`, which contains the header, interactive studio,
submission warning/examples, and contact-only footer.

`components/photo-studio/` keeps the interactive UI and state together:

| Module | Responsibility |
| --- | --- |
| `photo-studio.tsx` | Hero/workspace composition, error feedback, crop opening |
| `use-photo-studio.ts` | Selection, validation, requests, cancellation, object URLs |
| `photo-upload-form.tsx` | Country selection, file picker/drop, replacement |
| `photo-workspace.tsx` | Previews, result details, desktop/phone preparation tips |
| `photo-processing-actions.tsx` | Shared Generate/Cancel buttons and local action focus |
| `photo-framing-help.tsx` | Optional result advice and centering animation |
| `photo-crop-modal.tsx` | On-demand rectangular crop editor |

Small single-owner components are combined with their owners instead of split
into extra files. Styles stay beside their components; `app/globals.css` retains
tokens, shared controls, and page-wide rules. Shared countries, errors, limits,
crop geometry, and downloads remain in `frontend/lib/`; the server-side proxy
remains in `app/api/process/route.ts`. The comparison component/assets are unchanged
by these structural refactors.

Run `npm run format` to format frontend TypeScript, TSX, and CSS, or
`npm run format:check` to check formatting without changing files.

Double-click a selected photo on desktop, or tap it on a phone, to open the
rectangular crop editor. Keyboard users can focus it and press Enter or Space.
The editor and crop library load only when needed.
**Save crop** updates the preview and the photo used for generation;
Cancel or Escape leaves it unchanged. Reset restores the full original on save.
The original stays in local state for re-cropping without repeated compression.
Cropping uses original-resolution pixels and lossless PNG export, with the same
10 MB upload limit. Nothing is sent until **Generate passport photo** is clicked.
The modal lives in `components/photo-studio/photo-crop-modal.tsx`; pixel geometry
and export live in `lib/photo-crop.ts`. Crop/export and download regression checks
share `tests/frontend_photo_utils.test.mjs`.

Each successful generation automatically starts a JPEG download. The result
panel keeps country and photo size, with a **Download JPEG** button for saving
again or when the browser blocks automatic downloads. Browser settings determine
whether a Save dialog appears. Re-rendering, cropping, cancelling, and failed
requests do not start downloads. The download helper and shared filename live in
`lib/photo-download.ts`; run `node --test tests/frontend_photo_utils.test.mjs` for
the combined utility checks.

Phones at widths up to 600px show one preview at a time, with Original/Result
switching, tap-to-crop, full-width actions, and initially closed Photo tips.
Desktop keeps the paired previews and double-click crop interaction.

Completed details read: country/dimensions, Download JPEG, authority reminder,
then **Not happy with the framing?**. This initially closed disclosure contains
crop advice and common issues, including centering the face using the original
photo's crop. Its CSS/Lucide diagram repeats every three seconds without manual
playback controls; offscreen/hidden-tab playback pauses, and reduced motion shows
a centered still. A new result starts closed.

The large preparation panel and dead Photo guide navigation are removed. The
separate acceptance warning remains. **View photo examples** displays
`assets/sample_rules.jpg` inline, centered up to 653px wide, with only
`taken from: Singapore ICA.` above it. There is no image popup or full-image link.
The footer contains only **Contact me**, linking to `https://minhao.dev/home`.
Future mockups must be runnable HTML; keep verification screenshots outside the
repository. Product constraints and current styling live in `frontend/PRODUCT.md`
and `frontend/DESIGN.md`.

### Backend structure

`src/main.py` only configures the app, middleware, and startup lifespan.
`src/api.py` contains the health and photo routes, plus the shared public error
responses. `src/request_limits.py` bounds uploads before multipart parsing.

`src/services/image_processor.py` composes the image pipeline. Its stages live
in `utils/image_loading.py`, `services/segmentation.py`, `services/head_framing.py`,
`services/photo_framing.py`, and `services/photo_composition.py`.
`services/model_runtime.py` owns reusable segmentation models, the detector lock,
and the CPU ONNX session options. `services/head_framing.py` reuses the separate
face detector under its own lock. Native inference imports are deferred until
startup or processing; `services/modnet_session.py` stays standalone for Docker's
cached model-download layer.
`services/photo_requests.py` manages queue waits, disconnects,
and cancellation, while `services/processing_jobs.py` bounds admission and
native work. Image-header preflight stays with its decoder in
`utils/image_loading.py`. Shared limits and country sizes remain in `src/utils/`;
public error classes remain in `src/errors/`, with no legacy import shim.

The current pipeline uses the trained YOLO checkpoint, YuNet face guidance, and
MODNet portrait matting through `rembg`. Structural consolidation preserves the
models, formulas, limits, and HTTP contracts. The Uvicorn target remains `main:app`
with `--app-dir src`.

Python formatting and linting use the pinned Ruff development dependency:

```bash
python -m pip install -r requirements-dev.txt
python -m ruff format src tests
python -m ruff check src tests
```

Run these in the activated `.venv` after installing the runtime requirements.
For a `uv`-created environment without pip, use
`uv pip install --python .venv/bin/python -r requirements-dev.txt`.
Use `python -m ruff format --check src tests` for a read-only formatting check.
Ruff checks imports, common Python errors, unsafe patterns, and Python 3.11
syntax; its configuration lives in `pyproject.toml`. Production Docker images
continue to install only `requirements.txt`.

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

The requirements include `rembg[cpu]` and Pillow. The first local launch downloads
the MODNet portrait-matting model and takes longer than subsequent launches. Docker
bundles its checksum-verified weights during the build, not during requests. Keep
`best.pt` at the repository root; its path is resolved from the backend source,
independent of the working directory. Wait for application startup to finish before generating.
FastAPI's interactive API documentation is at http://127.0.0.1:8000/docs.
Once startup completes, http://127.0.0.1:8000/health returns
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
`frontend/next.config.ts` also allows `127.0.0.1` as a development origin, so
http://127.0.0.1:3000 receives the hydrated upload controls too.
Uploads must also be at most 20 megapixels, with neither side exceeding
10,000 pixels. Accepted images are reduced proportionally to a maximum
1,024-pixel working side before model processing. Large JPEGs are downsampled
during decoding where possible, rather than allocating their full-resolution
RGB pixels first. PNG and WebP still require a full decode within the source
dimension limits. WebP must be a still image;
its container and bitstream dimensions are checked before opening a decoder.

After selection, use **Change photo** below Generate or beside the original
preview to choose a replacement. Invalid replacements leave the current photo
intact. **Remove photo** returns to the upload state.

During generation, **Cancel** keeps the original photo, crop, and country available
for replacement or retry and discards any late response. The proxy forwards
the disconnect to FastAPI. A waiting photo is removed from the queue without
running the model. For an active photo, FastAPI checks for cancellation between
processing stages. A native model inference already in progress finishes its current
call before stopping; cancellation does not forcibly kill the shared model.

`BACKEND_URL` is server-only and defaults to `http://127.0.0.1:8000`.
Restart Next.js after changing it. The browser sends multipart requests to
`/api/process`; this Next.js route forwards the file to
`POST /images/process?country=...` and streams the JPEG back.
This avoids browser-to-FastAPI processing CORS and keeps `BACKEND_URL` out of
the browser bundle. It does not authenticate or protect a publicly exposed backend.

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

FastAPI returns JSON with `code` and `detail` for processing failures. Framing
failures also include a `tips` list, shown as two bullets beneath the explanation:
adjust the crop, or take a new photo with more of both shoulders visible.

| Code | Status | Meaning |
| --- | --- | --- |
| `PHOTO_ISSUE` | 400 or 422 | Invalid image, uncertain detection, or unusable subject mask |
| `PERSON_NOT_DETECTED` | 422 | No detection or the detected class is not the target subject |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected processing failure; details are logged server-side |
| `INVALID_COUNTRY` | 400 | Unsupported country |
| `PHOTO_ISSUE` | 413 | File, total request, or decoded dimensions exceed limits |
| `PHOTO_ISSUE` | 408 | Upload did not finish within 60 seconds |
| `SERVICE_BUSY` | 503 | Upload/queue capacity is full, or queue wait exceeded 180 seconds; retry later |

The trained YOLO checkpoint detects **people**, not faces. A separate lightweight
YuNet face detector now guides composition; when it finds no face, a recognizable
head/neck silhouette can still guide framing. An image with no detected person
returns `PERSON_NOT_DETECTED` (422). These are framing aids, not facial-visibility
or passport-compliance validation.

The Next.js proxy keeps these categories and adds a display title. Connection,
timeout, unexpected response, and unknown server errors use
`INTERNAL_SERVER_ERROR` with status 502 or 504. Frontend file-size validation
uses `PHOTO_ISSUE` with status 413. Users receive photo guidance for input issues
and retry guidance for service issues, without private exception details.
The proxy also recognizes the original backend's known detection/decode messages.

## Checks and production

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m ruff check src tests
.venv/bin/python -m ruff format --check src tests
npm run format:check
npm run typecheck
npm run test:frontend
npm run start
```

`npm run test:frontend` builds the production app and runs every
`tests/frontend_*.test.mjs` file. Component tests load actual combined modules via
`tests/frontend-test-utils.mjs`, which also owns module loading, browser-global
mocks, markup assertions, and the state/effect harness. Page, preparation tips,
and help checks share `frontend_components.test.mjs`; state tests cover stale
selection, crop reset,
cancellation/retry, object-URL cleanup, downloads, and local action focus.
Integration tests start Next.js and a local upstream stub, including the real
60-second stalled-upload deadline. Backend tests stub native inference; they do
not measure model quality or prove a deployment memory ceiling.

Deploy the Next.js app as a Node.js service, not a static export. Deploy FastAPI
separately and set `BACKEND_URL` to its reachable address. Configure infrastructure
request/idle timeouts to allow the queued request to remain open: the Next.js
upstream timeout is 430 seconds and the browser timeout is 500 seconds, including
upload and response allowances. Configure upload limits for 10 MiB files plus
64 KiB multipart overhead. Uploads have a separate 60-second deadline.
Hosted serverless providers may impose
smaller request limits or execution timeouts; use a long-running Node service
or adapt the upload architecture for those providers. This frontend validates
files but does not add authentication or per-client rate limiting.

Both services enforce total streamed request bytes, including chunked uploads
without `Content-Length`. FastAPI additionally enforces the selected-file
limit, allowed MIME types, actual image formats, and decoded dimension limits.
The Node service sends upload-rejection JSON before disposing unread bytes.
Post-response cleanup discards, without buffering, at most twice the request
limit plus one stream chunk and waits at most one second before cancellation.
It retains the admission slot during this bounded cleanup.
The Next.js process admits at most three active upload/processing requests.
Each FastAPI process admits at most three photos before multipart parsing and
runs one photo-processing job at a time. When the worker is occupied, up to two other
photos may upload or wait. Completed, validated uploads take worker slots in
FIFO order; a slow upload does not prevent a ready photo from running.
The worker is a thread in the server process and reuses the loaded models.
YOLO runs before background removal, avoiding segmentation for photos with no
usable detection. Its prediction stage remains locked because its predictor
setup and arguments are mutable shared state. A photo cancelled while waiting
for this lock is checked again before YOLO runs.

Waiting photos stay in Starlette's bounded upload files (large files spool to
temporary disk). The endpoint reads the selected file into a bytes buffer only
after receiving a worker slot. It then returns the JPEG over the original HTTP
request, so the existing loading screen and Cancel button continue to work.
There is no separate job ID, queue-position display, or polling endpoint.

A photo may wait up to 180 seconds for a worker. Queue-full and queue-timeout
responses return 503, `SERVICE_BUSY`, and `Retry-After: 10`; this is a retry
suggestion, not automatic retry or a per-user cooldown. Cancelled or timed-out
waiters are removed from the queue and do not run later. An active native job
retains its worker slot until it actually finishes, even if its HTTP request
is cancelled. Native model calls are not forcibly terminated.

This queue is in-process and not durable: restarting or terminating the backend
loses pending work, and users must resubmit. There is no RabbitMQ, Redis, or
cross-process coordination. `MAX_ACTIVE_JOBS`, `MAX_WAITING_JOBS`, and
`MAX_QUEUE_WAIT_SECONDS` in `src/utils/limits.py` set the active concurrency
(one), waiting capacity (two), and queue deadline. Keep the frontend's
three-request cap and `frontend/lib/processing-limits.ts` deadlines aligned if
changing these values.

These limits are per process. Measure real-model peak memory and latency on
the deployment host before choosing a replica/worker count. Keep FastAPI
private behind the frontend where practical, use HTTPS for public traffic
and untrusted network hops, and configure ingress request-rate limits.
Application limits do not replace platform connection limits or abuse control.

The Python regression suite stubs native inference while exercising request
limits, single-worker FIFO order, queue saturation, queued cancellation/timeout,
native slot ownership, shared-detector locking, resizing, and no-detection errors.
It also checks mask-only RGB compositing against the previous alpha formula,
all country output sizes, JPEG reduced decoding, and low-memory configuration.
Explicit two-worker unit coverage remains for future higher-memory configurations. The Node
suite starts the built production Next.js app and an isolated upstream stub
on temporary localhost ports; it checks multipart limits, busy/error mapping,
and cancellation without sending photos to an external service. Its stalled
upload regression deliberately takes 60 seconds to exercise the real deadline.

Backend suites share image encoding and the ASGI upload/request harness in
`tests/backend_test_utils.py`. Health/CORS and multipart tests use the same
transport fixture, while inference stubs remain suite-owned. Head/face guidance
and framing/export checks share `tests/test_photo_composition.py`; model-session
and native-probe checks remain separate. Shared fixtures reduce repeated setup
without removing named regression scenarios.

### Low-memory processing

The default pipeline keeps `rembg`, with a custom `ModnetPortraitSession` using
the existing CPU ONNX Runtime. MODNet predicts portrait alpha mattes rather than
coarse human segmentation. Its approximately 26 MB FP32 weights replace the
older `u2net_human_seg` default. Inputs preserve aspect ratio, use RGB / 127.5 - 1,
and are bounded to a 512-pixel side with dimensions divisible by 32.

The weights are the [Xenova ONNX export of MODNet](https://huggingface.co/Xenova/modnet),
pinned to revision `fa2fa546052fba4c08921230a26cc69a333fca12` and SHA-256
`07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9`.
The model is Apache-2.0 licensed; `src/assets/LICENSE.modnet.txt` includes its
license. Docker downloads it at build time. Local startup reuses the cache at
`$U2NET_HOME/models/modnet-portrait/`. The older human model remains supported by
the session factory for explicit comparisons, but is not loaded alongside MODNet.

One native job runs at a time, with two bounded uploading/waiting slots.
Images use at most a 1024-pixel working side. `rembg` returns only its soft mask,
which is spatially gated with an expanded YOLO outline. Interior holes in YOLO's
coarse mask are filled before gating; its probabilities do not overwrite the
matting model's soft edges. The gate margin scales with working-image dimensions,
not the original upload size, so a larger upload does not cut deeper into clothing.
No extra Gaussian blur is applied to the alpha matte.
At export, rembg's foreground estimation removes old background colour from
partially transparent edge pixels. Confident foreground pixels (alpha >= 250)
retain their original RGB values. Subject bounds use row/column occupancy, and
generated Pillow images are explicitly closed. JPEG dimensions remain unchanged.

The runtime profile in `src/services/model_runtime.py` disables ONNX Runtime's
retained CPU memory arena, keeping memory-pattern planning and graph optimization
at their defaults. Execution is sequential with one intra/inter-op thread.
The model remains FP32. Allocations may be slower without the retained arena,
so measure latency as well as RAM.

The backend Dockerfile also defaults to `MALLOC_ARENA_MAX=2` and one
OMP/OpenBLAS/MKL thread. The malloc setting takes effect when Linux starts the
process; setting it after Python starts is not equivalent. These are allocator
and library defaults, not a hard RAM cap or a blanket override of all PyTorch
thread settings. YOLO's completed request caches (`results`, `batch`, `dataset`)
are cleared while its model/predictor remain loaded, including on errors and
cancellation.

These changes target small hosts, but do not guarantee a 2 GB fit: leave memory for
Next.js, your deployment manager, and the operating system. Model weight size
is not the same as peak inference RAM. Warm-up and native allocators can retain
memory for reuse; measure repeated successful uploads, including large PNG/WebP
inputs and queue/cancellation cases, not only `/health` or startup.

For example, after building the backend image, test with an exact 2 GB container
ceiling (2,000,000,000 bytes, no additional swap allowance):

```bash
docker run --detach --name passport-backend-memory-check \
  --memory=2000000000 --memory-swap=2000000000 --cpus=2 \
  --publish 127.0.0.1:8001:8000 \
  passport-backend:local
docker stats passport-backend-memory-check
```

Wait for `/health` on local port 8001, then point a local frontend's
`BACKEND_URL` at that service and process representative test photos. For a
frontend in Docker Desktop, use `http://host.docker.internal:8001` instead of
loopback. Run `docker inspect --format '{{.State.OOMKilled}}' passport-backend-memory-check`
if the container exits. Sample memory throughout processing; a single
`docker stats --no-stream` reading can miss the peak. Also check whole-host
memory, since container limits do not reserve RAM for other services.

Build images on a separate builder when the production host is itself limited
to 2 GB; running a frontend build alongside inference can exhaust shared RAM.

The optional native probe compares pre-runtime-tuning and optimized profiles in
separate processes, with the same loaded model weights and image pipeline. It
checks soft-mask and JPEG hashes and reports whole-process peak RSS. It does not
measure other services or enforce a container limit:

```bash
U2NET_HOME=.venv/model-cache \
YOLO_CONFIG_DIR=.venv/ultralytics \
.venv/bin/python tests/native_memory_probe.py \
  --image /absolute/path/to/representative-portrait.jpg --rounds 3
```

Use several representative `--image` files. Full verification fails if YOLO
accepts none of them, if hashes differ, or if the native subprocess fails.
`--mask-only` allows the bundled Ultralytics fixtures to check segmentation
without claiming end-to-end JPEG verification. A successful local comparison
does not replace repeated uploads under the actual Linux memory cap.

### Frontend deployment with Docker

Deploy the frontend with `Dockerfile.frontend` and its companion
`Dockerfile.frontend.dockerignore`. Build from the repository root so Docker
can access the npm workspace manifests and root lockfile. This service uses
Node.js, not the Python runtime in `Dockerfile.backend`.

Use these frontend service settings:

| Setting | Value |
| --- | --- |
| Build strategy | Dockerfile |
| Site/output type | Non-static web application (Node.js server) |
| Base directory / build context | `/` (repository root) |
| Dockerfile path | `Dockerfile.frontend` relative to the repository root |
| Install/build/start overrides | Leave blank; supplied by the Dockerfile |
| Application port | `3000` |
| Static publish directory / static Nginx server | Not used |
| Pre/post-deployment commands | Leave blank |
| Health-check path | `/` |

If the platform displays Dockerfile paths with a leading slash, enter
`/Dockerfile.frontend`. Remove stale `RAILPACK_*` environment variables from
the frontend service. No Railpack configuration or runtime detection is used.
Do not deploy as a static Nginx site: `/api/process` must run on the Next.js
server.

The multi-stage image installs Node.js 22 and workspace dependencies with
`npm ci`, then runs the existing `npm run build` script. The runtime image
contains production dependencies, the compiled Next.js output, and public
assets. It runs Next.js directly as the non-root `node` user so shutdown
signals reach the server. Build caches, backend code/models, local `.env`
files, and local Node installations are not included in the runtime image.

Set `BACKEND_URL` in the frontend service's runtime environment to the backend's
reachable base URL. Prefer a private internal address, or HTTPS when using a
public address. Do not prefix it with `NEXT_PUBLIC_`; the API route reads it
server-side at request time. It is not required during `docker build` and
should not be passed as a build argument. Restart/redeploy the frontend after
changing it. Keep `PORT` at `3000`, or match the application routing port if
overriding it.

Build locally from the repository root:

```bash
docker build -f Dockerfile.frontend -t passport-frontend:local .
```

For a backend listening on the Mac host at port 8000, run the frontend using
Docker Desktop's host address. This example uses local port 3001 so an existing
development server on port 3000 can keep running:

```bash
docker run --detach --name passport-frontend \
  --restart unless-stopped \
  --publish 127.0.0.1:3001:3000 \
  --env BACKEND_URL=http://host.docker.internal:8000 \
  passport-frontend:local
docker logs -f passport-frontend
```

Open `http://127.0.0.1:3001`. For separate frontend and backend containers,
place both on a shared Docker network and use the backend's network hostname
instead, such as `http://passport-backend:8000`. `localhost` inside the frontend
container does not refer to the backend container.

The built-in health check requests `/` and checks frontend availability only;
it does not verify connectivity to FastAPI or run image processing.

### Backend deployment with Docker

Deploy the backend using `Dockerfile.backend` from the repository root.
The selected deployment branch must contain this file and its companion
`Dockerfile.backend.dockerignore`. The backend-specific filenames keep the
frontend build configuration and build context unchanged.

Use these backend service settings:

| Setting | Value |
| --- | --- |
| Build strategy | Dockerfile |
| Output type | Web application |
| Base directory / build context | `/` (repository root) |
| Dockerfile path | `Dockerfile.backend` relative to the repository root |
| Port | `8000` |
| Install command | Leave blank |
| Build command | Leave blank |
| Start command | Leave blank; the Dockerfile supplies it |
| Pre/post-deployment commands | Leave blank |
| Health-check path | `/health` |

If the platform displays Dockerfile paths with a leading slash, enter
`/Dockerfile.backend`. Remove any previously added `RAILPACK_*` variables
from the backend service; they are not used by this Docker build.

The image installs Python 3.11, CPU-only PyTorch wheels, the dependencies in
`requirements.txt`, and native libraries required by OpenCV. It includes
`best.pt` and downloads the checksum-verified MODNet weights during the build, so normal
container startup does not need to download it. The initial build needs
internet access and sufficient disk space for dependencies and model weights;
subsequent code-only builds can reuse the model layer. Do not mount an empty
directory over `/opt/models` or override `U2NET_HOME`, as that would hide the
bundled model.

The container runs as a non-root user with one Uvicorn worker and one internal
processing slot, avoiding concurrent segmentation memory peaks. `PORT` defaults to `8000`;
if overriding it, update the service routing port too. The built-in health check
uses `/health` and allows 120 seconds for startup before counting failures.
Adjust the hosting platform's startup allowance to suit measured model-loading
time on your deployment host.

Build and run locally from the repository root:

```bash
docker build -f Dockerfile.backend -t passport-backend:local .
docker run --detach --name passport-backend \
  --restart unless-stopped \
  --publish 127.0.0.1:8000:8000 \
  passport-backend:local
docker logs -f passport-backend
```

After model loading finishes, check readiness in another terminal:

```bash
curl --fail http://127.0.0.1:8000/health
```

The backend-specific ignore file excludes the frontend, local environments,
Node dependencies, Git history, and secrets from the build context. Python
dependency versions are currently unpinned, so fresh image builds can resolve
different versions. Test the built image before promoting it to production.

Keep the backend private. Set the frontend's `BACKEND_URL` to its reachable
internal address, for example `http://passport-backend:8000` when both containers
share a Docker network and that hostname is configured. `127.0.0.1` inside the
frontend container points to the frontend container itself, not the backend.

## Photo requirements and assets

Country names and dimensions in `frontend/lib/countries.ts` mirror
`src/utils/passport_sizes.py`; update both if the backend list changes.
The output uses a white background and the listed dimensions. The current
processor does not verify all country-specific passport rules or guarantee
acceptance. Always check the issuing authority's latest rules, including
restrictions on digitally edited photos.

### Framing safeguards

`services/photo_framing.py` checks both source coverage and foreground-mask
coverage for every frame, including the original composition. Source pixels
alone are not enough: a segmentation mask can end inside a wide source image,
leaving white strips beside abruptly cut-off shoulders.

Framing keeps the largest usable country-aspect crop, then resizes it
proportionally to the final output. A bounded loop tries source widths from
largest to smallest, trying valid vertical and horizontal positions before
zooming further. It returns the first crop that keeps the estimated full head,
a small horizontal hair margin, and useful headroom (at least 5% when available
in the source), plus space below the estimated chin of at least 10% of the
estimated head height. Both lower edges must have substantial foreground coverage,
or a small corner must come from a continuous outward-sloping shoulder.
An abrupt or flat inset-mask cutoff is not accepted as a natural shoulder.
At each width, strict lower-edge positions outrank the continuous-slope fallback.
Eligible positions minimize the larger bottom gap, then the combined gaps.
Remaining ties favor retained headroom, then face centering. Centering is not the
primary objective; users can adjust it in the crop editor. It does not
add white padding to force a headroom percentage. Cumulative foreground counts
avoid repeatedly scanning the same mask pixels; source dimensions bound both
the width and position searches to at most 1,024 pixels per side.

There is no target head-height percentage, 45-70% head-size restriction,
80% body-retention rule, or upper-half-of-body constraint. Lower torso is cropped
only as needed to find the largest clean frame. Users can adjust their desired
composition in the crop editor rather than having the processor force a head size.

`services/head_framing.py` first uses a detected face to locate the chin and
segmented hair above the face midpoint, without measuring shoulders below it.
If no face is detected, it looks for a head narrowing into
a neck and then widening into shoulders. If neither cue is available, it keeps
only an already clean original frame; it does not blindly zoom an unknown mask.
That conservative fallback retains the previous 10% headroom composition.
These are approximate head-preservation guides, not validation of each country's
official head dimensions, expression, pose, or acceptance.

The YuNet weights are shipped in `src/assets/face_detection_yunet_2023mar.onnx`
(232,589 bytes), under the accompanying MIT license. The original is from
[OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet);
SHA-256 is `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.
Face inference is limited to a 640-pixel working side and reuses one CPU detector.
No runtime model download or additional Python inference framework is required.
The existing Docker `COPY src/` includes both weights and license.

If no safe frame exists, the API returns HTTP 422 with `PHOTO_ISSUE`, not a JPEG.
It does not stretch the subject, synthesize shoulders, or change JPEG settings.
These crop safeguards do not certify official passport acceptance. Run the
framing and exported-pixel regression checks with:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p test_photo_composition.py -v
```

Restart the backend after source changes unless Uvicorn is running with `--reload`.
The default backend command does not enable reload.

User previews use local object URLs. Gothic A1, Bricolage Grotesque, and DM Sans
are self-hosted through `next/font/local`, with license files in
`frontend/assets/fonts/`; page rendering does not request Google Fonts.

The dated backend investigation and matrix results are preserved in
`debug-headroom-borders.md` and `framing-policy-test-results.md`. Their local
measurements are historical evidence, not universal framing, acceptance, or
Linux 2 GB memory guarantees.
