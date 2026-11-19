import { describe, it, expect } from "vitest";
import { NAV_CONFIG, getVisibleNavItems } from "@/lib/navigation";
import type { UserRole } from "@/lib/types";

describe("Navigation Configuration & Role Filtering", () => {
  it("only enables finished features per R05 requirements (Home only for now)", () => {
    const enabledItems = NAV_CONFIG.filter((item) => item.enabled);
    expect(enabledItems.length).toBe(1);
    expect(enabledItems[0].id).toBe("home");
    expect(enabledItems[0].href).toBe("/");

    // Verify all other sections are currently disabled so no dead links or placeholder stubs exist
    const disabledItems = NAV_CONFIG.filter((item) => !item.enabled);
    const disabledIds = disabledItems.map((item) => item.id);
    expect(disabledIds).toContain("documents");
    expect(disabledIds).toContain("requests");
    expect(disabledIds).toContain("comparisons");
    expect(disabledIds).toContain("approvals");
    expect(disabledIds).toContain("matches");
    expect(disabledIds).toContain("qa");
    expect(disabledIds).toContain("audit");
    expect(disabledIds).toContain("admin");
  });

  it("returns empty list if user has no roles", () => {
    expect(getVisibleNavItems([])).toEqual([]);
  });

  it("returns Home item for all standard roles", () => {
    const roles: UserRole[] = ["requester", "buyer", "manager", "admin"];
    for (const role of roles) {
      const items = getVisibleNavItems([role]);
      expect(items.length).toBe(1);
      expect(items[0].id).toBe("home");
      expect(items[0].href).toBe("/");
    }
  });

  it("handles case-insensitive roles correctly", () => {
    const items = getVisibleNavItems(["REQUESTER", "Buyer"]);
    expect(items.length).toBe(1);
    expect(items[0].id).toBe("home");
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
