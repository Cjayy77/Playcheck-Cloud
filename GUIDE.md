# Playcheck Cloud — Implementation & Product Guide

The hosted, commercial tier of [Playcheck](https://github.com/Cjayy77/Playcheck).
The free CLI runs `ansible-playbook --check --diff` and produces an honest
preview; this product is the convenience layer around it: hosted history,
team access, and audit trails. This guide covers what exists today (build-order
slices 1–4), both how it feels to a user and how it works underneath.

---

## 1 · The product in one paragraph

A CI job runs the `playcheck` CLI, saves the raw JSONL event stream, and POSTs
it to Playcheck Cloud with a project token. The dashboard renders the preview
exactly as the CLI would — per-host groups, colored diffs, and an impossible-
to-miss warning for every task that could **not** be simulated. Previews
accumulate into a searchable history per project: who ran what, on which
branch and commit, and what would have changed.

**The honesty guarantee is the product.** A preview that hides "5 tasks were
NOT simulated" is worse than no preview. Every screen keeps that warning
louder than anything else on the page.

---

## 2 · The user experience, screen by screen

### Signing in
- **Production**: "Continue with GitHub" (django-allauth OAuth). No passwords.
- **Local dev**: the Django admin login (`/admin/login/?next=/`) stands in,
  since GitHub OAuth needs registered credentials. Seeded users:
  `demo/demo12345` (admin of `acme`) and `teammate/teammate12345` (member).

On first visit after signup, a **personal org** is created automatically
(named after the username). Solo users never have to think about orgs — their
personal org behaves like a private workspace.

### Dashboard (`/`)
One section per org the user belongs to, each listing its projects with
preview counts and last-upload times. Buttons: **New project** (per org,
admins only), **Members**, and a top-nav **New organization**. The left
sidebar mirrors this: org headings with their projects, highlighted when
active.

### Organizations
- **Personal org**: auto-created, marked "(personal)". One per user.
- **Team orgs**: created via *New organization*; the creator becomes its
  first admin. There is no limit on how many orgs a user can belong to.
- All URLs are org-scoped: `/o/<org>/p/<project>/…`, `/o/<org>/members/`,
  `/o/<org>/billing/`, `/o/<org>/audit/`.

### Roles — exactly two
| Ability | Member | Admin |
|---|---|---|
| View projects, preview lists, preview details | ✅ | ✅ |
| View the members page | ✅ | ✅ |
| Create projects, rotate upload tokens | ❌ | ✅ |
| Invite people, change roles, remove members | ❌ | ✅ |
| View the audit log | ❌ | ✅ |
| Billing page, upgrade, manage subscription | ❌ | ✅ |

Rules: an org can never lose its last admin (demote/remove attempts are
refused with a message); non-members get **404s** (not 403s) on all org URLs,
so org names and existence never leak across tenants.

### Invites
From `/o/<org>/members/`, an admin enters an email + role and gets a
**copy-paste invite link** (`/invites/<token>/`) — nothing is emailed
automatically (no SMTP dependency; the admin sends the link over whatever
channel they use). The invitee logs in, sees "Join {org}?", and one click
makes them a member. Invites are single-use and revocable; pending invites
are listed with *Copy link* / *Revoke*.

### Projects & upload tokens
Creating a project immediately shows its upload token (`pck_…`) **once**,
with a copy button and a ready-made CI snippet. Only a SHA-256 hash is stored
— the token cannot be recovered, only rotated (project settings, admin only,
old token dies instantly).

### Preview list (`/o/<org>/p/<project>/`)
A dense table: when, branch + short commit + PR number, actor, hosts changed,
task changes, and warning badges — red "✗ N failed", fuchsia "⚠ N NOT
previewed", or green "✓ fully previewed". Branch filter dropdown, 30-second
auto-refresh (HTMX polling), pagination at 25 rows.

### Preview detail — the heart of the product
Top to bottom:
1. **Honesty banner** — fuchsia "⚠ N tasks were NOT simulated … the real run
   may change more than shown below", or green "✓ Every task could be
   previewed." Nothing renders above it.
2. **Summary tiles** — hosts that would change, task changes (with hidden-diff
   count), not-previewable count, failed/unreachable. Tiles carrying warnings
   are tinted.
3. **Amber strip** if any task executed for real despite `--check`
   (`check_mode: false`).
4. **Per-host groups** — hosts with identical results collapse into one card
   ("= identical on: web-01 web-02 …"), exactly like the CLI. Each task line
   mirrors the CLI's markers: `~` changed (with GitHub-style diffs: filename
   header bar, gutter `+`/`-` markers, green/red line backgrounds), `!` NOT
   PREVIEWED with the reason, `»` ran for real, `✗` FAILED/UNREACHABLE, plus
   hidden-diff labels (`no_log` / `diff: false`) and a quiet "N ok, N skipped
   by condition" footer.

