import re
import stripe
from django.template.loader import get_template
from django.utils.translation import gettext_lazy as _
from pretix.plugins.stripe.payment import (
    OrderPayment,
    PaymentException,
    Quota,
    ReferencedStripeObject,
    StripeRedirectMethod,
    eventreverse_absolute,
    logger,
    messages,
    reverse,
)


class StripeBlik(StripeRedirectMethod):
    identifier = "stripe_blik"
    verbose_name = _("BLIK via Stripe")
    public_name = _("BLIK")
    method = "blik"
    confirmation_method = "automatic"
    redirect_in_widget_allowed = False
    explanation = _("Kod BLIK podasz w ostatnim kroku, tuż przed złożeniem zamówienia.")

    code_field_name = "stripe_blik_code"

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
        return True

    def payment_is_valid_session(self, request):
        return True

    def _handle_payment_intent(self, request, payment, intent=None):
        self._init_api()

        existing_id = (payment.info_data or {}).get("id")

        try:
            if not existing_id:
                payment_method_id = request.session.get(
                    'payment_stripe_{}_payment_method_id'.format(self.method), None
                )
                idempotency_key_seed = payment_method_id if payment_method_id is not None else payment.full_id

                params = {}
                params.update(self._connect_kwargs(payment))
                params.update(self.api_kwargs)
                params.update(self._payment_intent_kwargs(request, payment))

                if self.method == "card":
                    params['statement_descriptor_suffix'] = self.statement_descriptor(payment)
                else:
                    params['statement_descriptor'] = self.statement_descriptor(payment)

                intent = stripe.PaymentIntent.create(
                    amount=self._get_amount(payment),
                    currency=self.event.currency.lower(),
                    payment_method=payment_method_id,
                    payment_method_types=[self.method],
                    confirmation_method=self.confirmation_method,
                    confirm=True,
                    description='{event}-{code}'.format(
                        event=self.event.slug.upper(),
                        code=payment.order.code
                    ),
                    metadata={
                        'order': str(payment.order.id),
                        'event': self.event.id,
                        'code': payment.order.code
                    },
                    idempotency_key=str(self.event.id) + payment.order.code + idempotency_key_seed,
                    return_url=eventreverse_absolute(self.event, 'plugins:stripe:sca.return', kwargs={
                        'order': payment.order.code,
                        'payment': payment.pk,
                        'hash': payment.order.tagged_secret('plugins:stripe'),
                    }),
                    expand=['latest_charge'],
                    **params
                )
            else:
                if not intent:
                    intent = stripe.PaymentIntent.retrieve(
                        existing_id,
                        expand=["latest_charge"],
                        **self.api_kwargs
                    )

        except stripe.error.CardError as e:
            if e.json_body:
                err = e.json_body['error']
                logger.exception('Stripe error: %s' % str(err))
            else:
                err = {'message': str(e)}
                logger.exception('Stripe error: %s' % str(e))
            payment.fail(info={'error': True, 'message': err['message']})
            raise PaymentException(_('Stripe reported an error with your card: %s') % err['message'])

        except stripe.error.StripeError as e:
            if e.json_body and 'error' in e.json_body:
                err = e.json_body['error']
                logger.exception('Stripe error: %s' % str(err))
                if err.get('code') == 'idempotency_key_in_use':
                    return
            else:
                err = {'message': str(e)}
                logger.exception('Stripe error: %s' % str(e))
            payment.fail(info={'error': True, 'message': err['message']})
            raise PaymentException(_('We had trouble communicating with Stripe. Please try again and get in touch '
                                    'with us if this problem persists.'))
        else:
            ReferencedStripeObject.objects.get_or_create(
                reference=intent.id,
                defaults={'order': payment.order, 'payment': payment}
            )

            if intent.status == 'requires_action':
                payment.info = str(intent)
                payment.state = OrderPayment.PAYMENT_STATE_CREATED
                payment.save()
                return self._redirect_to_sca(request, payment)

            if intent.status == 'requires_confirmation':
                payment.info = str(intent)
                payment.state = OrderPayment.PAYMENT_STATE_CREATED
                payment.save()
                self._confirm_payment_intent(request, payment)

            elif intent.status == 'succeeded' and intent.latest_charge.paid: # pyright: ignore[reportOptionalMemberAccess]
                try:
                    payment.info = str(intent)
                    payment.confirm()
                except Quota.QuotaExceededException as e:
                    raise PaymentException(str(e))
            elif intent.status == 'processing':
                if request:
                    messages.warning(request, _('Your payment is pending completion. We will inform you as soon as the '
                                                'payment completed.'))
                payment.info = str(intent)
                payment.state = OrderPayment.PAYMENT_STATE_PENDING
                payment.save()
                return
            elif intent.status == 'requires_payment_method':
                if request:
                    messages.warning(request, _('Your payment failed. Please try again.'))
                payment.fail(info=str(intent))
                return
            else:
                logger.info('Charge failed: %s' % str(intent))
                payment.fail(info=str(intent))
                raise PaymentException(_('Stripe reported an error: %s') % intent.last_payment_error.message) # pyright: ignore[reportOptionalMemberAccess]

    def execute_payment(self, request, payment: OrderPayment):
        if (payment.info_data or {}).get("id"):
            return None
        return super().execute_payment(request, payment)

    def checkout_confirm_render(self, request, order=None, info_data=None) -> str:
        template = get_template("pretix_stripe_blik_payment/checkout_confirm_blik_code.html")
        return template.render({
            "request": request,
            "event": self.event,
            "stash_url": reverse(
                "plugins:pretix_stripe_blik_payment:stash_code",
                kwargs={"organizer": self.event.organizer.slug, "event": self.event.slug},
            ),
        })

    def _payment_intent_kwargs(self, request, payment):
        kwargs = super()._payment_intent_kwargs(request, payment)

        if payment.info_data.get("id"):
            print(f"PaymentIntent already exists for payment {payment.pk}, skipping code requirement.")
            return kwargs

        code = (request.session.pop("stripe_blik_pending_code", None) or "").strip()
        if not code:
            print("Checking for BLIK code in POST data as fallback.")
            code = (request.POST.get(self.code_field_name) or "").strip()

        if not re.fullmatch(r"\d{6}", code):
            print(f"Invalid BLIK code provided: {code}")
            raise PaymentException(_("Podaj poprawny 6-cyfrowy kod BLIK."))

        kwargs["payment_method_options"] = {"blik": {"code": code}}
        return kwargs

    def payment_pending_render(self, request, payment: OrderPayment) -> str:
        template = get_template("pretix_stripe_blik_payment/pending_blik_wait.html")
        return template.render(
            {
                "request": request,
                "event": self.event,
                "payment": payment,
                "status_url": reverse(
                    "plugins:pretix_stripe_blik_payment:status",
                    kwargs={
                        "organizer": self.event.organizer.slug,
                        "event": self.event.slug,
                        "order": payment.order.code,
                        "payment": payment.pk,
                        "hash": payment.order.tagged_secret("plugins:stripe_blik"),
                    },
                ),
                "retry_url": reverse(
                    "plugins:pretix_stripe_blik_payment:retry",
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

    def _stripe_intent_id(self, payment: OrderPayment) -> str:
        return (payment.info_data or {}).get("id", "")

    def refresh_payment_state(self, payment: OrderPayment) -> str:
        intent_id = self._stripe_intent_id(payment)
        if not intent_id:
            return "failed"

        intent = stripe.PaymentIntent.retrieve(
            intent_id,
            api_key=self.settings.get("secret_key"),
            expand=["latest_charge"],
        )

        payment.info = str(intent)
        payment.save(update_fields=["info"])

        if intent.status == "succeeded":
            if payment.state != OrderPayment.PAYMENT_STATE_CONFIRMED:
                payment.confirm()
            return "succeeded"

        if intent.status in ("requires_payment_method", "canceled"):
            if payment.state not in (
                OrderPayment.PAYMENT_STATE_FAILED,
                OrderPayment.PAYMENT_STATE_CANCELED,
            ):
                payment.state = OrderPayment.PAYMENT_STATE_FAILED
                payment.save(update_fields=["state"])
            return "failed"

        return "processing"


    def retry_with_new_code(self, payment: OrderPayment, code: str):
        intent_id = self._stripe_intent_id(payment)
        if not intent_id:
            raise PaymentException(_("Nie znaleziono płatności do ponowienia."))

        api_key = self.settings.get("secret_key")
        intent = stripe.PaymentIntent.retrieve(intent_id, api_key=api_key)

        if intent.status not in ("requires_payment_method", "canceled"):
            return intent.status

        if intent.status == "canceled":
            raise PaymentException(
                _("Czas na płatność minął, spróbuj złożyć zamówienie ponownie.")
            )

        payment.state = OrderPayment.PAYMENT_STATE_CREATED
        payment.save(update_fields=["state"])

        intent = stripe.PaymentIntent.confirm(
            intent_id,
            api_key=api_key,
            payment_method_data={"type": "blik"},
            payment_method_options={"blik": {"code": code}},
            expand=["latest_charge"],
        )

        payment.info = str(intent)
        payment.save(update_fields=["info"])

        return intent.status
