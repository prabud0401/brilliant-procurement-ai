import { describe, it, expect } from "vitest";
import { formatMoneyAED, formatGSTDate, formatVatRate } from "@/lib/formatters";

describe("Formatting Utilities for UAE (AED & GST)", () => {
  describe("formatMoneyAED", () => {
    it("formats standard numbers with 2 decimal places and AED currency prefix", () => {
      expect(formatMoneyAED(12500)).toBe("AED 12,500.00");
      expect(formatMoneyAED(50.5)).toBe("AED 50.50");
      expect(formatMoneyAED(0)).toBe("AED 0.00");
    });

    it("formats string amounts cleanly", () => {
      expect(formatMoneyAED("19950.00")).toBe("AED 19,950.00");
      expect(formatMoneyAED("1250.75")).toBe("AED 1,250.75");
    });

    it("handles null, undefined, and empty string gracefully", () => {
      expect(formatMoneyAED(null)).toBe("AED 0.00");
      expect(formatMoneyAED(undefined)).toBe("AED 0.00");
      expect(formatMoneyAED("")).toBe("AED 0.00");
      expect(formatMoneyAED("invalid-num")).toBe("AED 0.00");
    });

    it("supports includeCurrency: false option", () => {
      expect(formatMoneyAED(12500, { includeCurrency: false })).toBe("12,500.00");
      expect(formatMoneyAED(null, { includeCurrency: false })).toBe("0.00");
    });
  });

  describe("formatGSTDate", () => {
    it("formats UTC timestamps in Gulf Standard Time (Asia/Dubai, UTC+4)", () => {
      // 2026-11-20T00:00:00Z in UTC is 04:00 in Asia/Dubai
      const utcDate = "2026-11-20T00:00:00Z";
      const formatted = formatGSTDate(utcDate);
      expect(formatted).toContain("2026");
      expect(formatted).toContain("04:00");
      expect(formatted).toContain("GST");
    });

    it("handles Date objects and numeric epoch milliseconds", () => {
      const date = new Date("2026-11-20T10:30:00Z");
      const formatted = formatGSTDate(date);
      // 10:30 UTC + 4h = 14:30 GST
      expect(formatted).toContain("14:30");
      expect(formatted).toContain("GST");
    });

    it("handles null and undefined with an em dash", () => {
      expect(formatGSTDate(null)).toBe("—");
      expect(formatGSTDate(undefined)).toBe("—");
      expect(formatGSTDate("")).toBe("—");
      expect(formatGSTDate("not-a-date")).toBe("—");
    });

    it("supports includeTime: false option", () => {
      const utcDate = "2026-11-20T12:00:00Z";
      const formatted = formatGSTDate(utcDate, { includeTime: false });
      expect(formatted).not.toContain("GST");
      expect(formatted).toContain("2026");
    });
  });

  describe("formatVatRate", () => {
    it("formats fractional rates (<= 1) as percentage: 0.05 -> 5%", () => {
      expect(formatVatRate(0.05)).toBe("5%");
      expect(formatVatRate("0.05")).toBe("5%");
      expect(formatVatRate("0.0500")).toBe("5%");
    });

    it("formats whole number rates as percentage: 5 -> 5%", () => {
      expect(formatVatRate(5)).toBe("5%");
      expect(formatVatRate("5")).toBe("5%");
      expect(formatVatRate("5.00")).toBe("5%");
    });

    it("supports optional decimals formatting: 0.05 with decimals=2 -> 5.00%", () => {
      expect(formatVatRate(0.05, { decimals: 2 })).toBe("5.00%");
      expect(formatVatRate(5, { decimals: 2 })).toBe("5.00%");
    });

    it("handles zero, null, undefined, empty, and non-numeric gracefully", () => {
      expect(formatVatRate(0)).toBe("0%");
      expect(formatVatRate(null)).toBe("0%");
      expect(formatVatRate(undefined)).toBe("0%");
      expect(formatVatRate("")).toBe("0%");
      expect(formatVatRate("invalid")).toBe("0%");
    });

    it("handles decimal percentages such as 5.5%", () => {
      expect(formatVatRate(0.055)).toBe("5.5%");
    });
  });
});
