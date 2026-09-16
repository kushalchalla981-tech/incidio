# AI Incident Copilot & Security Checker: Design Research Report

## Section A: Research Sources

1. **Linear / Developer Tools (Linear, Vercel, Supabase)**
   - **What I studied:** Information hierarchy, typography (Inter/Geist), dark-mode aesthetics, component states, and grid systems.
   - **What is useful:** Linear's constrained palette, 4px grid system, and semantic tokens (e.g., `surface-base`, `text-primary`). Tabular numbers for metrics. Vercel's clean project cards and deployment statuses.
   - **What should NOT be copied:** Linear's hyper-minimalist approach can sometimes hide important actions behind shortcuts. For incident management, critical actions must be visible.

2. **Incident Management & Observability (Sentry, PagerDuty, Incident.io)**
   - **What I studied:** Timeline presentation, severity indicators, log density, and investigation workflows.
   - **What is useful:** Sentry's approach to actionable evidence (highlighting stack traces). PagerDuty's unambiguous severity colors. Incident.io's clear chronological timelines.
   - **What should NOT be copied:** PagerDuty's dated, overly complex table structures that overwhelm users with non-actionable columns.

3. **Security Tooling (Snyk, Semgrep, GitHub Advanced Security)**
   - **What I studied:** Vulnerability presentation, security scoring, evidence highlighting, and remediation UX.
   - **What is useful:** Semgrep's inline code evidence highlighting. Snyk's categorization of risk (Critical/High/Medium/Low) paired with actionable fixes.
   - **What should NOT be copied:** Dashboard gamification. A single "100/100" score is less useful than a "Risk Posture" summary showing open criticals vs. resolved findings.

## Section B: Design Direction

