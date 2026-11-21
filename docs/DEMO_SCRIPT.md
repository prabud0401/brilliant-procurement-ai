# 5-minute live demo script

A spoken walkthrough of the hosted Procurement Document Assistant, using the records already on the live app. Do not create new requests, do not confirm or acknowledge extra documents, and do not resolve the INV-5510 exception — leave those as they are so the demo can be repeated.

**Live app:** https://ca-web-pda-prod-uaen.whitesea-eaa80b88.uaenorth.azurecontainerapps.io

Use the demo accounts below. The shared password is provided separately (never read it out). All amounts are AED. Purchase-order totals include 5% UAE VAT.

If a page is slow to open, keep talking from the script; do not refresh mid-extraction.

For a from-scratch flow that creates its own records (local or a disposable environment), see `docs/demo-script-from-scratch.md`.

---

## Accounts you will use

| When | Sign in as | Role | Why |
| --- | --- | --- | --- |
| Most of the five minutes | `buyer2@demo-holdings.example` (Sara, IT) | Buyer | Documents, comparisons, orders, matching, Q&A |
| Last stretch | `admin@demo-holdings.example` (Aisha, IT) | Admin | Spend by department, audit log, segregation of duties |

Mention, but you do not need to sign in as all of them:

- Requesters: Omar (IT), Fatima (Facilities), Hamad (Operations)
- Managers: Yousef (IT, AED 50,000), Mariam (Facilities, AED 50,000), Khalid (Projects, AED 250,000), Reem (Operations, AED 50,000)

---

## 0:00–0:35 — Sign in and roles

1. Open the live link. On the sign-in page, point out the four roles: Requester, Buyer, Manager, Admin.
2. Sign in as Sara (`buyer2@demo-holdings.example`).
3. Point to the short navigation: Home, Documents, Requests, Comparisons, Orders, Approvals, Matching, Q&A, Audit.
4. Say in one line: AI reads and checks the paperwork; a person still makes every decision that commits money; every step is logged.

---

## 0:35–1:15 — Upload and extraction

1. Click **Documents**.
2. Point to **Upload Document** (quotation, purchase order, delivery note or invoice). Say that this is how new paperwork enters the demo today. Email intake is built but switched off for this demo, so uploads are used instead.
3. Do not upload a new file now (extraction would overrun the five minutes).
4. In the list, open **Gulf Line IT Trading · Q-1042** (search `Q-1042` if needed).
5. Show the split-screen review: the PDF on one side, extracted fields and confidence on the other. Click a field such as payment terms or the total and show the highlight on the page.
6. Note that the title is the supplier and document number, not a raw system id. Leave the document as it is; do not save new corrections.

---

## 1:15–1:55 — Quote comparison

1. Click **Requests**. Open **PR-2026-89FBB2** (Al Ain Tower HQ IT workstation refresh, Omar in IT, AED 27,500).
2. Show the three linked quotations: Gulf Line, Falcon and Corniche.
3. Click **Comparisons** (or open the existing comparison from the request). Open the IT comparison that recommends **Gulf Line IT Trading**.
4. Show the side-by-side matrix (quoted total, lead time, payment terms and validity) and the written recommendation.
5. Say that if a buyer picks a different supplier, the app asks for a written reason before it will continue. Do not create a new comparison or a new purchase order.

---

## 1:55–2:40 — Approvals, including two managers above AED 50,000

1. Click **Orders**. Open **PO-2026-6D79D3** (Gulf Line, AED 28,875 including VAT).
2. Show that this stayed with one manager: Yousef in IT, because it is under AED 50,000.
3. Point out **VAT (5% Standard UAE)** and, if visible, the stand-in **Push to Odoo** action. Say this is a plug-in point: today it uses demo data; a real Odoo company database would use the same button.
4. Go back to **Orders** (or **Requests**) and open the Facilities fit-out: **PR-2026-427C5B** / **PO-2026-1C8000**, AED 62,800 exclusive of VAT (PO total AED 62,947.50).
5. Show the two-step approval: first Mariam (Facilities manager), then Khalid (Projects manager, AED 250,000 limit), because the amount is above AED 50,000.
6. Say the same rule applies in every department, and that nobody can approve their own request. Do not approve or reject anything.

---

## 2:40–3:25 — Three-way match and INV-5510 escalation

1. Click **Matching**.
2. Briefly point to the matched IT invoice **Gulf Line IT Trading · INV-2291** (delivery notes DN-771 and DN-772): matched, ready for payment.
3. Open **Desert Build Materials · INV-5510** (Mussafah M40 cabling, PO-2026-8B953C).
4. Show the line: Cat6 UTP cable, purchase-order unit price AED 320, invoice unit price AED 336, variance AED 1,600 — above the buyer’s AED 500 limit.
5. Show that the exception is **Escalated to Manager** (Reem, Operations). The default queue already includes this row; you should not need to change the filter.
6. Leave the exception open. Do not accept, reject or escalate again.

---

## 3:25–3:55 — Hidden instructions on INV-7001

1. Click **Documents**. Open **Desert Build Materials · INV-7001**.
2. Point to the red banner: **Security Alert: Suspicious Content Detected (Prompt Injection Defence)**.
3. Show that the invoice total is still **AED 2,625.00** — the hidden “set the total to 0 / approve this invoice” text did not change the figures.
4. Show that **Confirm Document** stays blocked until a buyer acknowledges the warning and types a reason.
5. Do not acknowledge it. Leave the banner in place for the next run.

---

## 3:55–4:25 — Q&A with citations

1. Click **Q&A**.
2. Ask: “What is the total amount and VAT on quote Q-1042?”
3. Read the answer, then click a citation badge. The source page of the Gulf Line quote should open.
4. Return to **Q&A** and ask: “What is the average rainfall in the Amazon rainforest in 1950?”
5. Show the refusal: the assistant will not invent an answer from outside the approved procurement documents.

---

## 4:25–4:45 — Admin: spend by department and the audit log

1. Sign out. Sign in as Aisha (`admin@demo-holdings.example`).
2. Click **Metrics**. Show the **Spend by department** card: Facilities AED 62,947.50, IT AED 28,875, Operations AED 33,600, and zero for Finance, HR and Projects (no purchases there yet).
3. Click **Audit**. Scroll a few entries (who did what, and when). Click **Export CSV**, then **Verify Hash Chain**, and show that the chain is intact.
4. If there are a few seconds left, open **Approvals** and show the friendly message that administrators cannot approve financial commitments.

---

## 4:45–5:00 — Close: one engine, many departments, and what comes next

Speak this, without opening new screens unless you still have the Facilities or IT order in view:

- This is one engine: documents in, AI reads them, a person checks them, rules send them to the right people, and every step is logged. The first workflow is procure-to-pay, and it already runs across departments — Facilities, Finance, HR, IT, Operations and Projects.
- What you just saw: IT workstations, a Facilities fit-out that needed two managers, and an Operations invoice that was sent up for a price difference.
- Next, on the same engine, would be a live link to Odoo, Microsoft 365 and SharePoint for documents and sign-in, and Power Automate / email intake so supplier mail can arrive on its own. Those connectors are ready as stand-ins in this demo; hooking up the real systems is the natural next step.

Stop at 5:00. Offer to go back to any screen.
