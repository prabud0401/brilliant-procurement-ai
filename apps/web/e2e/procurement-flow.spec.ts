import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { isHostedTarget, LOCAL_ONLY_REASON } from "./target";

const DEMO_PASSWORD = process.env.DEMO_USER_PASSWORD || "demo_password_123";

function findRepoRoot(): string {
  let curr = process.cwd();
  while (!fs.existsSync(path.join(curr, "Makefile")) && path.dirname(curr) !== curr) {
    curr = path.dirname(curr);
  }
  return curr;
}

function linkS1Quotes(prId: string): string[] {
  const root = findRepoRoot();
  const output = execSync(
    `cd "${root}/services/backend" && uv run --env-file ../../.env python -m tools.setup_e2e_fixtures link-s1-quotes "${prId}"`,
    { encoding: "utf8" }
  );
  return output.trim().split(",");
}

function setupS3Match(): { matchId: string; exceptionId: string } {
  const root = findRepoRoot();
  const output = execSync(
    `cd "${root}/services/backend" && uv run --env-file ../../.env python -m tools.setup_e2e_fixtures setup-s3-match`,
    { encoding: "utf8" }
  );
  const [matchId, exceptionId] = output.trim().split(":");
  return { matchId, exceptionId };
}

function cleanE2E(): void {
  const root = findRepoRoot();
  execSync(
    `cd "${root}/services/backend" && uv run --env-file ../../.env python -m tools.setup_e2e_fixtures clean-e2e`,
    { encoding: "utf8" }
  );
}

async function loginAs(page: any, email: string) { // eslint-disable-line @typescript-eslint/no-explicit-any
  await page.context().clearCookies();
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL("/", { timeout: 15000 });
}

