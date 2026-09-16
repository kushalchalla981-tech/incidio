import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "page-bg": "var(--page-bg)",
        "surface-base": "var(--surface-base)",
        "surface-elevated": "var(--surface-elevated)",
        "surface-sunken": "var(--surface-sunken)",
        "border-soft": "var(--border-soft)",
        "border-strong": "var(--border-strong)",

        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-tertiary": "var(--text-tertiary)",

        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        "accent-border": "var(--accent-border)",
        security: "var(--brand-security)",

        "status-critical": "var(--status-critical)",
        "status-high": "var(--status-high)",
        "status-medium": "var(--status-medium)",
        "status-low": "var(--status-low)",
        "status-success": "var(--status-success)",

        // Aliases for compatibility
        danger: "var(--status-critical)",
        warn: "var(--status-high)",
        info: "var(--status-medium)",
        muted: "var(--text-secondary)",
        fg: "var(--text-primary)",
        "fg-2": "var(--text-secondary)",
      },
      fontFamily: {
        display: ["Inter", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', '"SF Mono"', "ui-monospace", "Menlo", "monospace"],
      },
      fontSize: {
        "h1": ["24px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "600" }],
        "h2": ["16px", { lineHeight: "1.4", letterSpacing: "-0.01em", fontWeight: "600" }],
        "body": ["14px", { lineHeight: "1.5" }],
        "meta": ["12px", { lineHeight: "1.5" }],
        "2xl": ["22px", { lineHeight: "1.3", letterSpacing: "-0.02em" }],
        "3xl": ["28px", { lineHeight: "1.25", letterSpacing: "-0.02em" }],
        "4xl": ["36px", { lineHeight: "1.15", letterSpacing: "-0.025em" }],
        "5xl": ["46px", { lineHeight: "1.1", letterSpacing: "-0.03em" }],
      },
      borderRadius: {
        "sm": "4px",
        "DEFAULT": "6px",
        "md": "8px",
        "lg": "12px",
        "xl": "16px",
        "full": "9999px",
      },
      keyframes: {
        "float-a": {
          "0%,100%": { transform: "translateY(0) rotate(0deg)" },
          "50%": { transform: "translateY(-9px) rotate(-2deg)" },
        },
        "float-b": {
          "0%,100%": { transform: "translateY(0) rotate(0deg)" },
          "50%": { transform: "translateY(7px) rotate(2deg)" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "float-a": "float-a 7s ease-in-out infinite alternate",
        "float-b": "float-b 8s ease-in-out infinite alternate",
        "spin-slow": "spin-slow 20s linear infinite",
      },
      boxShadow: {
        "sm": "0 1px 2px rgba(16, 24, 40, 0.05)",
        "card": "0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 12px rgba(16, 24, 40, 0.06)",
        "md": "0 4px 12px rgba(16, 24, 40, 0.08)",
        "lg": "0 8px 24px rgba(16, 24, 40, 0.1)",
        "xl": "0 16px 40px rgba(16, 24, 40, 0.12)",
        "focus-accent": "0 0 0 3px var(--accent-soft)",
      },
      maxWidth: {
        container: "1200px",
        content: "1120px",
        text: "640px",
      },
    },
  },
  plugins: [],
};
export default config;