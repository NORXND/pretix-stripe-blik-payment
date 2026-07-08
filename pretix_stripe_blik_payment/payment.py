from collections import OrderedDict
from decimal import Decimal

from django import forms
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Order, OrderPayment
from pretix.plugins.stripe.payment import (
    StripeRedirectMethod,
)


class StripeBlik(StripeRedirectMethod):
    identifier = "stripe_blik"
    verbose_name = _("BLIK via Stripe") # pyright: ignore[reportAssignmentType, reportIncompatibleMethodOverride]
    public_name = _("BLIK") # pyright: ignore[reportAssignmentType, reportIncompatibleMethodOverride]
    method = "blik"
    confirmation_method = "automatic"
    redirect_in_widget_allowed = False
    explanation = _(
        "BLIK is a mobile payment method popular in Poland. Please open your banking app, generate a 6-digit "
        "BLIK code and enter it below before it expires."
    )

    @property
    def is_enabled(self) -> bool:
        return self.settings.get("_enabled", as_type=bool) and self.settings.get(
            "method_blik", as_type=bool
        )

    def is_allowed(self, request: HttpRequest, total: Decimal) -> bool: # pyright: ignore[reportIncompatibleMethodOverride]
        return super().is_allowed(request, total) and self.event.currency == "PLN"

    def payment_form_render(self, request) -> str:
        template = get_template(
            "pretixplugins/stripe/checkout_payment_form_simple.html"
        )
        return template.render(
            {
                "request": request,
                "event": self.event,
                "settings": self.settings,
                "explanation": self.explanation,
                "form": self.payment_form(request),
            }
        )

    @property
    def payment_form_fields(self):
        return OrderedDict(
            [
                (
                    "code",
                    forms.RegexField(
                        label=_("BLIK code"),
                        regex=r"^\d{6}$",
                        widget=forms.TextInput(
                            attrs={"inputmode": "numeric", "maxlength": "6"}
                        ),
                    ),
                ),
            ]
        )

    def checkout_prepare(self, request, cart): # pyright: ignore[reportIncompatibleMethodOverride]
        form = self.payment_form(request)
        if form.is_valid():
            request.session[f"payment_stripe_{self.method}_payment_method_id"] = None
            request.session[f"payment_stripe_{self.method}_code"] = form.cleaned_data[
                "code"
            ]
            return True
        return False

    def execute_payment(self, request: HttpRequest, payment: OrderPayment):
        try:
            return super().execute_payment(request, payment)
        finally:
            request.session.pop(f"payment_stripe_{self.method}_code", None)

    def _payment_intent_kwargs(self, request, payment):
        return {
            "payment_method_data": {
                "type": "blik",
                "billing_details": {"email": payment.order.email},
            },
            "payment_method_options": {
                "blik": {
                    "code": request.session.get(
                        f"payment_stripe_{self.method}_code", ""
                    )
                },
            },
        }
    
    @property
    def settings_form_fields(self):
        return {}
