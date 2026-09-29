"""
Template engine configuration for Jinja2 with custom filters, functions,
and full internationalization (i18n/l10n) support.

Uses the unified translation system from app.core.i18n.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List, Union, Callable

from fastapi import Request, Response
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
import os

# استيراد الإعدادات
from app.core.config import settings

# ✅ نظام الترجمة الموحّد (المصدر الوحيد للحقيقة)
from app.core.i18n import (
    get_texts,
    Texts,
    _TRANSLATIONS,
)

logger = logging.getLogger(__name__)


# ============================================================
# TRANSLATION COMPATIBILITY LAYER
# ============================================================

# للتوافق الخلفي مع أي كود يستورد DEFAULT_TRANSLATIONS من هذا الملف
DEFAULT_TRANSLATIONS = _TRANSLATIONS


def get_language_direction(lang: str = 'ar') -> str:
    """Get text direction for a language."""
    return 'rtl' if lang in ('ar', 'fa', 'he', 'ur') else 'ltr'


def is_rtl_language(lang: str) -> bool:
    """Check if a language is RTL."""
    return get_language_direction(lang) == 'rtl'


def get_supported_languages() -> Dict[str, str]:
    """Get supported languages with their names."""
    return {
        'ar': 'العربية',
        'en': 'English',
    }


def t(text: str, lang: str = 'ar', **kwargs) -> str:
    """
    Translate a text using the unified i18n module.

    Args:
        text: Text key to translate
        lang: Language code
        **kwargs: Format arguments

    Returns:
        str: Translated text
    """
    texts = get_texts(lang)                # ← يرجع Texts object من i18n.py
    translated = texts.get(text, text)     # ← Texts.get
    if kwargs:
        try:
            translated = translated.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return translated


# ============================================================
# CUSTOM FILTERS
# ============================================================

def escapejs(value: Any) -> Markup:
    """Escape a string for use in JavaScript."""
    if value is None:
        return Markup("")

    string_value = str(value)
    escaped = string_value.replace('\\', '\\\\')
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('\r', '\\r')
    escaped = escaped.replace('\t', '\\t')
    return Markup(escaped)


def tojson_safe(value: Any, indent: Optional[int] = None) -> Markup:
    """Convert to JSON safely for HTML."""
    if value is None:
        return Markup("null")
    try:
        if indent is not None:
            json_str = json.dumps(value, ensure_ascii=False, indent=indent, default=str)
        else:
            json_str = json.dumps(value, ensure_ascii=False, default=str)
        return Markup(json_str)
    except Exception:
        return Markup("null")


def timesince(value: Any, lang: str = 'ar') -> str:
    """Display time since a date."""
    if value is None:
        return ""
    try:
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return value
        elif isinstance(value, datetime):
            dt = value
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        else:
            return str(value)

        now = datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return t('now', lang)
        elif seconds < 3600:
            return t('minutes_ago', lang, minutes=int(seconds / 60))
        elif seconds < 86400:
            return t('hours_ago', lang, hours=int(seconds / 3600))
        elif seconds < 604800:
            return t('days_ago', lang, days=int(seconds / 86400))
        else:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def time_ago(value: Any, lang: str = 'ar') -> str:
    """Display time as 'X minutes ago' or 'X days ago'."""
    return timesince(value, lang)


def format_size(value: Any) -> str:
    """Format file size in human readable format."""
    if value is None:
        return "0 B"
    try:
        size = int(value)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    except Exception:
        return str(value)


def file_icon(value: str) -> str:
    """Get an icon for a file type."""
    if value is None:
        return "📄"
    ext = str(value).lower()
    icons = {
        'pdf': '📕', 'doc': '📄', 'docx': '📄', 'txt': '📝', 'rtf': '📝',
        'odt': '📄', 'md': '📝', 'rst': '📝',
        'xls': '📊', 'xlsx': '📊', 'xlsm': '📊', 'xlsb': '📊', 'ods': '📊',
        'csv': '📋', 'tsv': '📋',
        'ppt': '📊', 'pptx': '📊', 'odp': '📊',
        'json': '📄', 'xml': '📰', 'html': '🌐', 'htm': '🌐',
        'css': '🎨', 'js': '🟡', 'py': '🐍', 'java': '☕',
        'c': '⚙️', 'cpp': '⚙️', 'go': '🐹', 'rs': '🦀',
        'php': '🐘', 'sql': '🗄️', 'yaml': '📄', 'yml': '📄',
        'parquet': '📦', 'feather': '🪶', 'arrow': '🏹',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'webp': '🖼️', 'svg': '🖼️', 'ico': '🖼️', 'bmp': '🖼️',
        'tiff': '🖼️', 'heic': '🖼️', 'raw': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'bz2': '📦', 'xz': '📦',
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬',
        'exe': '⚙️', 'msi': '⚙️', 'dmg': '💿', 'iso': '💿',
    }
    return icons.get(ext, '📄')


def truncate_text(value: Any, length: int = 100, suffix: str = '...') -> str:
    """Truncate text to a specific length."""
    if value is None:
        return ""
    try:
        text = str(value)
        if len(text) <= length:
            return text
        return text[:length - len(suffix)] + suffix
    except Exception:
        return str(value)


def translate_filter(text: str, lang: str = 'ar') -> str:
    """Jinja2 filter for translation."""
    return t(text, lang)


# ============================================================
# DATE / DATETIME FILTERS
# ============================================================

def format_date(value: Any, fmt: str = '%Y-%m-%d') -> str:
    """Format a date/datetime/ISO-string safely."""
    if value is None:
        return '-'
    if isinstance(value, datetime):
        return value.strftime(fmt)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return '-'
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            return dt.strftime(fmt)
        except (ValueError, AttributeError):
            return s[:10] if len(s) >= 10 else s
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).strftime(fmt)
        except (ValueError, OSError):
            return str(value)
    return str(value)


def format_datetime(value: Any, fmt: str = '%Y-%m-%d %H:%M') -> str:
    """Format a datetime with time component."""
    return format_date(value, fmt)


def format_time(value: Any, fmt: str = '%H:%M') -> str:
    """Format only the time component."""
    return format_date(value, fmt)


# ============================================================
# CUSTOM TESTS
# ============================================================

def is_image(value: str) -> bool:
    if not value:
        return False
    return str(value).lower() in {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff', 'heic'}


def is_video(value: str) -> bool:
    if not value:
        return False
    return str(value).lower() in {'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm'}


def is_audio(value: str) -> bool:
    if not value:
        return False
    return str(value).lower() in {'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma'}


def is_document(value: str) -> bool:
    if not value:
        return False
    return str(value).lower() in {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'md', 'rst'}


def is_spreadsheet(value: str) -> bool:
    if not value:
        return False
    return str(value).lower() in {'xls', 'xlsx', 'xlsm', 'xlsb', 'ods', 'csv', 'tsv'}


# ============================================================
# TEMPLATE CONFIGURATION
# ============================================================

class CustomTemplates(Jinja2Templates):
    """
    Custom Jinja2 templates with additional filters, functions, and tests.
    """

    def __init__(self, directory: str, auto_reload: bool = True):
        super().__init__(directory=directory)
        try:
            if hasattr(self.env, 'auto_reload'):
                self.env.auto_reload = auto_reload
        except Exception as e:
            logger.warning(f"Could not set auto_reload: {e}")

        self._add_filters()
        self._add_globals()
        self._add_tests()

        logger.info("✅ Custom templates initialized successfully")

    def _add_filters(self):
        """Add custom filters to the environment."""
        self.env.filters['escapejs'] = escapejs
        self.env.filters['tojson_safe'] = tojson_safe
        self.env.filters['timesince'] = timesince
        self.env.filters['time_ago'] = time_ago
        self.env.filters['format_size'] = format_size
        self.env.filters['file_icon'] = file_icon
        self.env.filters['truncate_text'] = truncate_text
        self.env.filters['t'] = translate_filter
        self.env.filters['translate'] = translate_filter

        # date/time filters
        self.env.filters['format_date'] = format_date
        self.env.filters['format_datetime'] = format_datetime
        self.env.filters['format_time'] = format_time

        # JSON filters
        self.env.filters['json'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
        self.env.filters['pretty_json'] = lambda v: json.dumps(v, ensure_ascii=False, indent=2, default=str)

    def _add_globals(self):
        """Add global functions and variables to the environment."""
        self.env.globals.update({
            'now': datetime.now,
            'today': lambda: datetime.now().date(),
            'get_texts': get_texts,                 # ✅ من i18n.py
            't': t,
            'translate': t,
            'get_language_direction': get_language_direction,
            'get_supported_languages': get_supported_languages,
            'is_rtl_language': is_rtl_language,
            'DEFAULT_TRANSLATIONS': _TRANSLATIONS,  # ✅ القاموس الموحّد
            'settings': settings,
            'json_dumps': lambda v, **kwargs: json.dumps(v, ensure_ascii=False, **kwargs),
            'range': lambda start, end: range(start, end),
            'dict_get': lambda d, key, default=None: d.get(key, default) if d else default,
            'list_get': lambda l, index, default=None: l[index] if l and 0 <= index < len(l) else default,
            'format_date': format_date,
            'format_datetime': format_datetime,
        })

    def _add_tests(self):
        """Add custom tests to the environment."""
        self.env.tests['image'] = is_image
        self.env.tests['video'] = is_video
        self.env.tests['audio'] = is_audio
        self.env.tests['document'] = is_document
        self.env.tests['spreadsheet'] = is_spreadsheet

    def TemplateResponse(
        self,
        request: Request,
        name: str,
        context: Dict[str, Any],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: str = "text/html",
    ):
        """Override TemplateResponse to inject default context."""
        # Get language
        lang = context.get('lang')

        if not lang and hasattr(request.state, 'lang'):
            lang = request.state.lang

        if not lang and hasattr(request, 'cookies'):
            lang = request.cookies.get('lang')

        if not lang and hasattr(request.state, 'user'):
            user = request.state.user
            if user and hasattr(user, 'default_lang') and user.default_lang:
                lang = user.default_lang

        # ✅ التحقق من اللغة المدعومة
        if not lang or lang not in ('ar', 'en'):
            lang = 'ar'

        translations = get_texts(lang)            # ← يرجع Texts object
        direction = get_language_direction(lang)
        user = getattr(request.state, 'user', None)

        default_context = {
            'request': request,
            'now': datetime.now(),
            'lang': lang,
            'direction': direction,
            'translations': translations,
            'user': user,
            'is_authenticated': user is not None and getattr(user, 'is_active', False),
            'settings': settings,
            'get_texts': get_texts,
            't': t,
            'translate': t,
            'get_language_direction': get_language_direction,
            'get_supported_languages': get_supported_languages,
            'is_rtl_language': is_rtl_language,
            'DEFAULT_TRANSLATIONS': _TRANSLATIONS,
            'format_date': format_date,
            'format_datetime': format_datetime,
            'format_time': format_time,
        }

        merged_context = {**default_context, **context}

        request.state.lang = lang
        request.state.direction = direction
        request.state.translations = translations

        return super().TemplateResponse(
            request=request,
            name=name,
            context=merged_context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


# ============================================================
# SINGLETON INSTANCE
# ============================================================

def get_templates(template_dir: str = "templates") -> CustomTemplates:
    """Get or create the templates instance."""
    template_path = Path(template_dir)
    if not template_path.exists():
        logger.warning(f"⚠️ Templates directory not found: {template_dir}")
        template_path.mkdir(parents=True, exist_ok=True)

    try:
        return CustomTemplates(directory=template_dir)
    except Exception as e:
        logger.error(f"❌ Failed to initialize custom templates: {e}")
        return Jinja2Templates(directory=template_dir)


# Create global templates instance
try:
    templates = get_templates("templates")
    logger.info("✅ Templates initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize templates: {e}")
    templates = Jinja2Templates(directory="templates")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

async def render_template(
    request: Request,
    template_name: str,
    context: Dict[str, Any] = None,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
):
    """Helper to render templates with automatic language detection."""
    context = context or {}
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
        headers=headers,
    )


async def set_language_cookie(response: Response, lang: str, max_age: int = 60 * 60 * 24 * 30) -> None:
    """Set language cookie in response."""
    if lang not in ('ar', 'en'):
        lang = 'ar'

    response.set_cookie(
        key="lang",
        value=lang,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
    )


async def clear_language_cookie(response: Response) -> None:
    """Clear language cookie."""
    response.delete_cookie(key="lang", path="/")


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    'templates',
    'CustomTemplates',
    'get_templates',
    'render_template',
    'get_texts',
    't',
    'get_language_direction',
    'get_supported_languages',
    'is_rtl_language',
    'DEFAULT_TRANSLATIONS',
    'escapejs',
    'tojson_safe',
    'timesince',
    'time_ago',
    'format_size',
    'file_icon',
    'truncate_text',
    'format_date',
    'format_datetime',
    'format_time',
    'is_image',
    'is_video',
    'is_audio',
    'is_document',
    'is_spreadsheet',
    'set_language_cookie',
    'clear_language_cookie',
]
