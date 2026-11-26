---
name: "Passport Studio"
description: "Open Visitor's Desk: off-white space, sage controls, and quiet inline framing help."
colors:
  paper: "#f7f8f5"
  ink: "#334532"
  muted: "#586553"
  line: "#d6ddd2"
  accent: "#3d563c"
  lilac: "#ebe7f2"
  yellow: "#f3df85"
  focus: "#527449"
  white: "white"
  accent-hover: "#2d432d"
  disabled: "#dedfd9"
  field-border: "#879481"
  photo-surface: "#e9eee5"
  guide-ink: "#625370"
  guide-surface: "#f5f2f9"
  error-paper: "#fff0e9"
  error-border: "#e4bba8"
  error-ink: "#923b26"
typography:
  display:
    fontFamily: "Gothic A1, Bricolage Grotesque, Arial, sans-serif"
    fontSize: "clamp(40px, 3.4vw, 48px)"
    fontWeight: 700
    lineHeight: 1.16
    letterSpacing: "-0.035em"
  headline:
    fontFamily: "Bricolage Grotesque, Arial, sans-serif"
    fontSize: "36px"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-1.3px"
  title:
    fontFamily: "Bricolage Grotesque, Arial, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.45px"
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  label:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 500
  action:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "16px"
    fontWeight: 550
  brand:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "23px"
    fontWeight: 500
    letterSpacing: "-0.02em"
rounded:
  field: "6px"
  action: "7px"
  feedback: "8px"
  framing: "8px"
  workspace-inner: "13px"
  workspace: "14px"
  comparison: "18px"
spacing:
  inline-sm: "8px"
  inline: "12px"
  text: "16px"
  compact: "18px"
  control: "20px"
  gutter-mobile: "22px"
  group: "24px"
  gutter-tablet: "28px"
  section: "36px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.white}"
    typography: "{typography.action}"
    rounded: "{rounded.action}"
    padding: "14px 20px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.disabled}"
    textColor: "{colors.muted}"
  button-secondary:
    textColor: "{colors.ink}"
    rounded: "{rounded.action}"
    padding: "10px 14px"
  country-field:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "13px 38px 13px 14px"
    width: "100%"
  navigation:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    height: "100px"
  error-alert:
    backgroundColor: "{colors.error-paper}"
    textColor: "{colors.error-ink}"
    rounded: "{rounded.feedback}"
    padding: "20px"
  workspace:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.workspace}"
  framing-guide:
    backgroundColor: "{colors.guide-surface}"
    textColor: "{colors.guide-ink}"
    rounded: "{rounded.framing}"
    width: "140px"
    height: "176px"
---

# Design System: Passport Studio

## Overview

**Creative North Star: "Open Visitor's Desk"**

Passport Studio is an approachable, quietly practical place to prepare a photo. Off-white space, softened green lettering, thin sage rules, and humanist sans typography keep the interface open and readable. Controls feel direct and restrained rather than ornamental.

The small lilac centering diagram supplies warmth inside optional result help.
The former large preparation panel was removed. The rejected Sign Band direction
and large dark or saturated green fields are not part of this system.

**Key Characteristics:**
- Open off-white ground with muted green text and a concentrated primary action.
- Clear sans-serif hierarchy, generous spacing, and thin sage boundaries.
- Optional inline instruction with a CSS/Lucide head-and-shoulders diagram.
- Flat structural surfaces with localized depth on the protected comparison.
- Subtle state feedback, visible keyboard focus, and reduced-motion support.

This documents the built UI, not a proposal. Sources are `app/globals.css`,
`app/layout.tsx`, `components/passport-page.tsx` and its CSS module, the studio
components and colocated styles, both comparison files, and `PRODUCT.md`.
`app/page.tsx` delegates to the static page component; interactive state remains
inside `components/photo-studio/`. Structural refactors preserve this appearance.

Asset origins remain prose: `assets/bg.png` and `assets/bgremoved.png` are
pre-existing illustrative comparison rasters, not proof of official acceptance.
`assets/sample_rules.jpg` is the user-supplied Singapore ICA reference sheet.
The framing diagram uses CSS geometry and Lucide `UserRound`, not a raster.
Fonts are local with license files alongside them. Future mockups are runnable
HTML; verification screenshots and spent design boards do not ship.

## Colors

