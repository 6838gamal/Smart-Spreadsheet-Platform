"""
Bilingual translations — Arabic (ar) and English (en).

Usage in routes:
    lang = user.default_lang or request.cookies.get("lang", "ar")
    return templates.TemplateResponse("page.html", {"request": request, "lang": lang})

Usage in templates:
    {% set t = get_texts(lang) %}
    {{ t.get('nav_dashboard') }}
    {{ t['nav_dashboard'] }}       {# dict-style, also works #}
"""

from typing import Dict, Iterator, Iterable


# ============================================================
# SUPPORTED LANGUAGES
# ============================================================

SUPPORTED_LANGUAGES: tuple[str, ...] = ("ar", "en")
DEFAULT_LANGUAGE: str = "ar"


# ============================================================
# TRANSLATIONS DICTIONARY
# ============================================================

_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── Navigation ────────────────────────────────────────────────────────────
    "nav_workspace":    {"ar": "مساحة العمل",       "en": "Workspace"},
    "nav_dashboard":    {"ar": "لوحة التحكم",       "en": "Dashboard"},
    "nav_intelligence": {"ar": "ذكاء المستندات",     "en": "Doc Intelligence"},
    "nav_files":        {"ar": "إدارة الملفات",      "en": "Files"},
    "nav_converter":    {"ar": "محول الصيغ",         "en": "Converter"},
    "nav_cleaner":      {"ar": "تنظيف البيانات",     "en": "Data Cleaner"},
    "nav_merger":       {"ar": "دمج الملفات",        "en": "Merge Files"},
    "nav_analytics":    {"ar": "التحليلات",          "en": "Analytics"},
    "nav_datasets":     {"ar": "مجموعات البيانات",   "en": "Datasets"},
    "nav_models":       {"ar": "مدير النماذج",       "en": "Model Manager"},
    "nav_search":       {"ar": "البحث الذكي",         "en": "Smart Search"},
    "nav_logs":         {"ar": "سجل العمليات",       "en": "Operation Logs"},
    "nav_settings":     {"ar": "الإعدادات",          "en": "Settings"},
    "nav_contact":      {"ar": "تواصل مع المطور",    "en": "Contact Developer"},
    "contact_modal_title": {"ar": "تواصل مع المطور", "en": "Contact Developer"},
    "contact_close":    {"ar": "إغلاق",              "en": "Close"},

    # ── Topbar ────────────────────────────────────────────────────────────────
    "upload_file":      {"ar": "رفع ملف",            "en": "Upload"},
    "toggle_theme":     {"ar": "تبديل الوضع",        "en": "Toggle Theme"},
    "logout":           {"ar": "تسجيل الخروج",       "en": "Logout"},
    "switch_lang":      {"ar": "English",             "en": "عربي"},

    # ── Common ────────────────────────────────────────────────────────────────
    "view_all":         {"ar": "عرض الكل",           "en": "View All"},
    "search":           {"ar": "بحث",                "en": "Search"},
    "clear":            {"ar": "مسح",                "en": "Clear"},
    "view":             {"ar": "عرض",                "en": "View"},
    "download":         {"ar": "تحميل",              "en": "Download"},
    "convert":          {"ar": "تحويل",              "en": "Convert"},
    "delete":           {"ar": "حذف",                "en": "Delete"},
    "source_file":      {"ar": "الملف المصدر",       "en": "Source File"},
    "choose_file":      {"ar": "اختر ملفاً...",      "en": "Choose a file..."},
    "upload_first_link":{"ar": "ارفع ملفاً",         "en": "Upload a file"},
    "first_word":       {"ar": "أولاً",              "en": "first"},
    "output_format":    {"ar": "صيغة الإخراج",       "en": "Output Format"},
    "start_btn":        {"ar": "بدء",                "en": "Start"},
    "uploading":        {"ar": "جاري الرفع...",      "en": "Uploading..."},
    "rows_unit":        {"ar": "صف",                 "en": "rows"},
    "cols_unit":        {"ar": "عمود",               "en": "columns"},
    "no_ops":           {"ar": "لا توجد عمليات",     "en": "No operations"},

    # ── Dashboard ─────────────────────────────────────────────────────────────
    "stat_files":       {"ar": "الملفات",            "en": "Files"},
    "stat_size":        {"ar": "إجمالي الحجم",       "en": "Total Size"},
    "stat_ops":         {"ar": "العمليات",           "en": "Operations"},
    "stat_favorites":   {"ar": "المفضلة",            "en": "Favorites"},
    "recent_files":     {"ar": "آخر الملفات",        "en": "Recent Files"},
    "no_files_yet":     {"ar": "لا توجد ملفات بعد", "en": "No files yet"},
    "upload_first":     {"ar": "ارفع ملفك الأول",   "en": "Upload your first file"},
    "recent_ops":       {"ar": "آخر العمليات",       "en": "Recent Operations"},
    "format_dist":      {"ar": "توزيع الصيغ",        "en": "Format Distribution"},
    "quick_actions":    {"ar": "إجراءات سريعة",      "en": "Quick Actions"},
    "action_upload":    {"ar": "رفع ملف",            "en": "Upload File"},
    "action_convert":   {"ar": "تحويل صيغة",        "en": "Convert Format"},
    "action_clean":     {"ar": "تنظيف بيانات",       "en": "Clean Data"},
    "action_merge":     {"ar": "دمج ملفات",          "en": "Merge Files"},

    # ── Files ─────────────────────────────────────────────────────────────────
    "drag_drop":        {"ar": "اسحب وأفلت الملفات هنا",              "en": "Drag and drop files here"},
    "file_limit":       {"ar": "xlsx, csv, json, pdf والمزيد · الحد الأقصى 500MB", "en": "xlsx, csv, json, pdf and more · Max 500MB"},
    "choose_files":     {"ar": "اختر ملفات",         "en": "Choose Files"},
    "search_files":     {"ar": "بحث في الملفات...",  "en": "Search files..."},
    "all_formats":      {"ar": "كل الصيغ",           "en": "All Formats"},
    "confirm_delete":   {"ar": "حذف هذا الملف؟",    "en": "Delete this file?"},
    "no_files_empty":   {"ar": "لا توجد ملفات",      "en": "No files"},
    "upload_to_start":  {"ar": "ارفع ملفاتك للبدء في المعالجة", "en": "Upload your files to start processing"},
    "favorite":         {"ar": "مفضلة",              "en": "Favorite"},

    # ── Converter ─────────────────────────────────────────────────────────────
    "convert_file":     {"ar": "تحويل ملف",          "en": "Convert File"},
    "sheet_opt":        {"ar": "الورقة (اختياري)",   "en": "Sheet (optional)"},
    "sheet_hint":       {"ar": "اسم الورقة أو فارغ للأولى", "en": "Sheet name or empty for first"},
    "target_format":    {"ar": "الصيغة المستهدفة",   "en": "Target Format"},
    "start_convert":    {"ar": "بدء التحويل",        "en": "Start Conversion"},
    "converting":       {"ar": "جاري التحويل...",    "en": "Converting..."},
    "result":           {"ar": "النتيجة",            "en": "Result"},
    "choose_to_convert":{"ar": "اختر ملفاً وصيغة لبدء التحويل", "en": "Choose a file and format to start converting"},
    "supported_formats":{"ar": "الصيغ المدعومة",     "en": "Supported Formats"},
    "import_formats":   {"ar": "استيراد",            "en": "Import"},
    "export_formats_lbl":{"ar": "تصدير",             "en": "Export"},

    # ── Cleaner ───────────────────────────────────────────────────────────────
    "clean_options":    {"ar": "خيارات التنظيف",     "en": "Cleaning Options"},
    "clean_ops_lbl":    {"ar": "عمليات التنظيف",     "en": "Cleaning Operations"},
    "remove_dups":      {"ar": "حذف الصفوف المكررة", "en": "Remove Duplicate Rows"},
    "trim_spaces":      {"ar": "حذف المسافات الزائدة","en": "Trim Whitespace"},
    "remove_empty_rows":{"ar": "حذف الصفوف الفارغة", "en": "Remove Empty Rows"},
    "remove_empty_cols":{"ar": "حذف الأعمدة الفارغة","en": "Remove Empty Columns"},
    "fill_nulls":       {"ar": "استبدال القيم الفارغة بـ", "en": "Replace empty values with"},
    "fill_placeholder": {"ar": 'مثال: 0 أو "N/A" (اتركه فارغاً لتجاهله)', "en": 'e.g. 0 or "N/A" (leave empty to skip)'},
    "start_clean":      {"ar": "بدء التنظيف",        "en": "Start Cleaning"},
    "cleaning":         {"ar": "جاري التنظيف...",    "en": "Cleaning..."},
    "clean_result":     {"ar": "نتيجة التنظيف",      "en": "Cleaning Result"},
    "choose_to_clean":  {"ar": 'اختر ملفاً وخيارات التنظيف ثم اضغط "بدء التنظيف"', "en": 'Choose a file and options then click "Start Cleaning"'},
    "what_cleaned":     {"ar": "ما يمكن تنظيفه",     "en": "What can be cleaned"},
    "feat_dups":        {"ar": "حذف الصفوف المكررة", "en": "Remove duplicate rows"},
    "feat_spaces":      {"ar": "حذف المسافات الزائدة","en": "Trim whitespace"},
    "feat_empty_rows":  {"ar": "حذف الصفوف الفارغة", "en": "Remove empty rows"},
    "feat_empty_cols":  {"ar": "حذف الأعمدة الفارغة","en": "Remove empty columns"},
    "feat_fill_null":   {"ar": "استبدال القيم الفارغة","en": "Fill null values"},
    "feat_norm_types":  {"ar": "توحيد أنواع البيانات","en": "Normalize data types"},
    "feat_norm_dates":  {"ar": "توحيد التواريخ",     "en": "Normalize dates"},
    "feat_arabic":      {"ar": "تنظيف النصوص العربية","en": "Clean Arabic text"},

    # ── Merger ────────────────────────────────────────────────────────────────
    "merger_desc":      {"ar": "يمكنك دمج ملفات متعددة، دمج أوراق Excel، ودمج البيانات حسب الأعمدة المشتركة أو المفاتيح الأساسية.",
                         "en": "Merge multiple files, Excel sheets, or data by shared columns or primary keys."},
    "choose_to_merge":  {"ar": "اختر الملفات للدمج", "en": "Choose files to merge"},
    "merge_method":     {"ar": "طريقة الدمج",        "en": "Merge Method"},
    "merge_vertical":   {"ar": "رأسي (Append)",       "en": "Vertical (Append)"},
    "merge_horizontal": {"ar": "أفقي (Join)",         "en": "Horizontal (Join)"},
    "merge_by_col":     {"ar": "دمج حسب عمود مشترك", "en": "Merge by common column"},
    "coming_soon_note": {"ar": "قيد قادم: ميزة الدمج الكامل ستتوفر في الإصدار التالي. يمكنك في الوقت الحالي استخدام تحويل الصيغ للعمل مع الملفات الفردية.",
                         "en": "Coming soon: Full merge will be available in the next release. For now, use the converter for individual files."},
    "upload_first_btn": {"ar": "ارفع ملفات أولاً",  "en": "Upload Files First"},

    # ── Settings ──────────────────────────────────────────────────────────────
    "profile":          {"ar": "الملف الشخصي",       "en": "Profile"},
    "preferences":      {"ar": "التفضيلات",          "en": "Preferences"},
    "theme":            {"ar": "السمة",              "en": "Theme"},
    "theme_dark":       {"ar": "🌙 داكنة",           "en": "🌙 Dark"},
    "theme_light":      {"ar": "☀️ فاتحة",           "en": "☀️ Light"},
    "language":         {"ar": "اللغة",              "en": "Language"},
    "lang_ar":          {"ar": "🇸🇦 العربية",         "en": "🇸🇦 Arabic"},
    "lang_en":          {"ar": "🇺🇸 إنجليزية",        "en": "🇺🇸 English"},
    "save_prefs":       {"ar": "حفظ التفضيلات",      "en": "Save Preferences"},
    "saved_ok":         {"ar": "✓ تم الحفظ",         "en": "✓ Saved"},
    "app_info":         {"ar": "معلومات التطبيق",    "en": "App Info"},
    "platform_name":    {"ar": "اسم المنصة",         "en": "Platform Name"},
    "version":          {"ar": "الإصدار",            "en": "Version"},
    "data_engine":      {"ar": "محرك البيانات",      "en": "Data Engine"},
    "interface_lbl":    {"ar": "الواجهة",            "en": "Interface"},
    "storage":          {"ar": "التخزين",            "en": "Storage"},
    "storage_type":     {"ar": "نوع التخزين",        "en": "Storage Type"},

    # ── Logs ──────────────────────────────────────────────────────────────────
    "op_type":          {"ar": "النوع",              "en": "Type"},
    "op_status":        {"ar": "الحالة",             "en": "Status"},
    "op_file":          {"ar": "الملف",              "en": "File"},
    "op_duration":      {"ar": "المدة",              "en": "Duration"},
    "op_date":          {"ar": "التاريخ",            "en": "Date"},
    "status_success":   {"ar": "نجح",                "en": "Success"},
    "status_failed":    {"ar": "فشل",                "en": "Failed"},
    "status_running":   {"ar": "جارٍ",               "en": "Running"},
    "status_pending":   {"ar": "معلق",               "en": "Pending"},
    "no_logs":          {"ar": "لا توجد سجلات",      "en": "No logs found"},
    "ops_count":        {"ar": "عملية",              "en": "operations"},

    # ── Auth ──────────────────────────────────────────────────────────────────
    "login_heading":    {"ar": "تسجيل الدخول",       "en": "Login"},
    "subtitle_login":   {"ar": "منصة إدارة ومعالجة البيانات الاحترافية", "en": "Professional data management platform"},
    "subtitle_register":{"ar": "أنشئ حسابك وابدأ الآن", "en": "Create your account and get started"},
    "email_lbl":        {"ar": "البريد الإلكتروني",  "en": "Email"},
    "password_lbl":     {"ar": "كلمة المرور",        "en": "Password"},
    "login_btn":        {"ar": "دخول",               "en": "Login"},
    "no_account":       {"ar": "ليس لديك حساب؟",    "en": "Don't have an account?"},
    "create_account":   {"ar": "إنشاء حساب",         "en": "Create account"},
    "register_heading": {"ar": "إنشاء حساب جديد",   "en": "Create New Account"},
    "username_lbl":     {"ar": "اسم المستخدم",       "en": "Username"},
    "confirm_password_lbl": {"ar": "تأكيد كلمة المرور", "en": "Confirm Password"},
    "confirm_placeholder":  {"ar": "أعد كتابة كلمة المرور", "en": "Re-enter password"},
    "password_min":     {"ar": "8 أحرف على الأقل",  "en": "At least 8 characters"},
    "register_btn":     {"ar": "إنشاء الحساب",       "en": "Create Account"},
    "have_account":     {"ar": "لديك حساب بالفعل؟", "en": "Already have an account?"},
    "login_link":       {"ar": "تسجيل الدخول",       "en": "Login"},
}


