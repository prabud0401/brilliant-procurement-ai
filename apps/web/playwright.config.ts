import { defineConfig, devices } from "@playwright/test";
import fs from "fs";
import path from "path";

// Auto-load root .env if DEMO_USER_PASSWORD or ports are not in process.env
const envPath = path.resolve(__dirname, "../../.env");
if (fs.existsSync(envPath)) {
  const content = fs.readFileSync(envPath, "utf8");
  for (const line of content.split("\n")) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
      const idx = trimmed.indexOf("=");
      const key = trimmed.slice(0, idx).trim();
      const val = trimmed.slice(idx + 1).trim();
      if (!process.env[key]) {
        process.env[key] = val;
      }
    }
  }
}

const baseURL = process.env.WEB_BASE_URL || `http://localhost:${process.env.WEB_PORT || 3000}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        // If system google-chrome is available, use it when browser not installed
        channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL || "chrome",
      },
    },
  ],
});
