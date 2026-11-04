import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.security import create_access_token
from app.core.auth import COOKIE_AUTH_NAME

@pytest.mark.anyio
async def test_render_dashboard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Root without session -> 303 Redirect to /login (no public landing)
        res_root_anon = await ac.get("/", follow_redirects=False)
        assert res_root_anon.status_code in (302, 303, 307)
        assert res_root_anon.headers.get("location") == "/login"

        # 2. Unauthenticated dashboard -> 303 Redirect to login
        res_anon = await ac.get("/dashboard", follow_redirects=False)
        assert res_anon.status_code in (302, 303, 307)
        assert "/login" in res_anon.headers.get("location", "")

        # 3. /superadmin is removed -> 404
        res_sa = await ac.get("/superadmin", follow_redirects=False)
        assert res_sa.status_code == 404

        # 4. Authenticated as SUPERADMIN -> 200 OK
        super_login = await ac.post(
            "/login",
            data={"email": "superadmin@mercotruck.com", "password": "ggsolutions123"},
            follow_redirects=False
        )
        assert super_login.status_code in (302, 303)
        ac.cookies.set(COOKIE_AUTH_NAME, super_login.cookies[COOKIE_AUTH_NAME])
        response = await ac.get("/dashboard")
        assert response.status_code == 200
        assert "Mercotruck" in response.text
        assert "Radar" in response.text
        assert "crossTruck" not in response.text
        assert "Softtrade" not in response.text

        # Root with active session -> 303 Redirect to /dashboard
        res_root_auth = await ac.get("/", follow_redirects=False)
        assert res_root_auth.status_code in (302, 303, 307)
        assert res_root_auth.headers.get("location") == "/dashboard"

        # 5. SUPERADMIN can access /presentacion
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

        # Login as Matías Palomino (mpalomino@mercotruck.com)
        login_res = await ac.post(
            "/login",
            data={"email": "mpalomino@mercotruck.com", "password": "Mercotruck2026!"},
            follow_redirects=False
        )
        assert login_res.status_code in (302, 303)
        assert login_res.headers.get("location") == "/dashboard"
        ac.cookies.set(COOKIE_AUTH_NAME, login_res.cookies[COOKIE_AUTH_NAME])

        # Client dashboard hides Pitch Comercial, crossTruck & Softtrade
        dash_res = await ac.get("/dashboard")
        assert dash_res.status_code == 200
        assert "Matías Palomino" in dash_res.text
        assert "Pitch Comercial" not in dash_res.text
        assert "/presentacion" not in dash_res.text
        assert "Softtrade" not in dash_res.text
        assert "crossTruck" not in dash_res.text
        assert "Ganancia Total Estimada" in dash_res.text
        assert 'action="/dashboard"' in dash_res.text

        # Cached browser hitting /?search=... redirects to /dashboard?search=...
        search_from_root = await ac.get("/?search=MOLINOS", follow_redirects=False)
        assert search_from_root.status_code == 302
        assert search_from_root.headers.get("location") == "/dashboard?search=MOLINOS"

        # Filtering on /dashboard stays on /dashboard and formats KPI cleanly
        filtered_res = await ac.get("/dashboard?search=MOLINOS")
        assert filtered_res.status_code == 200
        assert "USD" in filtered_res.text

        # Direct access to /presentacion returns 403 Forbidden for client
        pres_client = await ac.get("/presentacion", follow_redirects=False)
        assert pres_client.status_code == 403

        # Equipment filter FRIO renders cleanly
        frio_res = await ac.get("/dashboard?equipment=FRIO")
        assert frio_res.status_code == 200
        assert "masterProfileDialog" in frio_res.text


@pytest.mark.anyio
async def test_master_profile_get_and_lock():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Unauthenticated call to master-profile returns 401
        unauth = await ac.get("/api/v1/prospects/1/master-profile")
        assert unauth.status_code == 401

        # Authenticate as Matías
        login_res = await ac.post(
            "/login",
            data={"email": "mpalomino@mercotruck.com", "password": "Mercotruck2026!"},
            follow_redirects=False
        )
        ac.cookies.set(COOKIE_AUTH_NAME, login_res.cookies[COOKIE_AUTH_NAME])

        list_res = await ac.get("/api/v1/prospects/?page_size=1")
        assert list_res.status_code == 200
        items = list_res.json().get("items", [])
        if items:
            pid = items[0]["id"]
            mp_get = await ac.get(f"/api/v1/prospects/{pid}/master-profile")
            assert mp_get.status_code == 200
            mp_data = mp_get.json()
            assert mp_data["prospect_id"] == pid

            # Save back the exact existing values to verify write + cache invalidation safely
            mp_post = await ac.post(
                f"/api/v1/prospects/{pid}/master-profile",
                json={
                    "trade_name": mp_data.get("trade_name") or "",
                    "shipper_plant_name": mp_data.get("shipper_plant_name") or "",
                    "verified_origin_city": mp_data.get("verified_origin_city") or "ROSARIO",
                    "verified_dest_city": mp_data.get("verified_dest_city") or "SANTIAGO",
                    "default_equipment": mp_data.get("default_equipment") or "SECO",
                    "pallet_mode": mp_data.get("pallet_mode") or "AUTO",
                    "notes": mp_data.get("notes") or ""
                }
            )
            assert mp_post.status_code == 200
            assert mp_post.json()["status"] == "success"