Light and dark mode throughout (class strategy, pre-paint script, toggle in
the nav); violet accent; Inter for UI, JetBrains Mono for anything code-like.

### Audit log (`/o/<org>/audit/`, admins)
Append-only table: when, actor, action, target. Recorded events:
`preview.uploaded` (actor = CI actor or `token <prefix>…`), `preview.viewed`,
`project.created`, `token.rotated`, `invite.created` / `invite.revoked`,
`member.joined` / `member.role_changed` / `member.removed`, `org.created`,
`billing.upgraded` / `billing.downgraded`. Paginated at 50.

---

## 3 · Plans, pricing, and where upgrading happens

### The two tiers
| | **Free** | **Team** |
|---|---|---|
| Projects per org | 1 | unlimited |
| Members per org | 2 | unlimited |
| Preview history | 14 days | unlimited |
| Price | $0 | set in Creem (see below) |

### Where the price lives
**The app does not hardcode a price.** Billing runs on
[Creem.io](https://creem.io) (merchant of record — Creem handles tax,
invoices, and payment methods). You create a "Team" subscription product in
the Creem dashboard, set its monthly/annual price there, and put its product
id in the `CREEM_PRODUCT_ID_TEAM` environment variable. Changing the price is
a Creem-dashboard operation; no deploy needed.

### Where upgrading happens (user's view)
1. An org **admin** opens `/o/<org>/billing/` (linked from the members page,
   and from every "limit reached" screen).
2. The page shows the current plan and live usage meters (projects 1/1,
   members 2/2, history 14 days).
3. **Upgrade to Team** redirects to Creem's hosted checkout — card entry,
   taxes, receipts all happen on Creem's page.
4. Creem redirects back to the billing page; the webhook (below) flips the
   org to Team within seconds.
5. Once on Team, the button becomes **Manage subscription**, which opens
   Creem's customer portal (change payment method, cancel, invoices).

Non-admin members never see billing; if they hit a limit they're told to ask
an org admin.

### How users encounter the limits (all enforced server-side)
- **2nd project (Free)** → a "You've hit a Free plan limit" page (HTTP 403)
  with an upgrade link. The project is not created.
- **3rd member (Free)** → the invite form refuses with a flash message. If an
  invite link already exists and the org fills up before it's used,
  **acceptance re-checks the limit** and refuses — a stale link can't bypass
  the cap.
- **Old previews (Free)** → the list shows only the last 14 days plus a
  violet notice "N older previews hidden — the Free plan keeps 14 days of
  history"; opening an old preview's URL directly returns the upgrade page
  (the preview payload never reaches the template). Data is *retained*, not
  deleted — upgrading reveals the full history instantly.

### The webhook lifecycle (technical)
`POST /billing/webhooks/creem` — CSRF-exempt, verified as HMAC-SHA256 of the
**raw body** against the `creem-signature` header using
`CREEM_WEBHOOK_SECRET` (constant-time compare; unsigned requests are rejected
in production, tolerated only in DEBUG for local testing).

