# Release checklist

Date checked: 22 Nov 2026, Asia/Dubai (GST, UTC+4)  
Live app: https://ca-web-pda-prod-uaen.whitesea-eaa80b88.uaenorth.azurecontainerapps.io  
Hosted image checked: `6d98534` (document titles and earlier must-fixes). Changes on `main` after `6d98534` are tests and documentation only.  
Repo: https://github.com/prabud0401/brilliant-procurement-ai

**Overall status: green for the in-scope live demo, with two honest notes.** Email intake is optional and left off. One leftover contrast issue on a loading label is recorded below and is not part of the demo path.

Evidence comes from the hosted smoke and Playwright runs against `6d98534`, the 22 Nov hosted walkthrough, and the post-fix hosted API and UI checks (`verify_f29_32`, `verify_ui`). Mutating Playwright suites that would create new records are skipped on the hosted app on purpose, so they do not disturb the demo data.

Passwords are not recorded here. Demo logins are provided separately.

---

## In-scope features

| Item | Status | Evidence |
| --- | --- | --- |
| Sign-in and role workspaces (Requester, Buyer, Manager, Admin) | Green | Hosted Playwright auth suite passed, including sign-in for all seeded demo accounts (12 passed / 12 skipped, 2.5 min). Hosted smoke signed in as `requester.fac@demo-holdings.example`. |
| Role-based navigation and unauthenticated redirect to `/login` | Green | Hosted Playwright: invalid credentials, role badges and capabilities, unauthenticated access redirects to `/login`. |
| Document upload, extraction and split-screen review | Green | Live demo documents are extracted and reviewable. Post-fix UI check opened named documents (for example Gulf Line IT Trading · Q-1042). Creating brand-new uploads is covered by local document Playwright tests, which are skipped on the hosted app so they do not add extra files. |
| Document titles use vendor and number, not a raw UUID | Green | Hosted API check: 14 documents include `vendor_name` or `document_number`. Hosted UI: documents list shows “Gulf Line IT Trading · Q-1042” and does not lead with a raw UUID. |
| Quote comparison and written recommendation | Green | Live IT request PR-2026-89FBB2 has three quotes (Gulf Line, Falcon, Corniche) and a recommendation for Gulf Line IT Trading. Facilities and Operations comparisons are also on the live app. |
| Purchase requests and purchase orders in AED, with 5% UAE VAT on POs | Green | Live POs: PO-2026-6D79D3 (AED 28,875), PO-2026-1C8000 (AED 62,947.50), PO-2026-8B953C (AED 33,600). Hosted UI shows “VAT (5% Standard UAE)” on the Operations PO, not 0.05%. |
| Approvals, including two managers above AED 50,000 | Green | IT PO approved by Yousef (IT manager, AED 50,000 limit). Facilities fit-out PR-2026-427C5B / PO-2026-1C8000 (AED 62,800 exclusive of VAT, above AED 50,000) approved by Mariam (Facilities) then Khalid (Projects, AED 250,000 limit). |
| Three-way match, including a visible escalated exception | Green | IT INV-2291 is matched and ready for payment. Operations INV-5510 shows a price variance of AED 1,600 (PO 320.00 vs invoice 336.00), line description “Cat6 UTP Solid Bulk Ethernet Cable Roll 305m CMR”, and is escalated to the Operations manager. The default exception queue shows the escalated row. |
| Document Q&A with citations, and refusal of out-of-scope questions | Green | Hosted Playwright: answerable question returns citations and the citation opens the source page; rainforest / out-of-scope question is refused. Walkthrough also checked Gulf Line total/VAT and cabling unit prices with citations. |
| Admin spend-by-department card (six departments) | Green | Hosted Playwright: card lists Facilities, Finance, HR, IT, Operations and Projects. Live totals after the walkthrough seed: Facilities AED 62,947.50, IT AED 28,875, Operations AED 33,600. Finance, HR and Projects show zero because no requests have been raised in those departments yet, which is honest. |
| Mock “Push to Odoo” on the purchase order | Green | Present on the PO screen with an idempotency key. This is a stand-in, not a live Odoo company database (see roadmap). |
| Demo data is fictional (Demo Holdings LLC) | Green | Branding and suppliers are invented demo data, not Brilliant production records. |

## Security

