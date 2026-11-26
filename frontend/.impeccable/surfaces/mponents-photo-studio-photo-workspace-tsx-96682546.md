---
version: 1
slug: "mponents-photo-studio-photo-workspace-tsx-96682546"
primary_target: "frontend/components/photo-studio/photo-workspace.tsx"
related_targets: ["frontend/components/photo-studio/photo-crop-modal.tsx", "frontend/components/photo-studio/photo-upload-form.tsx", "frontend/components/photo-studio/photo-framing-help.tsx", "frontend/components/photo-studio/photo-processing-actions.tsx", "frontend/components/photo-studio/use-photo-studio.ts"]
---

# Photo Workspace and Crop Editor

Mode: Operate. Extend the existing photo workspace without changing its identity.
The confirmed crop becomes the generation input; preserve the original locally.

## Direction contract

THESIS: Inspect and trim a selected photo before generation, using one rectangular
selection rather than a multi-tool image editor.

OWN-WORLD: Inherit paper #f7f8f5, ink #334532, muted #586553, line #d6ddd2,
accent #3d563c, and the existing white photo surfaces. Use existing DM Sans
controls and Bricolage section typography.

STORY: Double-click the photo (or focus it and press Enter or Space), adjust a
rectangle, then confirm with a checkmark. No separate Crop photo action is shown,
per user preference. Cancel leaves the current photo unchanged. Reopening uses
the original image and saved bounds; generation uses the saved crop.

FIRST VIEWPORT: Centered native dialog, compact left-aligned title and close
icon above a large image, crop dimensions below, then Reset, Cancel, and a green
checkmark Save crop action. The close icon has no filled hover treatment or
initial focus accent; the title receives initial focus, and controls retain
visible keyboard focus. Cropping instructions are screen-reader-only, with no
visible tutorial. On phones the editor fits the viewport and its controls wrap
without obscuring the image.

FORM: Narrow extension of the established workspace. No concept roll applies.
The signature interaction is directly resizing and moving a rectangular crop.
Editor motion is limited to brief control feedback; result-help motion is
documented below.

## Workspace actions

The desktop workspace gives the previews approximately 62% of its width, with
responsive preview rows up to 320px tall and photo columns up to 240px wide.
Use 28px desktop panel padding, 24px at intermediate widths, and compact phone
gutters. Preserve image aspect ratios, shared caption alignment, and the direct
double-click crop interaction. Change photo stays content-width beneath its image.

Country and dimensions form one compact summary above the primary action, with
the size label retained for assistive technology. On stacked tablets, place the
summary beside the action and use two columns for the tips. Phones show one
Original/Result preview at a time and keep a linear photo, summary, action,
initially closed Photo tips order. The same advice is available at every width.

After cropping, Generate passport photo is available in the country/size panel;
it invokes the same request handler as the hero form. Successful generation
shows the result for review and replaces this action with Download JPEG.
Downloading starts only when the user activates that link.

Change photo is a restrained outlined secondary action beneath the original,
consistent with the form. During generation, the crop hint and replacement action
are hidden without collapsing their space. Cancel sits beneath the result's
Creating your photo caption, using the same neutral treatment as the form.

Cancellation restores the ready state without a cancellation message or toast.
Keep the selected photo, crop, and country; restore action focus locally without
scrolling to the other section. Do not show the generate-above instruction or
processor-send explanation in the workspace.

Photo tips are owned by `photo-workspace.tsx` and appear beneath Generate as a
plain, readable four-item list, without
a card or live announcement. Cover upper-body framing, eye-level camera position
and expression, clear even lighting, and headwear/sunglasses with religious or
medical exceptions. The armpit crop is framing guidance, not an official size
rule; UK online applicants instead see advice to retain an uncropped original.
Keep tips during generation to avoid layout shifts, and remove them when the
download result appears.

## Completed Result Framing Help

THESIS: Offer the last approved framing guide only after generation and only
when requested, without interrupting the download or photo comparison.

OWN-WORLD: Reuse the existing sage controls and the approved lilac head-and-
shoulders diagram. Keep the instruction area inline, unboxed, and quiet.

STORY: Click or tap "Not happy with the framing?" to reveal crop advice and
the common issues about cut-off shoulders, an off-center face, and a turned
or tilted head. Centering advice directs users to crop their original with
similar space on both sides while keeping their head and shoulders visible.
Click again to close it. A new generated result starts closed.

FIRST VIEWPORT: Country and dimensions, Download JPEG, authority reminder,
then the collapsed footer at the panel bottom. Expanded content appears above
that same footer; photos and primary actions stay in place.

FORM: Approved narrow extension, code-led HTML/React implementation. No new
concept round. Keep the mobile footer compact and keyboard-operable. Omit the
obsolete Photo guide link because its destination was removed.

MOTION: Keep the crop marks fixed while the Lucide portrait moves from
24px off-center to centered in a repeating three-second cycle. A fixed dashed
centerline and the caption explain the goal; the check appears after alignment.
Keep the original slide timing and hold the centered result before each replay.
No manual playback controls, per user preference. Pause outside the viewport
and in hidden tabs. Reduced motion shows the centered still and check.
Use CSS and browser animation APIs, with no new dependency or raster asset.

Future mockups are runnable HTML, not raster boards. Remove spent mockup
artifacts after their approved design has been implemented and verified.

## Implementation and Verification

Keep state in `components/photo-studio/use-photo-studio.ts` and shared
Generate/Cancel markup and focus handling in `photo-processing-actions.tsx`.
Feedback belongs to `photo-studio.tsx`; preparation tips belong to the workspace.
Keep the crop editor and animated help separate because they own complex
interactions. The editor is dynamically loaded on demand.

Preserve original/cropped file separation, stale-request guards, quiet
cancellation, object-URL cleanup, user-initiated download, and keyboard focus.
Use the complete frontend tests plus production-browser checks for affected
desktop/phone states. Current visual tokens live in `frontend/DESIGN.md`; record
shipping asset origins in documentation, without modifying protected rasters.
Local Chrome checks do not establish physical-device or Safari compatibility.