The palette combines pale working surfaces, subdued botanical greens, and a quiet lilac instructional field. Frontmatter values are normative; names below explain their use.

### Primary
- **Desk Green** (`accent`): upload, generate, and download actions; `accent-hover` deepens only the interactive state.
- **Green Ink** (`ink`): primary lettering, navigation, and controls.
- **Focus Green** (`focus`): keyboard outlines and the active drop target.

### Secondary
- **Guide Lilac** (`lilac`): drag-over feedback.
- **Guide Ink** (`guide-ink`) and **Guide Surface** (`guide-surface`): the small
  centering diagram; advice text uses the normal ink and muted tokens.

### Tertiary
- **Selection Yellow** (`yellow`): selected text only, not an invented badge or additional call to action.

### Neutral
- **Open Paper** (`paper`): page ground.
- **White** (`white`): select and result surfaces, comparison backing, and action lettering.
- **Muted Sage** (`muted`): measurements, helper text, captions, and disabled action text.
- **Sage Rule** (`line`) and **Field Edge** (`field-border`): quiet structural dividers and the stronger native-select boundary.
- **Photo Sage** (`photo-surface`): original/result workspace backing.
- **Disabled Stone** (`disabled`): locked action background and border.

Error feedback uses `error-paper`, `error-border`, and `error-ink` together, with an icon and explicit text. It is a semantic exception, not another brand accent.

**The Mild Field Rule.** Keep broad surfaces off-white, pale sage, or gentle lilac; reserve dark green for lettering and the primary action.

The sidecar's tonal ramps are preview metadata, not additional implemented
palette tokens. Preserve the comparison's distinct border and divider cue.

## Typography

**Display Font:** Gothic A1, falling back through Bricolage Grotesque, Arial, and sans-serif.
**Body Font:** DM Sans with a sans-serif fallback.
**Section Font:** Bricolage Grotesque with Arial and sans-serif fallbacks.

The hero is firm and readable; the section headings are more rounded and conversational. DM Sans handles controls, copy, and the wordmark. All three fonts are local; `app/layout.tsx` registers them with `display: swap`.

### Hierarchy
- **Display** (`display`): the two-line hero. At viewport maxima of 1100px and 1000px it steps to 40px and 38px; at 900px it becomes 44px; at 600px it uses `clamp(32px, 8.4vw, 44px)` and slightly looser tracking (-0.03em).
- **Headline** (`headline`): workspace section heading; reduces to 30px at 900px
  and 24px at 600px.
- **Title** (`title`): country output heading (20px); framing issues use an 18px
  section heading, increasing to 20px on phones.
- **Body** (`body`): root text. Supporting paragraphs generally use 12-13px with 1.7 line height. Root line height is browser-normal, not a fabricated global token.
- **Label** (`label`): issuing-country label; measurements use tabular numerals and 14px, reducing to 13px on phones.
- **Action** (`action`): primary controls; becomes 15px at 600px.
- **Brand** (`brand`): header wordmark; reduces to 21px at 900px, 20px at 600px,
  and 18px at 360px. The footer has no wordmark.

There is no imposed mathematical type ratio, all-caps label system, or separate monospace face.

## Layout

The shared container is centered with a maximum border-box width of 1160px and horizontal padding of 36px. Padding becomes 28px at 1000px and 22px at 900px. Repeated spacing is extracted in frontmatter; it is an observed vocabulary, not a uniform arithmetic scale.

The current homepage uses an open hero, not an enclosing upload card. Its desktop grid is `1.1fr 1fr`, minimum height 567px, with 47px top and 65px bottom padding; at 1400px and above those paddings become 60px and 75px. The form has a 475px maximum width. At 1000px the grid becomes equal columns. At 900px it stacks; the copy is centered within a 520px maximum width and has a 387px minimum height, increasing to 410.5px at 600px. These measurements preserve the comparison's incumbent coordinates, not a reusable minimum height for every page.

The protected comparison is square, right-aligned, and at most 460px wide on desktop. At 900px and below it is at most 420px wide with `32px auto 0` margins. Keep its placement, image scale, and responsive behavior intact.

