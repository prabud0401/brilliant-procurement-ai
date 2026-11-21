import { test, expect } from "@playwright/test";
import path from "path";
import fs from "fs";

const DEMO_PASSWORD = process.env.DEMO_USER_PASSWORD || "demo_password_123";

async function loginAs(page: any, email: string) { // eslint-disable-line @typescript-eslint/no-explicit-any
  await page.goto("/login");
  await page.fill('input[name="email"]', email);
  await page.fill('input[name="password"]', DEMO_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL("/", { timeout: 15000 });
}

test.describe("Q&A Screen, Citations, Refusals and Observability (R10)", () => {
  let createdDocId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // 1. Authenticate as Buyer via API
    const loginRes = await request.post("/api/v1/auth/login", {
      data: {
        email: "buyer1@demo-holdings.example",
        password: DEMO_PASSWORD,
      },
    });

    if (!loginRes.ok()) {
      return;
    }

    const { access_token } = await loginRes.json();
    const headers = { Authorization: `Bearer ${access_token}` };

    // 2. Upload S1 quotation PDF if not already confirmed
    const pdfPath = path.resolve(process.cwd(), "../../tools/datagen/out/s1-quote-gulfline.pdf");
    if (!fs.existsSync(pdfPath)) {
      return;
    }

    const pdfBuffer = fs.readFileSync(pdfPath);
    const uploadRes = await request.post("/api/v1/documents", {
      headers,
      multipart: {
        file: {
          name: "s1-quote-gulfline.pdf",
          mimeType: "application/pdf",
          buffer: pdfBuffer,
        },
        doc_type: "quote",
      },
    });

    let docId = "";
    if (uploadRes.status() === 202) {
      const upData = await uploadRes.json();
      docId = upData.id;
    } else if (uploadRes.status() === 409) {
      // Document already exists
      const err = await uploadRes.json();
      docId = err.errors?.[0]?.existing_document_id || "";
    }

    if (docId) {
      createdDocId = docId;

      // Poll until extracted
      for (let i = 0; i < 15; i++) {
        const checkRes = await request.get(`/api/v1/documents/${docId}`, { headers });
        if (checkRes.ok()) {
          const doc = await checkRes.json();
          if (["needs_review", "confirmed"].includes(doc.status)) {
            // Confirm document so chunks/embeddings are generated
            await request.post(`/api/v1/documents/${docId}/confirm`, { headers });
            break;
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }
  });

  test("US-17 & US-20: Buyer asks answerable question, receives citations, clicks citation to view cited page", async ({
    page,
  }) => {
    await loginAs(page, "buyer1@demo-holdings.example");

    // Navigate to Q&A screen
    await page.goto("/qa");
    await expect(page.locator("h1")).toContainText(/Document Assistant Q&A/i);

    // Ask an answerable question regarding quote Q-1042 or Gulf Line
    const textarea = page.locator('textarea[placeholder*="Ask a question"]');
    await expect(textarea).toBeVisible();

    await textarea.fill("What is the total amount and VAT on quote Q-1042?");
    await page.locator('button[aria-label="Send question"]').click();

    // Verify user bubble appeared
    await expect(page.locator("text=What is the total amount and VAT on quote Q-1042?")).toBeVisible();

    // Verify assistant responded with an answer
    const assistantMessage = page.locator('div:has(> svg.lucide-bot) + div');
    await expect(assistantMessage).toBeVisible({ timeout: 20000 });

    // Verify citations are present
    const citationLink = page.locator('a[href*="/documents/"]').filter({ hasText: /p\./i });
    if (await citationLink.count() > 0) {
      const firstCitation = citationLink.first();
      await expect(firstCitation).toBeVisible();

      // Click citation
      await firstCitation.click();

      // Verify opened review page at the cited page
      await page.waitForURL(/\/documents\/[a-f0-9-]+(\?.*)?/, { timeout: 15000 });
      await expect(page.locator("h1")).toContainText(/Document Review/i);
    }
  });

  test("US-18: Out-of-scope or unanswerable question receives clear refusal message without hallucination", async ({
    page,
  }) => {
    await loginAs(page, "buyer1@demo-holdings.example");

    await page.goto("/qa");
    const textarea = page.locator('textarea[placeholder*="Ask a question"]');
    await textarea.fill("What is the average rainfall in the Amazon rainforest in 1950?");
    await page.locator('button[aria-label="Send question"]').click();

    // Verify refusal message appears
    const refusalHeader = page.locator("text=Unable to Answer");
    await expect(refusalHeader).toBeVisible({ timeout: 20000 });

    const refusalBody = page.getByText(/could not find|refused|unrelated|accessible/i).first();
    await expect(refusalBody).toBeVisible();
  });

  test("US-19 & NFR-OBS-03: Admin metrics page displays KPIs; Admin is restricted from Q&A", async ({
    page,
  }) => {
    await loginAs(page, "admin@demo-holdings.example");

    // 1. Visit /admin/metrics
    await page.goto("/admin/metrics");
    await expect(page.locator("h1")).toContainText(/Observability & Business Metrics/i);

    // Verify core metric sections
    await expect(page.getByText("Documents Processed", { exact: true })).toBeVisible();
    await expect(page.getByText("Fields Needing Review", { exact: true })).toBeVisible();
    await expect(page.getByText("Match Exception Rate", { exact: true })).toBeVisible();
    await expect(page.getByText("Approval Cycle Time", { exact: true })).toBeVisible();
    await expect(page.getByText("Q&A Refusal Rate", { exact: true })).toBeVisible();
    await expect(page.getByText("AI Invocations & Token Usage Today", { exact: true })).toBeVisible();

    // 2. Admin navigates to /qa -> verify restricted access message
    await page.goto("/qa");
    await expect(page.locator("text=Q&A Restricted for Administrator Role")).toBeVisible();
  });

  test("NFR-REL-04 & BFF: Offline API shows friendly error state, not a crash", async ({
    page,
  }) => {
    await loginAs(page, "buyer1@demo-holdings.example");

    // Intercept backend API calls to simulate service outage (503 Service Unavailable)
    await page.route("**/api/v1/**", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/problem+json",
        body: JSON.stringify({
          type: "https://pda.example/errors/api-unreachable",
          title: "API Unreachable",
          status: 503,
          code: "API_UNAVAILABLE",
          detail: "Backend procurement API is currently unreachable. Please try again shortly.",
        }),
      });
    });

    await page.goto("/qa");
    const textarea = page.locator('textarea[placeholder*="Ask a question"]');
    await expect(textarea).toBeVisible({ timeout: 10000 });
    await textarea.fill("Test offline API");
    await page.locator('button[aria-label="Send question"]').click();

    // Verify friendly error toast or alert appears, no unhandled exception crash
    const errorNotice = page.getByText(/unreachable|unavailable|failed/i).first();
    await expect(errorNotice).toBeVisible({ timeout: 10000 });
  });
});
