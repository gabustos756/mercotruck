import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.security import create_access_token
from app.core.auth import COOKIE_AUTH_NAME

@pytest.mark.anyio
async def test_render_dashboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Unauthenticated -> 303 Redirect to login
        res_anon = await ac.get("/", follow_redirects=False)
        assert res_anon.status_code in (302, 303, 307)
        assert "/login" in res_anon.headers.get("location", "")

        # 2. Authenticated with access token -> 200 OK
        token = create_access_token({"sub": "1", "email": "admin@mercotruck.com", "role": "ADMIN"})
        ac.cookies.set(COOKIE_AUTH_NAME, token)
        response = await ac.get("/")
        assert response.status_code == 200
        assert "Mercotruck" in response.text
