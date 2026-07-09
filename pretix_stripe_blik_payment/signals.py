from datetime import timedelta
from django.core.cache import cache
from django.dispatch import receiver
from django.utils.timezone import now
from pretix.base.models import OrderPayment
from pretix.base.signals import periodic_task, register_payment_providers


@receiver(register_payment_providers, dispatch_uid="stripe_blik")
def register_payment_provider(sender, **kwargs):
    from .payment import StripeBlik

    return [StripeBlik]

@receiver(periodic_task, dispatch_uid="stripe_blik_daily_refresh")
def refresh_pending_blik_payments(sender, **kwargs):
    lock_acquired = cache.add("stripe_blik_daily_refresh_lock", "1", timeout=23 * 3600)
    if not lock_acquired:
        return

    stale_payments = (
        OrderPayment.objects.filter(
            provider="stripe_blik",
            state__in=[
                OrderPayment.PAYMENT_STATE_CREATED,
                OrderPayment.PAYMENT_STATE_PENDING,
            ],
            created__lt=now() - timedelta(hours=1),
            created__gt=now() - timedelta(days=14),
        )
        .select_related("order")
        .iterator()
    )

    for payment in stale_payments:
        try:
            payment.payment_provider.refresh_payment_state(payment)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Failed to refresh BLIK payment %s in daily periodic task",
                payment.full_id,
            )