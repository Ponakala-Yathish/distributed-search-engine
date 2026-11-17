import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#f2efe7",
        "paper-raised": "#faf8f2",
        ink: "#171813",
        muted: "#5d6057",
        line: "#c9c6bc",
        cobalt: {
          DEFAULT: "#2948d4",
          soft: "#e3e7ff",
          deep: "#17319f",
        },
        healthy: "#2f6b4f",
        degraded: "#9a5a12",
        critical: "#a13a32",
      },
      fontFamily: {
        sans: [
          "Source Sans 3 Variable",
          "Source Sans 3",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(23, 24, 19, 0.05), 0 16px 40px rgba(23, 24, 19, 0.08)",
      },
      maxWidth: {
        reading: "75ch",
      },
    },
  },
  plugins: [],
};

export default config;
