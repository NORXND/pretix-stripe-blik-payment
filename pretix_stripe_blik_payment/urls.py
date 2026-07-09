from django.urls import re_path
from .views import BlikPayView, BlikStashCodeView, BlikStatusView, BlikRetryView

event_patterns = [
    re_path(
        r"^blik/(?P<order>[^/]+)/(?P<payment>\d+)/(?P<hash>[^/]+)/pay/$",
        BlikPayView.as_view(),
        name="pay",
    ),
    re_path(
        r"^blik/(?P<order>[^/]+)/(?P<payment>\d+)/(?P<hash>[^/]+)/status/$",
        BlikStatusView.as_view(),
        name="status",
    ),
    re_path(
        r"^blik/(?P<order>[^/]+)/(?P<payment>\d+)/(?P<hash>[^/]+)/retry/$",
        BlikRetryView.as_view(),
        name="retry",
    ),
    re_path(
        r"^checkout/blik-code/$",
        BlikStashCodeView.as_view(),
        name="stash_code",
    ),
]
