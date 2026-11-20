import { describe, it, expect } from "vitest";
import { NAV_CONFIG, getVisibleNavItems } from "@/lib/navigation";
import type { UserRole } from "@/lib/types";

describe("Navigation Configuration & Role Filtering", () => {
  it("enables finished features (Home, Q&A, Admin Metrics)", () => {
    const enabledItems = NAV_CONFIG.filter((item) => item.enabled);
    const enabledIds = enabledItems.map((item) => item.id);
    expect(enabledIds).toContain("home");
    expect(enabledIds).toContain("qa");
    expect(enabledIds).toContain("admin-metrics");

    // Verify other unfinished sections are currently disabled
    const disabledItems = NAV_CONFIG.filter((item) => !item.enabled);
    const disabledIds = disabledItems.map((item) => item.id);
    expect(disabledIds).toContain("documents");
    expect(disabledIds).toContain("requests");
    expect(disabledIds).toContain("comparisons");
    expect(disabledIds).toContain("approvals");
    expect(disabledIds).toContain("matches");
    expect(disabledIds).toContain("audit");
    expect(disabledIds).toContain("admin");
  });

  it("returns empty list if user has no roles", () => {
    expect(getVisibleNavItems([])).toEqual([]);
  });

  it("returns role-appropriate items for standard roles (Admin has no Q&A)", () => {
    // Requester, buyer, manager see Home and Q&A
    const operationalRoles: UserRole[] = ["requester", "buyer", "manager"];
    for (const role of operationalRoles) {
      const items = getVisibleNavItems([role]);
      const ids = items.map((i) => i.id);
      expect(ids).toContain("home");
      expect(ids).toContain("qa");
      expect(ids).not.toContain("admin-metrics");
    }

    // Admin sees Home and Metrics, but NOT Q&A
    const adminItems = getVisibleNavItems(["admin"]);
    const adminIds = adminItems.map((i) => i.id);
    expect(adminIds).toContain("home");
    expect(adminIds).toContain("admin-metrics");
    expect(adminIds).not.toContain("qa");
  });

  it("handles case-insensitive roles correctly", () => {
    const items = getVisibleNavItems(["REQUESTER", "Buyer"]);
    const ids = items.map((i) => i.id);
    expect(ids).toContain("home");
    expect(ids).toContain("qa");
  });

  it("filters items by role when enabled is true", () => {
    // Test logic simulating a feature enabled for admin only
    const mockConfig = [
      {
        id: "admin-feature",
        label: "Admin Only",
        href: "/admin-feature",
        iconName: "Settings",
        allowedRoles: ["admin" as UserRole],
        enabled: true,
        description: "Admin feature",
      },
    ];

    const rolesSetBuyer = new Set(["buyer"]);
    const visibleForBuyer = mockConfig.filter(
      (item) => item.enabled && item.allowedRoles.some((r) => rolesSetBuyer.has(r))
    );
    expect(visibleForBuyer.length).toBe(0);

    const rolesSetAdmin = new Set(["admin"]);
    const visibleForAdmin = mockConfig.filter(
      (item) => item.enabled && item.allowedRoles.some((r) => rolesSetAdmin.has(r))
    );
    expect(visibleForAdmin.length).toBe(1);
  });
});
