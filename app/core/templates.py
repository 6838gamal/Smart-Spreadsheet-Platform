"""Template engine configuration for Jinja2 with custom filters and functions."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List, Union
from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
import os

logger = logging.getLogger(__name__)


# ============================================================
# TRANSLATION / I18N - L10N
# ============================================================

# Default translations dictionary - يمكنك إضافة المزيد من اللغات
DEFAULT_TRANSLATIONS = {
    'ar': {
        # Auth
        'login': 'تسجيل الدخول',
        'logout': 'تسجيل الخروج',
        'register': 'إنشاء حساب',
        'email': 'البريد الإلكتروني',
        'password': 'كلمة المرور',
        'confirm_password': 'تأكيد كلمة المرور',
        'username': 'اسم المستخدم',
        'remember_me': 'تذكرني',
        'forgot_password': 'نسيت كلمة المرور؟',
        'reset_password': 'إعادة تعيين كلمة المرور',
        'sign_in': 'تسجيل الدخول',
        'sign_up': 'إنشاء حساب',
        'welcome_back': 'مرحباً بعودتك',
        'create_account': 'إنشاء حساب جديد',
        'already_have_account': 'لديك حساب بالفعل؟',
        'dont_have_account': 'ليس لديك حساب؟',
        
        # Files
        'files': 'الملفات',
        'upload_file': 'رفع ملف',
        'upload_files': 'رفع ملفات',
        'file_name': 'اسم الملف',
        'file_size': 'حجم الملف',
        'file_format': 'نوع الملف',
        'uploaded_at': 'تاريخ الرفع',
        'no_files': 'لا يوجد ملفات',
        'delete_file': 'حذف الملف',
        'download_file': 'تحميل الملف',
        'view_file': 'عرض الملف',
        'analyze_file': 'تحليل الملف',
        'convert_file': 'تحويل الملف',
        'favorite': 'المفضلة',
        'storage_used': 'المساحة المستخدمة',
        'total_files': 'إجمالي الملفات',
        'file_uploaded': 'تم رفع الملف',
        'file_deleted': 'تم حذف الملف',
        'file_analyzed': 'تم تحليل الملف',
        'file_converted': 'تم تحويل الملف',
        
        # Actions
        'save': 'حفظ',
        'cancel': 'إلغاء',
        'delete': 'حذف',
        'edit': 'تعديل',
        'update': 'تحديث',
        'search': 'بحث',
        'filter': 'تصفية',
        'sort': 'ترتيب',
        'refresh': 'تحديث',
        'loading': 'جاري التحميل...',
        'processing': 'جاري المعالجة...',
        'success': 'تم بنجاح',
        'error': 'حدث خطأ',
        'warning': 'تحذير',
        'info': 'معلومات',
        'confirm': 'تأكيد',
        'yes': 'نعم',
        'no': 'لا',
        'close': 'إغلاق',
        'back': 'رجوع',
        'next': 'التالي',
        'previous': 'السابق',
        'home': 'الرئيسية',
        'dashboard': 'لوحة التحكم',
        'settings': 'الإعدادات',
        'profile': 'الملف الشخصي',
        'help': 'المساعدة',
        'about': 'حول',
        
        # Messages
        'delete_confirm': 'هل أنت متأكد من حذف هذا العنصر؟',
        'delete_success': 'تم الحذف بنجاح',
        'delete_error': 'فشل الحذف',
        'upload_success': 'تم الرفع بنجاح',
        'upload_error': 'فشل الرفع',
        'save_success': 'تم الحفظ بنجاح',
        'save_error': 'فشل الحفظ',
        'update_success': 'تم التحديث بنجاح',
        'update_error': 'فشل التحديث',
        'file_too_large': 'الملف كبير جداً',
        'unsupported_format': 'صيغة غير مدعومة',
        'invalid_credentials': 'بيانات الدخول غير صحيحة',
        'user_not_found': 'المستخدم غير موجود',
        'email_exists': 'البريد الإلكتروني موجود مسبقاً',
        'passwords_mismatch': 'كلمات المرور غير متطابقة',
        'password_reset_sent': 'تم إرسال رابط إعادة التعيين',
        
        # Languages
        'arabic': 'العربية',
        'english': 'الإنجليزية',
        'language': 'اللغة',
        'change_language': 'تغيير اللغة',
        
        # Time
        'now': 'الآن',
        'minutes_ago': 'منذ {minutes} دقيقة',
        'hours_ago': 'منذ {hours} ساعة',
        'days_ago': 'منذ {days} يوم',
        'weeks_ago': 'منذ {weeks} أسبوع',
        'months_ago': 'منذ {months} شهر',
        'years_ago': 'منذ {years} سنة',
        
        # Workspace
        'workspace': 'مساحة العمل',
        'new_workspace': 'مساحة عمل جديدة',
        'workspace_name': 'اسم مساحة العمل',
        'workspace_description': 'وصف مساحة العمل',
        'workspace_created': 'تم إنشاء مساحة العمل',
        'workspace_deleted': 'تم حذف مساحة العمل',
        'workspace_updated': 'تم تحديث مساحة العمل',
    },
    'en': {
        # Auth
        'login': 'Login',
        'logout': 'Logout',
        'register': 'Register',
        'email': 'Email',
        'password': 'Password',
        'confirm_password': 'Confirm Password',
        'username': 'Username',
        'remember_me': 'Remember Me',
        'forgot_password': 'Forgot Password?',
        'reset_password': 'Reset Password',
        'sign_in': 'Sign In',
        'sign_up': 'Sign Up',
        'welcome_back': 'Welcome Back',
        'create_account': 'Create Account',
        'already_have_account': 'Already have an account?',
        'dont_have_account': "Don't have an account?",
        
        # Files
        'files': 'Files',
        'upload_file': 'Upload File',
        'upload_files': 'Upload Files',
        'file_name': 'File Name',
        'file_size': 'File Size',
        'file_format': 'File Format',
        'uploaded_at': 'Uploaded At',
        'no_files': 'No Files',
        'delete_file': 'Delete File',
        'download_file': 'Download File',
        'view_file': 'View File',
        'analyze_file': 'Analyze File',
        'convert_file': 'Convert File',
        'favorite': 'Favorite',
        'storage_used': 'Storage Used',
        'total_files': 'Total Files',
        'file_uploaded': 'File Uploaded',
        'file_deleted': 'File Deleted',
        'file_analyzed': 'File Analyzed',
        'file_converted': 'File Converted',
        
        # Actions
        'save': 'Save',
        'cancel': 'Cancel',
        'delete': 'Delete',
        'edit': 'Edit',
        'update': 'Update',
        'search': 'Search',
        'filter': 'Filter',
        'sort': 'Sort',
        'refresh': 'Refresh',
        'loading': 'Loading...',
        'processing': 'Processing...',
        'success': 'Success',
        'error': 'Error',
        'warning': 'Warning',
        'info': 'Info',
        'confirm': 'Confirm',
        'yes': 'Yes',
        'no': 'No',
        'close': 'Close',
        'back': 'Back',
        'next': 'Next',
        'previous': 'Previous',
        'home': 'Home',
        'dashboard': 'Dashboard',
        'settings': 'Settings',
        'profile': 'Profile',
        'help': 'Help',
        'about': 'About',
        
        # Messages
        'delete_confirm': 'Are you sure you want to delete this item?',
        'delete_success': 'Deleted successfully',
        'delete_error': 'Delete failed',
        'upload_success': 'Uploaded successfully',
        'upload_error': 'Upload failed',
        'save_success': 'Saved successfully',
        'save_error': 'Save failed',
        'update_success': 'Updated successfully',
        'update_error': 'Update failed',
        'file_too_large': 'File is too large',
        'unsupported_format': 'Unsupported format',
        'invalid_credentials': 'Invalid credentials',
        'user_not_found': 'User not found',
        'email_exists': 'Email already exists',
        'passwords_mismatch': 'Passwords do not match',
        'password_reset_sent': 'Password reset link sent',
        
        # Languages
        'arabic': 'Arabic',
        'english': 'English',
        'language': 'Language',
        'change_language': 'Change Language',
        
        # Time
        'now': 'Now',
        'minutes_ago': '{minutes} minutes ago',
        'hours_ago': '{hours} hours ago',
        'days_ago': '{days} days ago',
        'weeks_ago': '{weeks} weeks ago',
        'months_ago': '{months} months ago',
        'years_ago': '{years} years ago',
        
        # Workspace
        'workspace': 'Workspace',
        'new_workspace': 'New Workspace',
        'workspace_name': 'Workspace Name',
        'workspace_description': 'Workspace Description',
        'workspace_created': 'Workspace Created',
        'workspace_deleted': 'Workspace Deleted',
        'workspace_updated': 'Workspace Updated',
    }
}


# ============================================================
# TRANSLATION FUNCTIONS
# ============================================================

def get_texts(lang: str = 'ar') -> Dict[str, str]:
    """
    Get translations for a specific language.
    
    Args:
        lang: Language code (ar, en, etc.)
    
    Returns:
        Dict: Translation dictionary
    """
    if lang not in DEFAULT_TRANSLATIONS:
        lang = 'ar'  # Default to Arabic
    return DEFAULT_TRANSLATIONS[lang]


def t(text: str, lang: str = 'ar', **kwargs) -> str:
    """
    Translate a text to the specified language.
    
    Args:
        text: Text to translate (key)
        lang: Language code
        **kwargs: Format arguments
    
    Returns:
        str: Translated text
    """
    translations = get_texts(lang)
    translated = translations.get(text, text)
    
    # Replace placeholders with kwargs
    if kwargs:
        try:
            translated = translated.format(**kwargs)
        except (KeyError, ValueError):
            pass
    
    return translated


def get_language_direction(lang: str = 'ar') -> str:
    """
    Get text direction for a language.
    
    Args:
        lang: Language code
    
    Returns:
        str: 'rtl' or 'ltr'
    """
    rtl_languages = ['ar', 'fa', 'he', 'ur']
    return 'rtl' if lang in rtl_languages else 'ltr'


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


def tojson_safe(value: Any) -> Markup:
    """
    Convert to JSON safely for HTML.
    
    Example:
        {{ my_data|tojson_safe }}
    """
    if value is None:
        return Markup("null")
    
    try:
        json_str = json.dumps(value, ensure_ascii=False, default=str)
        return Markup(json_str)
    except Exception:
        return Markup("null")


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
        elif isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value)
        else:
            return str(value)
        
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "الآن" if get_texts('ar') else "Now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"منذ {minutes} دقيقة" if get_texts('ar') else f"{minutes} minutes ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"منذ {hours} ساعة" if get_texts('ar') else f"{hours} hours ago"
        elif seconds < 604800:
            days = int(seconds / 86400)
            return f"منذ {days} يوم" if get_texts('ar') else f"{days} days ago"
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
        'pdf': '📕', 'doc': '📄', 'docx': '📄', 'txt': '📝', 'rtf': '📝',
        'xls': '📊', 'xlsx': '📊', 'xlsm': '📊', 'xlsb': '📊', 'ods': '📊',
        'csv': '📋', 'tsv': '📋',
        'ppt': '📊', 'pptx': '📊', 'odp': '📊',
        'json': '📄', 'xml': '📰', 'html': '🌐', 'htm': '🌐',
        'css': '🎨', 'js': '🟡', 'py': '🐍', 'java': '☕',
        'c': '⚙️', 'cpp': '⚙️', 'go': '🐹', 'rs': '🦀',
        'php': '🐘', 'sql': '🗄️',
        'parquet': '📦', 'feather': '🪶',
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'webp': '🖼️', 'svg': '🖼️', 'ico': '🖼️',
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'mp3': '🎵', 'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬',
    }
    
    return icons.get(ext, '📄')


def translate_filter(text: str, lang: str = 'ar') -> str:
    """Jinja2 filter for translation."""
    return t(text, lang)


# ============================================================
# TEMPLATE CONFIGURATION
# ============================================================

class CustomTemplates(Jinja2Templates):
    """Custom Jinja2 templates with additional filters and functions."""
    
    def __init__(self, directory: str, auto_reload: bool = True):
        super().__init__(directory=directory, auto_reload=auto_reload)
        
        # Add custom filters
        self.env.filters['escapejs'] = escapejs
        self.env.filters['tojson_safe'] = tojson_safe
        self.env.filters['time_ago'] = time_ago
        self.env.filters['format_size'] = format_size
        self.env.filters['file_icon'] = file_icon
        self.env.filters['json'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
        self.env.filters['pretty_json'] = lambda v: json.dumps(v, ensure_ascii=False, indent=2, default=str)
        self.env.filters['t'] = translate_filter
        self.env.filters['translate'] = translate_filter
        
        # Add global functions
        self.env.globals['now'] = datetime.now
        self.env.globals['get_texts'] = get_texts
        self.env.globals['t'] = t
        self.env.globals['translate'] = t
        self.env.globals['get_language_direction'] = get_language_direction
        self.env.globals['json_dumps'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
        
        logger.info("✅ Custom templates initialized with translation support")
    
    def TemplateResponse(
        self,
        request: Request,
        name: str,
        context: Dict[str, Any],
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        media_type: str = "text/html",
    ):
        """
        Override TemplateResponse to inject default context.
        
        Args:
            request: FastAPI request
            name: Template name
            context: Template context
            status_code: HTTP status code
            headers: HTTP headers
            media_type: Response media type
        
        Returns:
            TemplateResponse: Rendered template response
        """
        # Get language from request or context
        lang = context.get('lang', 'ar')
        
        # Try to get from cookie
        if hasattr(request, 'cookies') and 'lang' in request.cookies:
            cookie_lang = request.cookies.get('lang')
            if cookie_lang in DEFAULT_TRANSLATIONS:
                lang = cookie_lang
        
        # Try to get from user session
        if hasattr(request, 'state') and hasattr(request.state, 'user'):
            user = request.state.user
            if user and hasattr(user, 'default_lang') and user.default_lang in DEFAULT_TRANSLATIONS:
                lang = user.default_lang
        
        # Get translations
        translations = get_texts(lang)
        direction = get_language_direction(lang)
        
        default_context = {
            'request': request,
            'now': datetime.now(),
            'lang': lang,
            'direction': direction,
            'get_texts': get_texts,
            't': t,
            'translate': t,
            'translations': translations,
        }
        
        # Merge with provided context (provided context takes precedence)
        merged_context = {**default_context, **context}
        
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
    """
    Get or create the templates instance.
    
    Args:
        template_dir: Templates directory path
    
    Returns:
        CustomTemplates: Templates instance
    """
    template_path = Path(template_dir)
    if not template_path.exists():
        logger.warning(f"Templates directory not found: {template_dir}")
        template_path.mkdir(parents=True, exist_ok=True)
    
    return CustomTemplates(directory=template_dir)


# Create global templates instance
try:
    templates = get_templates("templates")
    logger.info("✅ Templates initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize templates: {e}")
    # Fallback to default
    templates = Jinja2Templates(directory="templates")


# ============================================================
# HELPER FUNCTIONS FOR ROUTES
# ============================================================

async def render_template(
    request: Request,
    template_name: str,
    context: Dict[str, Any] = None,
    status_code: int = 200,
    headers: Optional[Dict[str, str]] = None,
) -> CustomTemplates.TemplateResponse:
    """
    Helper function to render templates with automatic language detection.
    
    Args:
        request: FastAPI request
        template_name: Template name
        context: Template context
        status_code: HTTP status code
        headers: HTTP headers
    
    Returns:
        TemplateResponse: Rendered template response
    """
    context = context or {}
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
        headers=headers,
    )


async def set_language_cookie(response, lang: str) -> None:
    """
    Set language cookie in response.
    
    Args:
        response: Response object
        lang: Language code
    """
    response.set_cookie(
        key="lang",
        value=lang,
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/",
        httponly=True,
        samesite="lax",
    )
