import re
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from pretix.base.models import Order, OrderPayment
from pretix.presale.views import EventViewMixin


class BlikStashCodeView(EventViewMixin, View):
    def post(self, request, *args, **kwargs):
        code = (request.POST.get("code") or "").strip()
        if not re.fullmatch(r"\d{6}", code):
            print(f"Invalid BLIK code provided: {code}")
            return JsonResponse(
                {"error": str(_("Podaj poprawny 6-cyfrowy kod BLIK."))}, status=400
            )
        request.session["stripe_blik_pending_code"] = code
        return JsonResponse({"ok": True})


class BlikBaseView(EventViewMixin, View):
    def dispatch(self, request, *args, **kwargs):
        self.order = get_object_or_404(Order, code=kwargs["order"], event=request.event)
        if kwargs["hash"] != self.order.tagged_secret("plugins:stripe_blik"):
            return JsonResponse({"error": "invalid_hash"}, status=403)
        self.payment = get_object_or_404(
            OrderPayment, pk=kwargs["payment"], order=self.order
        )
        return super().dispatch(request, *args, **kwargs)


class BlikPayView(BlikBaseView):
    def post(self, request, *args, **kwargs):
        provider = self.payment.payment_provider
        return provider._handle_payment_intent(request, self.payment)


class BlikStatusView(BlikBaseView):
    def get(self, request, *args, **kwargs):
        provider = self.payment.payment_provider
        status = provider.refresh_payment_state(self.payment)

        return JsonResponse(
            {
                "status": status,  # processing | succeeded | failed
            }
        )


class BlikRetryView(BlikBaseView):
    def post(self, request, *args, **kwargs):
        code = (request.POST.get("code") or "").strip()
        print(f"Retrying BLIK payment for order {self.order.code}, payment {self.payment.pk} with code {code}")
        if not re.fullmatch(r"\d{6}", code):
            print(f"Invalid BLIK code provided for retry: {code}")
            return JsonResponse(
                {"error": _("Podaj poprawny 6-cyfrowy kod BLIK.")}, status=400
            )

        provider = self.payment.payment_provider
        try:
            status = provider.retry_with_new_code(self.payment, code)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

        return JsonResponse(
            {"status": "processing" if status != "succeeded" else "succeeded"}
        )
