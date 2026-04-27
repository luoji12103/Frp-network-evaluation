---
name: mc-netprobe
description: Operational panel for monitoring Minecraft and FRP network paths.
colors:
  panel-ink: "#020617"
  text-strong: "#0f172a"
  text-muted: "#475569"
  text-subtle: "#64748b"
  surface: "#ffffff"
  surface-soft: "#f8fafc"
  surface-tint: "#eef2ff"
  border-subtle: "#e2e8f0"
  accent-sky: "#0ea5e9"
  accent-sky-strong: "#0369a1"
  accent-teal: "#14b8a6"
  success-soft: "#ecfdf5"
  success-ink: "#047857"
  warning-soft: "#fffbeb"
  warning-ink: "#b45309"
  danger-soft: "#fff1f2"
  danger-ink: "#be123c"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.875rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.3
  title:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.16em"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  pill: "9999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
  xl: "24px"
  xxl: "32px"
components:
  surface-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.xl}"
    padding: "20px"
  button-primary:
    backgroundColor: "{colors.panel-ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "8px 12px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-strong}"
    rounded: "{rounded.pill}"
    padding: "8px 12px"
  nav-pill-active:
    backgroundColor: "{colors.panel-ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "12px 16px"
  badge-info:
    backgroundColor: "{colors.surface-soft}"
    textColor: "{colors.accent-sky-strong}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
---

# Design System: mc-netprobe

## 1. Overview

**Creative North Star: "The Calm Operations Console"**

This system is a light, high-clarity operational console for a technically literate user who needs to inspect topology health, correlate runs and alerts, and act without losing trust in the interface. The visual language is restrained, cool-toned, and explicit: soft slate neutrals carry most surfaces, deep ink anchors navigation and primary controls, and selective sky or teal accents mark direction, state, and focus.

It should feel infrastructural rather than theatrical. The UI is allowed to have polish, including soft gradients at the page edge and glass-like headers on the public view, but those details must support orientation rather than becoming the story. The system explicitly rejects neon observability clichés, purple-gradient dashboards, and consumer-style playfulness inside operator workflows.

**Key Characteristics:**
- Light-first operational canvas with tinted neutrals.
- Large radii and pill actions used to soften structure without making it casual.
- Strong separation between read-only context and executable controls.
- Metrics, timestamps, and IDs treated as first-class supporting typography.
- Public and admin surfaces share a family resemblance, but the admin view carries more density and stronger navigational weight.

## 2. Colors

The palette is intentionally restrained: neutral surfaces dominate, a near-black slate provides authority, and sky or teal accents are introduced only where navigation, refresh, path access, or state visibility need emphasis.

### Primary
- **Panel Ink** (`#020617`): Used for active navigation pills, primary buttons, code blocks, and the strongest anchoring elements. This is the weight-bearing color of the system.
- **Command Slate** (`#0f172a`): Used for page titles, strong labels, and high-importance text when the surface should stay lighter than full panel ink.

### Secondary
- **Signal Sky** (`#0ea5e9`): Used in the admin shell background glow, navigational links, and informational callouts where the UI needs a directional accent without implying danger.
- **Status Teal** (`#14b8a6`): Used in the public shell background glow and for read-only health emphasis where the surface should feel transparent and steady rather than urgent.

### Tertiary
- **Recovery Green** (`#047857` on `#ecfdf5`): Used for success and healthy completion states.
- **Escalation Rose** (`#be123c` on `#fff1f2`): Used for failed, conflicted, or destructive states.
- **Operator Amber** (`#b45309` on `#fffbeb`): Used for warning or degraded states that need attention but not panic.

### Neutral
- **Operator White** (`#ffffff`): Default card and modal surface.
- **Slate Mist** (`#f8fafc`): Page canvas, empty states, and subdued fills.
- **Topology Tint** (`#eef2ff`): Admin background falloff and soft structural tinting.
- **Quiet Border** (`#e2e8f0`): Default border and separation color.
- **Muted Copy** (`#475569`): Secondary copy, descriptions, supporting metadata.
- **Subtle Copy** (`#64748b`): Timestamps, labels, and tertiary metadata.

### Named Rules
**The Calm Signal Rule.** Accent colors do not own the page. They appear where the user needs to orient, decide, or verify state, and then they get out of the way.

## 3. Typography

**Display Font:** `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
**Body Font:** `ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
**Label/Mono Font:** system mono only for inline code, topology IDs, commands, logs, and build labels.

**Character:** The current type system is utilitarian and modern. It does not attempt personality through font choice; instead it relies on disciplined scale, spacing, and contrast to feel exact and trustworthy.

