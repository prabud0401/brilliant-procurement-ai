import { describe, it, expect } from "vitest";
import { NAV_CONFIG, getVisibleNavItems } from "@/lib/navigation";
import type { UserRole } from "@/lib/types";

describe("Navigation Configuration & Role Filtering", () => {
  it("enables completed features (R08 + R09) while leaving QA disabled for R10", () => {
    const disabledItems = NAV_CONFIG.filter((item) => !item.enabled);
    const disabledIds = disabledItems.map((item) => item.id);
    expect(disabledIds).toEqual(["qa"]);

    const enabledItems = NAV_CONFIG.filter((item) => item.enabled);
    const enabledIds = enabledItems.map((item) => item.id);
    expect(enabledIds).toContain("home");
    expect(enabledIds).toContain("documents");
    expect(enabledIds).toContain("requests");
    expect(enabledIds).toContain("comparisons");
    expect(enabledIds).toContain("purchase-orders");
    expect(enabledIds).toContain("approvals");
    expect(enabledIds).toContain("matches");
    expect(enabledIds).toContain("audit");
    expect(enabledIds).toContain("admin");
  });

  it("returns empty list if user has no roles", () => {
    expect(getVisibleNavItems([])).toEqual([]);
  });

  it("filters navigation items strictly according to user roles", () => {
    // Admin role
    const adminItems = getVisibleNavItems(["admin"]).map((i) => i.id);
    expect(adminItems).toEqual(["home", "documents", "audit", "admin"]);
    expect(adminItems).not.toContain("approvals");
    expect(adminItems).not.toContain("requests");

    // Requester role
    const requesterItems = getVisibleNavItems(["requester"]).map((i) => i.id);
    expect(requesterItems).toEqual([
      "home",
      "documents",
      "requests",
      "comparisons",
      "purchase-orders",
      "audit",
    ]);
    expect(requesterItems).not.toContain("approvals");
    expect(requesterItems).not.toContain("admin");

    // Buyer role
    const buyerItems = getVisibleNavItems(["buyer"]).map((i) => i.id);
    expect(buyerItems).toEqual([
      "home",
      "documents",
      "requests",
      "comparisons",
      "purchase-orders",
      "approvals",
      "matches",
      "audit",
    ]);
    expect(buyerItems).not.toContain("admin");

    // Manager role
    const managerItems = getVisibleNavItems(["manager"]).map((i) => i.id);
    expect(managerItems).toEqual([
      "home",
      "documents",
      "requests",
      "comparisons",
      "purchase-orders",
      "approvals",
      "matches",
      "audit",
    ]);
    expect(managerItems).not.toContain("admin");
  });

  it("handles case-insensitive roles correctly", () => {
    const items = getVisibleNavItems(["ADMIN"]);
    expect(items.map((i) => i.id)).toContain("admin");
    expect(items.map((i) => i.id)).toContain("home");
  });
});
