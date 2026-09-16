# UI Architecture & Design System — AI Incident Copilot

> **Status note (reference design):** This document is the **reference design**
> captured during planning. It describes a **dark, terminal-meets-glassmorphism
> theme** (deep charcoal `#0A0A0F`, cyan `#00FFC8` accent). The **implemented
> UI currently differs**: it uses a **light theme** with its own design tokens
> (defined in `frontend/src/app/globals.css`), while keeping the overall layout
> concepts (sidebar, topbar, card-based dashboard, `/incidents`, `/logs`,
> `/analytics`, `/settings`, plus a `/scans` page for the Security Scan
> feature). Treat the visual language below as the original specification, not
> a description of the current UI. The rest of the architectural guidance
> remains valid.

## Design Philosophy

**"Calm in the chaos."** Every pixel serves the operator during a Sev-1. The interface is a control room, not a marketing page — authoritative, minimal, and ruthlessly purposeful.

### Core Tenets
- **Terminal-meets-glassmorphism** — Engineers trust CLIs. The UI borrows monospaced log views, ASCII-style progress, and a command-prompt nav metaphor, layered with modern glass panels and depth.
- **Single-accent urgency** — One high-energy color (cyan `#00FFC8`) against deep charcoal `#0A0A0F`. Red/orange reserved exclusively for active incidents. No decorative gradients.
- **Progressive disclosure** — Summary first. Drill on hover. Detail on click. The homepage shows 3 KPIs, not 40.
- **Role-aware defaults** — A SOC analyst, on-call engineer, and CISO each see a different dashboard without touching settings.

---

## Visual Language

### Color System

```
--bg-deep:       #0A0A0F     (Primary background)
--bg-surface:    #13131A     (Card/surface background)
--bg-elevated:   #1C1C26     (Elevated panels, modals)
--border-subtle: #252533     (Card borders)
--border-focus:  #2E2E40

--accent-cyan:   #00FFC8     (Primary accent — healthy, active, AI insights)
--accent-green:  #22C55E     (Resolved, operational)
--accent-yellow: #EAB308     (Warning, degraded)
--accent-red:    #EF4444     (Critical incident, alert)
--accent-orange: #F97316     (Escalating, attention needed)

--text-primary:  #F1F1F6
--text-secondary:#9090A8
--text-muted:    #5C5C72
```

### Typography

| Token | Family | Weight | Size | Use |
|---|---|---|---|---|
| `--font-display` | Inter | 600 | 32px | Page titles |
| `--font-heading` | Inter | 600 | 20px | Section headers |
| `--font-body` | Inter | 400 | 14px | Body text, labels |
| `--font-mono` | JetBrains Mono | 400 | 13px | Logs, timestamps, code, severity badges |
| `--font-mono-sm` | JetBrains Mono | 400 | 11px | Timestamps, secondary data |

All body text uses `14px` — never smaller than `13px`. Log views use `13px` monospace with `1.5` line height for scanability.

### Spacing & Sizing

4px grid base. Key spacings: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.

Card corner radius: `12px`. Buttons: `8px`. Badges: `6px`.

---

## Layout Architecture

### Bento-Grid Dashboard

The main dashboard uses a CSS Grid with named template areas:

```tsx
// Conceptual layout — 12-column responsive grid
gridTemplateAreas: `
  "sidebar  header  header"
  "sidebar  kpis    kpis"
  "sidebar  feed    timeline"
  "sidebar  logs    ai-insights"
`
```

- **Sidebar** — Collapsible (minimal icon bar when collapsed). Navigation + active incident indicator + on-call status.
- **Header** — Breadcrumb, search bar, role switcher, notification bell.
- **KPI Row** — 3–5 metric cards: Active Incidents, MTTR, MTTD, Alert Volume, Unresolved Criticals.
- **Incident Feed** — Real-time scrollable list of active incidents. Each card shows severity (color), service, timestamp, AI-generated summary.
- **Timeline** — Per-incident timeline when an incident is selected. Auto-populated with events, status changes, Slack messages.
- **Logs Panel** — Live log stream with syntax highlighting. Filterable by service, level, time.
- **AI Insights Panel** — Root cause suggestion, similar past incidents, auto-generated runbook steps.

