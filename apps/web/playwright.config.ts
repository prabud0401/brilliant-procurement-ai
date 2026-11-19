import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.WEB_BASE_URL || "http://localhost:3000";

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
