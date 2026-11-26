# Project Conventions

## Frontend Organization

- Keep `frontend/app/page.tsx` as a small Server Component entry point.
- Compose the static shell in `frontend/components/passport-page.tsx`.
- Keep studio UI, its state hook, and processing actions together in
  `frontend/components/photo-studio/`; keep shared non-UI utilities in `frontend/lib/`.
- Combine small, single-owner components instead of creating a file for every
  element. Keep complex interactions such as cropping and animated help separate.
- Keep styles beside their owning components. Reserve `app/globals.css` for
  shared tokens, base styles, and page-wide rules.
- Preserve the approved desktop/mobile interface during structural refactors.

## Backend Organization

- Keep `src/main.py` focused on app setup and startup; keep routes and public
  error responses together in `src/api.py`.
- Keep `services/image_processor.py` as the pipeline orchestrator. Combine
  single-owner helpers with their owner: ONNX options in `model_runtime.py`,
  image-header preflight in `utils/image_loading.py`.
- Keep framing, segmentation, composition, HTTP request lifetime, and native-job
  scheduling separate. Preserve models, output formulas, limits, and cancellation.
- Defer native inference imports until startup or processing. Keep the standalone
  MODNet session compatible with the Docker model-download layer.
- Share test fixtures without dropping named scenarios or leaking native stubs
  between suites. Run the Python suite and Ruff checks after backend changes.

## UI Mockups

- Create all future UI mockups as runnable HTML, with CSS and JavaScript as needed.
- Do not commit PNG/JPEG mockup boards or screenshots as design deliverables.
- Keep intermediate drafts and verification screenshots outside the repository.
- After implementing an approved mockup, remove its obsolete mockup artifacts.
- Preserve shipping assets and production components during mockup cleanup.

## Documentation and Checks

- Update Markdown paths and current behavior when changing component ownership.
- Keep experiment reports dated; do not turn historical measurements into new
  verification claims.
- Run `npm run test:frontend` for the production build and complete frontend
  tests, plus `npm run typecheck` and `npm run format:check`.
- Verify affected interactions in the rendered app. Keep screenshots and
  intermediate verification scripts outside the repository.
