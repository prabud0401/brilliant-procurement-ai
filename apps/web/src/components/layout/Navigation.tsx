"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  FileText,
  ShoppingCart,
  GitCompare,
  FileCheck,
  CheckSquare,
  Layers,
  HelpCircle,
  Shield,
  Settings,
} from "lucide-react";
import { getVisibleNavItems } from "@/lib/navigation";
import type { UserRole } from "@/lib/types";

export interface NavigationProps {
  userRoles: (UserRole | string)[];
}

const ICON_MAP: Record<string, React.FC<{ className?: string }>> = {
  Home,
  FileText,
  ShoppingCart,
  GitCompare,
  FileCheck,
  CheckSquare,
  Layers,
  HelpCircle,
  Shield,
  Settings,
};

export const Navigation: React.FC<NavigationProps> = ({ userRoles }) => {
  const pathname = usePathname();
  const visibleItems = getVisibleNavItems(userRoles);

  return (
    <nav
      className="border-b border-slate-200 bg-white"
      aria-label="Main Navigation"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex space-x-8">
          {visibleItems.map((item) => {
            const Icon = ICON_MAP[item.iconName] || Home;
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.id}
                href={item.href}
                className={`inline-flex items-center gap-2 border-b-2 py-3.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                <Icon
                  className={`h-4 w-4 ${
                    isActive ? "text-blue-600" : "text-slate-400"
                  }`}
                  aria-hidden="true"
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
};
