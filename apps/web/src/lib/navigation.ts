import type { UserRole } from "./types";

export interface NavItem {
  id: string;
  label: string;
  href: string;
  iconName: string;
  allowedRoles: UserRole[];
  enabled: boolean;
  description: string;
}

/**
 * Master navigation registry for the Procurement Document Assistant.
 *
 * NOTE: Per R05 spec, ONLY finished features are enabled.
 * For now that is Home only. Subsequent runs (R08, R09, R10)
 * enable their respective sections by setting enabled: true.
 * No disabled/placeholder links are rendered in navigation.
 */
export const NAV_CONFIG: NavItem[] = [
  {
    id: "home",
    label: "Home",
    href: "/",
    iconName: "Home",
    allowedRoles: ["requester", "buyer", "manager", "admin"],
    enabled: true,
    description: "Overview dashboard and role capabilities",
  },
  {
    id: "documents",
    label: "Documents",
    href: "/documents",
    iconName: "FileText",
    allowedRoles: ["requester", "buyer", "manager", "admin"],
    enabled: false, // Activated in R08
    description: "Upload, view and review procurement documents and extractions",
  },
  {
    id: "requests",
    label: "Purchase Requests",
    href: "/requests",
    iconName: "ShoppingCart",
    allowedRoles: ["requester", "buyer", "manager"],
    enabled: false, // Activated in R09
    description: "Create and track purchase requests and line items",
  },
  {
    id: "comparisons",
    label: "Comparisons",
    href: "/comparisons",
    iconName: "GitCompare",
    allowedRoles: ["requester", "buyer", "manager"],
    enabled: false, // Activated in R09
    description: "Quote comparison matrices, scoring, and recommendations",
  },
  {
    id: "approvals",
    label: "Approvals",
    href: "/approvals",
    iconName: "CheckSquare",
    allowedRoles: ["buyer", "manager"],
    enabled: false, // Activated in R09
    description: "Review and approve pending purchase requests and POs",
  },
  {
    id: "matches",
    label: "Three-Way Match",
    href: "/matches",
    iconName: "Layers",
    allowedRoles: ["buyer", "manager"],
    enabled: false, // Activated in R09
    description: "Match POs, delivery notes, and invoices with tolerance rules",
  },
  {
    id: "qa",
    label: "Document Q&A",
    href: "/qa",
    iconName: "HelpCircle",
    allowedRoles: ["requester", "buyer", "manager"],
    enabled: true, // Activated in R10
    description: "AI-assisted Q&A across procurement documents with citations",
  },
  {
    id: "audit",
    label: "Audit Trail",
    href: "/audit",
    iconName: "Shield",
    allowedRoles: ["requester", "buyer", "manager", "admin"],
    enabled: false, // Activated in R09
    description: "Tamper-evident hash-chained audit log and CSV export",
  },
  {
    id: "admin",
    label: "Admin",
    href: "/admin",
    iconName: "Settings",
    allowedRoles: ["admin"],
    enabled: false, // Activated in R09
    description: "System configuration, user management, and tolerances",
  },
  {
    id: "admin-metrics",
    label: "Metrics",
    href: "/admin/metrics",
    iconName: "BarChart",
    allowedRoles: ["admin"],
    enabled: true, // Activated in R10
    description: "System observability and procurement business metrics",
  },
];

/**
 * Filters navigation items for a given user based on their roles and feature flag status.
 * Only returns items where enabled === true and user holds at least one allowed role.
 */
export function getVisibleNavItems(userRoles: (UserRole | string)[]): NavItem[] {
  if (!userRoles || userRoles.length === 0) return [];

  const rolesSet = new Set(userRoles.map((r) => r.toLowerCase()));

  return NAV_CONFIG.filter(
    (item) => item.enabled && item.allowedRoles.some((role) => rolesSet.has(role))
  );
}
