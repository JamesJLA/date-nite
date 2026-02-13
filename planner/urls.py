from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

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
    path("", HomeView.as_view(), name="home"),
    path("vote/<uuid:token>/", VoteView.as_view(), name="vote"),
    path("results/<uuid:token>/", ResultsView.as_view(), name="results"),
]
