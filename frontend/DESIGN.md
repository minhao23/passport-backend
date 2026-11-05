---
name: "Passport Studio"
description: "Open Visitor's Desk: softer greens, off-white space, and a lilac illustrated guide."
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
  guide-ink: "#34313a"
  guide-muted: "#64606a"
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
  guide-headline:
    fontFamily: "Bricolage Grotesque, Arial, sans-serif"
    fontSize: "43px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.035em"
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
  remove: "4px"
  field: "6px"
  action: "7px"
  feedback: "8px"
  framing: "9px"
  workspace-inner: "13px"
  workspace: "14px"
  guide-mobile: "15px"
  comparison: "18px"
  guide: "20px"
spacing:
  inline-sm: "8px"
  inline: "12px"
  text: "16px"
  compact: "18px"
  control: "20px"
  gutter-mobile: "22px"
  group: "24px"
  gutter-tablet: "28px"
  panel-compact: "30px"
  section: "36px"
  panel: "40px"
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
  guide-panel:
    backgroundColor: "{colors.lilac}"
    textColor: "{colors.guide-ink}"
    rounded: "{rounded.guide}"
    padding: "40px"
  framing-guide:
    rounded: "{rounded.framing}"
    width: "200px"
    height: "250px"
---

# Design System: Passport Studio

## Overview

**Creative North Star: "Open Visitor's Desk"**

Passport Studio is an approachable, quietly practical place to prepare a photo. Off-white space, softened green lettering, thin sage rules, and humanist sans typography keep the interface open and readable. Controls feel direct and restrained rather than ornamental.

The lilac illustrated guide supplies warmth without turning the page into a large saturated field. The approved open mockup is a visual guide, not a pixel-exact specification: the original comparison and illustrated preparation guide take precedence. The rejected Sign Band direction and large dark or saturated green fields are not part of this system.

**Key Characteristics:**
- Open off-white ground with muted green text and a concentrated primary action.
- Clear sans-serif hierarchy, generous spacing, and thin sage boundaries.
- Gentle lilac instruction with a retained head-and-shoulders illustration.
- Flat structural surfaces with localized depth on the protected comparison.
- Subtle state feedback, visible keyboard focus, and reduced-motion support.

This documents the built UI, not a proposal. Sources are `app/globals.css`, `app/layout.tsx`, `app/page.tsx`, both `components/background-comparison` files, and `PRODUCT.md`. The approved direction is an open layout with restrained greens, the original comparison slider, and the illustrated lilac photo guide. Temporary mockups and workflow records were removed after implementation.

Asset origins remain prose: `assets/bg.png` and `assets/bgremoved.png` are pre-existing illustrative comparison rasters, not customer examples or evidence of official acceptance. The framing guide is retained CSS geometry and a Lucide `UserRound` icon. The local font files supply Gothic A1, Bricolage Grotesque, and DM Sans, with license files alongside them. The approved mockup is a direction artifact, not a shipping image. No new raster ships, and no provenance metadata is embedded into protected images.

## Colors

The palette combines pale working surfaces, subdued botanical greens, and a quiet lilac instructional field. Frontmatter values are normative; names below explain their use.

### Primary
- **Desk Green** (`accent`): upload, generate, and download actions; `accent-hover` deepens only the interactive state.
- **Green Ink** (`ink`): primary lettering, navigation, and controls.
- **Focus Green** (`focus`): keyboard outlines and the active drop target.

### Secondary
- **Guide Lilac** (`lilac`): the preparation panel and drop-target feedback.
- **Guide Ink** (`guide-ink`) and **Guide Muted** (`guide-muted`): instruction headings and supporting copy on lilac.

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

The sidecar's eight-step tonal ramps are synthesized preview metadata, not additional implemented palette tokens. Preserve the protected comparison's distinct border and focus colors rather than silently harmonizing them.

## Typography

**Display Font:** Gothic A1, falling back through Bricolage Grotesque, Arial, and sans-serif.
**Body Font:** DM Sans with a sans-serif fallback.
**Section Font:** Bricolage Grotesque with Arial and sans-serif fallbacks.

The hero is firm and readable; the section headings are more rounded and conversational. DM Sans handles controls, copy, and the wordmark. All three fonts are local; `app/layout.tsx` registers them with `display: swap`.

