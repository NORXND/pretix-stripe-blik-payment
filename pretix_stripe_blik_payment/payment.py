from collections import OrderedDict
from decimal import Decimal
import re

from django import forms
from django.http import HttpRequest
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _

from pretix.base.models import Order, OrderPayment
from pretix.plugins.stripe.payment import (
    PaymentException,
    StripeRedirectMethod,
)


class StripeBlik(StripeRedirectMethod):
    identifier = "stripe_blik"
    verbose_name = _("BLIK via Stripe")
    public_name = _("BLIK")
    method = "blik"
    confirmation_method = "automatic"
    redirect_in_widget_allowed = False
    explanation = _(
        "You will be asked to enter a 6-digit code from your banking app on the confirmation page, right before placing your order."
    )

    @property
    def is_enabled(self) -> bool:
        return self.settings.get("_enabled", as_type=bool) and self.settings.get(
            "method_blik", as_type=bool
        )

    def is_allowed(self, request, total=None):
        return super().is_allowed(request, total) and self.event.currency == "PLN"

    # Na etapie payment_step nic już nie zbieramy – tylko informacja, że kod poda się na końcu
    def payment_form_render(self, request) -> str:
        template = get_template(
            "pretixplugins/stripe/checkout_payment_form_simple_noform.html"
        )
        return template.render(
            {
                "request": request,
                "event": self.event,
                "settings": self.settings,
                "explanation": self.explanation,
            }
        )

    def checkout_prepare(self, request, cart):
        request.session[f"payment_stripe_{self.method}_payment_method_id"] = None
        return True

    def payment_is_valid_session(self, request):
        return f"payment_stripe_{self.method}_payment_method_id" in request.session

    # To renderuje się na stronie CONFIRM, w tym samym <form> co przycisk "Złóż zamówienie"
    def checkout_confirm_render(self, request, **kwargs) -> str:
        template = get_template(
            "pretix_stripe_blik_payment/confirm_blik_code_field.html"
        )
        return template.render({"request": request})

    def _payment_intent_kwargs(self, request, payment):
        code = request.POST.get("stripe_blik_code", "")
        if not re.match(r"^\d{6}$", code):
            raise PaymentException(_("Please enter a valid 6-digit BLIK code."))
        return {
            "payment_method_data": {
                "type": "blik",
                "billing_details": {"email": payment.order.email},
            },
            "payment_method_options": {
                "blik": {"code": code},
            },
        }
