"""
Template engine configuration for Jinja2 with custom filters, functions,
and full internationalization (i18n/l10n) support.
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

logger = logging.getLogger(__name__)


# ============================================================
# TRANSLATION / I18N - L10N
# ============================================================

# Default translations dictionary - يمكنك إضافة المزيد من اللغات
DEFAULT_TRANSLATIONS = {
    'ar': {
        # Auth
        'login': 'تسجيل الدخول',
        'login_heading': 'تسجيل الدخول',
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
        'sign_in_to_continue': 'سجل الدخول للمتابعة',
        'or_continue_with': 'أو تابع باستخدام',
        'sign_in_with_google': 'تسجيل الدخول عبر جوجل',
        'switch_lang': 'English',
        'subtitle_login': 'تسجيل الدخول إلى منصة الجداول الذكية',
        'admin_login': 'دخول الإدارة',
        'admin_only': 'للمسؤولين فقط',
        'back_to_client_login': 'العودة إلى تسجيل دخول العميل',
        'email_placeholder': 'example@email.com',
        'password_placeholder': '••••••••',
        'logout_success': 'تم تسجيل الخروج بنجاح',
        
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
        'file_not_found': 'الملف غير موجود',
        'file_too_large': 'الملف كبير جداً',
        'unsupported_format': 'صيغة غير مدعومة',
        
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
        'invalid_credentials': 'بيانات الدخول غير صحيحة',
        'user_not_found': 'المستخدم غير موجود',
        'email_exists': 'البريد الإلكتروني موجود مسبقاً',
        'passwords_mismatch': 'كلمات المرور غير متطابقة',
        'password_reset_sent': 'تم إرسال رابط إعادة التعيين',
        'session_expired': 'انتهت صلاحية الجلسة',
        'state_mismatch': 'انتهت صلاحية جلسة تسجيل الدخول. حاول مجدداً.',
        'google_not_configured': 'تسجيل الدخول عبر جوجل غير مفعّل.',
        'access_denied': 'تم رفض الإذن من جوجل. حاول مجدداً.',
        'invalid_request': 'طلب غير صالح. حاول مجدداً.',
        'no_token': 'يرجى تسجيل الدخول للمتابعة.',
        
        # Languages
        'arabic': 'العربية',
        'english': 'الإنجليزية',
        'french': 'الفرنسية',
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
        
        # Navigation
        'navigation': 'القائمة',
        'menu': 'القائمة',
        'toggle_navigation': 'تبديل القائمة',
        
        # Errors
        'page_not_found': 'الصفحة غير موجودة',
        'server_error': 'خطأ في الخادم',
        'bad_request': 'طلب غير صحيح',
        'unauthorized': 'غير مصرح',
        'forbidden': 'ممنوع',
        
        # Common
        'or': 'أو',
        'and': 'و',
        'with': 'مع',
        'from': 'من',
        'to': 'إلى',
        'for': 'لـ',
        'of': 'من',
        'in': 'في',
        'on': 'على',
        'at': 'في',
    },
    'en': {
        # Auth
        'login': 'Login',
        'login_heading': 'Login',
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
        'sign_in_to_continue': 'Sign in to continue',
        'or_continue_with': 'Or continue with',
        'sign_in_with_google': 'Sign in with Google',
        'switch_lang': 'العربية',
        'subtitle_login': 'Login to Smart Spreadsheet Platform',
        'admin_login': 'Admin Login',
        'admin_only': 'For Administrators Only',
        'back_to_client_login': 'Back to Client Login',
        'email_placeholder': 'example@email.com',
        'password_placeholder': '••••••••',
        'logout_success': 'Logged out successfully',
        
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
        'file_not_found': 'File Not Found',
        'file_too_large': 'File is too large',
        'unsupported_format': 'Unsupported format',
        
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
        'invalid_credentials': 'Invalid credentials',
        'user_not_found': 'User not found',
        'email_exists': 'Email already exists',
        'passwords_mismatch': 'Passwords do not match',
        'password_reset_sent': 'Password reset link sent',
        'session_expired': 'Session expired',
        'state_mismatch': 'Login session expired. Please try again.',
        'google_not_configured': 'Google login is not configured.',
        'access_denied': 'Access denied from Google. Please try again.',
        'invalid_request': 'Invalid request. Please try again.',
        'no_token': 'Please login to continue.',
        
        # Languages
        'arabic': 'Arabic',
        'english': 'English',
        'french': 'French',
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
        
        # Navigation
        'navigation': 'Navigation',
        'menu': 'Menu',
        'toggle_navigation': 'Toggle Navigation',
        
        # Errors
        'page_not_found': 'Page Not Found',
        'server_error': 'Server Error',
        'bad_request': 'Bad Request',
        'unauthorized': 'Unauthorized',
        'forbidden': 'Forbidden',
        
        # Common
        'or': 'or',
        'and': 'and',
        'with': 'with',
        'from': 'from',
        'to': 'to',
        'for': 'for',
        'of': 'of',
        'in': 'in',
        'on': 'on',
        'at': 'at',
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
    if not lang or lang not in DEFAULT_TRANSLATIONS:
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


def get_supported_languages() -> Dict[str, str]:
    """
    Get supported languages with their names.
    
    Returns:
        Dict: Language code -> Language name
    """
    return {
        'ar': 'العربية',
        'en': 'English',
        'fr': 'Français',
    }


def is_rtl_language(lang: str) -> bool:
    """
    Check if a language is RTL.
    
    Args:
        lang: Language code
    
    Returns:
        bool: True if RTL
    """
    return get_language_direction(lang) == 'rtl'


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


def tojson_safe(value: Any, indent: Optional[int] = None) -> Markup:
    """
    Convert to JSON safely for HTML.
    
    Example:
        {{ my_data|tojson_safe }}
    """
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


def time_ago(value: Any, lang: str = 'ar') -> str:
    """
    Display time as "X minutes ago" or "X days ago".
    
    Example:
        {{ my_date|time_ago }}
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
            return t('now', lang)
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return t('minutes_ago', lang, minutes=minutes)
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return t('hours_ago', lang, hours=hours)
        elif seconds < 604800:
            days = int(seconds / 86400)
            return t('days_ago', lang, days=days)
        elif seconds < 2592000:  # 30 days
            weeks = int(seconds / 604800)
            return t('weeks_ago', lang, weeks=weeks)
        else:
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def format_size(value: Any) -> str:
    """
    Format file size in human readable format.
    
    Example:
        {{ file_size|format_size }}
    """
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
    """
    Get an icon for a file type.
    
    Example:
        {{ file_format|file_icon }}
    """
    if value is None:
        return "📄"
    
    ext = str(value).lower()
    
    icons = {
        # Documents
        'pdf': '📕', 'doc': '📄', 'docx': '📄', 'txt': '📝', 'rtf': '📝',
        'odt': '📄', 'md': '📝', 'rst': '📝',
        
        # Spreadsheets
        'xls': '📊', 'xlsx': '📊', 'xlsm': '📊', 'xlsb': '📊', 'ods': '📊',
        'csv': '📋', 'tsv': '📋',
        
        # Presentations
        'ppt': '📊', 'pptx': '📊', 'odp': '📊',
        
        # Code & Data
        'json': '📄', 'xml': '📰', 'html': '🌐', 'htm': '🌐',
        'css': '🎨', 'js': '🟡', 'py': '🐍', 'java': '☕',
        'c': '⚙️', 'cpp': '⚙️', 'go': '🐹', 'rs': '🦀',
        'php': '🐘', 'sql': '🗄️', 'yaml': '📄', 'yml': '📄',
        'parquet': '📦', 'feather': '🪶', 'arrow': '🏹',
        
        # Images
        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️',
        'webp': '🖼️', 'svg': '🖼️', 'ico': '🖼️', 'bmp': '🖼️',
        'tiff': '🖼️', 'heic': '🖼️', 'raw': '🖼️',
        
        # Archives
        'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
        'bz2': '📦', 'xz': '📦',
        
        # Media
        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
        'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬',
        
        # Other
        'exe': '⚙️', 'msi': '⚙️', 'dmg': '💿', 'iso': '💿',
    }
    
    return icons.get(ext, '📄')


