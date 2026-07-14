# Changelog

## 3.0.0 - 2026-07-14

- Rebuilt the CLI around public HTTP reads, privacy-preserving CDP logged-in reads, and explicit browser commits.
- Added `auth-status`, `me-tickets`, `host-events`, `browser-read`, and `event-draft` commands.
- Expanded the route and action maps across attendee, organizer, event, marketing, users, finance, and account areas.
- Added detail-level post-filtering so promoted cards cannot bypass city, mode, time, verification, or free-only filters.
- Distinguished free, paid, and mixed pricing; `--price free` now means fully free.
- Added public-detail caching, conservative request budgets, bounded concurrency, and rate-limit/CAPTCHA circuit breaking.
- Added code-level automatic-registration prohibitions for paid, real-name, identity-document, marketing-risk, excluded-topic, and WeChat-only flows.
- Added required signup-field coverage checks without exposing values.
- Made format, event type, time preference, and business-goal aliases participate in recommendation scoring.
- Added CSV formula-injection protection, flexible form-option parsing, 36 regression tests, and GitHub Actions CI.
- Made public and logged-in browser reads reject activity verification pages, and report temporary-tab cleanup explicitly.
- Required an event ID for every event-scoped action plan and fixed Saturday/Sunday strict-filter windows.
- Removed personal data and unsafe auto-registration guidance from the legacy `huodongxing` Skill via a compatibility alias.

## 2.2.0 - 2026-07-14

- Added persistent local profile and registration policy outside the Skill directory.
- Added business-goal scoring, marketing/exclusion risk penalties and confidence output.
- Added policy-aware signup plans for free, paid, review, real-name and WeChat cases.
- Parallelized recommendation detail enrichment.
- Added reusable weekly, monthly, multi-city and signup workflow templates.

## 2.1.0 - 2026-07-14

- Add OpenClaw, OpenAI Codex, Claude Code, and generic Agent Skill packaging.
- Add Claude Code plugin marketplace manifests and Codex UI metadata.
- Make default search and recommendation behavior neutral for public users.
- Export search and recommendation CSV data one event per row.
- Add `open-route --print-only` for headless agents and sandboxes.
- Add release builder, distribution consistency checks, CI, license, and security review.

## 2.0.0 - 2026-07-14

- Initial public-data CLI and OpenClaw Skill release.
