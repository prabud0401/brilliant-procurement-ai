import { test, expect } from "@playwright/test";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { isHostedTarget, LOCAL_ONLY_REASON } from "../target";

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

function reindexQA(): void {
  const root = findRepoRoot();
  execSync(
    `cd "${root}/services/backend" && uv run --env-file ../../.env python -m app.qa.reindex`,
    { encoding: "utf8" }
  );
}

function createSaltedPdf(sourceRelativePath: string): { tempPath: string; cleanup: () => void } {
  const root = findRepoRoot();
  const sourcePath = path.resolve(root, sourceRelativePath);
  const content = fs.readFileSync(sourcePath);
  const salt = `\n% demo-salt-${Date.now()}-${Math.floor(Math.random() * 1000000)}\n`;
  const saltedContent = Buffer.concat([content, Buffer.from(salt, "utf-8")]);
  const tempDir = path.resolve(root, "apps/web/e2e/.tmp");
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }
  const tempPath = path.join(tempDir, `demo-${Date.now()}-${path.basename(sourcePath)}`);
  fs.writeFileSync(tempPath, saltedContent);
  return {
    tempPath,
    cleanup: () => {
      try {
        if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
      } catch {
        // ignore
      }
    },
  };
}

async function loginAs(page: any, email: string) { // eslint-disable-line @typescript-eslint/no-explicit-any
  await page.context().clearCookies();
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL("/", { timeout: 15000 });
}