### Page Map

```
/                          → Incident Feed (main dashboard)
/incidents/[id]            → Incident Detail (timeline, logs, RCA, chat)
/incidents/[id]/postmortem → Postmortem Editor (AI-draft, edit, approve)
/analytics                 → Analytics Dashboard (trends, MTTR charts, service health)
/analytics/reports         → Reports / Export
/settings                  → Integrations, on-call schedules, notification rules
/settings/team             → Team management, roles
/logs                      → Log Explorer (full-screen, queryable)
```

---

## Component Hierarchy

### Primitives (ui/)

```
ui/
├── Badge          — Severity badge (critical/warning/info) with dot + label
├── Button         — Variants: primary(cyan), destructive(red), ghost, outline
├── Card           — Glass surface container with optional hover state
├── KPI            — Single metric: label, value, trend arrow, sparkline
├── Input          — Search, filter inputs with dark bg
├── Select         — Dropdown with custom styling
├── Tabs           — Underline-style tab navigation
├── Toggle         — Switch component
├── Tooltip        — Hover detail tooltip (appears instantly, no delay)
├── Modal          — Slide-up overlay for confirmations, forms
└── Spinner        — Loading state (uses accent-cyan)
```

### Composables (features/)

```
features/
├── incident-feed/
│   ├── IncidentCard        — Severity dot, service, timestamp, AI summary, action buttons
│   ├── IncidentList        — Virtual-scrolled list with real-time updates
│   └── IncidentFilters     — Severity, service, status, time range
│
├── incident-detail/
│   ├── IncidentHeader      — Title, severity badge, status, timestamps
│   ├── Timeline            — Vertical event stream with icons
│   ├── TimelineEvent       — Single event node (auto + manual entries)
│   ├── ServiceMap          — Dependency graph of affected services
│   ├── RCA                 — AI root-cause analysis panel (expandable)
│   └── ActionLog           — Who did what, when
│
├── logs/
│   ├── LogStream           — Terminal-style scrolling log view
│   ├── LogLine             — Single line: timestamp, level, service, message
│   ├── LogSearch           — Full-text search with highlighting
│   └── LogFilters          — Level, service, time range, regex toggle
│
├── ai-panel/
│   ├── InsightCard         — AI-generated observation with confidence score
│   ├── SimilarIncidents    — Historical similar incidents list
│   ├── RunbookSuggestion   — Suggested next steps from AI
│   └── PostmortemDraft     — Auto-generated postmortem with edit capability
│
├── analytics/
│   ├── TrendChart          — Time-series chart (MTTR, alert volume, etc.)
│   ├── ServiceHealth       — Per-service health matrix
│   ├── MTTRBreakdown       — MTTR by service, severity, time of day
│   └── TopIncidents        — Most frequent incident types
│
├── navigation/
│   ├── Sidebar             — Collapsible nav with active incident indicator
│   ├── Topbar              — Search, role switcher, notification bell
│   └── Breadcrumb          — Page hierarchy
│
└── shared/
    ├── EmptyState          — Illustration + message + CTA
    ├── ErrorState          — Error message + retry button
    ├── LoadingSkeleton     — Shimmer skeleton matching card layout
    └── OnCallBadge         — Shows who's on call now
```

---

## States & Edge Cases

Every data-driven component handles 4 states:

| State | Visual |
|---|---|
| **Loading** | Skeleton shimmer matching final layout (never spinners for primary content) |
| **Empty** | Illustration + "No incidents yet" or "No matching logs" + contextual CTA |
| **Error** | Red-tinted card + error message + "Retry" button. Never a generic toast. |
| **Success** | Normal render. Success toasts only for mutations (acknowledge, resolve). |

