import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#050C16",
          900: "#0A192F", // Deep Navy primary
          800: "#112240",
          700: "#1B3358",
          600: "#234476",
        },
        cyan: {
          50: "#F0FDFF",
          100: "#E0F7FA",
          200: "#B2EBF2",
          400: "#38BDF8",
          500: "#00B4D8", // Cyan accent / active
          600: "#0096C7",
          700: "#0077B6",
        },
        brand: {
          50: "#F0FDFF",
          100: "#E0F7FA",
          200: "#B2EBF2",
          300: "#90E0EF",
          400: "#48CAE4",
          500: "#00B4D8", // Cyan accent
          600: "#0096C7",
          700: "#0077B6",
          800: "#112240",
          900: "#0A192F", // Deep Navy primary
          950: "#050C16",
        },
      },
      keyframes: {
        "fade-in": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out both",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
