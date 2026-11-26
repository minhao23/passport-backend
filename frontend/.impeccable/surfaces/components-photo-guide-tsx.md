---
version: 1
slug: "components-photo-guide-tsx"
primary_target: "frontend/components/passport-page.tsx"
related_targets: ["frontend/components/passport-page.module.css", "frontend/app/page.tsx"]
---

# Submission Photo Examples

Mode: Read. Preserve the existing submission guidance. Keep the studio,
protected comparison, and completed-result framing help unchanged.

## Direction Contract

THESIS: Make the supplied photo-example sheet available on request without
adding a long preparation panel to the initial page.

OWN-WORLD: Reuse the off-white ground, sage text, quiet utility links, and
shared green focus outline. The supplied sheet keeps its original pixels.

STORY: Open "View photo examples" to see the sample comparisons inline.
No image URL link, new tab, or popup. The user requested removal of the
text-version disclosure and explanatory copy, leaving only the attribution
"taken from: Singapore ICA." above the sheet.

FIRST VIEWPORT: The existing acceptance warning remains below the studio.
A compact, initially closed native disclosure follows it. Expanded content
contains the attribution and complete sheet centered at a readable size.
The footer contains only "Contact me".

FORM: Narrow code-led extension; no concept round or new visual system.
Use a keyboard-operable native disclosure and the clearer sample_rules.jpg.
Preserve its 653:3058 image ratio, render at up to 653px wide, and fit it to
phone widths without cropping. Provenance: user-supplied local JPEG, identified
by the user as a Singapore ICA reference. Keep only sample_rules.jpg;
the redundant sample_rules.jpeg has been removed.

## Implementation and Verification

The static header, submission warning/examples, and footer share the
`components/passport-page.tsx` Server Component. `app/page.tsx` remains a small
entry point, and examples styling stays in `passport-page.module.css`.
The historical brief slug remains stable after that consolidation.

Regression checks render the actual combined page with only the interactive
studio stubbed. Verify warning/examples/footer order, initially closed native
disclosure, exact attribution, JPG dimensions, no image links, and the single
contact link. Production-browser checks cover keyboard/touch toggling, centered
responsive sizing, and asset parity. Keep temporary captures outside the repo;
future mockups are runnable HTML.