def truncate_text(value: Any, length: int = 100, suffix: str = '...') -> str:
    """
    Truncate text to a specific length.
    
    Example:
        {{ long_text|truncate_text(50) }}
    """
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
# CUSTOM TESTS
# ============================================================

def is_image(value: str) -> bool:
    """Check if a file is an image."""
    if not value:
        return False
    ext = str(value).lower()
    image_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'ico', 'bmp', 'tiff', 'heic'}
    return ext in image_extensions


def is_video(value: str) -> bool:
    """Check if a file is a video."""
    if not value:
        return False
    ext = str(value).lower()
    video_extensions = {'mp4', 'avi', 'mkv', 'mov', 'wmv', 'flv', 'webm'}
    return ext in video_extensions


def is_audio(value: str) -> bool:
    """Check if a file is an audio file."""
    if not value:
        return False
    ext = str(value).lower()
    audio_extensions = {'mp3', 'wav', 'flac', 'aac', 'ogg', 'wma'}
    return ext in audio_extensions


def is_document(value: str) -> bool:
    """Check if a file is a document."""
    if not value:
        return False
    ext = str(value).lower()
    document_extensions = {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'md', 'rst'}
    return ext in document_extensions


def is_spreadsheet(value: str) -> bool:
    """Check if a file is a spreadsheet."""
    if not value:
        return False
    ext = str(value).lower()
    spreadsheet_extensions = {'xls', 'xlsx', 'xlsm', 'xlsb', 'ods', 'csv', 'tsv'}
    return ext in spreadsheet_extensions


# ============================================================
# TEMPLATE CONFIGURATION
# ============================================================

