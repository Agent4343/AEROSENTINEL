/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        /* Emergency-domain palette */
        "fire-red":     "#ef4444",
        "fire-orange":  "#f97316",
        "water-blue":   "#3b82f6",
        "water-cyan":   "#06b6d4",
        "damage-amber": "#f59e0b",
        "rescue-green": "#22c55e",
        "hazard-violet": "#8b5cf6",

        /* Dark ops centre surfaces */
        "ops-950": "#020617",
        "ops-900": "#0f172a",
        "ops-850": "#131c31",
        "ops-800": "#1e293b",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        glow: "0 0 15px 2px rgba(251,191,36,0.15)",
        "glow-red": "0 0 15px 2px rgba(239,68,68,0.2)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
  ],
};