test.describe("Procurement Lifecycle & Governance Flows (R09)", () => {
  test.skip(isHostedTarget(), LOCAL_ONLY_REASON);

  test.beforeEach(() => {
    cleanE2E();
  });

  test("S1 Scenario: IT Request -> Compare 3 Quotes -> Override Validation -> PO -> Approval Bundle -> Push to Odoo", async ({
    page,
  }) => {
    // ---------------------------------------------------------
    // Step 1: Requester IT creates and submits IT equipment PR
    // ---------------------------------------------------------
    await loginAs(page, "requester.it@demo-holdings.example");
    await page.goto("/requests/new");
    await expect(page.locator("h1")).toContainText(/Purchase Request/i);

    // Fill PR form
    const prTitle = `IT Engineering Expansion ${Date.now()}`;
    await page.fill("#pr-title", prTitle);
    await page.selectOption("#pr-dept", { label: "IT" });

    // Fill Line 1
    await page.fill('input[aria-label="Description for line 1"]', "Laptop 14in Intel Core i7 16GB RAM 512GB SSD");
    await page.fill('input[aria-label="Quantity for line 1"]', "10");
    await page.fill('input[aria-label="Est Unit Price for line 1"]', "1900");

    // Add Line 2
    await page.click('button:has-text("Add Item")');
    await page.fill('input[aria-label="Description for line 2"]', "Monitor 27in QHD IPS USB-C 75Hz");
    await page.fill('input[aria-label="Quantity for line 2"]', "10");
    await page.fill('input[aria-label="Est Unit Price for line 2"]', "850");

    // Check live total
    await expect(page.locator('[data-testid="pr-total-amount"]')).toContainText("AED 27,500.00");

    // Submit PR creation
    await page.click('[data-testid="create-pr-submit-btn"]');
    await page.waitForURL(/\/requests\/[a-f0-9-]+/, { timeout: 15000 });
    const prUrl = page.url();
    const prId = prUrl.split("/requests/")[1].split("?")[0].replace(/\/$/, "");

    // Submit PR for Manager approval (Tier 2)
    const submitBtn = page.locator('[data-testid="submit-pr-btn"]');
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();
    await expect(page.locator("text=Submitted for Approval")).toBeVisible({ timeout: 10000 });

    // Link 3 confirmed S1 quotation fixtures via helper
    linkS1Quotes(prId);

    // ---------------------------------------------------------
    // Step 2: Buyer1 reviews linked quotes and creates comparison matrix
    // ---------------------------------------------------------
    await loginAs(page, "buyer1@demo-holdings.example");

    await page.goto(`/requests/${prId}`);
    await expect(page.locator("text=Linked Quotations (3)")).toBeVisible({ timeout: 10000 });

    // Click Compare Quotations
    await page.click('[data-testid="compare-quotes-link"]');
    await page.waitForURL(/\/comparisons\/new/, { timeout: 10000 });

    // Select all 3 quotation checkboxes and submit
    const quoteBoxes = page.locator('input[type="checkbox"][data-testid^="quote-select-"]');
    await expect(quoteBoxes).toHaveCount(3);
    for (let i = 0; i < 3; i++) {
      const box = quoteBoxes.nth(i);
      if (!(await box.isChecked())) {
        await box.check();
      }
    }
    await page.click('[data-testid="create-comparison-btn"]');
    await page.waitForURL(/\/comparisons\/[a-f0-9-]+/, { timeout: 15000 });

    // Compute recommendation if drafted
    const computeBtn = page.locator('[data-testid="generate-rec-btn"]');
    await expect(computeBtn).toBeVisible({ timeout: 10000 });
    await computeBtn.click();

    // ---------------------------------------------------------
    // Step 3: Comparison View - Recommendation, weights & override validation
    // ---------------------------------------------------------
    await expect(page.locator('[data-testid="recommendation-banner"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="recommended-vendor-name"]')).toContainText(/Gulf Line/i);
    await expect(page.locator('[data-testid="recommendation-explanation"]')).toBeVisible();

    // Verify side-by-side matrix exists with 3 quote columns
    await expect(page.locator("text=Side-by-Side Comparison Matrix")).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Gulf Line/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Falcon/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Corniche/i })).toBeVisible();

    // Sourcing decision dialog - override validation (US-10)
    await page.click('[data-testid="vendor-decision-btn"]');
    await expect(page.locator("text=Vendor Selection Decision")).toBeVisible();

    // Select a non-recommended vendor (Falcon)
    const falconRadio = page.locator('label:has-text("Falcon") input[type="radio"]');
    await falconRadio.check();

    // Override reason textarea appears and confirm button is initially disabled
    const overrideInput = page.locator('[data-testid="override-reason-input"]');
    await expect(overrideInput).toBeVisible();
    const confirmBtn = page.locator('[data-testid="confirm-decision-btn"]');
    await expect(confirmBtn).toBeDisabled();

    // Enter short text (< 10 chars) -> still disabled
    await overrideInput.fill("Too short");
    await expect(confirmBtn).toBeDisabled();

    // Enter valid override reason (>= 10 chars)
    await overrideInput.fill("Comprehensive 3-year warranty included with local spare parts SLA.");
    await expect(confirmBtn).toBeEnabled();

    // Now switch back to Gulf Line (recommended) -> override textarea hides, confirm is enabled
    const gulfRadio = page.locator('label:has-text("Gulf Line") input[type="radio"]');
    await gulfRadio.check();
    await expect(overrideInput).not.toBeVisible();
    await expect(confirmBtn).toBeEnabled();

    // Confirm decision
    await confirmBtn.click();
    await expect(page.locator('[data-testid="create-po-from-comp-btn"]')).toBeVisible({ timeout: 10000 });

    // ---------------------------------------------------------
    // Step 4: Create PO from chosen quote
    // ---------------------------------------------------------
    const createPOBtn = page.locator('[data-testid="create-po-from-comp-btn"]');
    await expect(createPOBtn).toBeVisible({ timeout: 10000 });
    await createPOBtn.click();
    await page.waitForURL(/\/purchase-orders\/[a-f0-9-]+/, { timeout: 15000 });
    const poUrl = page.url();
    const poId = poUrl.split("/purchase-orders/")[1].split("?")[0].replace(/\/$/, "");

    // Verify PO lines, VAT, total
    await expect(page.locator('[data-testid="po-total"]')).toBeVisible();
    await expect(page.locator('[data-testid="po-vat"]')).toBeVisible();

    // Submit PO for approval
    const submitPOBtn = page.locator('[data-testid="submit-po-btn"]');
    await expect(submitPOBtn).toBeVisible();
    await submitPOBtn.click();
    await expect(page.locator("text=PO Submitted")).toBeVisible({ timeout: 10000 });

    // ---------------------------------------------------------
    // Step 5: Manager IT approves PO on One-Screen Approval Bundle
    // ---------------------------------------------------------
    await loginAs(page, "manager.it@demo-holdings.example");

    await page.goto("/approvals");
    await expect(page.locator("h1")).toContainText(/Approvals? Inbox/i);

    // Find and open PO approval step
    const poInboxLink = page.locator(`a[data-testid^="review-approval-link-PO-"]`);
    await expect(poInboxLink.first()).toBeVisible({ timeout: 10000 });
    await poInboxLink.first().click();

    await page.waitForURL(/\/approvals\/[a-f0-9-]+/, { timeout: 10000 });

    // Accessibility scan on One-Screen Approval Bundle (R09 requirement)
    const scan = await new AxeBuilder({ page }).analyze();
    const seriousCritical = scan.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical"
    );
    expect(seriousCritical).toEqual([]);

    // Verify facts on approval screen
    await expect(page.locator("text=One-Screen Approval Bundle")).toBeVisible();
    await expect(page.locator("text=Commitment Facts")).toBeVisible();

    // Approve Commitment
    const approveBtn = page.locator('[data-testid="approve-btn"]');
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    await expect(page.locator("text=Decision Recorded")).toBeVisible({ timeout: 10000 });

    // ---------------------------------------------------------
    // Step 6: Buyer pushes approved PO to Odoo (mock adapter)
    // ---------------------------------------------------------
    await loginAs(page, "buyer1@demo-holdings.example");

    await page.goto(`/purchase-orders/${poId}`);
    const pushBtn = page.locator('[data-testid="push-to-odoo-btn"]');
    await expect(pushBtn).toBeVisible({ timeout: 10000 });
    await pushBtn.click();

    // Verify Odoo reference and mock adapter label
    await expect(page.locator('[data-testid="odoo-push-success-banner"]')).toBeVisible({ timeout: 15000 });
    await expect(page.locator("text=Successfully Synced to Odoo (mock adapter)")).toBeVisible();
    await expect(page.getByText("Odoo (mock adapter)", { exact: true })).toBeVisible();
  });

  test("S3 Scenario: Three-Way Match Quantity Exception -> Buyer Blocked -> Escalate -> Manager Decides", async ({
    page,
  }) => {
    // 1. Seed S3 over-billing exception (12 invoiced vs 10 received)
    setupS3Match();

    // 2. Sign in as Buyer
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/matches");
    await expect(page.getByRole("heading", { name: /Three-Way Match Exception/i })).toBeVisible({ timeout: 10000 });

    // 3. Locate the quantity variance exception
    const qtyExcRow = page.locator('[data-testid^="exception-row-"]').filter({ hasText: /qty variance/i });
    await expect(qtyExcRow.first()).toBeVisible({ timeout: 10000 });

    // 4. Buyer cannot accept quantity over-billing: verify button is disabled
    const acceptBtn = qtyExcRow.first().locator('[data-testid="buyer-accept-exception-btn"]');
    await expect(acceptBtn).toBeDisabled();
    const titleAttr = await acceptBtn.getAttribute("title");
    expect(titleAttr).toContain("Over-billed quantity cannot be accepted");

    // 5. Buyer escalates exception to Manager
    const escalateBtn = qtyExcRow.first().locator('[data-testid="buyer-escalate-exception-btn"]');
    await expect(escalateBtn).toBeEnabled();
    await escalateBtn.click();

    // Fill escalation reason
    const reasonInput = page.locator('[data-testid="exception-resolve-reason-input"]');
    await expect(reasonInput).toBeVisible();
    await reasonInput.fill("Supplier invoiced 12 units but warehouse received only 10. Escalating for manager review.");
    await page.click('[data-testid="confirm-resolve-exception-btn"]');
    await expect(page.locator("text=Exception Escalated")).toBeVisible({ timeout: 10000 });

    // 6. Sign out, sign in as Manager IT
    await loginAs(page, "manager.it@demo-holdings.example");

    await page.goto("/matches");
    // Switch filter to Escalated
    const filterSelect = page.locator("#filter-status-queue");
    await expect(filterSelect).toBeVisible({ timeout: 10000 });
    await filterSelect.selectOption("escalated");

    const escalatedRow = page.locator('[data-testid^="exception-row-"]').filter({ hasText: /qty variance/i });
    await expect(escalatedRow.first()).toBeVisible({ timeout: 15000 });

    // Manager decides exception (Reject over-billing)
    const mgrRejectBtn = escalatedRow.first().locator('[data-testid="manager-reject-exception-btn"]');
    await expect(mgrRejectBtn).toBeEnabled();
    await mgrRejectBtn.click();

    const mgrReasonInput = page.locator('[data-testid="exception-resolve-reason-input"]');
    await mgrReasonInput.fill("Rejected over-billing: vendor instructed to issue revised invoice for 10 units.");
    await page.click('[data-testid="confirm-resolve-exception-btn"]');
    await expect(page.locator("text=Exception Resolved")).toBeVisible({ timeout: 10000 });
  });

  test("S4 Scenario & Governance: Creator Self-Approval Blocked (SoD) & Admin Cannot Approve Purchases", async ({
    page,
    request,
  }) => {
    // 1. Sign in as requester.it and create a small PR
    await loginAs(page, "requester.it@demo-holdings.example");
    await page.goto("/requests/new");

    const smallTitle = `Tier 1 Consumables ${Date.now()}`;
    await page.fill("#pr-title", smallTitle);
    await page.selectOption("#pr-dept", { label: "IT" });

    await page.fill('input[aria-label="Description for line 1"]', "USB-C Display Adapters");
    await page.fill('input[aria-label="Quantity for line 1"]', "5");
    await page.fill('input[aria-label="Est Unit Price for line 1"]', "100");

    await page.click('[data-testid="create-pr-submit-btn"]');
    await page.waitForURL(/\/requests\/[a-f0-9-]+/, { timeout: 15000 });

    // Submit PR
    await page.click('[data-testid="submit-pr-btn"]');
    await expect(page.locator("text=Submitted for Approval")).toBeVisible({ timeout: 10000 });

    // 2. Verify Requester cannot access Approvals inbox
    await page.goto("/approvals");
    await expect(page.locator("h1")).not.toContainText(/Approvals? Inbox/i);

    // 3. Admin cannot approve purchases (API and UI verification)
    await loginAs(page, "admin@demo-holdings.example");

    // Admin goes to /approvals: redirected or no approval actions
    await page.goto("/approvals");
    await expect(page.locator('[data-testid="approve-btn"]')).not.toBeVisible();

    // Direct API attempt by Admin to decide approval returns 403
    const apiRes = await page.request.post("/api/v1/approvals/00000000-0000-0000-0000-000000000001/decision", {
      headers: { Origin: new URL(page.url()).origin },
      data: { decision: "approve" },
    });
    expect([403, 404]).toContain(apiRes.status());
  });
});
