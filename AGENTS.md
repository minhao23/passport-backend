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
