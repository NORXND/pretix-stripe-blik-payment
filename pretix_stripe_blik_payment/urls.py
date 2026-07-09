from django.urls import path
from . import views

event_patterns = [
    path(
        "stripeblik/<str:order>/<str:payment>/<str:hash>/pay/",
        views.BlikPayView.as_view(),
        name="pay",
    ),
]