### Edge Cases to Handle
- **Real-time disconnect** — Banner at top: "Live updates paused. Reconnecting..." with pulsing indicator
- **Stale data** — Timestamp shows "2m ago" in muted color. After 5m, card border shifts to warning yellow
- **Overflow** — Incident feed hits 50+ active. Virtual scroll + "Showing 50 of 142" counter. Auto-collapse older items
- **Empty log search** — "No matches for `foobar`" with tips: try broader term, check time range, regex syntax reminder
- **Mobile incident declaration** — Simplified form: 3 fields max (title, severity, service). Progressive disclosure for advanced fields

---

## Interaction Patterns

### Log Stream
- Auto-scrolls by default; pause on manual scroll-up
- "Jump to bottom" FAB appears when paused
- Click any log line to pin it + open detail panel
- Ctrl+F highlights instantly (no modal)

### Incident Cards
- Hover: reveal AI summary + action buttons (acknowledge, escalate, resolve)
- Click: navigate to `/incidents/[id]`
- Drag to reassign severity (desktop only)
- Right-click context menu: "Copy ID", "Open in Slack", "Silence for 15m"

### Timeline
- Auto-populated from Slack, PagerDuty, deploy events
- Hover any event: show exact timestamp + source
- Click: scroll to source log/alert
- "Summarize" button collapses timeline into AI-generated narrative

### AI Insights Panel
- Collapsed by default (show only count: "3 insights")
- Expand to show ranked suggestions
- Each insight has a confidence bar + "Accept" / "Dismiss" buttons
- Dismissed insights train the model (stored locally as feedback)

---

## Responsive Behavior

| Breakpoint | Layout Change |
|---|---|
| `>=1280px` (desktop) | Full bento-grid, sidebar visible, multi-column |
| `1024px–1279px` (tablet landscape) | Sidebar collapsed to icons, 2-column KPI row |
| `768px–1023px` (tablet) | Single column, stacked panels, scrollable feed |
| `<768px` (mobile) | Bottom nav bar replaces sidebar, full-screen panels, simplified cards |

Mobile-specific:
- Incident detail opens as a full-screen slide-over (not a new page)
- Swipe left/right to navigate between timeline/logs/RCA
- Pull-to-refresh on incident feed
- Bottom sheet for filters instead of sidebar

---

## Technology Alignment

| Concern | Choice | Why |
|---|---|---|
| Styling | Tailwind CSS v4 | Utility-first, matches project conventions |
| Charts | Recharts (or lightweight `@tremor/react`) | Composable, dark-mode aware |
| Icons | Lucide React | Consistent, tree-shakeable, monochrome-friendly |
| Real-time | Server-Sent Events (backend) + React `use` hook | Simpler than WebSockets for log streams |
| Virtual scroll | `@tanstack/react-virtual` | Handles 10k+ log lines / incident cards |
| Fonts | Inter (UI) + JetBrains Mono (code) via `next/font` | Zero CLS, self-hosted |
| State | React Server Components by default + `useActionState` for mutations | Next.js 16 native patterns |

---

## Dark Mode (Default, No Toggle)

This project is **dark-only**. The entire design assumes a dark operating environment (NOC, war room, late-night on-call). No light mode. This eliminates an entire class of color bugs and ensures the accent colors always read correctly.

---

## Implementation Priority

When building, follow this order:

1. **Design tokens** — Tailwind config: colors, fonts, spacing, animations
2. **Primitives** — `ui/` components: Button, Card, Badge, KPI, Input
3. **Shell** — Sidebar + Topbar layout, responsive grid
4. **Incident Feed** — The hero view (empty → loading → populated)
5. **Incident Detail** — Timeline + log stream + AI panel
6. **Analytics** — Charts + trend data
7. **Postmortem** — Editor + AI draft
8. **Polish** — Micro-interactions, skeleton states, error boundaries, accessibility

Every component ships with its 4 states (loading, empty, error, success) before any feature work is considered done.
