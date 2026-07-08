from django.apps import AppConfig


class PluginApp(AppConfig):
    name = "pretix_stripe_blik_payment"
    verbose_name = "Stripe BLIK"

    class PretixPluginMeta:
        name = "Stripe BLIK"
        author = "Norbert Dudziak"
        version = "0.1.0"
        category = "PAYMENT"
        description = "Adds a BLIK payment method backed by the built-in Stripe plugin"
        visible = True

    def ready(self):
        from . import signals  # noqa

        self._patch_stripe_settings_form()

    def _patch_stripe_settings_form(self):
        from pretix.plugins.stripe.payment import StripeSettingsHolder

        # guard against double-patching (ready() can run more than once, e.g. in tests)
        if getattr(StripeSettingsHolder, "_blik_patched", False):
            return

        original_fget = StripeSettingsHolder.settings_form_fields.fget

        def patched_settings_form_fields(self):
            from django import forms
            from django.utils.translation import gettext_lazy as _

            d = original_fget(self) # pyright: ignore[reportOptionalCall]
            if not d:
                return d  # e.g. Stripe Connect not configured yet, no fields to extend

            d["method_blik"] = forms.BooleanField(
                label=_("BLIK"),
                disabled=self.event.currency != "PLN",
                help_text=_(
                    "Some payment methods might need to be enabled in the settings of your Stripe account "
                    "before they work properly."
                ),
                required=False,
            )
            return d

        StripeSettingsHolder.settings_form_fields = property( # pyright: ignore[reportAttributeAccessIssue]
            patched_settings_form_fields
        )
        StripeSettingsHolder._blik_patched = True # pyright: ignore[reportAttributeAccessIssue]


default_app_config = "pretix_stripe_blik_payment.apps.PluginApp"
