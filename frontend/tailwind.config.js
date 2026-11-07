/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        // "vert olive patiné": the action and selection colour (see DESIGN.md)
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
