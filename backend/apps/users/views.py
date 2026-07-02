from __future__ import annotations

import base64
import json
import os
import secrets
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import login as django_login, logout as django_logout
from django.core.files.base import ContentFile
from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"


class SpotifyAuthError(Exception):
    """An error occurring during Spotify OAuth or profile fetch."""


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _spotify_basic_auth_header() -> str:
    raw = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}".encode(
        "utf-8"
    )
    token = base64.b64encode(raw).decode("utf-8")
    return f"Basic {token}"


def _build_spotify_login_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": settings.SPOTIFY_SCOPE,
        "state": state,
    }
    return f"{SPOTIFY_AUTH_URL}?{urlencode(params)}"


def _exchange_code_for_tokens(code: str) -> dict:
    request = Request(
        SPOTIFY_TOKEN_URL,
        data=urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
            }
        ).encode("utf-8"),
        method="POST",
    )
    request.add_header("Authorization", _spotify_basic_auth_header())
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise SpotifyAuthError(
            detail or f"Token exchange failed with HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise SpotifyAuthError(f"Token exchange failed: {exc.reason}") from exc


def _fetch_spotify_profile(access_token: str) -> dict:
    request = Request(
        SPOTIFY_ME_URL, headers={"Authorization": f"Bearer {access_token}"}
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise SpotifyAuthError(
            detail or f"Fetching Spotify profile failed with HTTP {exc.code}"
        ) from exc
    except URLError as exc:
        raise SpotifyAuthError(
            f"Fetching Spotify profile failed: {exc.reason}"
        ) from exc


def _save_spotify_avatar(user: User, avatar_url: str | None) -> None:
    if not avatar_url:
        return
    try:
        with urlopen(avatar_url, timeout=15) as response:
            content = response.read()
    except Exception:
        return

    extension = os.path.splitext(urlparse(avatar_url).path)[1] or ".jpg"
    filename = f"spotify-{user.spotify_id}{extension}"
    user.avatar.save(filename, ContentFile(content), save=False)


def _sync_user_from_spotify(profile: dict, tokens: dict) -> User:
    spotify_id = profile["id"]
    display_name = profile.get("display_name") or spotify_id
    email = profile.get("email") or ""
    images = profile.get("images") or []
    avatar_url = images[0].get("url") if images else None

    user, _created = User.objects.get_or_create(
        spotify_id=spotify_id,
        defaults={"display_name": display_name, "email": email},
    )

    user.display_name = display_name
    if email:
        user.email = email

    access_token = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token") or user.refresh_token or ""
    expires_in = int(tokens.get("expires_in", 0) or 0)

    user.access_token = access_token
    user.refresh_token = refresh_token
    user.token_expires_at = (
        timezone.now() + timedelta(seconds=expires_in) if expires_in else None
    )

    if avatar_url:
        _save_spotify_avatar(user, avatar_url)

    user.save()
    return user


def _serialize_user(user: User, request: DRFRequest) -> dict:
    avatar_url = None
    if user.avatar:
        try:
            avatar_url = request.build_absolute_uri(user.avatar.url)
        except Exception:
            avatar_url = None

    return {
        "id": user.spotify_id,
        "spotify_id": user.spotify_id,
        "display_name": user.display_name or user.spotify_id,
        "email": user.email,
        "avatar_url": avatar_url,
    }


class SpotifyLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request: DRFRequest) -> Response:
        get_token(request._request)
        state = secrets.token_urlsafe(32)
        request.session["spotify_oauth_state"] = state
        return Response({"authorizationUrl": _build_spotify_login_url(state)})


class SpotifyCallbackView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request: DRFRequest) -> Response:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        saved_state = request.session.pop("spotify_oauth_state", None)

        if not code:
            return Response(
                {"detail": "Missing authorization code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not state or not saved_state or state != saved_state:
            return Response(
                {"detail": "Invalid OAuth state"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tokens = _exchange_code_for_tokens(code)
            profile = _fetch_spotify_profile(tokens["access_token"])
            user = _sync_user_from_spotify(profile, tokens)
        except (SpotifyAuthError, KeyError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        django_login(request._request, user)
        return redirect(_frontend_url())


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def get(self, request: DRFRequest) -> Response:
        get_token(request._request)
        return Response(_serialize_user(request.user, request))


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [SessionAuthentication]

    def post(self, request: DRFRequest) -> Response:
        django_logout(request._request)
        return Response({"detail": "Logged out"})
