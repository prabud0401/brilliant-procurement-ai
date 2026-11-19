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
        brand: {
          50: "#f0f7ff",
          100: "#e0effe",
          200: "#bae0fd",
          300: "#7cc5fb",
          400: "#38a5f6",
          500: "#0e87e9",
          600: "#026ac7",
          700: "#0354a1",
          800: "#074784",
          900: "#0c3c6e",
          950: "#082749",
        },
      },
    },
  },
  plugins: [],
};

export default config;
