from django.urls import path

from . import views

urlpatterns = [
    path("o/<slug:org_slug>/billing/", views.billing_page, name="org-billing"),
    path("o/<slug:org_slug>/billing/checkout/", views.checkout, name="org-checkout"),
    path("o/<slug:org_slug>/billing/portal/", views.portal, name="org-portal"),
    path("billing/webhooks/creem", views.webhook, name="creem-webhook"),
]
