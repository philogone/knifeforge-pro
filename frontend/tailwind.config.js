/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        // "le carnet du coutelier": warm graphite neutrals on paper (see DESIGN.md).
        // Overrides Tailwind's cool slate so every surface shares one warm ramp; the values
        // live in main.css as CSS variables so the dark theme swaps the whole ramp at once.
        slate: Object.fromEntries(
          [50, 100, 200, 300, 400, 500, 600, 700, 800, 900].map((k) => [k, `rgb(var(--slate-${k}) / <alpha-value>)`]),
        ),
        // the sheet colour: white by day, warm charcoal at night
        paper: "rgb(var(--paper) / <alpha-value>)",
        // "vert olive patiné": the action and selection colour
        accent: {
          50: "#f4f6ea",
          100: "#e7ecd2",
          200: "#cfd8a6",
          300: "#b0bd72",
          400: "#8c9b45",
          500: "#6b7a2c",
          600: "#4d5a1c",
          700: "#3f4a17",
          800: "#343c15",
          900: "#2b3213",
        },
      },
    },
  },
  plugins: [],
};