# ============================================================
# TEXTS CLASS
# ============================================================

class Texts:
    """
    Dot-access + dict-access wrapper around a language slice of _TRANSLATIONS.

    Supports:
        t.get('nav_dashboard')          → "لوحة التحكم"
        t['nav_dashboard']              → "لوحة التحكم"
        t.nav_dashboard                 → "لوحة التحكم"
        'nav_dashboard' in t            → True
        for key in t: ...               → iterate keys
        t.keys() / t.values() / t.items()
        t.to_dict()                     → plain dict for current lang
    """

    __slots__ = ("_lang",)

    def __init__(self, lang: str) -> None:
        self._lang = lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    # ── Properties ────────────────────────────────────────────────────────────
    @property
    def lang(self) -> str:
        """Current language code."""
        return self._lang

    # ── Core access ───────────────────────────────────────────────────────────
    def _resolve(self, key: str, default: str | None = None) -> str | None:
        entry = _TRANSLATIONS.get(key)
        if entry is None:
            return default
        return entry.get(self._lang) or entry.get(DEFAULT_LANGUAGE) or default

    def get(self, key: str, default: str = "") -> str:
        """dict-style .get() — always returns a string."""
        result = self._resolve(key, None)
        return result if result is not None else default

    def __getitem__(self, key: str) -> str:
        """dict-style t['key'] — raises KeyError if missing."""
        result = self._resolve(key, None)
        if result is None:
            raise KeyError(key)
        return result

    def __getattr__(self, key: str) -> str:
        """dot-style t.key — falls back to the key name if missing."""
        # Avoid recursion during unpickling / copy
        if key.startswith("__") and key.endswith("__"):
            raise AttributeError(key)
        result = self._resolve(key, None)
        return result if result is not None else key

    # ── Container protocol ────────────────────────────────────────────────────
    def __contains__(self, key: object) -> bool:
        return isinstance(key, str) and key in _TRANSLATIONS

    def __iter__(self) -> Iterator[str]:
        return iter(_TRANSLATIONS)

    def __len__(self) -> int:
        return len(_TRANSLATIONS)

    def __bool__(self) -> bool:
        return True  # a Texts instance is always truthy

    # ── dict-like views ───────────────────────────────────────────────────────
    def keys(self):
        return _TRANSLATIONS.keys()

    def values(self) -> Iterable[str]:
        for k in _TRANSLATIONS:
            yield self.get(k)

    def items(self):
        for k in _TRANSLATIONS:
            yield k, self.get(k)

    def to_dict(self) -> Dict[str, str]:
        """Return a plain {key: value} dict for the current language."""
        return {
            k: (v.get(self._lang) or v.get(DEFAULT_LANGUAGE, k))
            for k, v in _TRANSLATIONS.items()
        }

    # ── Debug / repr ──────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        return f"Texts(lang={self._lang!r}, keys={len(_TRANSLATIONS)})"


