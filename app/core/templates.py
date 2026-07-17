"""Shared Jinja2Templates instance with i18n support."""

from fastapi.templating import Jinja2Templates
from app.core.i18n import get_texts

templates = Jinja2Templates(directory="templates")
templates.env.globals["get_texts"] = get_texts
