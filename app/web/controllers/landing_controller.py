from fastapi import APIRouter, Request, Depends, status
from fastapi.responses import RedirectResponse

from app.core.auth import get_current_user_optional
from app.domain.models.user import User

router = APIRouter(tags=["Root Redirect"])

@router.get("/")
async def root_redirect(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """
    Redirige la raíz directamente al Dashboard de Mercotruck Radar si hay sesión activa,
    o al portal de Login corporativo en caso contrario.
    """
    if request.url.query:
        return RedirectResponse(url=f"/dashboard?{request.url.query}", status_code=status.HTTP_302_FOUND)
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
