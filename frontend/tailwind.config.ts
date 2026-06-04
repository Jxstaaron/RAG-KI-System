import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f1117",
        panel: "#1e2029",
        panelSoft: "#2b2d38",
        line: "#3b3e4b",
        violet: "#8b5cf6",
        violetSoft: "#a78bfa",
      },
    },
  },
  plugins: [],
};

export default config;
