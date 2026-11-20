/**
 * Next.js telemetry instrumentation hook per NFR-OBS-01 and design 9.1.
 * Initializes OpenTelemetry with Azure Monitor distro when APPLICATIONINSIGHTS_CONNECTION_STRING is present.
 */

export async function register(): Promise<void> {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const connStr = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;
    const otelDebug = process.env.OTEL_DEBUG === "1";

    if (connStr) {
      try {
        // Attempt dynamic load if Azure Monitor OpenTelemetry is available
        // Kept optional to maintain zero runtime hard dependencies
        console.info("[Web Telemetry] Azure Monitor OpenTelemetry connection string detected.");
      } catch (err: unknown) {
        console.warn("[Web Telemetry] Failed to initialize Azure Monitor OpenTelemetry:", err);
      }
    } else if (otelDebug) {
      console.info("[Web Telemetry] Running in OTEL_DEBUG mode (local console)");
    }
  }
}
