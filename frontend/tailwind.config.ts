import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#001d38",
          deep: "#000f24",
        },
        cream: {
          50: "#f8f6f2",
          100: "#f1ede4",
          200: "#e2e2df",
          300: "#b5b7ba",
          400: "#8b8e93",
          500: "#777a7f",
          600: "#62656a",
          700: "#383d3f",
        },
        rail: {
          DEFAULT: "#ecebe5",
          strong: "#d9d6cb",
        },
        conda: {
          ink: "#2f6b0e",
          bg: "#ecf6dc",
          "bg-soft": "#f4faea",
          border: "#c9e29f",
          dot: "#70c038",
        },
        pypi: {
          ink: "#1f33b8",
          bg: "#e8ecff",
          "bg-soft": "#f1f3ff",
          border: "#b6c1ff",
          dot: "#5773ff",
        },
        brand: {
          yellow: "#ffd432",
          "yellow-alt": "#ffca16",
        },
        error: {
          bg: "#fdebe3",
          border: "#f5c8b4",
          ink: "#7c2e14",
          accent: "#b03919",
        },
        warning: {
          bg: "#fff7d6",
          border: "#f1da6e",
          ink: "#7a5b00",
        },
      },
      fontFamily: {
        display: ['"Moranga"', "Fraunces", "ui-serif", "Georgia", "serif"],
        sans: [
          '"Inter"',
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "monospace",
        ],
      },
      maxWidth: {
        canvas: "1080px",
      },
      boxShadow: {
        card: "0 4px 8px 0 rgba(59, 61, 63, 0.02)",
        dropdown:
          "0 12px 32px -8px rgba(0, 29, 56, 0.12), 0 4px 8px -2px rgba(0, 29, 56, 0.06)",
      },
      ringColor: {
        focus: "rgba(87, 115, 255, 0.22)",
      },
      fontSize: {
        "2xs": ["10.5px", "1.4"],
      },
      letterSpacing: {
        eyebrow: "0.12em",
        tracker: "0.1em",
      },
    },
  },
  plugins: [],
} satisfies Config;
