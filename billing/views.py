import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orgs.models import Org, record
from orgs.permissions import get_membership_or_404

from . import creem, entitlements
from .models import Subscription


@login_required
def billing_page(request, org_slug):
    membership = get_membership_or_404(request, org_slug, admin=True)
    org = membership.org
    return render(
        request,
        "billing/billing.html",
        {
            "org": org,
            "usage": entitlements.usage(org),
            "subscription": getattr(org, "subscription", None),
            "creem_configured": bool(settings.CREEM_API_KEY),
        },
    )


@login_required
@require_POST
def checkout(request, org_slug):
    membership = get_membership_or_404(request, org_slug, admin=True)
    org = membership.org
    if entitlements.is_team(org):
        return redirect("org-billing", org_slug=org_slug)
    success_url = request.build_absolute_uri(f"/o/{org.slug}/billing/")
    try:
        url = creem.create_checkout(org, success_url)
    except creem.CreemNotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("org-billing", org_slug=org_slug)
    return redirect(url)


@login_required
@require_POST
def portal(request, org_slug):
    membership = get_membership_or_404(request, org_slug, admin=True)
    subscription = getattr(membership.org, "subscription", None)
    if not subscription or not subscription.creem_customer_id:
        messages.error(request, "No billing account yet — upgrade first.")
        return redirect("org-billing", org_slug=org_slug)
    try:
        url = creem.create_portal_link(subscription.creem_customer_id)
    except creem.CreemNotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("org-billing", org_slug=org_slug)
    return redirect(url)


def _customer_id(obj: dict) -> str:
    customer = obj.get("customer")
    if isinstance(customer, dict):
        return str(customer.get("id", ""))
    return str(customer or "")


def _org_from_metadata(metadata: dict):
    try:
        return Org.objects.filter(pk=int(metadata.get("org_id"))).first()
    except (TypeError, ValueError):
        return None


def apply_event(event: dict) -> bool:
    """Apply one Creem webhook event to our Subscription state. Returns
    whether the event was recognized. Kept separate from the view so tests
    exercise the exact production code path."""
    event_type = event.get("eventType", "")
    obj = event.get("object") or {}

    if event_type == "checkout.completed":
        org = _org_from_metadata(obj.get("metadata") or {})
        if org is None:
            return False
        sub_obj = obj.get("subscription") or {}
        subscription, _ = Subscription.objects.get_or_create(org=org)
        subscription.creem_customer_id = _customer_id(obj) or subscription.creem_customer_id
        if isinstance(sub_obj, dict) and sub_obj.get("id"):
            subscription.creem_subscription_id = str(sub_obj["id"])
            subscription.status = str(sub_obj.get("status") or "active")
        else:
            subscription.status = "active"
        subscription.save()
        record(org, "creem", "billing.upgraded", detail={"event": event_type})
        return True

    if event_type.startswith("subscription."):
        sub_id = str(obj.get("id", ""))
        subscription = Subscription.objects.filter(
            creem_subscription_id=sub_id
        ).select_related("org").first()
        if subscription is None:
            org = _org_from_metadata(obj.get("metadata") or {})
            if org is None:
                return False
            subscription, _ = Subscription.objects.get_or_create(org=org)
            subscription.creem_subscription_id = sub_id
        was_team = subscription.is_team
        subscription.status = str(obj.get("status") or subscription.status)
        subscription.creem_customer_id = _customer_id(obj) or subscription.creem_customer_id
        period_end = obj.get("current_period_end_date")
        if period_end:
            from django.utils.dateparse import parse_datetime

            subscription.current_period_end = parse_datetime(str(period_end))
        subscription.save()
        if was_team != subscription.is_team:
            record(
                subscription.org, "creem",
                "billing.upgraded" if subscription.is_team else "billing.downgraded",
                detail={"event": event_type, "status": subscription.status},
            )
        return True

    return False


@csrf_exempt
@require_POST
def webhook(request):
    if not creem.signature_valid(
        request.body, request.headers.get("creem-signature", "")
    ):
        return HttpResponse(status=400)
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    apply_event(event)  # unrecognized events are acknowledged and ignored
    return JsonResponse({"received": True})