- `checkout.completed` → creates/updates the org's `Subscription` row with
  Creem's customer + subscription ids, status `active`. The org is matched via
  `metadata.org_id`, which we attach when creating the checkout session.
- `subscription.*` (`active`, `paid`, `update`, `trialing`, `canceled`,
  `expired`, `past_due`, `paused`) → status is stored verbatim;
  `current_period_end_date` is parsed when present.
- **Entitlement rule**: Team ⇔ status ∈ {`active`, `trialing`}. Everything
  else (including `past_due`, `canceled`) falls back to Free limits
  automatically — no cron needed.
- Plan transitions write `billing.upgraded` / `billing.downgraded` audit
  events. Webhooks are the *only* writer of subscription status; no
  user-facing view can grant Team.

Sandbox testing: set `CREEM_API_BASE=https://test-api.creem.io` with test-mode
keys.

---

## 4 · Integrations (how previews get in)

### The ingest contract — `POST /api/v1/previews`
- **Auth**: `Authorization: Bearer pck_…` (per-project token).
- **Body**: the playcheck JSONL event stream, **verbatim** — the server never
  receives anything the CLI didn't emit.
- **Query params** (all optional): `repo`, `branch`, `commit`, `pr`, `actor`.
- **Returns**: `201` with `{id, url, summary}`; `401` bad token; `400` empty
  body; `422` not a playcheck stream; `413` over 10 MB; `429` over 30
  uploads/project/minute.
- Versioned path — future changes must stay backward-compatible with old CLIs.

### GitHub Actions (the recommended path)
The public Action already runs playcheck and posts a PR comment. The prepared
patch ([contrib/public-repo-patches/0001-optional-cloud-upload.patch](contrib/public-repo-patches/0001-optional-cloud-upload.patch),
apply in the PUBLIC repo) adds two **optional** inputs:

```yaml
- uses: Cjayy77/Playcheck@v1
  with:
    playbook: site.yml
    inventory: inventories/production
    upload-url: https://your-playcheck-cloud-host   # optional
    api-token: ${{ secrets.PLAYCHECK_TOKEN }}        # optional
```

Implementation: the patch adds `--save-events FILE` to the CLI (writes the
raw JSONL alongside the normal markdown output — one ansible run, two
outputs) and an upload step gated on both inputs being set. Upload failure
prints a workflow warning but **never fails the job or the PR comment**.
Without the inputs, the Action behaves exactly as before — the free product
is never degraded.

### Any other CI
```sh
pip install playcheck
playcheck run site.yml -i inventories/production --quiet --save-events events.jsonl
curl -sS --fail -X POST \
  "https://HOST/api/v1/previews?repo=$CI_REPO&branch=$CI_BRANCH&commit=$CI_COMMIT&actor=$CI_USER" \
  -H "Authorization: Bearer $PLAYCHECK_TOKEN" \
  --data-binary @events.jsonl
```

The in-app docs page at **`/docs/`** (public, linked in the nav) carries both
snippets with copy buttons, plus API notes.

### Secrets never reach the server
Ansible censors `no_log` and `diff: false` content before the CLI's callback
ever sees it, so censored diffs arrive as flags, not content. The dashboard
labels them ("diff censored (no_log)" / "diff hidden by task setting").
Payloads are treated as sensitive anyway.

---

## 5 · Technical architecture

### Stack
Django 5 + Postgres (SQLite fallback for dev via `DATABASE_URL`), Django
templates + Tailwind (standalone CLI, compiled CSS checked in) + HTMX
(vendored), django-allauth for GitHub OAuth, whitenoise for static files,
Creem.io for billing. One service, one database, no queues.

### Apps and responsibilities
| App | Owns |
|---|---|
| `orgs` | `Org`, `Membership` (roles), `Invite`, `AuditEvent` + `record()`, permission helpers |
| `projects` | `Project` (org FK, hashed token), dashboard, project/settings/token views |
| `previews` | `Preview` (raw + parsed snapshot), ingest API, list/detail views, parsing pipeline |
| `billing` | `Subscription`, entitlements, Creem client, checkout/portal/webhook views |

