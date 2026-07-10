# Playcheck Cloud  

Hosted dashboard for [Playcheck](https://github.com/Cjayy77/Playcheck) previews.
Private and commercial; the CLI stays MIT. See CLAUDE.md for ground rules and
[GUIDE.md](GUIDE.md) for the full product + technical guide (plans, roles,
orgs, billing, integrations, architecture). 
 
## Run locally 

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo    # demo/demo12345 + real fixture data
.venv\Scripts\python manage.py runserver
```

Sign in at http://127.0.0.1:8000/ — in local dev use the Django admin login
(`/admin/login/?next=/`) with a seeded user; production uses GitHub OAuth
(set `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`).

Seeded users: `demo/demo12345` (admin of the `acme` org) and
`teammate/teammate12345` (member). Orgs own projects; URLs are
`/o/<org>/p/<project>/…`. Members can view previews; admins additionally
manage projects, tokens, invites, roles, and see the audit log at
`/o/<org>/audit/`. Invites are copy-paste links (no SMTP), created from
`/o/<org>/members/`.

Database: set `DATABASE_URL=postgres://...` for Postgres (production);
without it, dev falls back to SQLite.

## Upload a preview from CI

```sh
playcheck --output jsonl playbook.yml > events.jsonl
curl -X POST "https://HOST/api/v1/previews?repo=org/app&branch=main&commit=$SHA&pr=17&actor=$USER" \
  -H "Authorization: Bearer $PLAYCHECK_TOKEN" \
  --data-binary @events.jsonl
```

The body is the playcheck JSONL event stream verbatim; parsing/classification
happens server-side with the canonical `playcheck` PyPI package.

## Rebuild CSS after template changes

```powershell
tailwindcss -c tailwind.config.js -i tailwind.input.css -o static/css/tailwind.css --minify
```

## Tests

```powershell
.venv\Scripts\python manage.py test
```

Tenant-isolation tests live in `previews/tests.py`, role/invite/audit tests
in `orgs/tests.py` — keep them green.

After changing the snapshot format or upgrading the `playcheck` package,
rebuild stored previews from their verbatim raw events:

```powershell
.venv\Scripts\python manage.py reparse_previews
```
