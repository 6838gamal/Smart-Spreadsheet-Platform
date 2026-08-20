"""Template engine configuration for Jinja2 with custom filters and functions."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List
from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

logger = logging.getLogger(__name__)


# ============================================================
# CUSTOM FILTERS
# ============================================================

def escapejs(value: Any) -> Markup:
    """
    Escape a string for use in JavaScript.
    
    Example:
        {{ my_string|escapejs }}
    """
    if value is None:
        return Markup("")
    
    string_value = str(value)
    
    # Escape for JavaScript
    escaped = string_value.replace('\\', '\\\\')
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace('"', '\\"')
    escaped = escaped.replace('\n', '\\n')
    escaped = escaped.replace('\r', '\\r')
    escaped = escaped.replace('\t', '\\t')
    
    return Markup(escaped)


def time_ago(value: Any) -> str:
    """
    Display time as "X minutes ago" or "X days ago".
    """
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
        else:
            return str(value)
        
        now = datetime.now()
        diff = now - dt
        
        if diff.total_seconds() < 60:
            return "الآن"
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"منذ {minutes} دقيقة"
        elif diff.total_seconds() < 86400:
            hours = int(diff.total_seconds() / 3600)
            return f"منذ {hours} ساعة"
        elif diff.total_seconds() < 604800:
            days = int(diff.total_seconds() / 86400)
            return f"منذ {days} يوم"
        else:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


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
        'pdf': '📕', 'doc': '📄', 'docx': '📄', 'txt': '📝',
        'xls': '📊', 'xlsx': '📊', 'csv': '📋',
        'json': '📄', 'xml': '📰', 'html': '🌐',
        'py': '🐍', 'js': '🟡',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'webp': '🖼️', 'svg': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦',
    }
    
    return icons.get(ext, '📄')


# ============================================================
# TEMPLATE CONFIGURATION
# ============================================================

class CustomTemplates(Jinja2Templates):
    """Custom Jinja2 templates with additional filters."""
    
    def __init__(self, directory: str, auto_reload: bool = True):
        super().__init__(directory=directory, auto_reload=auto_reload)
        
        # Add custom filters
        self.env.filters['escapejs'] = escapejs
        self.env.filters['time_ago'] = time_ago
        self.env.filters['format_size'] = format_size
        self.env.filters['file_icon'] = file_icon
        self.env.filters['json'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
        
        # Add global functions
        self.env.globals['now'] = datetime.now
        self.env.globals['json_dumps'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
    
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
        default_context = {
            'request': request,
            'now': datetime.now(),
        }
        merged_context = {**default_context, **context}
        
        return super().TemplateResponse(
            request=request,
            name=name,
            context=merged_context,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )


# Create global templates instance
try:
    templates = CustomTemplates(directory="templates")
    logger.info("✅ Templates initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize templates: {e}")
    templates = Jinja2Templates(directory="templates")
