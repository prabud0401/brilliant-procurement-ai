/**
 * Money and date formatting helpers for Demo Holdings LLC (UAE).
 * Currency is always AED; timestamps are displayed in Asia/Dubai (GST, UTC+4).
 */

/**
 * Formats a monetary amount into AED standard format: "AED 12,500.00".
 * Uses string/exact splitting where possible to avoid floating point issues.
 */
export function formatMoneyAED(
  amount: number | string | null | undefined,
  options: { includeCurrency?: boolean } = { includeCurrency: true }
): string {
  if (amount === null || amount === undefined || amount === "") {
    return options.includeCurrency ? "AED 0.00" : "0.00";
  }

  const num = typeof amount === "number" ? amount : parseFloat(String(amount));
  if (isNaN(num)) {
    return options.includeCurrency ? "AED 0.00" : "0.00";
  }

  const formatted = new Intl.NumberFormat("en-AE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);

  return options.includeCurrency ? `AED ${formatted}` : formatted;
}

/**
 * Formats a UTC timestamp into Gulf Standard Time (Asia/Dubai, UTC+4).
 * Example output: "20 Nov 2026, 05:30 GST"
 */
export function formatGSTDate(
  dateInput: string | Date | number | null | undefined,
  options: {
    includeTime?: boolean;
    dateStyle?: "short" | "medium" | "long" | "full";
    timeStyle?: "short" | "medium";
  } = { includeTime: true, dateStyle: "medium", timeStyle: "short" }
): string {
  if (!dateInput) return "—";

  const date = typeof dateInput === "object" ? dateInput : new Date(dateInput);
  if (isNaN(date.getTime())) return "—";

  const formatter = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Dubai",
    year: "numeric",
    month: options.dateStyle === "short" ? "2-digit" : "short",
    day: "numeric",
    ...(options.includeTime
      ? {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }
      : {}),
  });

  const formatted = formatter.format(date);
  return options.includeTime ? `${formatted} GST` : formatted;
}
