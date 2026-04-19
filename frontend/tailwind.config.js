/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', '"system-ui"', "sans-serif"],
      },
      colors: {
        ink: {
          900: "#0b0b0c",
          800: "#17181a",
          700: "#25262a",
          600: "#3a3c42",
          500: "#60636b",
          400: "#9699a1",
          300: "#c8cad0",
          200: "#e5e6ea",
          100: "#f2f3f5",
          50: "#fafafb",
        },
        accent: {
          50: "#fffaf0",
          500: "#f59e0b",
          600: "#d97706",
        },
      },
    },
  },
  plugins: [],
};
