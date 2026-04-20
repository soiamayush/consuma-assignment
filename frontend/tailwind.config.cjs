/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', '"system-ui"', "sans-serif"],
        display: ['"Fraunces"', '"Playfair Display"', '"Georgia"', "serif"],
      },
      colors: {
        ink: {
          950: "#07070a",
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
          100: "#fdf1d7",
          200: "#fbdda2",
          300: "#f6c46a",
          400: "#efa63a",
          500: "#d98a1f",
          600: "#b36b14",
          700: "#8c5210",
        },
        blush: {
          50: "#fdf3f4",
          100: "#fbe4e7",
          200: "#f6ccd1",
          300: "#eea8b2",
          400: "#e37a8b",
          500: "#d75871",
          600: "#bf3f5c",
          700: "#9e314d",
          800: "#822a42",
          900: "#6d2639",
        },
        cream: {
          50: "#fdfbf7",
          100: "#f9f4ea",
          200: "#f2e7d2",
          300: "#e6d3ae",
          400: "#d4b57e",
          500: "#b79355",
          600: "#957340",
        },
        plum: {
          50: "#f8f4f7",
          100: "#efe3ec",
          200: "#dec6d9",
          300: "#c19fba",
          400: "#9e7495",
          500: "#7b5474",
          600: "#5f3e5a",
          700: "#4a3047",
          800: "#3a2638",
        },
      },
      boxShadow: {
        glass:
          "0 1px 2px rgba(17, 24, 39, 0.04), 0 8px 24px -12px rgba(123, 84, 116, 0.18)",
        lift:
          "0 2px 6px rgba(17, 24, 39, 0.05), 0 18px 40px -18px rgba(215, 88, 113, 0.25)",
      },
      backgroundImage: {
        "mesh-rose":
          "radial-gradient(900px 520px at 8% -8%, rgba(215,88,113,0.22), transparent 60%), radial-gradient(780px 520px at 105% 6%, rgba(246,196,106,0.28), transparent 62%), radial-gradient(820px 720px at 50% 115%, rgba(193,159,186,0.25), transparent 62%)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.35s ease-out both",
        float: "float 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

