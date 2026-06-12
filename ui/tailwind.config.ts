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
        canvas: "#F8F7F4",
        surface: "#FFFFFF",
        ink: "#1A1A2E",
        "ink-muted": "#6B7280",
        accent: "#2D6A4F",
        "accent-light": "#D8F3DC",
        border: "#E5E7EB",
        danger: "#DC2626",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      maxWidth: {
        page: "1120px",
        form: "560px",
      },
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
        "30": "7.5rem",
      },
      letterSpacing: {
        heading: "0.04em",
      },
      boxShadow: {
        card: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)",
        "card-hover":
          "0 10px 25px -5px rgb(0 0 0 / 0.08), 0 4px 10px -5px rgb(0 0 0 / 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
