# Passport Studio

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People preparing their own passport photos at home, on desktop or phone.

## Product Purpose

Help someone turn an existing photo into a downloadable passport-sized JPEG.
Success means choosing the issuing country, selecting and optionally cropping a
photo, generating it, and downloading the result.

## Operating Context

A Next.js server proxies same-origin browser requests to the FastAPI image
processor. Visitors choose the country issuing their passport, not their travel
destination. Shared studio state and handlers serve both desktop and phone.

## Capabilities and Constraints

- Select from the countries and dimensions in `lib/countries.ts`.
- Accept JPG, PNG, or WebP images up to 10 MB.
- Preview the selected image locally before the user explicitly generates.
- Open a rectangular crop editor by desktop double-click, phone tap, or keyboard
  activation. Preserve the original and save the crop as generation input.
- Remove the background, apply listed dimensions, and return a JPEG.
- Automatically start a download on successful generation, retaining a manual
  Download JPEG action.
- Cancel quietly without losing the photo, crop, or country. Discard stale
  responses and allow replacement or retry.
- Show country-specific preparation tips before generation. Offer initially
  closed framing help after generation, including user-controlled centering
  through cropping.
- The centering diagram repeats every three seconds without manual playback
  controls. Reduced motion shows a still; hidden/offscreen playback pauses.
- Offer the supplied Singapore ICA examples inline, initially closed, with the
  attribution "taken from: Singapore ICA." and no image popup or URL link.
- No acceptance guarantee: the processor does not validate every authority's requirements. Keep the instruction to check current issuing-authority rules.
- No account or payment step is implemented. Do not reintroduce the removed
  "Free. No account needed." marketing line.
- No invented testimonials, approval rates, processing-time guarantees, or privacy-retention claims.

## Brand Commitments

Keep the Passport Studio identity and the approved off-white, sage interface.
The large preparation panel and obsolete Photo guide navigation were removed.
Keep the compact workspace tips and separate acceptance warning.

Preserve the before-and-after comparison's images, size, interaction, and
responsive placement. Its outer green focus ring was intentionally removed;
keyboard focus now uses a subtle divider cue. The footer contains only Contact
me, linking to `https://minhao.dev/home`.

## Evidence on Hand

- `assets/bg.png` and `assets/bgremoved.png`: existing illustrative comparison assets, not customer testimonials or proof of government acceptance.
- `assets/sample_rules.jpg`: user-supplied Singapore ICA reference (653 x 3058);
  a shipping asset, not an obsolete mockup.
- `lib/countries.ts`: supported country names and listed dimensions.
- `components/passport-page.tsx`: static shell, examples, and contact footer.
- `components/photo-studio/`: interactive studio, colocated state and controls.
- `app/api/process/route.ts`: bounded server-only processing proxy.
- Repository README: startup, limits, deployment, pipeline, and verification.

## Product Principles

- Make the upload-to-download task clear to a first-time visitor.
- Distinguish a prepared photo from an officially accepted photo.
- Preserve user control over when a photo is sent for processing.
- Keep optional guidance quiet and discoverable.
- Combine small implementation pieces where ownership is clearer; a structural
  refactor does not authorize redesign or feature removal.

## Open Decisions

Long-term monetization and a retention policy are not established. Official
acceptance, physical-phone/Safari behavior, and operation under a Linux 2 GB
memory ceiling are not certified by the existing local tests.
