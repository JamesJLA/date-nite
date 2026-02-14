from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordChangeDoneView,
    PasswordChangeView,
)
from django.urls import path
from django.urls import reverse_lazy

from .views import HomeView, ResultsView, SignUpView, VoteView

app_name = "planner"

urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path(
        "login/",
        LoginView.as_view(
            template_name="planner/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path(
        "settings/password/",
        PasswordChangeView.as_view(
            template_name="planner/password_change.html",
            success_url=reverse_lazy("planner:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "settings/password/done/",
        PasswordChangeDoneView.as_view(
            template_name="planner/password_change_done.html"
        ),
        name="password_change_done",
    ),
    path("", HomeView.as_view(), name="home"),
    path("vote/<uuid:token>/", VoteView.as_view(), name="vote"),
    path("results/<uuid:token>/", ResultsView.as_view(), name="results"),
]