### The parsing pipeline (the load-bearing decision)
The PyPI **`playcheck` package is the single source of truth for
classification** — this repo never reimplements what "NOT PREVIEWED" means.

```
raw JSONL body ──▶ playcheck.parse.parse_events ──▶ RunReport
                     (canonical classifier)            │
                                                       ▼
        previews/reportjson.py snapshot() — reshapes for rendering:
        summary counts · group_identical_hosts() · per-task dicts ·
        diff entries (filename header + gutter-typed lines)
                                                       │
                                                       ▼
        Preview row: raw_events (verbatim) + parsed (JSON, versioned v2)
                     + denormalized counts for the list page
```

Parsing happens **once at ingest**. The verbatim `raw_events` makes snapshots
rebuildable: `manage.py reparse_previews` re-parses everything after a format
change or a `playcheck` package upgrade (the version pin `playcheck>=0.1,<0.2`
guards the one private-API import, the diff-line builder).

### Tenant isolation (existential — see CLAUDE.md)
- Every org lookup goes through `orgs.permissions.get_membership_or_404`;
  every project/preview lookup chains from that membership. There is no
  unscoped query path in any view.
- Non-membership → 404, so names never leak.
- Upload tokens: `pck_` + 32 random urlsafe bytes; stored as SHA-256 hash +
  a 12-char display prefix (also the lookup index); constant-time comparison.
- Cross-tenant tests in `previews/tests.py` sweep every org URL as the wrong
  user; role-gate tests in `orgs/tests.py`; entitlement-bypass tests in
  `billing/tests.py`. 42 tests total — keep them green.

### Production hardening
- Refuses to boot with the dev `SECRET_KEY` when `DJANGO_DEBUG=0`.
- Secure/HSTS/SSL-redirect settings and proxy header when not in DEBUG;
  `DJANGO_CSRF_TRUSTED_ORIGINS` env.
- Whitenoise with compressed-manifest storage in production.
- Ingest rate limit: 30 uploads/project/minute (locmem cache — fine for one
  process; revisit if scaling out).
- 10 MB ingest body cap; styled 404/500 pages.

### Environment variables
| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | required in production |
| `DJANGO_DEBUG` | `0` in production (default `1`) |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` | comma-separated |
| `DATABASE_URL` | `postgres://…` (SQLite fallback if unset) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub OAuth app |
| `CREEM_API_KEY` | Creem secret key (billing disabled-but-visible if unset) |
| `CREEM_WEBHOOK_SECRET` | webhook HMAC secret (required in production) |
| `CREEM_PRODUCT_ID_TEAM` | the Team product created in Creem — **price is set there** |
| `CREEM_API_BASE` | `https://test-api.creem.io` for sandbox |
| `INGEST_UPLOADS_PER_MINUTE` | default 30 |

### Developer workflow
```powershell
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo          # demo users + real fixture data
.venv\Scripts\python manage.py runserver
.venv\Scripts\python manage.py test               # 42 tests, keep green
.venv\Scripts\python manage.py reparse_previews   # after snapshot/package changes
tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify
```
All fixtures are **real captured playcheck output** (from the public repo's
test suite) — never hand-invented JSON.

---

## 6 · What's deliberately not built yet

Per the build order in CLAUDE.md:
- **Slice 5 — GitHub App org connect** (connect a GitHub org once instead of
  per-repo tokens): gated on slices 1–4 running end-to-end in production,
  which still needs a deployment, a registered GitHub OAuth app, and Creem
  credentials.
- **Slice 6 — Approvals + Slack notifications**: gated on real paying-tier
  interest.
- Also open: applying the public-repo patch (and releasing a new `playcheck`
  version so `--save-events` ships on PyPI), preview retention/deletion
  controls, and org deletion/renaming.
