# CLAUDE.md — Playcheck Cloud (private, commercial)

Ground truth for this repo. Read fully before any implementation decision.

## What this is

The paid, closed-source hosted tier of Playcheck. The free, MIT-licensed CLI +
GitHub Action live at https://github.com/Cjayy77/Playcheck (PyPI: `playcheck`)
and stay open source forever — never move core preview logic into this repo.

Playcheck (the CLI) runs `ansible-playbook --check --diff` and produces an
honest, readable preview — including flagging every task that could NOT be
simulated. This repo sells the convenience layer around it:

- **Hosted dashboard**: previews land in a web UI — full history across repos,
  who ran what and when, diffs over time.
- **Org connect**: connect a GitHub org once instead of per-repo CI setup.
- **Team features**: approval workflows for risky changes, Slack notifications,
  audit logs.

Business model: open core (GitLab/Sentry/Plausible shape). Free tier generous,
Team tier paid via Stripe subscriptions.

## Architecture decisions (settled — do not relitigate)

- **Backend: Python (Django 5 + Postgres)**. Reason: `pip install playcheck`
  gives you the canonical parser/classifier (`playcheck.parse.parse_events`,
  `playcheck.model`) — NEVER reimplement result classification here; the CLI
  package is the single source of truth for what "NOT PREVIEWED" means.
- **Frontend: Django templates + Tailwind + HTMX.** One deployable service, no
  separate SPA. This is a dashboard, not an app-store app.
- **Auth: GitHub OAuth** (django-allauth). Devs won't create another password.
- **Billing: Creem.io (merchant of record) — hosted checkout, customer
  portal, HMAC-signed webhooks.** Changed from Stripe by owner decision on
  2026-07-04; Creem handles global tax/invoicing, which suits a solo
  maintainer.
- **Ingest contract**: CI uploads the playcheck JSONL event stream verbatim
  (`POST /api/v1/previews`, bearer token per project). The server parses with
  the `playcheck` package. Version the endpoint; never break old CLI versions.

## Build order — vertical slices, each one shippable. Do not skip ahead.

1. **Ingest + view.** GitHub login; create a project; get an upload token;
   `POST /api/v1/previews` accepts JSONL + metadata (repo, branch, commit, PR#,
   actor); preview list page; preview detail page rendering per-host groups,
   colored diffs, and the NOT PREVIEWED warnings. Seed with real fixtures from
   the public repo (`tests/fixtures/jsonl_output.jsonl`). This slice alone is
   the product.
2. **Teams.** Orgs, member invites, roles (admin/member), audit log of
   uploads/views/settings changes.
3. **Billing.** Free tier: 1 project, 14-day history, 2 members. Team tier:
   unlimited projects/history/members. Creem webhooks drive entitlements;
   gate features server-side, never in the template only.
4. **Integration docs + Action support.** Docs page with copy-paste snippets.
   The public Action gains optional `upload-url` + `api-token` inputs (that
   change happens in the PUBLIC repo, kept minimal and optional).
5. **GitHub App org connect.** Only after 1–4 work end to end.
6. **Approvals + Slack.** Only with real paying-tier interest.

## Ground rules

- **The honesty guarantee transfers.** The dashboard must render "N tasks were
  NOT simulated" at least as loudly as the CLI does. A pretty UI that buries
  that warning defeats the product. Correctness of this over any feature.
- **Tenant isolation is existential.** Every query scoped to the requesting
  org; write cross-tenant access tests before shipping slice 1. Upload tokens
  stored hashed. Preview payloads are already secret-censored upstream
  (`no_log`/`diff: false` never reach the CLI's callback), but treat all
  payloads as sensitive anyway.
- **UI: GitHub-like but distinctive.** Familiar bones — top nav, left repo/
  project sidebar, dense tables, monospace diffs with green/red line
  backgrounds, light + dark mode. Distinctive skin: violet/purple accent
  (matches the Action's marketplace branding), own typography. It should feel
  instantly navigable to a GitHub user without looking like a clone.
- **Solo-maintainer bias.** Boring dependencies, one service, one database,
  migrations always reversible. No microservices, no queues until something
  measurably needs one.
- **Verify with real data.** Render real captured playcheck output, never
  hand-invented JSON. If a fixture is missing a case (unreachable hosts, loop
  diffs, 15-host grouping), generate it with the real CLI first.

## When returning in a new session

1. Check which build-order slice is actually current from the repo state.
2. Run the test suite before and after changes; keep tenant-isolation tests green.
3. New feature ideas: if it isn't required by the current slice, write it down
   at the bottom of this file instead of building it.
