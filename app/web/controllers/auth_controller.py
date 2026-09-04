from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, DEFAULT_TOKEN_EXPIRY_SECONDS
from app.core.auth import COOKIE_AUTH_NAME, get_current_user_optional, get_current_user
from app.domain.models.user import User

router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory="app/templates")

class LoginApiRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = True

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Muestra el formulario de inicio de sesión."""
    # Si ya está autenticado, redirigir a dashboard o next
    if current_user:
        target = next if (next and next.startswith("/") and not next.startswith("/login")) else "/"
        return RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "next": next or "/",
            "error": None
        }
    )

@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(None),
    next: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Procesa el inicio de sesión web y emite la cookie de sesión."""
    clean_email = email.strip().lower()
    
    # Buscar usuario en la base de datos
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "next": next or "/",
                "error": "Email o contraseña incorrectos. Por favor verifica tus credenciales.",
                "email_val": clean_email
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )
    
    if not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "next": next or "/",
                "error": "Tu cuenta de usuario ha sido desactivada. Consulta al administrador.",
                "email_val": clean_email
            },
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    # Calcular tiempo de expiración
    is_remember = bool(remember_me)
    expires_in = DEFAULT_TOKEN_EXPIRY_SECONDS if is_remember else 24 * 3600  # 7 días o 1 día
    
    # Generar token firmado
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "name": user.full_name,
            "role": user.role.value
        },
        expires_in=expires_in
    )
    
    # Determinar URL de destino
    target = next if (next and next.startswith("/") and not next.startswith("/login")) else "/"
    
    response = RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)
    
    # Setear cookie HTTP-Only segura
    response.set_cookie(
        key=COOKIE_AUTH_NAME,
        value=token,
        max_age=expires_in,
        expires=expires_in,
        httponly=True,
        samesite="lax",
        secure=False  # Cambia a True si se usa HTTPS estricto detrás de proxy
    )
    
    return response

@router.get("/logout")
@router.post("/logout")
async def logout():
    """Cierra la sesión del usuario eliminando la cookie de acceso."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key=COOKIE_AUTH_NAME, httponly=True, samesite="lax")
    return response

# ── API REST ENDPOINTS DE AUTENTICACIÓN ─────────────────────────────────────────

@router.post("/api/v1/auth/login")
async def api_login(
    payload: LoginApiRequest,
    db: AsyncSession = Depends(get_db)
):
    """Login vía API JSON (devuelve token Bearer y datos de usuario)."""
    clean_email = payload.email.strip().lower()
    query = select(User).where(User.email == clean_email)
    res = await db.execute(query)
    user = res.scalar_one_or_none()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo."
        )
        
    expires_in = DEFAULT_TOKEN_EXPIRY_SECONDS if payload.remember_me else 24 * 3600
    token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "name": user.full_name,
            "role": user.role.value
        },
        expires_in=expires_in
    )
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    }

@router.get("/api/v1/auth/me")
async def api_get_me(current_user: User = Depends(get_current_user)):
    """Obtiene los datos del usuario autenticado actual."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None
    }