# ============================================================
# PUBLIC API
# ============================================================

def get_texts(lang: str = DEFAULT_LANGUAGE) -> Texts:
    """Return a Texts wrapper for the given language code."""
    return Texts(lang)


def get_translation(key: str, lang: str = DEFAULT_LANGUAGE, default: str = "") -> str:
    """Direct one-shot translation lookup."""
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return default
    return entry.get(lang) or entry.get(DEFAULT_LANGUAGE, default)


def get_language_direction(lang: str = DEFAULT_LANGUAGE) -> str:
    """Return 'rtl' for RTL languages, 'ltr' otherwise."""
    return "rtl" if lang in ("ar", "fa", "he", "ur") else "ltr"


def is_rtl_language(lang: str) -> bool:
    """True if the given language uses RTL direction."""
    return get_language_direction(lang) == "rtl"


def get_supported_languages() -> Dict[str, str]:
    """Return {code: native_name} for all supported languages."""
    return {
        "ar": "العربية",
        "en": "English",
    }


def is_supported(lang: str) -> bool:
    """Check if a language code is supported."""
    return lang in SUPPORTED_LANGUAGES


# ============================================================
# EXPORTS
# ============================================================

__all__ = [
    "SUPPORTED_LANGUAGES",
    "DEFAULT_LANGUAGE",
    "Texts",
    "get_texts",
    "get_translation",
    "get_language_direction",
    "is_rtl_language",
    "get_supported_languages",
    "is_supported",
]