class CustomTemplates(Jinja2Templates):
    """
    Custom Jinja2 templates with additional filters, functions, and tests.
    """
    
    def __init__(self, directory: str, auto_reload: bool = True):
        """
        Initialize custom templates.
        
        Args:
            directory: Templates directory path
            auto_reload: Auto reload templates in development
        """
        # ✅ إصلاح: إزالة auto_reload من super()
        super().__init__(directory=directory)
        
        # ✅ تعيين auto_reload يدوياً إذا كان مدعوماً
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
        # Core filters
        self.env.filters['escapejs'] = escapejs
        self.env.filters['tojson_safe'] = tojson_safe
        self.env.filters['time_ago'] = time_ago
        self.env.filters['format_size'] = format_size
        self.env.filters['file_icon'] = file_icon
        self.env.filters['truncate_text'] = truncate_text
        self.env.filters['t'] = translate_filter
        self.env.filters['translate'] = translate_filter
        
        # JSON filters
        self.env.filters['json'] = lambda v: json.dumps(v, ensure_ascii=False, default=str)
        self.env.filters['pretty_json'] = lambda v: json.dumps(v, ensure_ascii=False, indent=2, default=str)
    
    def _add_globals(self):
        """Add global functions and variables to the environment."""
        self.env.globals.update({
            # Time
            'now': datetime.now,
            'today': lambda: datetime.now().date(),
            
            # Translation
            'get_texts': get_texts,
            't': t,
            'translate': t,
            'get_language_direction': get_language_direction,
            'get_supported_languages': get_supported_languages,
            'is_rtl_language': is_rtl_language,
            'DEFAULT_TRANSLATIONS': DEFAULT_TRANSLATIONS,
            
            # JSON
            'json_dumps': lambda v, **kwargs: json.dumps(v, ensure_ascii=False, **kwargs),
            
            # Helpers
            'range': lambda start, end: range(start, end),
            'dict_get': lambda d, key, default=None: d.get(key, default) if d else default,
            'list_get': lambda l, index, default=None: l[index] if l and 0 <= index < len(l) else default,
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
        # Get language from various sources
        lang = context.get('lang')
        
        # Try from request state
        if not lang and hasattr(request.state, 'lang'):
            lang = request.state.lang
        
        # Try from cookie
        if not lang and hasattr(request, 'cookies'):
            lang = request.cookies.get('lang')
        
        # Try from user in request state
        if not lang and hasattr(request.state, 'user'):
            user = request.state.user
            if user and hasattr(user, 'default_lang') and user.default_lang:
                lang = user.default_lang
        
        # Default
        if not lang or lang not in DEFAULT_TRANSLATIONS:
            lang = 'ar'
        
        # Get translations and direction
        translations = get_texts(lang)
        direction = get_language_direction(lang)
        
        # Get user from request state
        user = getattr(request.state, 'user', None)
        
        # Build default context
        default_context = {
            'request': request,
            'now': datetime.now(),
            'lang': lang,
            'direction': direction,
            'translations': translations,
            'user': user,
            'is_authenticated': user is not None and getattr(user, 'is_active', False),
            'get_texts': get_texts,
            't': t,
            'translate': t,
            'get_language_direction': get_language_direction,
            'get_supported_languages': get_supported_languages,
            'is_rtl_language': is_rtl_language,
            'DEFAULT_TRANSLATIONS': DEFAULT_TRANSLATIONS,
        }
        
        # Merge with provided context (provided context takes precedence)
        merged_context = {**default_context, **context}
        
        # Store language in request state for future use
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
    """
    Get or create the templates instance.
    
    Args:
        template_dir: Templates directory path
    
    Returns:
        CustomTemplates: Templates instance
    """
    template_path = Path(template_dir)
    if not template_path.exists():
        logger.warning(f"⚠️ Templates directory not found: {template_dir}")
        template_path.mkdir(parents=True, exist_ok=True)
    
    try:
        return CustomTemplates(directory=template_dir)
    except Exception as e:
        logger.error(f"❌ Failed to initialize custom templates: {e}")
        # Fallback to default Jinja2Templates
        return Jinja2Templates(directory=template_dir)


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


async def set_language_cookie(response: Response, lang: str, max_age: int = 60 * 60 * 24 * 30) -> None:
    """
    Set language cookie in response.
    
    Args:
        response: Response object
        lang: Language code
        max_age: Cookie max age in seconds
    """
    if lang not in DEFAULT_TRANSLATIONS:
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
    """
    Clear language cookie.
    
    Args:
        response: Response object
    """
    response.delete_cookie(key="lang", path="/")


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    # Main instance
    'templates',
    'CustomTemplates',
    'get_templates',
    'render_template',
    
    # Translation
    'get_texts',
    't',
    'get_language_direction',
    'get_supported_languages',
    'is_rtl_language',
    'DEFAULT_TRANSLATIONS',
    
    # Filters
    'escapejs',
    'tojson_safe',
    'time_ago',
    'format_size',
    'file_icon',
    'truncate_text',
    
    # Tests
    'is_image',
    'is_video',
    'is_audio',
    'is_document',
    'is_spreadsheet',
    
    # Helpers
    'set_language_cookie',
    'clear_language_cookie',
]
