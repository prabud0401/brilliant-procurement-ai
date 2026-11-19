import { test, expect } from "@playwright/test";

const DEMO_PASSWORD = process.env.DEMO_USER_PASSWORD || "demo_password_123";

test.describe("Authentication, RBAC Navigation and Security", () => {
  test("shows validation error on invalid credentials", async ({ page }) => {
    await page.goto("/login");

    await page.fill('input[name="email"]', "requester.fac@demo-holdings.example");
    await page.fill('input[name="password"]', "wrong-password-attempt");
    await page.click('button[type="submit"]');

    const errorAlert = page.locator('[role="alert"]').filter({ hasText: /invalid|unauthorized/i });
    await expect(errorAlert).toBeVisible({ timeout: 10000 });
    await expect(errorAlert).toContainText(/invalid/i);
  });

  test("signs in as Requester, sees role capabilities, and signs out", async ({
    page,
    context,
  }) => {
    await page.goto("/login");

    // Click demo account button to populate email
    await page.click(
      'button:has-text("requester.fac@demo-holdings.example")'
    );
    await page.fill('input[name="password"]', DEMO_PASSWORD);
    await page.click('button[type="submit"]');

    // Wait for navigation to home page
    await page.waitForURL("/", { timeout: 10000 });
    await expect(page.locator("h1")).toContainText(/Welcome back/i);

    // Verify Requester role badge in header
    const requesterBadge = page.locator('header span:has-text("Requester")');
    await expect(requesterBadge).toBeVisible();

    // Verify Requester Workspace capabilities on home page
    await expect(
      page.locator('h3:has-text("Requester Workspace")')
    ).toBeVisible();

    // Verify Navigation has ONLY finished features (Home only)
    const navLinks = page.locator('nav[aria-label="Main Navigation"] a');
    await expect(navLinks).toHaveCount(1);
    await expect(navLinks.first()).toHaveText("Home");

    // Security Verification: HttpOnly and SameSite=Lax cookie
    const cookies = await context.cookies();
    const sessionCookie = cookies.find((c) => c.name === "pda_session");
    expect(sessionCookie).toBeDefined();
    expect(sessionCookie?.httpOnly).toBe(true);
    expect(sessionCookie?.sameSite.toLowerCase()).toBe("lax");

    // Security Verification: document.cookie does NOT expose the token
    const documentCookie = await page.evaluate(() => document.cookie);
    expect(documentCookie).not.toContain("pda_session");
    expect(documentCookie).not.toContain("eyJ");

    // Sign out
    await page.click('button:has-text("Sign Out")');
    await page.waitForURL("/login", { timeout: 10000 });
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("signs in as Buyer and verifies Buyer role badge & capabilities", async ({
    page,
  }) => {
    await page.goto("/login");

    await page.click('button:has-text("buyer1@demo-holdings.example")');
    await page.fill('input[name="password"]', DEMO_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForURL("/", { timeout: 10000 });
    await expect(page.locator('header span:has-text("Buyer")')).toBeVisible();
    await expect(page.locator('h3:has-text("Buyer Workspace")')).toBeVisible();
    await expect(
      page.locator("text=automated quote comparison matrices")
    ).toBeVisible();

    await page.click('button:has-text("Sign Out")');
    await page.waitForURL("/login", { timeout: 10000 });
  });

  test("signs in as Manager and verifies approval delegation limit", async ({
    page,
  }) => {
    await page.goto("/login");

    await page.click(
      'button:has-text("manager.facilities@demo-holdings.example")'
    );
    await page.fill('input[name="password"]', DEMO_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForURL("/", { timeout: 10000 });
    await expect(page.locator('header span:has-text("Manager")')).toBeVisible();
    await expect(page.locator('h3:has-text("Manager (Approver) Workspace")')).toBeVisible();
    await expect(page.locator("text=AED 50,000.00")).toBeVisible();

    await page.click('button:has-text("Sign Out")');
    await page.waitForURL("/login", { timeout: 10000 });
  });

  test("signs in as Admin and verifies Admin workspace", async ({ page }) => {
    await page.goto("/login");

    await page.click('button:has-text("admin@demo-holdings.example")');
    await page.fill('input[name="password"]', DEMO_PASSWORD);
    await page.click('button[type="submit"]');

    await page.waitForURL("/", { timeout: 10000 });
    await expect(page.locator('header span:has-text("Admin")')).toBeVisible();
    await expect(
      page.locator('h3:has-text("System Administration Workspace")')
    ).toBeVisible();

    await page.click('button:has-text("Sign Out")');
    await page.waitForURL("/login", { timeout: 10000 });
  });

  test("signs in successfully for all seeded demo accounts", async ({ page }) => {
    const demoEmails = [
      "requester.fac@demo-holdings.example",
      "requester.it@demo-holdings.example",
      "buyer1@demo-holdings.example",
      "buyer2@demo-holdings.example",
      "manager.facilities@demo-holdings.example",
      "manager.it@demo-holdings.example",
      "manager.projects@demo-holdings.example",
      "admin@demo-holdings.example",
    ];

    for (const email of demoEmails) {
      await page.goto("/login");
      await page.fill('input[name="email"]', email);
      await page.fill('input[name="password"]', DEMO_PASSWORD);
      await page.click('button[type="submit"]');

      await page.waitForURL("/", { timeout: 10000 });
      await expect(page.locator("h1")).toContainText(/Welcome back/i);

      // Sign out
      await page.click('button:has-text("Sign Out")');
      await page.waitForURL("/login", { timeout: 10000 });
    }
  });

  test("unauthenticated access redirects to /login", async ({ page }) => {
    await page.goto("/");
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });
});
