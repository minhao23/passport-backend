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
Uploads must also be at most 20 megapixels, with neither side exceeding
10,000 pixels. Accepted images are reduced proportionally to a maximum
2,048-pixel working side before model processing. WebP must be a still image;
its container and bitstream dimensions are checked before opening a decoder.

After selection, use **Change photo** below Generate or beside the original
preview to choose a replacement. Invalid replacements leave the current photo
intact. **Remove photo** returns to the upload state.

During generation, **Cancel processing** keeps the original photo available
for replacement or retry and discards any late response. The proxy forwards
the disconnect to FastAPI. A waiting photo is removed from the queue without
running the model. For an active photo, FastAPI checks for cancellation between
processing stages. A native model inference already in progress finishes its current
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
| `PHOTO_ISSUE` | 413 | File, total request, or decoded dimensions exceed limits |
| `PHOTO_ISSUE` | 408 | Upload did not finish within 60 seconds |
| `SERVICE_BUSY` | 503 | Upload/queue capacity is full, or queue wait exceeded 180 seconds; retry later |

The trained checkpoint detects **people**, not faces. An image with no
detected person returns `PERSON_NOT_DETECTED` (422); a person with an obscured
or invisible face can still pass. This is not facial-visibility or passport
compliance validation.

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
node --test tests/frontend_limits.test.mjs
npm run start
```

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
The Next.js process admits at most four active upload/processing requests.
Each FastAPI process admits at most four photos before multipart parsing and
runs two photo-processing jobs concurrently. When both workers are occupied, up to two other
photos may upload or wait. Completed, validated uploads take worker slots in
FIFO order; a slow upload does not prevent a ready photo from running.
The workers are threads in the same process and share the loaded models.
Background removal can overlap; the YOLO prediction stage is locked because
its predictor setup and arguments are mutable shared state. A photo cancelled
while waiting for this lock is checked again before YOLO runs.

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
(two), waiting capacity (two), and queue deadline. Keep the frontend's
four-request cap and `frontend/lib/processing-limits.ts` deadlines aligned if
changing these values.

These limits are per process. Measure real-model peak memory and latency on
the deployment host before choosing a replica/worker count. Keep FastAPI
private behind the frontend where practical, use HTTPS for public traffic
and untrusted network hops, and configure ingress request-rate limits.
Application limits do not replace platform connection limits or abuse control.

The Python regression suite stubs native inference while exercising request
limits, two-worker overlap, FIFO order, queue saturation, queued cancellation/timeout,
native slot ownership, shared-detector locking, resizing, and no-detection errors. The Node
suite starts the built production Next.js app and an isolated upstream stub
on temporary localhost ports; it checks multipart limits, busy/error mapping,
and cancellation without sending photos to an external service. Its stalled
upload regression deliberately takes 60 seconds to exercise the real deadline.

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
`best.pt` and downloads the BiRefNet portrait model during the build, so normal
container startup does not need to download it. The initial build needs
internet access and sufficient disk space for the dependencies and large model;
subsequent code-only builds can reuse the model layer. Do not mount an empty
directory over `/opt/models` or override `U2NET_HOME`, as that would hide the
bundled model.

The container runs as a non-root user with one Uvicorn worker. Its two internal
processing slots still allow two jobs to overlap. `PORT` defaults to `8000`;
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

User previews use local object URLs. Google Fonts supplies the page fonts, with local sans-serif
fallbacks if unavailable.