### Hierarchy
- **Display** (`display`): the two-line hero. At viewport maxima of 1100px and 1000px it steps to 40px and 38px; at 900px it becomes 44px; at 600px it uses `clamp(32px, 8.4vw, 44px)` and slightly looser tracking (-0.03em).
- **Headline** (`headline`): workspace section heading; reduces to 30px at 900px.
- **Guide Headline** (`guide-headline`): the retained guide title; 36px at 1100px, 44px at 600px, and 39px at 360px.
- **Title** (`title`): base tertiary heading; country output uses 24px and guide tips use 17px.
- **Body** (`body`): root text. Supporting paragraphs generally use 12-13px with 1.7 line height. Root line height is browser-normal, not a fabricated global token.
- **Label** (`label`): issuing-country label; measurements use tabular numerals and 14px, reducing to 13px on phones.
- **Action** (`action`): primary controls; becomes 15px at 600px.
- **Brand** (`brand`): text wordmark; responsive and footer sizes are smaller without changing its family.

There is no imposed mathematical type ratio, all-caps label system, or separate monospace face.

## Layout

The shared container is centered with a maximum border-box width of 1160px and horizontal padding of 36px. Padding becomes 28px at 1000px and 22px at 900px. Repeated spacing is extracted in frontmatter; it is an observed vocabulary, not a uniform arithmetic scale.

The current homepage uses an open hero, not an enclosing upload card. Its desktop grid is `1.1fr 1fr`, minimum height 567px, with 47px top and 65px bottom padding; at 1400px and above those paddings become 60px and 75px. The form has a 475px maximum width. At 1000px the grid becomes equal columns. At 900px it stacks; the copy is centered within a 520px maximum width and has a 387px minimum height, increasing to 410.5px at 600px. These measurements preserve the comparison's incumbent coordinates, not a reusable minimum height for every page.

The protected comparison is square, right-aligned, and at most 460px wide on desktop. At 900px and below it is at most 420px wide with `32px auto 0` margins. Keep its placement, image scale, and responsive behavior intact.

The guide uses `1.06fr 1fr 1.05fr` columns, 36px gaps, and 40px padding. At 1100px padding/gaps become 30px/24px. At 900px it has two columns with the tips spanning a three-column row. At 600px it stacks intro, illustration, and tips into one column with 30px gaps and `30px 25px` padding. At 360px horizontal padding becomes 22px.

The conditional workspace uses `minmax(0, 1.4fr) minmax(0, 1fr)` and stacks at 900px. Photo and details padding is 36px, reducing to 26px at 1100px; phone photo padding is `25px 18px` and details padding is 24px. The output frame follows the selected country's aspect ratio. Keep the result-download action with the workspace heading; on phones the heading and action stack.

Navigation height changes from 100px to 80px at 900px. At 600px the free/no-account note moves from navigation to the form. Footer content wraps at 900px and its middle tagline hides.

## Elevation & Depth

Most depth comes from tonal surfaces and fine borders: the page, white working areas, pale sage photo backing, and lilac guide. The form and guide have no ambient card shadow. The protected comparison is the localized exception.

### Shadow Vocabulary
- **Comparison Stage** (`0 16px 40px #243c3210`): soft lift on the existing image stage.
- **Comparison Divider** (`0 0 0 1px #243c3230`): contrast around the white two-pixel divider.

Keyboard focus is an outline, not a shadow: general controls use 3px in `focus` with a 5px offset. The comparison retains its own 3px `#a9bf72` focus-within outline and 5px offset.

**The Local Depth Rule.** Keep ambient lift confined to the existing comparison; use tone and fine boundaries for the form, guide, and workspace.

## Shapes

Small controls have modest corners: fields use `field`, actions use `action`, and alerts use `feedback`. Larger regions are softer: the workspace uses `workspace`, the comparison uses `comparison`, and the guide uses `guide`, reducing to `guide-mobile` on phones. The photo-side workspace corners use `workspace-inner` inside the outer border.

Most structural borders are one pixel. The illustration window uses `framing`, clips the figure, and carries four small right-angle corner marks plus dashed headroom and eye-level lines. Its specific silhouette is retained instruction, not decoration to replace with a generic image.

## Components

### Buttons

