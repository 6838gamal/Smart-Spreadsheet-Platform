"""Shared Jinja2Templates instance with i18n support."""

from fastapi.templating import Jinja2Templates
from app.core.i18n import get_texts
from app.core.config import settings
from datetime import datetime
import re

# ============================================================
# Custom Filters
# ============================================================

def timesince_filter(dt, default="الآن"):
    """
    Returns a human-readable time difference between now and the given datetime.
    
    Args:
        dt: The datetime to compare against (datetime object or string)
        default: Default text if dt is None
    
    Returns:
        str: Human-readable time difference in Arabic
    
    Examples:
        - الآن (if less than 1 minute)
        - منذ 5 دقائق
        - منذ ساعة
        - منذ 3 ساعات
        - منذ يوم
        - منذ 5 أيام
        - منذ أسبوع
        - منذ 3 أسابيع
    """
    if not dt:
        return default
    
    # Convert string to datetime if needed
    if isinstance(dt, str):
        try:
            # Try ISO format
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            try:
                # Try common format
                from dateutil import parser
                dt = parser.parse(dt)
            except:
                return default
    
    # If dt is timezone-aware, convert to naive for comparison
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()
    
    # Handle future dates
    if seconds < 0:
        return "في المستقبل"
    
    # Arabic time strings
    if seconds < 60:
        return "الآن"
    elif seconds < 120:
        return "منذ دقيقة"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"منذ {minutes} دقائق"
    elif seconds < 7200:
        return "منذ ساعة"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"منذ {hours} ساعات"
    elif seconds < 172800:
        return "منذ يوم"
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f"منذ {days} أيام"
    elif seconds < 1209600:
        return "منذ أسبوع"
    elif seconds < 2419200:
        weeks = int(seconds // 604800)
        return f"منذ {weeks} أسابيع"
    elif seconds < 4838400:
        return "منذ شهر"
    elif seconds < 29030400:
        months = int(seconds // 2419200)
        return f"منذ {months} أشهر"
    elif seconds < 58060800:
        return "منذ سنة"
    else:
        years = int(seconds // 29030400)
        return f"منذ {years} سنوات"


def filesize_filter(size_bytes):
    """
    Convert bytes to human-readable file size.
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        str: Human-readable file size
    
    Examples:
        - 1024 -> 1.0 KB
        - 1048576 -> 1.0 MB
        - 1073741824 -> 1.0 GB
    """
    if not size_bytes:
        return "0 B"
    
    size_bytes = int(size_bytes)
    
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    elif size_bytes < 1024 * 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.1f} TB"


def truncate_filter(text, length=50, suffix="..."):
    """
    Truncate text to a specific length.
    
    Args:
        text: The text to truncate
        length: Maximum length
        suffix: String to append when truncated
    
    Returns:
        str: Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= length:
        return text
    
    return text[:length] + suffix


def format_date_filter(dt, format_str="%Y-%m-%d %H:%M"):
    """
    Format a datetime object or string to a specific format.
    
    Args:
        dt: Datetime object or string
        format_str: Date format string
    
    Returns:
        str: Formatted date string
    """
    if not dt:
        return ""
    
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
        except ValueError:
            return dt
    
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    
    return dt.strftime(format_str)


# ============================================================
# Setup Templates
# ============================================================

# Create templates instance
templates = Jinja2Templates(directory="templates")

# Add global variables
templates.env.globals["get_texts"] = get_texts
templates.env.globals["settings"] = settings
templates.env.globals["now"] = datetime.now

# Add custom filters
templates.env.filters["timesince"] = timesince_filter
templates.env.filters["filesize"] = filesize_filter
templates.env.filters["truncate"] = truncate_filter
templates.env.filters["format_date"] = format_date_filter

# Optional: Add tests
def is_image_filter(value):
    """Check if a file is an image based on format."""
    if not value:
        return False
    image_formats = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'heic'}
    return value.lower() in image_formats

templates.env.tests["image"] = is_image_filter

# ============================================================
# Optional: Add Django-style filters
# ============================================================

# Add pluralize filter (like Django's pluralize)
def pluralize_filter(count, singular, plural=None):
    """
    Returns plural or singular form based on count.
    
    Args:
        count: Number
        singular: Singular form
        plural: Plural form (optional)
    
    Returns:
        str: The appropriate form
    
    Examples:
        - pluralize(1, "ملف", "ملفات") -> "ملف"
        - pluralize(5, "ملف", "ملفات") -> "ملفات"
    """
    if plural is None:
        plural = singular + "s"
    
    return plural if count != 1 else singular

templates.env.filters["pluralize"] = pluralize_filter

# Add default filter (like Django's default)
def default_filter(value, default="—"):
    """Return default if value is None or empty."""
    if value is None or value == "":
        return default
    return value

templates.env.filters["default"] = default_filter

# ============================================================
# Optional: Add utility functions
# ============================================================

# Get file extension
def file_extension(filename):
    """Get the extension of a filename."""
    if not filename:
        return ""
    parts = filename.split('.')
    return parts[-1].lower() if len(parts) > 1 else ""

templates.env.globals["file_extension"] = file_extension

# Check if file is image
def is_image_file(filename):
    """Check if a file is an image based on extension."""
    if not filename:
        return False
    ext = file_extension(filename)
    return ext in {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'heic'}

templates.env.globals["is_image_file"] = is_image_file

# Get file icon based on format
def file_icon(format):
    """Get emoji icon for file format."""
    icons = {
        'xlsx': '📊',
        'xls': '📊',
        'xlsm': '📊',
        'xlsb': '📊',
        'csv': '📋',
        'json': '📄',
        'pdf': '📕',
        'txt': '📝',
        'html': '🌐',
        'xml': '📰',
        'parquet': '📦',
        'jpg': '🖼️',
        'jpeg': '🖼️',
        'png': '🖼️',
        'gif': '🖼️',
        'bmp': '🖼️',
        'webp': '🖼️',
        'svg': '🖼️',
        'ico': '🖼️',
        'doc': '📄',
        'docx': '📄',
        'ppt': '📊',
        'pptx': '📊',
        'zip': '📦',
        'rar': '📦',
        '7z': '📦',
        'tar': '📦',
        'gz': '📦',
    }
    return icons.get(format.lower() if format else '', '📄')

templates.env.globals["file_icon"] = file_icon

print("✅ Templates configured with custom filters and globals")
