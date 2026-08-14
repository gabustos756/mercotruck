from fastapi.templating import Jinja2Templates
from app.core.config import settings

templates = Jinja2Templates(directory="app/templates")

# Register global Jinja variables accessible in all HTML templates
templates.env.globals["google_maps_api_key"] = settings.GOOGLE_MAPS_API_KEY