### Hierarchy
- **Display** (600, `1.875rem`, 1.1): Page-level headings like `Admin Panel`, `Public Panel`, and major section titles.
- **Headline** (600, `1.25rem`, 1.3): Surface titles and dense section headers.
- **Title** (600, `1.125rem`, 1.4): Sub-section labels, run cards, node names, and key values.
- **Body** (400, `0.875rem`, 1.6): Descriptions, status summaries, and operational copy. Keep long-form lines under roughly 70ch.
- **Label** (600, `0.75rem`, tracking `0.16em`): Uppercase micro-labels for stat cards, metadata rows, and category framing.

### Named Rules
**The Instrument Label Rule.** Small labels should read like control-surface markings: short, uppercase where appropriate, and never verbose enough to compete with the data.

## 4. Elevation

This system is flat by default with a small amount of ambient lift. Most surfaces separate themselves through background contrast, borders, and large-radius containment. Shadows exist to establish a readable stack, not to create drama.

### Shadow Vocabulary
- **Resting Surface:** Soft shadow on white cards, typically the equivalent of Tailwind `shadow-sm` with a slate-tinted cast. Use for panels, cards, and summary surfaces.
- **Selected Surface:** Stronger lift on active navigation and selected list items, equivalent to `shadow-lg` with a pale slate cast. Use only when a current selection must remain obvious.
- **Modal Surface:** Heaviest lift in the system. Pair with a darkened backdrop rather than increasing card ornamentation.

### Named Rules
**The Flat-Until-Stateful Rule.** Surfaces stay mostly flat until they need to signal selection, modal isolation, or active focus.

## 5. Components

### Buttons
- **Shape:** Predominantly pill-shaped for compact actions, with `9999px` radius. Login form actions use a smaller `8px` radius for formality.
- **Primary:** Deep ink fill with white text. Used for direct operator actions and the public dashboard return button.
- **Secondary:** White or soft-neutral fill with a subtle ring and dark text. Used for refresh, sign-out, and low-risk contextual actions.
- **Danger:** Rose fill with white text. Reserved for destructive or clearly risky operations.
- **Hover / Focus:** Color shifts are subtle. Focus is communicated through visible rings, not motion tricks.

### Chips
- **Style:** Rounded full badges with soft background tint, strong text color, and inset ring.
- **State:** Severity and runtime states map to green, amber, rose, sky, or slate families. The shape remains stable while only tone changes.

### Cards / Containers
- **Corner Style:** Primary surfaces use `24px` radii, inner detail blocks use `16px`, and compact inline metrics use `12px`.
- **Background:** White cards on a mist-tinted page canvas. Secondary blocks use `#f8fafc` rather than another card layer whenever possible.
- **Shadow Strategy:** Very soft resting shadows, stronger only for selected objects or overlays.
- **Border:** Thin slate borders are the default separator. Dashed borders are reserved for empty states.
- **Internal Padding:** `20px` is the core panel padding, with `16px` used for denser sub-blocks.

### Inputs / Fields
- **Style:** Simple white or transparent fields with a subtle slate border, smaller radius than navigation or action pills, and high-contrast labels.
- **Focus:** A visible slate focus ring with offset, prioritizing reliability over stylistic flourish.
- **Error / Disabled:** Error states use rose-tinted surfaces; disabled states reduce opacity and pointer affordance instead of changing layout.

### Navigation
- **Admin Navigation:** Left rail with active destinations shown as dark rounded pills with white text and shadow. Inactive items stay quiet until hover.
- **Public Navigation:** Header-level action cluster that keeps the public surface light and approachable, with build identity and admin entry side by side.
- **Metadata Blocks:** Topology ID, generated-at freshness, build labels, and route-level state all live in supporting containers rather than competing with primary content.

### Signature Component
- **Operational Surface Stack:** `Surface`, `SurfaceBody`, `SurfaceTitle`, `StatCard`, and `ToneBadge` together define the system more than any single screen. The design language is built from these reusable, quiet primitives rather than bespoke hero sections.

## 6. Do's and Don'ts

### Do:
- **Do** keep the default canvas light, cool, and readable for long operational sessions.
- **Do** reserve the deepest slate for active state, primary controls, and code-heavy content.
- **Do** use large radii to make dense information feel organized, then keep ornamentation low.
- **Do** show operational freshness explicitly with generated-at, last-captured, and last-run timestamps.
- **Do** pair every state color with text labels, summaries, or badges so meaning survives without hue.
- **Do** let public surfaces feel related to admin surfaces while remaining clearly read-only.

### Don't:
- **Don't** turn the panel into a generic neon observability dashboard.
- **Don't** introduce purple-gradient branding, glass-heavy cards, or decorative glows that compete with health data.
- **Don't** hide risky actions inside visually identical controls. Action severity must be legible before interaction.
- **Don't** collapse everything into undifferentiated data tables or endlessly repeated cards.
- **Don't** use marketing-style reassurance or hype language inside operator workflows.
- **Don't** treat motion as the main carrier of hierarchy or meaning.
