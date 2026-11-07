/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "Consolas", "monospace"],
      },
      colors: {
        // "le carnet du coutelier": warm graphite neutrals on paper (see DESIGN.md).
        // Overrides Tailwind's cool slate so every surface shares one warm ramp.
        slate: {
          50: "#f8f6f1",
          100: "#f0ede6",
          200: "#e3dfd5",
          300: "#cdc7ba",
          400: "#a39d90",
          500: "#6f6a60",
          600: "#57534b",
          700: "#403d37",
          800: "#2b2925",
          900: "#1c1b18",
        },
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