The conditional workspace uses `minmax(0, 1.6fr) minmax(0, 1fr)` and stacks at 900px. Photos lead with columns up to 240px wide and a shared preview row of `clamp(240px, 26vw, 320px)`. Padding is 28px, reducing to 24px at 1100px. The stacked tablet preview row is 280px. At 600px and below the workspace uses one preview at a time, sized to `min(360px, 80vw)`, with 20px photo and details padding. Preserve image aspect ratios.

Country and dimensions share a compact summary, followed by Generate or Download JPEG and the preparation tips or result guidance. Keep Change photo content-width and attached to its source preview. Before generation, from 601px through 900px the summary sits beside the primary action and tips use two columns; on phones these return to a linear stack. Preparation tips remain fully visible above 600px; phones use the disclosure described below.

Completed results read: country and dimensions, Download JPEG, authority rules
reminder, then "Not happy with the framing?" at the panel bottom. Help starts
closed, with an info icon and a keyboard-operable toggle. Expanded content
appears above the same toggle without a modal, live announcement, or nested card.
The details panel stretches on desktop; flexible space and 24px top separation
keep the help last.

Navigation height changes from 100px to 80px at 900px. Below the studio, a separate
acceptance warning precedes the native View photo examples disclosure. Its image
is centered, up to 653px wide, with a preserved 653:3058 ratio. The centered footer
contains only Contact me.

### Mobile Workflow

Phone-specific controls are hidden above 600px. Keep the desktop and tablet layouts, copy, double-click cropping, and action focus behavior unchanged.

- Before generation, show the uploaded photo without a blank result placeholder or direction arrow.
- After generation, show the result by default. Two plain, underlined Original/Result buttons switch the single preview; pressed state is exposed to assistive technology.
- A single tap on the uploaded preview opens the same rectangular crop editor. Change photo and Remove photo sit beneath that preview. Saving a crop still requires explicit generation.
- Use a full-width Generate photo or Download JPEG action. While processing, show activity and a neutral Cancel control in the same action area; cancellation stays quiet.
- Put the same country-specific preparation advice in a native Photo tips
  disclosure, initially closed. Keep the rules reminder and optional framing
  help on completed results.
- After selecting or saving a crop, bring the phone workspace into view. The hero's duplicate Generate action becomes a Review your photo link; the comparison's placement, size, assets, and interaction stay intact.

Phone-specific workflow controls use the 600px breakpoint; the small framing
diagram also stacks at 360px. Share processing state and handlers across screen
sizes, rather than creating a separate mobile app.

## Elevation & Depth

Most depth comes from tonal surfaces and fine borders: off-white page, white
working areas, pale sage previews, and the small lilac diagram. The form,
workspace, and inline help have no ambient card shadow. The comparison is the
localized exception.

### Shadow Vocabulary
- **Comparison Stage** (`0 16px 40px #243c3210`): soft lift on the existing image stage.
- **Comparison Divider** (`0 0 0 1px #243c3230`): contrast around the white two-pixel divider.

Keyboard focus is an outline, not a shadow: general controls use 3px in `focus` with a 5px offset. The comparison has no outer focus ring; keyboard-only focus uses an ink-colored divider with a 2px white outline.

**The Local Depth Rule.** Keep ambient lift confined to the comparison; use tone
and fine boundaries elsewhere.

## Shapes

Fields use `field`, actions use `action`, and alerts use `feedback`. Larger
regions are softer: workspace uses `workspace`, comparison uses `comparison`,
and photo-side corners use `workspace-inner`.

Most structural borders are one pixel. The diagram uses `framing`, clips the
portrait, and carries four corner marks, dashed headroom, and a vertical
centerline. There is no eye-level line or full-page illustrated panel.

## Components

### Buttons

Direct, full-width for the main form task. Primary styling is captured in
`button-primary`; minimum height is 58px and icon gap is 12px. Upload and generate
span the form; download lives in the details panel and is full-width on phones
with a 52px minimum height. Utility controls have 44px minimum hit targets.

Hover deepens both background and border over 0.18s ease-out. Disabled controls use `button-primary-disabled` and a not-allowed cursor. Focus uses the shared outline. No custom pressed transform or decorative entrance animation exists.

Change photo is a restrained outlined action; Remove photo is an underlined
utility. Generate/Cancel markup and local focus restoration share
`photo-processing-actions.tsx`. No separate animation playback controls exist.

### Inputs / Fields

