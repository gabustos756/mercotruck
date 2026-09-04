from typing import Optional
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.domain.models.user import User, UserRole

COOKIE_AUTH_NAME = "access_token"

async def extract_token_from_request(request: Request) -> Optional[str]:
    """Extrae el token de acceso desde la cookie HTTP-Only o del header Authorization Bearer."""
    # 1. Buscar en cookie
    token = request.cookies.get(COOKIE_AUTH_NAME)
    if token:
        return token
    
    # 2. Buscar en Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    
    return None

async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Devuelve el usuario actual si la sesión es válida, o None si es anónimo."""
    token = await extract_token_from_request(request)
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None
    
    user_id = payload.get("sub")
    try:
        query = select(User).where(User.id == int(user_id), User.is_active == True)
        res = await db.execute(query)
        return res.scalar_one_or_none()
    except Exception:
        return None

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """Dependencia para APIs REST. Lanza 401 si no está autenticado."""
    user = await get_current_user_optional(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado o sesión expirada.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

async def get_current_user_web(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependencia para controladores Web.
    Si no hay sesión activa, redirige inmediatamente a /login?next=<url>.
    """
    user = await get_current_user_optional(request, db)
    if not user:
        # Guardar URL solicitada para redirección posterior
        next_url = request.url.path
        if request.url.query:
            next_url += f"?{request.url.query}"
        
        # Redirección HTTP 303 See Other
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": f"/login?next={next_url}"}
        )
    return user

def require_role(*allowed_roles: UserRole):
    """Verifica que el usuario pertenezca a uno de los roles autorizados."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción."
            )
        return current_user
    return role_checker

require_admin = require_role(UserRole.ADMIN)
