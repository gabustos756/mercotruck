import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.security import create_access_token
from app.core.auth import COOKIE_AUTH_NAME

@pytest.mark.anyio
async def test_render_dashboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Public Landing -> 200 OK
        res_landing = await ac.get("/", follow_redirects=False)
        assert res_landing.status_code == 200
        assert "crossTruck" in res_landing.text

        # 2. Unauthenticated dashboard -> 303 Redirect to login
        res_anon = await ac.get("/dashboard", follow_redirects=False)
        assert res_anon.status_code in (302, 303, 307)
        assert "/login" in res_anon.headers.get("location", "")

        # 3. Authenticated with access token -> 200 OK
        token = create_access_token({"sub": "1", "email": "superadmin@mercotruck.com", "role": "SUPERADMIN"})
        ac.cookies.set(COOKIE_AUTH_NAME, token)
        response = await ac.get("/dashboard")
        assert response.status_code == 200
        assert "crossTruck" in response.text