The issuing-country control is a native select inside a white, one-pixel bordered row with `field` corners. Its label and tabular dimensions sit above it. The chevron is an inert inline icon; the select retains keyboard behavior and descriptions. Disabled state locks country changes during processing without a separate painted field variant.

The actual file input is visually hidden and reached through the upload button. Accepted formats and size remain visible. Drag-over adds a lilac background and the shared focus-colored outline. Selecting a photo shows a local preview; upload is not automatic processing.

### Navigation

The header contains only the text wordmark and a keyboard-visible skip link.
The removed Photo guide anchor has no replacement menu. The footer's single
Contact me link opens `https://minhao.dev/home` in a new tab, with a
screen-reader-only notice. Hover underlines and keyboard focus remain explicit.

### Cards / Containers

The workspace is a bordered white container with sage photo backing, aligned
captions, country details, and processing status. Preparation tips have a thin
top rule, not a card, and share one content definition across desktop and phone.
The acceptance warning remains outside the workspace.

The recoverable error alert uses a warm background, matching border, 20px padding, 12px icon gap, and 13px text at 1.6 line height. It has `role="alert"` and receives focus when an error appears. The result heading receives focus when processing succeeds. Neither state is communicated by color alone.

### Framing Help and Crop Editor

Optional completed-result help pairs a 140px by 176px diagram with crop advice,
then common issues: tight shoulders, off-center face, and turned/tilted head.
Corner marks are 13px at a 10px inset. The portrait is 151px by 165px, clipped
below the window. At 600px the window is 130px by 170px; at 360px the diagram and
advice stack. Each new result resets the disclosure closed.

The rectangular crop editor is the only modal. Its native dialog is at most
880px wide and viewport-bounded, with a plain Close control and initial title
focus. Cropping instructions are screen-reader-only. Reset, Cancel, and Save crop
retain keyboard access, a visible two-tone crop-handle focus cue, and focus
restoration. The editor and crop library load on demand.

### Protected Comparison

`components/background-comparison.tsx`, its CSS module, and both imported rasters are protected. The original layer scales by 1.08; the removed-background layer is clipped rather than resized. A native range input overlays the stage and reports the revealed percentage.

Its existing animation traverses at 0.012 percentage points per millisecond, reverses at the limits, and pauses on mouse hover, keyboard focus, drag, or reduced-motion preference. Pointer dragging and one-percent arrow-key steps remain intact. Do not reproduce a mockup's approximate comparison in place of this component.

Processing spinners rotate over 1.2s linearly; reduced motion disables them and all CSS transitions, changes smooth scrolling to auto, and stops the comparison's automatic sweep.

### Framing Motion

The completed-result framing help repeats its centering demonstration every three seconds.
Its Lucide portrait moves 24px horizontally into the fixed crop's center; a dashed
centerline and the "Center your face in the crop" caption explain the goal.
The original slide timing is retained, followed by a longer centered hold before
the next replay. The check appears once aligned. Manual playback controls were
removed at the user's request. Playback pauses offscreen and in hidden tabs.
Reduced motion shows a centered still and check.
This uses CSS and browser animation APIs, without a new raster asset or dependency.

The design sidecar contains source-derived, framework-free previews of primary
and secondary actions, the country field, header, error alert, and framing
diagram. They illustrate styling, not application handlers; shipping raster
content is not duplicated into previews.

## Do's and Don'ts

### Do:
- **Do** keep the off-white ground, sage hierarchy, and small lilac diagram.
- **Do** use the implemented native controls, visible focus treatments, and reduced-motion behavior.
- **Do** preserve the comparison's original source, images, interaction, dimensions, and responsive placement.
- **Do** retain compact preparation tips, optional framing help, inline ICA
  examples, and the separate acceptance warning.
- **Do** record asset origins in prose and treat tonal ramps as preview metadata rather than new UI colors.

### Don't:
- **Don't** reintroduce the rejected Sign Band or large dark or saturated green fields.
- **Don't** treat the approved mockup as pixel-exact authority over the user's retained originals.
- **Don't** modify protected rasters or embed provenance metadata into them.
- **Don't** reintroduce the large preparation panel, dead Photo guide link, or
  manual centering-animation controls.
- **Don't** add enclosing upload cards, generic chip systems, or decorative entrance motion to this documented homepage.
- **Don't** imply official acceptance, automatic upload on selection, or unverified privacy guarantees.
