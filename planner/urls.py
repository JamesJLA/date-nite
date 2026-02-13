from django.urls import path

from .views import HomeView, ResultsView, VoteView

app_name = "planner"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("vote/<uuid:token>/", VoteView.as_view(), name="vote"),
    path("results/<uuid:token>/", ResultsView.as_view(), name="results"),
]
