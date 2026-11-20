/**
 * True when Playwright targets a hosted deployment rather than the local stack.
 * Specs that seed or clean data through direct database access
 * (services/backend tools.setup_e2e_fixtures + the local .env) can only run locally.
 */
export function isHostedTarget(): boolean {
  const base = process.env.WEB_BASE_URL ?? "http://localhost:3000";
  return !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/.test(base);
}

export const LOCAL_ONLY_REASON =
  "Needs direct DB fixture access (tools.setup_e2e_fixtures); runs on the local stack only.";
