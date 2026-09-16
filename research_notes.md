# UX/UI Research Notes

## Sentry / Incident.io / PagerDuty
- Focus on fast debugging, very high information density.
- Sentry: Extensive context around exceptions (breadcrumbs, tags, stack traces). Very semantic color usage (red for error, yellow for warning).
- Incident.io: Focus on collaboration, timeline clarity, clear role assignments.
- PagerDuty: Clear alerts, on-call schedules, strong use of primary colors to denote alert urgency.
- **Key Takeaway**: Incident Manager needs high legibility, timeline visibility, and clear visual cues for "what is broken" and "how severe".

## Vercel / Linear / Developer Tools
- **Linear**: Very strong aesthetic. Dark mode primary (#080A0A surface base), Inter font, 4px grid system, tabular numbers for data. Highly constrained semantic palette. Focus on typography hierarchy (60px headings, 17px body). Minimalist, functional.
- **Vercel**: Clean, high contrast, heavy use of Geist font. Focus on deployment status. Good use of empty states.
- **Key Takeaway**: Developer tools thrive on clean layouts, monospace fonts for data, standard sans-serif (Inter/Geist) for UI, and a very structured design token system.

## Snyk / GitHub Advanced Security / Semgrep
- **Snyk / GHAS**: Actionable findings are key. Instead of a giant list of problems, they show severity, location, and remediation (often with AI autofix now).
- **Semgrep**: Excellent at showing code snippets (evidence) with the exact line highlighted.
- **Key Takeaway**: Security Checker needs to make findings actionable. Showing a score is less useful than showing "What is the highest risk finding and how do I fix it?". Use semantic colors for severity (Critical = Red/Crimson, High = Orange, Medium = Yellow/Blue).

## Color Systems
- Semantic tokens are required. Don't use raw hex values in UI. Use CSS variables like `--surface-base`, `--text-primary`, `--status-critical`.
- Avoid using brand colors (like the current blue or purple) for states if it conflicts with meaning (e.g. don't use blue for success).

## Typography
- Inter or Geist for primary UI.
- JetBrains Mono or SF Mono for code/logs/IDs.
- Use `tabular-nums` for numeric data (like scan scores or latency).
