# Product

## Register

product

## Users
Operators and maintainers of `mc-netprobe` deployments, usually a single technically capable owner or a small infra-minded team.

They use the panel while pairing agents, checking FRP and Minecraft path health, validating a new build, investigating degraded latency or packet loss, and deciding whether a problem is on the client, relay, server, or panel side.

The public surface serves a secondary audience: teammates or stakeholders who need read-only visibility into path health and recent alerts without receiving operator-only controls.

## Product Purpose
`mc-netprobe` is a persistent monitoring and control plane for Minecraft plus FRP network paths.

Its job is to make a three-role topology understandable at a glance, keep historical evidence close to operational decisions, and let an operator move from symptom to affected node, path, run, or action without opening separate host sessions first.

Success looks like this: an operator can confirm whether the system is healthy, see exactly which path or node is degraded, pair and manage agents safely, and validate a release with minimal ambiguity and minimal hidden state.

## Brand Personality
Exacting, trustworthy, operationally calm.

The interface should feel like an instrument panel for a real system, not a marketing page and not a novelty dashboard. The emotional target is confidence under pressure: clear enough for fast triage, quiet enough to stay readable during incidents, and disciplined enough that operator actions feel deliberate rather than playful.

## Anti-references
- Generic neon observability dashboards, especially dark canvases with loud blue or purple glows.
- Crypto-style control panels with flashy gradients, glassmorphism, or decorative motion competing with status information.
- Consumer productivity UI tropes that make operational state feel soft, vague, or toy-like.
- Dense table-only admin screens with no hierarchy, no path to remediation, and no distinction between observation and action.
- Marketing copy patterns inside the operator workflow, including exaggerated success language or empty reassurance.

## Design Principles
- Operator confidence before novelty. Every screen should help a technically literate user trust what the system is saying and what an action will do.
- Path-first diagnosis. The UI should make it easy to move from a symptom to the affected topology slice, not bury network state behind generic object lists.
- Safe action framing. Mutating controls need explicit state, conflict visibility, confirmation where appropriate, and clear recovery hints.
- Calm visual hierarchy. Important signals should stand out without turning the whole interface into an alarm surface.
- Public transparency with scoped disclosure. The public panel should expose useful health and trend information while preserving the backend privacy contract and separating operator-only details.

## Accessibility & Inclusion
Aim for WCAG 2.1 AA or better on both admin and public surfaces.

Operational state must never rely on color alone; badges, labels, summaries, and timestamps should stay readable in monochrome or reduced-color conditions. Keyboard access should cover navigation, actions, filters, dialogs, and refresh controls. Motion should stay subtle and optional, with no essential meaning hidden inside animation. Inline code and log-like surfaces must preserve contrast and legibility for long sessions.