test.describe("5-Minute Demo Script End-to-End Suite (US-01..US-29, AIQ-01..AIQ-10)", () => {
  test.skip(isHostedTarget(), LOCAL_ONLY_REASON);

  test.beforeAll(() => {
    cleanE2E();
  });

  // =========================================================================
  // Demo 0:00 - 0:30: Role-Based Authentication & Segregation of Duties
  // =========================================================================
  test("0:00-0:30 Role Sign-In & SoD Checks: Requester, Buyer, Manager, Admin workspaces; Admin blocked from approval", async ({
    page,
  }) => {
    // 1. Requester sign-in
    await loginAs(page, "requester.it@demo-holdings.example");
    await expect(page.locator('header span:has-text("Requester")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h3:has-text("Requester Workspace")')).toBeVisible();

    // 2. Buyer sign-in
    await loginAs(page, "buyer1@demo-holdings.example");
    await expect(page.locator('header span:has-text("Buyer")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h3:has-text("Buyer Workspace")')).toBeVisible();

    // 3. Manager sign-in
    await loginAs(page, "manager.it@demo-holdings.example");
    await expect(page.locator('header span:has-text("Manager")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h3:has-text("Manager (Approver) Workspace")')).toBeVisible();

    // 4. Admin sign-in
    await loginAs(page, "admin@demo-holdings.example");
    await expect(page.locator('header span:has-text("Admin")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('h3:has-text("System Administration Workspace")')).toBeVisible();

    // 5. Governance: Admin cannot approve purchases (UI and API checks)
    await page.goto("/approvals");
    await expect(page.locator('[data-testid="approve-btn"]')).not.toBeVisible();

    const apiRes = await page.request.post("/api/v1/approvals/00000000-0000-0000-0000-000000000001/decision", {
      headers: { Origin: new URL(page.url()).origin },
      data: { decision: "approve" },
    });
    expect([403, 404]).toContain(apiRes.status());
  });

  // =========================================================================
  // Demo 0:30 - 2:30: S1 Procurement Flow
  // Upload & Review -> PR -> Compare 3 Quotes -> Override Validation -> PO -> Approval
  // =========================================================================
  test("0:30-2:30 S1 Flow: Document Upload & Review -> PR -> Compare 3 Quotes -> Override Reason -> PO -> Manager Approval", async ({
    page,
  }) => {
    const runId = Date.now();

    // -----------------------------------------------------------------------
    // Part A: Buyer uploads quotation, reviews fields & highlight, confirms
    // -----------------------------------------------------------------------
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/documents");
    await expect(page.locator("h1")).toContainText(/Procurement Documents/i);

    // Open upload modal
    const uploadBtn = page.locator('[data-testid="open-upload-modal-btn"]');
    await expect(uploadBtn).toBeVisible();
    await uploadBtn.click();

    // Upload S1 Gulf Line quote with unique salt
    const { tempPath: saltedQuotePath, cleanup: cleanQuote } = createSaltedPdf("tools/datagen/out/s1-quote-gulfline.pdf");
    try {
      const fileInput = page.locator('[data-testid="file-upload-input"]');
      await fileInput.setInputFiles(saltedQuotePath);

      const submitUploadBtn = page.locator('[data-testid="upload-submit-btn"]');
      await expect(submitUploadBtn).toBeEnabled();
      await submitUploadBtn.click();

      // Polling: wait for extraction
      const statusTracker = page.locator('[data-testid="upload-status-tracker"]');
      await expect(statusTracker).toBeVisible({ timeout: 10000 });

      const openReviewLink = page.locator('a:has-text("Open Review Screen")');
      await expect(openReviewLink).toBeVisible({ timeout: 35000 });
      await openReviewLink.click();

      await page.waitForURL(/\/documents\/[a-f0-9-]+/, { timeout: 15000 });
      await expect(page.locator('[data-testid="extraction-review-panel"]')).toBeVisible({ timeout: 20000 });

      // Field row interaction & highlight overlay
      const vendorRow = page.locator('[data-testid="field-row-vendor_name"]');
      await expect(vendorRow).toBeVisible();
      await vendorRow.click();
      await expect(page.locator('[data-testid="bbox-highlight-overlay"]')).toBeAttached();

      // Field correction
      const editBtn = page.locator('button[aria-label="Correct Payment Terms"]');
      if (await editBtn.isVisible()) {
        await editBtn.click();
        const input = page.locator("#corrected-value");
        await expect(input).toBeVisible();
        await input.fill("Net 30 Days");
        await page.click('button:has-text("Save Correction")');
        await expect(page.locator("text=Field Corrected")).toBeVisible({ timeout: 10000 });
      }

      // Confirm any open fields
      const fieldConfirmButtons = page.locator('button[title="Confirm this field value"]');
      const count = await fieldConfirmButtons.count();
      for (let i = 0; i < count; i++) {
        const btn = fieldConfirmButtons.first();
        if (await btn.isVisible()) {
          await btn.click();
          await page.waitForTimeout(300);
        }
      }

      // Confirm document
      const confirmDocBtn = page.locator('[data-testid="confirm-document-btn"]');
      if (await confirmDocBtn.isVisible() && await confirmDocBtn.isEnabled()) {
        await confirmDocBtn.click();
      }
      await expect(page.getByText("Confirmed by Buyer")).toBeVisible({ timeout: 10000 });
    } finally {
      cleanQuote();
    }

    // -----------------------------------------------------------------------
    // Part B: Requester creates IT PR and submits for Manager approval
    // -----------------------------------------------------------------------
    await loginAs(page, "requester.it@demo-holdings.example");
    await page.goto("/requests/new");
    await expect(page.locator("h1")).toContainText(/Purchase Request/i);

    const prTitle = `Demo IT Expansion ${runId}`;
    await page.fill("#pr-title", prTitle);
    await page.selectOption("#pr-dept", { label: "IT" });

    // Item 1: Laptops
    await page.fill('input[aria-label="Description for line 1"]', "Laptop 14in Intel Core i7 16GB RAM 512GB SSD");
    await page.fill('input[aria-label="Quantity for line 1"]', "10");
    await page.fill('input[aria-label="Est Unit Price for line 1"]', "1900");

    // Item 2: Monitors
    await page.click('button:has-text("Add Item")');
    await page.fill('input[aria-label="Description for line 2"]', "Monitor 27in QHD IPS USB-C 75Hz");
    await page.fill('input[aria-label="Quantity for line 2"]', "10");
    await page.fill('input[aria-label="Est Unit Price for line 2"]', "850");

    await expect(page.locator('[data-testid="pr-total-amount"]')).toContainText("AED 27,500.00");

    await page.click('[data-testid="create-pr-submit-btn"]');
    await page.waitForURL(/\/requests\/[a-f0-9-]+/, { timeout: 15000 });
    const prUrl = page.url();
    const prId = prUrl.split("/requests/")[1].split("?")[0].replace(/\/$/, "");

    // Submit PR
    await page.click('[data-testid="submit-pr-btn"]');
    await expect(page.locator("text=Submitted for Approval")).toBeVisible({ timeout: 10000 });

    // Link 3 confirmed S1 quotes (Gulf Line, Falcon, Corniche) and reindex QA chunks
    linkS1Quotes(prId);
    reindexQA();

    // -----------------------------------------------------------------------
    // Part C: Buyer compares 3 quotes, tests override reason, creates PO
    // -----------------------------------------------------------------------
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto(`/requests/${prId}`);
    await expect(page.locator("text=Linked Quotations (3)")).toBeVisible({ timeout: 10000 });

    // Navigate to comparison creation
    await page.click('[data-testid="compare-quotes-link"]');
    await page.waitForURL(/\/comparisons\/new/, { timeout: 10000 });

    // Select all 3 quotations
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

    // Generate recommendation
    const computeBtn = page.locator('[data-testid="generate-rec-btn"]');
    await expect(computeBtn).toBeVisible({ timeout: 10000 });
    await computeBtn.click();

    // Verify AI recommendation & explanation
    await expect(page.locator('[data-testid="recommendation-banner"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="recommended-vendor-name"]')).toContainText(/Gulf Line/i);
    await expect(page.locator('[data-testid="recommendation-explanation"]')).toBeVisible();

    // Verify side-by-side matrix columns
    await expect(page.locator("text=Side-by-Side Comparison Matrix")).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Gulf Line/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Falcon/i })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: /Corniche/i })).toBeVisible();

    // Override validation dialog (US-10)
    await page.click('[data-testid="vendor-decision-btn"]');
    await expect(page.locator("text=Vendor Selection Decision")).toBeVisible();

    // Select non-recommended vendor (Falcon)
    const falconRadio = page.locator('label:has-text("Falcon") input[type="radio"]');
    await falconRadio.check();

    const overrideInput = page.locator('[data-testid="override-reason-input"]');
    await expect(overrideInput).toBeVisible();
    const confirmDecisionBtn = page.locator('[data-testid="confirm-decision-btn"]');
    await expect(confirmDecisionBtn).toBeDisabled();

    // Invalid override (< 10 chars)
    await overrideInput.fill("Too short");
    await expect(confirmDecisionBtn).toBeDisabled();

    // Valid override reason (>= 10 chars)
    await overrideInput.fill("Comprehensive 3-year warranty with next-business-day replacement SLA.");
    await expect(confirmDecisionBtn).toBeEnabled();

    // Switch back to Gulf Line (recommended)
    const gulfRadio = page.locator('label:has-text("Gulf Line") input[type="radio"]');
    await gulfRadio.check();
    await expect(overrideInput).not.toBeVisible();
    await expect(confirmDecisionBtn).toBeEnabled();

    await confirmDecisionBtn.click();
    await expect(page.locator('[data-testid="create-po-from-comp-btn"]')).toBeVisible({ timeout: 10000 });

    // Create PO
    await page.click('[data-testid="create-po-from-comp-btn"]');
    await page.waitForURL(/\/purchase-orders\/[a-f0-9-]+/, { timeout: 15000 });

    await expect(page.locator('[data-testid="po-total"]')).toBeVisible();
    await expect(page.locator('[data-testid="po-vat"]')).toBeVisible();

    // Submit PO
    await page.click('[data-testid="submit-po-btn"]');
    await expect(page.locator("text=PO Submitted")).toBeVisible({ timeout: 10000 });

    // -----------------------------------------------------------------------
    // Part D: SoD - Requester self-approval blocked
    // -----------------------------------------------------------------------
    await loginAs(page, "requester.it@demo-holdings.example");
    await page.goto("/approvals");
    await expect(page.locator('[data-testid="approve-btn"]')).not.toBeVisible();

    // -----------------------------------------------------------------------
    // Part E: Manager IT approves PO on One-Screen Approval Bundle
    // -----------------------------------------------------------------------
    await loginAs(page, "manager.it@demo-holdings.example");
    await page.goto("/approvals");
    await expect(page.locator("h1")).toContainText(/Approvals? Inbox/i);

    const poApprovalLink = page.locator('a[data-testid^="review-approval-link-PO-"]');
    await expect(poApprovalLink.first()).toBeVisible({ timeout: 10000 });
    await poApprovalLink.first().click();

    await page.waitForURL(/\/approvals\/[a-f0-9-]+/, { timeout: 10000 });
    await expect(page.locator("text=One-Screen Approval Bundle")).toBeVisible();
    await expect(page.locator("text=Commitment Facts")).toBeVisible();

    // Approve Commitment
    const approveBtn = page.locator('[data-testid="approve-btn"]');
    await expect(approveBtn).toBeVisible();
    await approveBtn.click();
    await expect(page.locator("text=Decision Recorded")).toBeVisible({ timeout: 10000 });
  });

  // =========================================================================
  // Demo 3:15 - 4:00: S3 Three-Way Match & Exception Management
  // =========================================================================
  test("3:15-4:00 S3 Flow: Three-Way Match Quantity Variance -> Buyer Blocked -> Escalate -> Manager Decides", async ({
    page,
  }) => {
    // 1. Setup S3 match exception (12 invoiced vs 10 received)
    setupS3Match();

    // 2. Buyer verifies blocked acceptance & escalates
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/matches");
    await expect(page.getByRole("heading", { name: /Three-Way Match Exception/i })).toBeVisible({ timeout: 10000 });

    const qtyExcRow = page.locator('[data-testid^="exception-row-"]').filter({ hasText: /qty variance/i });
    await expect(qtyExcRow.first()).toBeVisible({ timeout: 10000 });

    // Buyer cannot accept quantity over-billing
    const acceptBtn = qtyExcRow.first().locator('[data-testid="buyer-accept-exception-btn"]');
    await expect(acceptBtn).toBeDisabled();
    const tooltip = await acceptBtn.getAttribute("title");
    expect(tooltip).toContain("Over-billed quantity cannot be accepted");

    // Buyer escalates to Manager IT
    const escalateBtn = qtyExcRow.first().locator('[data-testid="buyer-escalate-exception-btn"]');
    await expect(escalateBtn).toBeEnabled();
    await escalateBtn.click();

    const reasonInput = page.locator('[data-testid="exception-resolve-reason-input"]');
    await expect(reasonInput).toBeVisible();
    await reasonInput.fill("Supplier invoiced 12 units but warehouse confirmed receipt of 10. Escalating to Manager IT.");
    await page.click('[data-testid="confirm-resolve-exception-btn"]');
    await expect(page.locator("text=Exception Escalated")).toBeVisible({ timeout: 10000 });

    // 3. Manager IT reviews and decides (rejects over-billing)
    await loginAs(page, "manager.it@demo-holdings.example");
    await page.goto("/matches");

    const filterSelect = page.locator("#filter-status-queue");
    await expect(filterSelect).toBeVisible({ timeout: 10000 });
    await filterSelect.selectOption("escalated");

    const escalatedRow = page.locator('[data-testid^="exception-row-"]').filter({ hasText: /qty variance/i });
    await expect(escalatedRow.first()).toBeVisible({ timeout: 15000 });

    const mgrRejectBtn = escalatedRow.first().locator('[data-testid="manager-reject-exception-btn"]');
    await expect(mgrRejectBtn).toBeEnabled();
    await mgrRejectBtn.click();

    const mgrReasonInput = page.locator('[data-testid="exception-resolve-reason-input"]');
    await mgrReasonInput.fill("Rejected over-billing: vendor instructed to issue revised invoice for exactly 10 units.");
    await page.click('[data-testid="confirm-resolve-exception-btn"]');
    await expect(page.locator("text=Exception Resolved")).toBeVisible({ timeout: 10000 });
  });

  // =========================================================================
  // Demo 4:00 - 4:40: Document Assistant Q&A and S7 Prompt Injection Defence
  // =========================================================================
  test("4:00-4:40 Q&A & Security: Answered Question with Citations, Refusal, and S7 Prompt Injection Banner", async ({
    page,
  }) => {
    // -----------------------------------------------------------------------
    // Part A: Q&A Answered Question with Citations & Click-Through
    // -----------------------------------------------------------------------
    await loginAs(page, "buyer1@demo-holdings.example");
    await page.goto("/qa");
    await expect(page.locator("h1")).toContainText(/Document Assistant Q&A/i);

    const textarea = page.locator('textarea[placeholder*="Ask a question"]');
    await expect(textarea).toBeVisible();

    await textarea.fill("What is the total amount and VAT on quote Q-1042?");
    await page.locator('button[aria-label="Send question"]').click();

    // Verify user message appeared
    await expect(page.locator("text=What is the total amount and VAT on quote Q-1042?")).toBeVisible();

    // Verify assistant answer appeared
    const assistantMessage = page.locator('div:has(> svg.lucide-bot) + div');
    await expect(assistantMessage).toBeVisible({ timeout: 25000 });

    // Verify citations and click-through navigation
    const citationLink = page.locator('a[href*="/documents/"]').filter({ hasText: /p\./i });
    if ((await citationLink.count()) > 0) {
      await citationLink.first().click();
      await page.waitForURL(/\/documents\/[a-f0-9-]+/, { timeout: 15000 });
      await expect(page.locator("h1")).toContainText(/Document Review/i);
    }

    // -----------------------------------------------------------------------
    // Part B: Q&A Refusal for Out-of-Scope / Unanswerable Question
    // -----------------------------------------------------------------------
    await page.goto("/qa");
    const qaInput = page.locator('textarea[placeholder*="Ask a question"]');
    await qaInput.fill("What is the average rainfall in the Amazon rainforest in 1950?");
    await page.locator('button[aria-label="Send question"]').click();

    const refusalHeader = page.locator("text=Unable to Answer");
    await expect(refusalHeader).toBeVisible({ timeout: 20000 });

    const refusalBody = page.getByText(/could not find|refused|unrelated|accessible/i).first();
    await expect(refusalBody).toBeVisible();

    // -----------------------------------------------------------------------
    // Part C: S7 Prompt Injection Defence (US-29)
    // -----------------------------------------------------------------------
    await page.goto("/documents");
    await page.locator('[data-testid="open-upload-modal-btn"]').click();

    const { tempPath: saltedS7Path, cleanup: cleanS7 } = createSaltedPdf("tools/datagen/out/s7-inv-7001-inj.pdf");
    try {
      const fileInput = page.locator('[data-testid="file-upload-input"]');
      await fileInput.setInputFiles(saltedS7Path);

      await page.locator('[data-testid="upload-submit-btn"]').click();

      const openReviewLink = page.locator('a:has-text("Open Review Screen")');
      await expect(openReviewLink).toBeVisible({ timeout: 35000 });
      await openReviewLink.click();

      // Suspicious Content Alert Banner (Prompt Injection Defence)
      const alertBanner = page.locator('[role="alert"]').filter({ hasText: /Suspicious Content/i });
      await expect(alertBanner).toBeVisible({ timeout: 20000 });
      await expect(alertBanner).toContainText(/Prompt Injection Defence/i);

      // Verify ground-truth total preserved (AED 2625.00, NOT AED 0)
      const totalRow = page.locator('[data-testid="field-row-total"]');
      await expect(totalRow).toContainText("2625.00");

      // Verify confirmation blocked while suspicious flag is active
      const confirmDocBtn = page.locator('[data-testid="confirm-document-btn"]');
      await expect(confirmDocBtn).toBeDisabled();

      // Acknowledge suspicious content
      const ackBtn = page.locator('button:has-text("Acknowledge Suspicious Content")');
      await expect(ackBtn).toBeVisible();
      await ackBtn.click();

      const reasonInput = page.locator("#ack-reason");
      await expect(reasonInput).toBeVisible();
      await reasonInput.fill("Verified invoice physically against contract terms. Ignored prompt injection instruction.");

      const submitAckBtn = page.locator('button:has-text("Acknowledge & Lift Block")');
      await expect(submitAckBtn).toBeEnabled();
      await submitAckBtn.click();

      await expect(page.getByRole("heading", { name: /Suspicious Content Acknowledged/i })).toBeVisible({ timeout: 10000 });
    } finally {
      cleanS7();
    }
  });

  // =========================================================================
  // Demo 4:40 - 5:00: Audit Trail & Cryptographic Verification
  // =========================================================================
  test("4:40-5:00 Audit Trail & Integrity Log: Log Entries & SHA-256 Chain Cryptographic Verification", async ({
    page,
  }) => {
    // 1. Sign in as Admin
    await loginAs(page, "admin@demo-holdings.example");
    await page.goto("/audit");
    await expect(page.locator("h1")).toContainText(/Audit Trail & Integrity Log/i);

    // 2. Verify audit table displays entries
    await expect(page.locator("table")).toBeVisible({ timeout: 10000 });

    // 3. Verify Admin has CSV export button
    await expect(page.locator('[data-testid="export-audit-csv-btn"]')).toBeVisible();

    // 4. Click 'Verify Hash Chain' and verify cryptographic confirmation banner
    const verifyChainBtn = page.locator('[data-testid="verify-audit-chain-btn"]');
    await expect(verifyChainBtn).toBeVisible();
    await verifyChainBtn.click();

    const resultBanner = page.locator('[data-testid="audit-verify-result-banner"]');
    await expect(resultBanner).toBeVisible({ timeout: 15000 });
    await expect(resultBanner).toContainText(/Hash-Chain Verification Passed/i);
  });
});
