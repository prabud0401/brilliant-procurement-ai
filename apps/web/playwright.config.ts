import { defineConfig, devices } from "@playwright/test";
import path from "path";

try {
  process.loadEnvFile(path.resolve(__dirname, "../../.env"));
} catch {
  // Ignore if .env doesn't exist or already loaded
}

const baseURL =
  process.env.WEB_BASE_URL ||
  (process.env.WEB_PORT ? `http://localhost:${process.env.WEB_PORT}` : "http://localhost:3000");

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
