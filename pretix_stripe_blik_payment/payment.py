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
    reverse,
)


class StripeBlik(StripeRedirectMethod):
    identifier = "stripe_blik"
    verbose_name = _("BLIK via Stripe")
    public_name = _("BLIK")
    method = "blik"
    confirmation_method = "automatic"
    redirect_in_widget_allowed = False
    explanation = _(
        "You will be able to pay after placing an order."
    )

    @property
    def is_enabled(self) -> bool:
        return self.settings.get("_enabled", as_type=bool) and self.settings.get(
            "method_blik", as_type=bool
        )

    def is_allowed(self, request, total=None):
        return super().is_allowed(request, total) and self.event.currency == "PLN"

    def payment_form_render(self, request, total, order=None) -> str:
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

    def execute_payment(self, request, payment: OrderPayment):
        payment.state = OrderPayment.PAYMENT_STATE_CREATED
        payment.save()
        return None


    def _payment_intent_kwargs(self, request, payment):
        kwargs = super()._payment_intent_kwargs(request, payment)

        kwargs["payment_method_options"] = {
            "blik": {
                "code": request.POST["code"],
            }
        }

        return kwargs

    def payment_pending_render(self, request, payment: OrderPayment) -> str:
        template = get_template(
            "pretix_stripe_blik_payment/pending_blik_code_form.html"
        )
        return template.render(
            {
                "request": request,
                "event": self.event,
                "payment": payment,
                "action_url": reverse(
                    "plugins:pretix_stripe_blik_payment:pay",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                        "order": payment.order.code,
                        "payment": payment.pk,
                        "hash": payment.order.tagged_secret("plugins:stripe_blik"),
                    },
                ),
            },
            request=request,
        )