Direct, full-width where they perform the main form task. Primary shape, color, typography, and padding are captured in `button-primary`; minimum height is 58px and icon gap is 12px. Upload and generate span the form; download is content-width beside the workspace heading.

Hover deepens both background and border over 0.18s ease-out. Disabled controls use `button-primary-disabled` and a not-allowed cursor. Focus uses the shared outline. No custom pressed transform or decorative entrance animation exists.

The retained "I have a photo" link has a 44px minimum height, arrow, 13px medium text, and a thin bottom rule; hover underlines the text. File-change and remove actions are smaller utility controls, not invented secondary filled buttons.

### Inputs / Fields

The issuing-country control is a native select inside a white, one-pixel bordered row with `field` corners. Its label and tabular dimensions sit above it. The chevron is an inert inline icon; the select retains keyboard behavior and descriptions. Disabled state locks country changes during processing without a separate painted field variant.

The actual file input is visually hidden and reached through the upload button. Accepted formats and size remain visible. Drag-over adds a lilac background and the shared focus-colored outline. Selecting a photo shows a local preview; upload is not automatic processing.

### Navigation

Text wordmark on the left, a "Photo guide" anchor and free/no-account note on the right. Links have 44px minimum height; desktop navigation text is 15px with 36px gaps, reducing to 12px gaps at 900px and 13px link text at 600px. Hover underlines; keyboard focus remains explicit. This is in-page navigation with no invented selected tab, chip system, or mobile hamburger.

### Cards / Containers

The workspace is a bordered white container with a pale sage photo area, paired captions, country details, and a live status message. The lilac guide has no border or shadow and retains its intro, framing diagram, three tips, and return link. The acceptance disclaimer remains beneath it.

The recoverable error alert uses a warm background, matching border, 20px padding, 12px icon gap, and 13px text at 1.6 line height. It has `role="alert"` and receives focus when an error appears. The result heading receives focus when processing succeeds. Neither state is communicated by color alone.

### Illustrated Framing Guide

The retained CSS/Lucide illustration has a 200px by 250px window, growing to 215px wide at 600px. The `UserRound` figure is 215px by 230px, centered and clipped below the window. Corner markers are 18px square at a 12px inset. Dashed headroom and eye lines sit at 39px and 103px. Keep the visible headroom label, eye-level label, and head-and-shoulders caption together with the accessible description.

### Protected Comparison

`components/background-comparison.tsx`, its CSS module, and both imported rasters are protected. The original layer scales by 1.08; the removed-background layer is clipped rather than resized. A native range input overlays the stage and reports the revealed percentage.

Its existing animation traverses at 0.012 percentage points per millisecond, reverses at the limits, and pauses on mouse hover, keyboard focus, drag, or reduced-motion preference. Pointer dragging and one-percent arrow-key steps remain intact. Do not reproduce a mockup's approximate comparison in place of this component.

Processing spinners rotate over 1.2s linearly; reduced motion disables them and all CSS transitions, changes smooth scrolling to auto, and stops the comparison's automatic sweep. No new motion is specified.

The sidecar intentionally contains five actual source-derived previews: primary action, country field, navigation, error alert, and illustrated framing guide. They are framework-free HTML/CSS samples, not a substitute for the app's handlers. There is no chip component to invent, and protected raster content is not duplicated into previews.

## Do's and Don'ts

### Do:
- **Do** keep the off-white ground, softer green hierarchy, and gentle lilac illustrated guide.
- **Do** use the implemented native controls, visible focus treatments, and reduced-motion behavior.
- **Do** preserve the comparison's original source, images, interaction, dimensions, and responsive placement.
- **Do** retain the illustrated guide's framing diagram, preparation tips, return link, and acceptance disclaimer.
- **Do** record asset origins in prose and treat tonal ramps as preview metadata rather than new UI colors.

### Don't:
- **Don't** reintroduce the rejected Sign Band or large dark or saturated green fields.
- **Don't** treat the approved mockup as pixel-exact authority over the user's retained originals.
- **Don't** modify protected rasters or embed provenance metadata into them.
- **Don't** add enclosing upload cards, generic chip systems, or decorative entrance motion to this documented homepage.
- **Don't** imply official acceptance, automatic upload on selection, or unverified privacy guarantees.