- **Overall Visual Style:** "Editorial Developer Tool Aesthetic." Clean, structured, functional, and slightly opinionated.
- **Light/Dark Strategy:** Dark-first. Developer tools for security and incidents often run in environments where dark mode reduces eye strain. A unified dark theme (#080A0A base) establishes a premium, focused environment.
- **Density:** High density for data (tables, logs, findings), but low density for layout framing (plenty of padding around main sections).
- **Typography:** Sans-serif for UI, monospace for data and code.
- **Shape Language:** Crisp. 6px-8px border radii for interactive elements (buttons, inputs), 12px for cards. Move away from the current massive 20px+ rounded corners.
- **Border Style:** Subtle 1px solid borders (`rgba(255,255,255,0.1)`) instead of heavy shadows or glows.
- **Shadow Style:** Flat/minimalist. Use elevation through surface lightness rather than drop shadows.
- **Motion Style:** Snappy and functional (150ms-200ms). No floating orbs, mesh gradients, or endless pulses unless they denote a true "live" state.
- **Icon Style:** Lucide icons (current), but scaled down slightly and used with consistent stroke widths (1.5px or 2px).

## Section C: Color System

Move away from generic blue/purple and scattered hex values. Implement a Semantic Token system based on Radix/Tailwind principles.

**Global Palette (Dark Mode Base):**
- `page-bg`: `#080A0A` (Deep dark)
- `surface-base`: `#121415` (Cards, panels)
- `surface-elevated`: `#1C1F21` (Dropdowns, modals)
- `border-soft`: `rgba(255,255,255,0.08)`
- `border-strong`: `rgba(255,255,255,0.16)`
- `text-primary`: `#EDEDED`
- `text-secondary`: `#A1A1AA` (Muted)
- `text-tertiary`: `#71717A` (Placeholders)

**Incident Manager Palette (Action/Ops oriented):**
- `accent-inc-base`: `#3B82F6` (Blue)
- `accent-inc-soft`: `rgba(59, 130, 246, 0.15)`
- `accent-inc-border`: `rgba(59, 130, 246, 0.3)`

**Security Checker Palette (Analysis oriented):**
- `accent-sec-base`: `#8B5CF6` (Purple/Violet)
- `accent-sec-soft`: `rgba(139, 92, 246, 0.15)`
- `accent-sec-border`: `rgba(139, 92, 246, 0.3)`

**Semantic Colors (Strictly for status, never for branding):**
- `status-critical` / `status-error`: `#EF4444` (Red)
- `status-high` / `status-warn`: `#F59E0B` (Amber)
- `status-medium` / `status-info`: `#3B82F6` (Blue - context dependent, or use Yellow)
- `status-low` / `status-neutral`: `#71717A` (Gray)
- `status-success`: `#10B981` (Emerald Green)

## Section D: Typography

- **Primary Font (UI):** `Inter` (or `Geist` if available). Focus on legibility and clean letterforms.
- **Monospace Font (Code/Logs):** `JetBrains Mono` or `Geist Mono`. Excellent for reading code and terminal output.
- **Numeric Font:** Ensure `font-variant-numeric: tabular-nums` is used everywhere data changes (KPIs, tables, logs).
- **Scale:**
  - H1: `24px`, font-weight 600, tracking `-0.02em`.
  - H2: `16px`, font-weight 600.
  - Body: `14px`, font-weight 400, line-height `1.5`.
  - Meta/Small: `12px` or `11px`, font-weight 400 (often used with uppercase/tracking-wide for labels).

## Section E: Design Principles

1. **Content Over Chrome:** The data is the product. Remove ambient backgrounds, floating orbs, and heavy glassmorphism.
2. **Semantic Clarity:** Colors mean something. Red means critical or error. It should never be used decoratively.
3. **Actionable Density:** Tables and logs must be dense enough to prevent excessive scrolling, but spaced enough to prevent misclicks.
4. **Context Preservation:** When viewing an incident or a security finding, the user shouldn't lose context of where they are in the app.
5. **Deterministic Layouts:** Avoid layout shifts. Use skeleton loaders that exactly match the final loaded state dimensions.
6. **Keyboard Navigable:** Forms, command menus, and lists must prioritize keyboard accessibility.
7. **Obvious State:** Active, Hover, Disabled, and Loading states must be visually distinct and consistent globally.
8. **Scalable Hierarchy:** The typography and layout must scale from a 320px mobile screen up to a 4K ultrawide without breaking.

## Section F: Product-Specific Design

- **Incident Manager:** Needs to feel like an operational control room. High contrast for alerts, clear chronological timelines, and a focus on "What's on fire right now?". The dashboard should prioritize active incidents and active log streams.
- **Security Checker:** Needs to feel like an analytical workspace. Focus on categorization, filtering, and deep dives into code evidence. The dashboard should prioritize security posture (Risk Profile > Arbitrary Score) and top unresolved findings.
- **Differentiation:** They share the `surface-base` and typography, but the topbar/sidebar highlight accents shift (Blue vs. Purple). The terminology shifts from "Investigate/Resolve" to "Review/Remediate".

## Section G: Component System

Core components to rebuild first:
1. **App Layout (Shell, Sidebar, Topbar):** Remove glassmorphism. Use solid dark colors with crisp borders.
2. **Cards:** Remove `shine`, `glow`, and 20px radii. Implement standard 1px borders with subtle inner padding.
3. **Badges:** Standardize semantic variants (`success`, `warning`, `error`, `neutral`, `info`) across both products.
4. **Tables:** Create a highly dense, border-bottom separated table component with sticky headers for findings and history.
5. **Buttons:** Primary (Accent), Secondary (Outline), Ghost (Text only), Danger (Red outline/text).
6. **Data Display (Code Block):** Create a dedicated component for raw logs and security evidence that uses `JetBrains Mono` and syntax/line highlighting.

## Section H: Page-by-Page Redesign Direction

| Page | Current Problem | New Direction |
|---|---|---|
| **Home (`/`)** | Generic layout, large glowing cards. | Minimal "Command Center" split-screen entry. Clear choice between Ops (Incidents) and Sec (Security). |
| **Inc. Dashboard** | Mock charts, confusing KPIs. | Focus on "Active Incidents" list. Remove mock charts. Show real System Health (based on recent logs) and MTTR (if available). |
| **Incident Detail** | Oversized header, poor timeline. | Split pane: Left 60% is Incident Details + Evidence. Right 40% is Chronological Timeline + Status Actions. |
| **Logs Stream** | Hard to read, expands awkwardly. | Dense terminal-style view. Tabular layout for Timestamp, Level, Service, Message. Inline expansion for raw JSON. |
| **Sec. Dashboard** | Gamified score, cluttered tables. | Replace Grade/Score with "Risk Posture" (Critical/High counts). Prioritize actionable "Top Findings to Fix". |
| **Scan Detail** | Overwhelming metadata. | Tabbed interface: "Overview", "Findings", "Raw Output". Clean split of evidence vs. remediation. |
| **New Scan/Inc.** | Large centered forms. | Structured left-aligned forms within a constrained width container. Clear stepper for Incident creation. |

## Visual Reference Board (Conceptual)

- **Brand / Global Shell:** Linear app, Vercel dashboard. (Dark, crisp, 4px grid, Inter font).
- **Incident Manager:** Sentry issues page, Incident.io timelines. (Clear severity badging, dense stack traces, chronological feeds).
- **Security Checker:** Semgrep App, GitHub Advanced Security. (Code evidence highlighting, grouped vulnerability views).
- **Components:** Radix UI primitives, shadcn/ui. (Accessible, unstyled-by-default, semantic).

## Final Recommendation

**Direction: "Technical Editorial" (Dark-First Semantic Design)**

I recommend moving away from the "flashy AI startup" aesthetic (ambient floating orbs, mesh gradients, glassmorphism) and adopting a **"Technical Editorial"** design system.

**Why?**
1. **Usability:** Engineers use incident and security tools in high-stress or highly focused scenarios. Glowing borders and translucent backgrounds cause eye strain and distract from the data.
2. **Data Density:** The current UI wastes space with 20px border radii and large padding. A crisp 4px/8px grid system allows for denser, more readable tables and logs.
3. **Scalability:** By enforcing strict semantic color tokens (e.g., `text-primary`, `status-critical`), the application can easily support theming, accessibility (high contrast modes), and consistent component building.
4. **Product Differentiation:** By standardizing the neutral surfaces, the accent colors (Incident Blue vs. Security Purple) become meaningful contextual cues rather than decorative background noise.

This direction preserves all existing functionality but presents it in a serious, professional, and highly accessible manner suited for daily developer use.
