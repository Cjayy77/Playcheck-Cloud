"""POST /api/v1/previews — the versioned ingest contract.

CI sends the playcheck JSONL event stream *verbatim* as the request body and
run metadata as query parameters:

    curl -X POST "$UPLOAD_URL/api/v1/previews?repo=org/app&branch=main&commit=abc123&pr=17&actor=cedric" \
         -H "Authorization: Bearer $PLAYCHECK_TOKEN" \
         --data-binary @events.jsonl

Never break old CLI versions: additions to this endpoint must be optional.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from projects.models import Project

from .services import NoEventsError, store_preview

MAX_BODY_BYTES = 10 * 1024 * 1024  # a JSONL preview stream should never be near this


def _bearer_token(request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return ""


@csrf_exempt
@require_POST
def ingest_preview(request):
    project = Project.authenticate_token(_bearer_token(request))
    if project is None:
        return JsonResponse({"error": "invalid or missing upload token"}, status=401)

    rate_key = f"ingest:{project.pk}"
    cache.add(rate_key, 0, timeout=60)
    if cache.incr(rate_key) > settings.INGEST_UPLOADS_PER_MINUTE:
        return JsonResponse({"error": "rate limit exceeded; retry in a minute"}, status=429)

    body = request.body
    if len(body) > MAX_BODY_BYTES:
        return JsonResponse({"error": "payload too large"}, status=413)
    text = body.decode("utf-8", errors="replace")
    if not text.strip():
        return JsonResponse({"error": "empty body; expected playcheck JSONL"}, status=400)

    pr_raw = request.GET.get("pr", "").strip()
    try:
        pr_number = int(pr_raw) if pr_raw else None
    except ValueError:
        pr_number = None

    try:
        preview = store_preview(
            project,
            text,
            repo=request.GET.get("repo", ""),
            branch=request.GET.get("branch", ""),
            commit=request.GET.get("commit", ""),
            pr_number=pr_number,
            actor=request.GET.get("actor", ""),
        )
    except NoEventsError:
        return JsonResponse(
            {"error": "no playcheck events found; upload the JSONL stream verbatim"},
            status=422,
        )
    return JsonResponse(
        {
            "id": preview.id,
            "url": f"/o/{project.org.slug}/p/{project.slug}/previews/{preview.id}/",
            "summary": preview.parsed["summary"],
        },
        status=201,
    )
