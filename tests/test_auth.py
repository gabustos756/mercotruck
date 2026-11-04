import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

from main import app
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.core.auth import COOKIE_AUTH_NAME

def test_password_hashing():
    pwd = "SecretPassword123"
    hashed = get_password_hash(pwd)
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False
    assert verify_password("", hashed) is False

def test_token_creation_and_decoding():
    data = {"sub": "42", "email": "test@mercotruck.com", "role": "ADMIN"}
    token = create_access_token(data, expires_in=3600)
    assert token is not None
    assert "." in token
    
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["email"] == "test@mercotruck.com"
    assert decoded["role"] == "ADMIN"
    assert "exp" in decoded

def test_token_expired():
    data = {"sub": "1"}
    # Token expirado hace 10 segundos
    token = create_access_token(data, expires_in=-10)
    decoded = decode_access_token(token)
    assert decoded is None

def test_token_tampered():
    data = {"sub": "1"}
    token = create_access_token(data, expires_in=3600)
    # Modificar parte del payload
    tampered = "X" + token[1:]
    assert decode_access_token(tampered) is None

@pytest.mark.anyio
async def test_unauthenticated_redirect_to_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Intento de acceso a ruta protegida sin autenticación debe redirigir a /login
        response = await client.get("/dashboard", follow_redirects=False)
        assert response.status_code in (302, 303, 307)
        assert "/login" in response.headers.get("location", "")

@pytest.mark.anyio
async def test_login_flow_and_authenticated_access():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login con credenciales de superadmin
        login_res = await client.post(
            "/login",
            data={
                "email": "superadmin",
                "password": "ggsolutions123",
                "remember_me": "true",
                "next": "/dashboard"
            },
            follow_redirects=False
        )
        assert login_res.status_code in (302, 303)
        assert COOKIE_AUTH_NAME in login_res.cookies
        
        # 2. Acceso con cookie persistida
        client.cookies.set(COOKIE_AUTH_NAME, login_res.cookies[COOKIE_AUTH_NAME])
        dash_res = await client.get("/dashboard")
        assert dash_res.status_code == 200
        assert "Mercotruck" in dash_res.text
        assert "crossTruck" not in dash_res.text

@pytest.mark.anyio
async def test_login_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/login",
            data={
                "email": "superadmin",
                "password": "wrongpassword"
            },
            follow_redirects=False
        )
        assert login_res.status_code == 400
        assert "incorrectos" in login_res.text

@pytest.mark.anyio
async def test_api_auth_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "mpalomino@mercotruck.com",
                "password": "Mercotruck2026!"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "mpalomino@mercotruck.com"
        assert data["user"]["role"] == "ADMIN"

        # Verificar /api/v1/auth/me con token Bearer
        me_res = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {data['access_token']}"}
        )
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "mpalomino@mercotruck.com"


def test_create_default_users_handles_coexisting_legacy_superadmin():
    from app.core.database import SyncSessionLocal
    from app.domain.models.user import User, UserRole
    from app.etl.pipeline import create_default_users

    db = SyncSessionLocal()
    try:
        legacy = db.query(User).filter(User.email == "superadmin@crosstruck.com").first()
        if not legacy:
            legacy = User(
                email="superadmin@crosstruck.com",
                full_name="Legacy crossTruck",
                hashed_password=get_password_hash("ggsolutions123"),
                role=UserRole.SUPERADMIN,
                company_id=None,
                is_active=True,
            )
            db.add(legacy)
            db.commit()

        # Ejecutar dos veces seguidas simula init_db_tables() + run_etl_pipeline() en la VPS
        create_default_users(db)
        create_default_users(db)

        merco_sa = db.query(User).filter(User.email == "superadmin@mercotruck.com").first()
        legacy_sa = db.query(User).filter(User.email == "superadmin@crosstruck.com").first()

        assert merco_sa is not None
        assert merco_sa.is_active is True
        assert legacy_sa is not None
        assert legacy_sa.is_active is False
    finally:
        db.close()
