import stripe
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views import View
from django.contrib import messages

from pretix.base.models import Order, OrderPayment
from pretix.presale.views import EventViewMixin


class BlikPayView(EventViewMixin, View):
    def post(self, request, *args, **kwargs):
        order = get_object_or_404(Order, code=kwargs["order"], event=request.event)
        payment = get_object_or_404(OrderPayment, pk=kwargs["payment"], order=order)

        if payment.order.tagged_secret("plugins:stripe_blik") != kwargs["hash"]:
            messages.error(request, _("Invalid link."))
            return HttpResponseRedirect(order.get_absolute_url())

        code = request.POST.get("code", "")
        provider = payment.payment_provider

        provider._init_api()

        request.session[f"_blik_code_{payment.pk}"] = (
            code
        )
        provider._handle_payment_intent(request, payment)

        return HttpResponseRedirect(order.get_absolute_url())
