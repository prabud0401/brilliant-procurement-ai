# 4. Replay, Mock, and Live AI Provider Abstraction

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Calling external LLM and document intelligence APIs during local development, CI builds, and unit testing incurs network latency, variable costs, quota exhaustion, and test flakiness. However, production requires real cloud AI services (Azure OpenAI and Azure Document Intelligence).

## Decision
Encapsulate all AI interactions behind unified interfaces in `app/ai` (`DocumentAnalyzer`, `LlmClient`, `Embedder`, `AnswerWriter`). Implement three swappable providers controlled via the `AI_PROVIDER` environment variable:
1. `mock`: Rule-based deterministic synthetic returns for rapid headless tests.
2. `replay`: High-fidelity offline evaluation and local development using captured fixtures.
3. `live`: Production Azure OpenAI and Document Intelligence with managed identity authentication and cost metering.

## Consequences
- **Positive:** Unit and CI tests run completely offline with zero Azure API costs or credentials; evaluation metrics can be validated reproducibly on ground truth; switching to live mode requires only configuration changes.
- **Negative:** Replay fixtures must be refreshed when document schemas or test cases evolve; subtle discrepancies between live API latency/behavior and recorded fixtures can occur.
