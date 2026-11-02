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

        # 3. Authenticated as SUPERADMIN -> 200 OK
        super_login = await ac.post(
            "/login",
            data={"email": "superadmin@crosstruck.com", "password": "ggsolutions123"},
            follow_redirects=False
        )
        assert super_login.status_code in (302, 303)
        ac.cookies.set(COOKIE_AUTH_NAME, super_login.cookies[COOKIE_AUTH_NAME])
        response = await ac.get("/dashboard")
        assert response.status_code == 200
        assert "crossTruck" in response.text
        assert "Softtrade" not in response.text

        # 4. SUPERADMIN can access /presentacion
        pres_super = await ac.get("/presentacion", follow_redirects=False)
        assert pres_super.status_code == 200
        assert "Pitch Comercial" in pres_super.text

@pytest.mark.anyio
async def test_client_cannot_see_or_access_pitch_comercial():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthenticated /presentacion redirects to /login
        anon_pres = await ac.get("/presentacion", follow_redirects=False)
        assert anon_pres.status_code in (302, 303, 307)
        assert "/login" in anon_pres.headers.get("location", "")

        # Login as Mercotruck client (admin@mercotruck.com)
        login_res = await ac.post(
            "/login",
            data={"email": "admin@mercotruck.com", "password": "ggsolutions123"},
            follow_redirects=False
        )
        assert login_res.status_code in (302, 303)
        ac.cookies.set(COOKIE_AUTH_NAME, login_res.cookies[COOKIE_AUTH_NAME])

        # Client dashboard hides Pitch Comercial & Softtrade
        dash_res = await ac.get("/dashboard")
        assert dash_res.status_code == 200
        assert "Pitch Comercial" not in dash_res.text
        assert "/presentacion" not in dash_res.text
        assert "Softtrade" not in dash_res.text

        # Direct access to /presentacion returns 403 Forbidden for client
        pres_client = await ac.get("/presentacion", follow_redirects=False)
        assert pres_client.status_code == 403
