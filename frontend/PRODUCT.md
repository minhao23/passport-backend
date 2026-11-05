# Passport Studio

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

People preparing their own passport photos at home. The user confirmed this audience and brief as the starting point; they may revise it after seeing the redesign.

## Product Purpose

Help someone turn an existing photo into a downloadable passport-sized JPEG without an account or payment. Success means choosing the issuing country, selecting a photo, generating it, and downloading the result.

## Operating Context

A Next.js and React frontend connects to the existing FastAPI image processor. Visitors may use a desktop or phone. They choose the country issuing their passport, not their travel destination.

## Capabilities and Constraints

- Select from the countries and dimensions in `lib/countries.ts`.
- Accept JPG, PNG, or WebP images up to 10 MB.
- Preview the selected image locally before the user explicitly generates.
- Remove the background, apply listed dimensions, and return a JPEG.
- Preserve upload validation, processing feedback, recoverable errors, country changes, and download behavior.
- No acceptance guarantee: the processor does not validate every authority's requirements. Keep the instruction to check current issuing-authority rules.
- Free and no account required, confirmed by the user for this brief.
- No invented testimonials, approval rates, processing-time guarantees, or privacy-retention claims.

## Brand Commitments

Keep the Passport Studio identity and product purpose. The user permits substantial visual and structural redesign, including removing sections.

The existing before-and-after comparison is explicitly protected: preserve its images, interaction, size, and current placement, including responsive placement. Do not edit `components/background-comparison.tsx`, its CSS module, or its image assets.

## Evidence on Hand

- `assets/bg.png` and `assets/bgremoved.png`: existing illustrative comparison assets, not customer testimonials or proof of government acceptance.
- `lib/countries.ts`: supported country names and listed dimensions.
- `app/page.tsx` and `app/api/process/route.ts`: implemented upload and processing workflow.
- Existing photo-taking advice and limitations in the page and repository README.

## Product Principles

- Make the upload-to-download task clear to a first-time visitor.
- Distinguish a prepared photo from an officially accepted photo.
- Preserve user control over when a photo is sent for processing.
- Keep the protected comparison intact while improving the surrounding interface.

## Open Decisions

Long-term monetization, retention policy, and positioning beyond the confirmed free at-home tool are not established.
