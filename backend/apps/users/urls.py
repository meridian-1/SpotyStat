from django.urls import path
from . import views

app_name = "users"

urlpatterns = [
    # Spotify OAuth
    path(
        "auth/spotify/login/",
        views.SpotifyLoginView.as_view(),
        name="spotify-login",
    ),
    path(
        "auth/spotify/callback/",
        views.SpotifyCallbackView.as_view(),
        name="spotify-callback",
    ),
    # Current session user
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
]
