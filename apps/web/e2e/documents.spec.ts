import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";
import { execSync } from "child_process";
import AxeBuilder from "@axe-core/playwright";
import { isHostedTarget, LOCAL_ONLY_REASON } from "./target";

const DEMO_PASSWORD = process.env.DEMO_USER_PASSWORD || "demo_password_123";

function cleanE2E(): void {
  let curr = process.cwd();
  while (!fs.existsSync(path.join(curr, "Makefile")) && path.dirname(curr) !== curr) {
    curr = path.dirname(curr);
  }
  execSync(
    `cd "${curr}/services/backend" && uv run --env-file ../../.env python -m tools.setup_e2e_fixtures clean-e2e`,
    { encoding: "utf8" }
  );
}

// Helper to sign in with email and demo password
async function loginAs(page: any, email: string) { // eslint-disable-line @typescript-eslint/no-explicit-any
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL("/", { timeout: 15000 });
}

test.describe("Procurement Document Review & Processing Flows (R08)", () => {
  test.skip(isHostedTarget(), LOCAL_ONLY_REASON);

  test.beforeAll(() => {
    cleanE2E();
  });
  test("S1 scenario: Buyer uploads Gulfline quotation, reviews with highlight, corrects a field, and confirms", async ({
    page,
  }) => {
    // 1. Sign in as Buyer
    await loginAs(page, "buyer1@demo-holdings.example");

    // 2. Navigate to /documents
    await page.goto("/documents");
    await expect(page.locator("h1")).toContainText(/Procurement Documents/i);

    // 3. Open Upload Modal
    const uploadBtn = page.locator('[data-testid="open-upload-modal-btn"]');
    await expect(uploadBtn).toBeVisible();
    await uploadBtn.click();

    // 4. Upload S1 Gulf Line Quotation PDF
    const filePath = path.resolve(
      process.cwd(),
      "../../tools/datagen/out/s1-quote-gulfline.pdf"
    );

    const fileInput = page.locator('[data-testid="file-upload-input"]');
    await fileInput.setInputFiles(filePath);

    // Submit upload
    const submitBtn = page.locator('[data-testid="upload-submit-btn"]');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // 5. Polling on modal: wait for extraction to complete without page reload
    const statusTracker = page.locator('[data-testid="upload-status-tracker"]');
    await expect(statusTracker).toBeVisible({ timeout: 10000 });

    const openReviewLink = page.locator('a:has-text("Open Review Screen")');
    await expect(openReviewLink).toBeVisible({ timeout: 30000 });

    // 6. Navigate to Review Split Screen
    await openReviewLink.click();
    await expect(page).toHaveURL(/\/documents\/[a-f0-9-]+/);

    // Verify Review Panel & Document Viewer exist
    const reviewPanel = page.locator('[data-testid="extraction-review-panel"]');
    await expect(reviewPanel).toBeVisible({ timeout: 20000 });

    // 7. Verify Highlight interaction: click on a field row and see highlight
    const vendorRow = page.locator('[data-testid="field-row-vendor_name"]');
    await expect(vendorRow).toBeVisible();
    await vendorRow.click();

    // Verify bounding box overlay exists
    const highlightOverlay = page.locator('[data-testid="bbox-highlight-overlay"]');
    await expect(highlightOverlay).toBeAttached();

    // 8. Correct a field inline
    const editBtn = page.locator('button[aria-label="Correct Payment Terms"]');
    if (await editBtn.isVisible()) {
      await editBtn.click();
      const input = page.locator("#corrected-value");
      await expect(input).toBeVisible();
      await input.fill("Net 30 Days");
      await page.click('button:has-text("Save Correction")');
      await expect(page.locator("text=Field Corrected")).toBeVisible({ timeout: 10000 });
    }

    // 9. Confirm any remaining open fields if needs_review
    const fieldConfirmButtons = page.locator('button[title="Confirm this field value"]');
    const count = await fieldConfirmButtons.count();
    for (let i = 0; i < count; i++) {
      const btn = fieldConfirmButtons.first();
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(500);
      }
    }

    // 10. Confirm document (or verify confirmed)
    const confirmedBadge = page.locator("text=Confirmed by Buyer");
    const confirmDocBtn = page.locator('[data-testid="confirm-document-btn"]');
    if (await confirmDocBtn.isVisible()) {
      if (await confirmDocBtn.isEnabled()) {
        await confirmDocBtn.click();
      }
    }
    await expect(confirmedBadge).toBeVisible({ timeout: 10000 });
  });

  test("S7 scenario: Injected invoice displays suspicious banner, blocks confirmation until acknowledged", async ({
    page,
  }) => {
    // 1. Sign in as Buyer
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/documents");

    // 2. Open Upload Modal
    await page.locator('[data-testid="open-upload-modal-btn"]').click();

    // 3. Upload S7 injected invoice
    const s7FilePath = path.resolve(
      process.cwd(),
      "../../tools/datagen/out/s7-inv-7001-inj.pdf"
    );

    const fileInput = page.locator('[data-testid="file-upload-input"]');
    await fileInput.setInputFiles(s7FilePath);

    await page.locator('[data-testid="upload-submit-btn"]').click();

    const openReviewLink = page.locator('a:has-text("Open Review Screen")');
    await expect(openReviewLink).toBeVisible({ timeout: 30000 });
    await openReviewLink.click();

    // 4. Verify Suspicious Content Banner (US-29)
    const alertBanner = page.locator('[role="alert"]').filter({ hasText: /Suspicious Content/i });
    await expect(alertBanner).toBeVisible({ timeout: 20000 });
    await expect(alertBanner).toContainText(/Prompt Injection Defence/i);

    // 5. Verify ground-truth total is preserved (AED 2625.00, NOT AED 0)
    const totalRow = page.locator('[data-testid="field-row-total"]');
    await expect(totalRow).toContainText("2625.00");

    // 6. Verify Confirm Document button is blocked while suspicious flag is open
    const openItemsBanner = page.locator('[data-testid="open-items-banner"]');
    await expect(openItemsBanner).toBeVisible();
    await expect(openItemsBanner).toContainText(/Suspicious Content/i);

    const confirmDocBtn = page.locator('[data-testid="confirm-document-btn"]');
    await expect(confirmDocBtn).toBeDisabled();

    // 7. Acknowledge suspicious content with a reason (10+ characters)
    const ackBtn = page.locator('button:has-text("Acknowledge Suspicious Content")');
    await expect(ackBtn).toBeVisible();
    await ackBtn.click();

    const reasonInput = page.locator("#ack-reason");
    await expect(reasonInput).toBeVisible();
    await reasonInput.fill("Verified invoice physically against contract terms. Ignored instruction injection.");

    const submitAckBtn = page.locator('button:has-text("Acknowledge & Lift Block")');
    await expect(submitAckBtn).toBeEnabled();
    await submitAckBtn.click();

    // 8. Verify status updates to Acknowledged
    await expect(page.getByRole("heading", { name: /Suspicious Content Acknowledged/i })).toBeVisible({ timeout: 10000 });
  });

  test("Requester role permissions: sees own view, read-only mode, and gets 404 for unauthorized documents", async ({
    page,
  }) => {
    // 1. Sign in as Requester
    await loginAs(page, "requester.fac@demo-holdings.example");
    await page.goto("/documents");

    // Requester can upload own files
    const uploadBtn = page.locator('[data-testid="open-upload-modal-btn"]');
    await expect(uploadBtn).toBeVisible();

    // 2. Action buttons in list show 'View' (not 'Review')
    const actionLinks = page.locator('a:has-text("View")');
    if ((await actionLinks.count()) > 0) {
      await actionLinks.first().click();

      // Read-only notice is displayed
      await expect(
        page.locator("text=You are viewing this document in read-only mode")
      ).toBeVisible({ timeout: 10000 });

      // Review action buttons are hidden
      await expect(page.locator("text=Change Vendor")).not.toBeVisible();
      await expect(page.locator('[data-testid="confirm-document-btn"]')).not.toBeVisible();
    }

    // 3. Unauthorized document access returns 404 page (spec / US-03 / Design 7.2)
    // Non-existent or inaccessible document UUID
    await page.goto("/documents/00000000-0000-0000-0000-000000000000");
    await expect(page.locator("h1")).toContainText(/Page Not Found/i);
  });

  test("Axe accessibility scan on Document Review screen", async ({ page }) => {
    // Sign in as Buyer
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/documents");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("h1")).toContainText(/Procurement Documents/i);

    // 1. Scan the first listed document (deterministic wait)
    const firstReviewLink = page.locator('a:has-text("Review"), a:has-text("View")').first();
    await expect(firstReviewLink).toBeVisible({ timeout: 15000 });
    await firstReviewLink.click();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-testid="extraction-review-panel"]')).toBeVisible({ timeout: 20000 });

    // Run Axe accessibility scan on first document
    const scanResultsDoc1 = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const seriousOrCriticalViolationsDoc1 = scanResultsDoc1.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCriticalViolationsDoc1).toEqual([]);

    // 2. Also open a document that has a below-high-confidence field (showing a "(Review)" marker)
    await page.goto("/documents");
    await page.waitForLoadState("networkidle");

    // Locate the row for the S7 injected invoice (flagged as Suspicious) or Invoice type seeded by earlier tests
    const suspiciousRow = page.locator("tbody tr", { has: page.locator("text=Suspicious") });
    const invoiceRow = page.locator("tbody tr", { has: page.locator("text=Invoice") });
    const belowHighDocRow = (await suspiciousRow.count()) > 0
      ? suspiciousRow.first()
      : (await invoiceRow.count()) > 0
      ? invoiceRow.first()
      : page.locator("tbody tr").last();

    const secondReviewLink = belowHighDocRow.locator('a:has-text("Review"), a:has-text("View")');
    await expect(secondReviewLink).toBeVisible({ timeout: 15000 });
    await secondReviewLink.click();
    await page.waitForLoadState("networkidle");
    await expect(page.locator('[data-testid="extraction-review-panel"]')).toBeVisible({ timeout: 20000 });

    // Verify at least one below-high-confidence "(Review)" marker is displayed on the screen
    await expect(page.locator("text=(Review)").first()).toBeVisible({ timeout: 15000 });

    // Run Axe accessibility scan on document with below-high-confidence fields
    const scanResultsDoc2 = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();

    const seriousOrCriticalViolationsDoc2 = scanResultsDoc2.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousOrCriticalViolationsDoc2).toEqual([]);
  });
});
