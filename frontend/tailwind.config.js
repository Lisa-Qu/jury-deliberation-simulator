/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1a1814",
        parchment: "#f4ecd8",
        oak: "#6b4f2e",
      },
    },
  },
  plugins: [],
};
