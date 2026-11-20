import { describe, it, expect } from "vitest";
import { NAV_CONFIG, getVisibleNavItems } from "@/lib/navigation";

describe("Navigation Configuration & Role Filtering", () => {
  it("enables all finished features (R08, R09, R10)", () => {
    const disabledIds = NAV_CONFIG.filter((item) => !item.enabled).map((item) => item.id);
    expect(disabledIds).toEqual([]);
  });

  it("returns empty list if user has no roles", () => {
    expect(getVisibleNavItems([])).toEqual([]);
  });

  it("filters navigation items strictly according to user roles", () => {
    expect(getVisibleNavItems(["admin"]).map((i) => i.id)).toEqual([
      "home",
      "documents",
      "audit",
      "admin",
      "admin-metrics",
    ]);
    expect(getVisibleNavItems(["requester"]).map((i) => i.id)).toEqual([
      "home",
      "documents",
      "requests",
      "comparisons",
      "purchase-orders",
      "qa",
      "audit",
    ]);
    const operational = [
      "home",
      "documents",
      "requests",
      "comparisons",
      "purchase-orders",
      "approvals",
      "matches",
      "qa",
      "audit",
    ];
    expect(getVisibleNavItems(["buyer"]).map((i) => i.id)).toEqual(operational);
    expect(getVisibleNavItems(["manager"]).map((i) => i.id)).toEqual(operational);
  });

  it("Admin has no Q&A and non-admins have no admin pages", () => {
    expect(getVisibleNavItems(["admin"]).map((i) => i.id)).not.toContain("qa");
    for (const role of ["requester", "buyer", "manager"] as const) {
      const ids = getVisibleNavItems([role]).map((i) => i.id);
      expect(ids).not.toContain("admin");
      expect(ids).not.toContain("admin-metrics");
    }
  });

  it("handles case-insensitive roles correctly", () => {
    const ids = getVisibleNavItems(["ADMIN"]).map((i) => i.id);
    expect(ids).toContain("admin");
    expect(ids).toContain("home");
  });
});