| Item | Status | Evidence |
| --- | --- | --- |
| Role-based access control | Green | Hosted Playwright role workspaces and navigation. Questions search only the signed-in person's department. Admin is restricted from Q&A. |
| Segregation of duties | Green | Admin opening `/approvals` sees “Segregation of Duties Enforced” / “System administrators cannot approve financial commitments”, not a raw 403. Self-approval is blocked in product rules and in the local procurement-flow tests (skipped on hosted). |
| Prompt-injection defence (S7, INV-7001) | Green | After the PDF-text-layer scanner was deployed and the live invoice was re-extracted: `suspicious=true`, red banner “Security Alert: Suspicious Content Detected (Prompt Injection Defence)”, and the invoice total stayed AED 2,625.00. Banner copy has no internal story IDs. Confirm stays blocked until a buyer acknowledges with a reason. Left unacknowledged so the demo can show it again. |
| Tamper-evident audit log and CSV export | Green | Walkthrough on 22 Nov 2026, 00:08 GST: hash-chain verification passed (337 entries at that time). Audit page and CSV export are in the live Admin path and in the demo script. Re-click “Verify Hash Chain” during the demo. |
| No secrets in the repository; no cost figures on company-facing screens | Green | gitleaks runs in local and GitHub CI. Hosted admin Metrics page no longer shows “Estimated Cost Today”, “Daily AI Budget”, budget utilisation, or AI spend in AED. Volume and department-spend figures remain. |
| Unauthenticated API access is rejected | Green | Hosted smoke: `/api/v1/me` returns HTTP 401 without a token. |

## Tests and hosting

| Item | Status | Evidence |
| --- | --- | --- |
| Hosted health and sign-in smoke | Green | `scripts/smoke.sh` against the live URL: `/healthz` 200, `/readyz` 200, `/login` 200, unauthenticated `/api/v1/me` 401, `requester.fac` sign-in 200, authenticated `/me` 200. |
| Hosted Playwright (non-mutating) | Green | 12 passed, 12 skipped, 2.5 min, image `6d98534`. Skipped tests are the demo-script, document-upload and procurement-flow suites, which are marked local-only so they do not create records on the live app. Those paths were checked on the live data by the walkthrough and the post-fix API/UI scripts. |
| Post-fix hosted verification of the three must-fixes and polish | Green | `verify_f29_32` (API) and `verify_ui` (browser): all checks passed, including injection banner, match line fields, VAT 5%, human document titles, hidden cost fields, short nav labels, and the friendly SoD page. |
| Hosting on Azure Container Apps (UAE North) | Green | Live web URL above is serving the checked image. Web, API and worker container apps are up (smoke `/healthz` and `/readyz`). |
| Email intake (Outlook / Power Automate path) | Optional, disabled | The Logic App connection exists but is not authorised. Email intake is switched off for this demo and is not required for the walkthrough, which uses in-app upload. Turning it on needs a one-time Outlook.com sign-in in the Azure portal (see “Needs a person”). |

## Documentation

| Item | Status | Evidence |
| --- | --- | --- |
| Company-facing explainer (plain English) | Green | Notion page and Google Doc updated with the live URL (logins provided separately) and a simple “one engine, many departments” diagram in place of the placeholder. |
| 5-minute demo script using live demo data | Green | `docs/DEMO_SCRIPT.md` (this repository). |
| This checklist | Green | `docs/RELEASE_CHECKLIST.md`. |

---

## Not green, or out of scope — recorded honestly

1. **Email intake is off.** It is optional for the demo. It stays disabled until the Outlook.com connection is authorised. The upload path is the supported way to get documents into the live app.
2. **Residual contrast issue.** The “Loading document viewer…” placeholder can be slightly too faint for a moment while a document opens. It failed an accessibility check once in four earlier runs. It was left unfixed (no further coding runs were approved). It is not on the spoken demo path once the document has loaded.
3. **Finance, HR and Projects show zero spend.** Six departments exist and sign-in works for their requesters and managers. Only IT, Facilities and Operations have completed purchases on the live app. The zeros are correct, not a defect.
4. **Roadmap, not in this release:** live Odoo and SharePoint connectors (stand-ins only today), Microsoft 365 / Entra SSO, contractor tenders / BoQ / retention, multi-entity group companies, Arabic UI, budget vs actual / WBS, and a full catalogue for HVAC, MEP or landscaping.

## Needs a person

- A one-time Outlook.com sign-in in the Azure portal if email intake should be part of a later walkthrough: resource group `rg-brilliant-demo-prod`, API connection `outlook-pda-prod-uaen`, Edit API connection, then Authorise.
- Nothing from this checklist should be sent to Brilliant until the owner is happy with the app and the handover pack.
