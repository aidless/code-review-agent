"""Offline-suite guards.

Tests may patch requests or the OpenAI client. If a patch is missing, this
fixture fails the call instead of letting it reach GitHub or a model API.
"""
import pytest


_BLOCKED_HOSTS = ("api.github.com", "api.deepseek.com", "api.openai.com")


def _blocked(url) -> bool:
    text = str(url)
    return any(host in text for host in _BLOCKED_HOSTS)


@pytest.fixture(autouse=True)
def block_outbound_review_hosts(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")

    import requests

    real_request = requests.sessions.Session.request

    def guarded(self, method, url, *args, **kwargs):
        if _blocked(url):
            raise RuntimeError(f"blocked outbound {method} {url}")
        return real_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", guarded)

    import httpx

    real_send = httpx.Client.send

    def guarded_send(self, request, *args, **kwargs):
        if _blocked(request.url):
            raise RuntimeError(f"blocked outbound {request.method} {request.url}")
        return real_send(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, "send", guarded_send)

    real_asend = httpx.AsyncClient.send

    async def guarded_asend(self, request, *args, **kwargs):
        if _blocked(request.url):
            raise RuntimeError(f"blocked outbound {request.method} {request.url}")
        return await real_asend(self, request, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "send", guarded_asend)
