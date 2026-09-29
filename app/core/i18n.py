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

    # ══════════════════════════════════════════════════════════════════════════
    # ── Workspace ─────────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    "workspace_title":       {"ar": "مساحة العمل",              "en": "Workspace"},
    "workspace_subtitle":    {"ar": "Talk to Doc",               "en": "Talk to Doc"},
    "workspace_header_sub":  {"ar": "مساحة العمل",              "en": "Workspace"},

    # Steps
    "step_tool":             {"ar": "الأداة",                    "en": "Tool"},
    "step_file":             {"ar": "الملف",                     "en": "File"},
    "step_convert":          {"ar": "التحويل",                   "en": "Convert"},
    "step_choose_tool_hint":{"ar": "اختر أداة تحويل للبدء",     "en": "Choose a tool to start"},
    "step_choose_file_hint":{"ar": "اختر ملفاً",                 "en": "Choose a file"},
    "step_ready_hint":       {"ar": "جاهز للتحويل",              "en": "Ready to convert"},

    # Hero
    "hero_badge":            {"ar": "تحويل سريع، آمن، ومجاني 100%", "en": "Fast, secure, and 100% free conversion"},
    "hero_title_1":          {"ar": "اختر أداة التحويل",         "en": "Choose the right"},
    "hero_title_2":          {"ar": "المناسبة",                   "en": "conversion tool"},
    "hero_subtitle":         {"ar": "بعد اختيار الأداة ستنتقل لاختيار الملف المطلوب.", "en": "After choosing the tool, you'll proceed to pick the file."},

    # Tools section
    "tools_available":       {"ar": "أدوات التحويل المتاحة",     "en": "Available Conversion Tools"},
    "tools_available_hint":  {"ar": "اختر الأداة المطلوبة للبدء","en": "Choose the tool you want to start with"},
    "tool_free":             {"ar": "مجاني",                     "en": "Free"},
    "tool_start":            {"ar": "ابدأ التحويل",              "en": "Start Conversion"},
    "no_tools_found":        {"ar": "لا توجد أدوات مطابقة",      "en": "No matching tools"},
    "all_categories":        {"ar": "الكل",                      "en": "All"},
    "cat_to_pdf":            {"ar": "تحويل إلى PDF",             "en": "To PDF"},
    "cat_from_pdf":          {"ar": "تحويل من PDF",              "en": "From PDF"},
    "cat_excel":             {"ar": "أدوات Excel",               "en": "Excel Tools"},
    "cat_word_image":        {"ar": "Word والصور",               "en": "Word & Images"},

    # Active tool banner
    "active_tool_label":     {"ar": "🎯 الأداة المختارة",        "en": "🎯 Selected Tool"},
    "active_tool_hint":      {"ar": "اختر ملفاً من القائمة أدناه، أو ارفع ملفاً جديداً — الملفات المتوافقة فقط تظهر.",
                              "en": "Choose a file from the list below, or upload a new one — only compatible files are shown."},
    "change_tool":           {"ar": "تغيير الأداة",              "en": "Change Tool"},

    # Storage status
    "storage_provider":      {"ar": "مزود التخزين",              "en": "Storage Provider"},
    "total_files_lbl":       {"ar": "إجمالي الملفات",            "en": "Total Files"},
    "total_size_lbl":        {"ar": "الحجم الكلي",               "en": "Total Size"},
    "refresh":               {"ar": "تحديث",                     "en": "Refresh"},

    # Upload zone
    "drag_drop":             {"ar": "اسحب وأفلت الملفات هنا",     "en": "Drag and drop files here"},
    "file_limit":            {"ar": "الحد الأقصى 100MB لكل ملف",  "en": "Max 100MB per file"},
    "stored_in_cloud":       {"ar": "مخزن في السحابة",           "en": "Stored in cloud"},
    "choose_files":          {"ar": "اختر الملفات",              "en": "Choose Files"},
    "drop_to_upload":        {"ar": "أفلت الملفات للرفع",         "en": "Drop files to upload"},
    "uploading_to_cloud":    {"ar": "جاري الرفع إلى السحابة…",   "en": "Uploading to cloud…"},
    "one_file":              {"ar": "ملف واحد",                  "en": "one file"},
    "files_count":           {"ar": "ملفات",                     "en": "files"},

    # URL import
    "import_from_url":       {"ar": "استيراد ملف من رابط",       "en": "Import file from URL"},
    "import_url_desc":       {"ar": "أدخل رابط ملف مباشر وسيتم سحبه إلى المنصة", "en": "Enter a direct file URL and it will be fetched into the platform"},
    "enter_file_url":        {"ar": "https://example.com/file.pdf", "en": "https://example.com/file.pdf"},
    "fetching_file":         {"ar": "جاري السحب...",             "en": "Fetching..."},
    "fetch_file":            {"ar": "سحب الملف",                 "en": "Fetch File"},
    "stage_validating":      {"ar": "تحقق",                      "en": "Validate"},
    "stage_downloading":     {"ar": "تحميل",                     "en": "Download"},
    "stage_processing":      {"ar": "معالجة",                    "en": "Process"},
    "stage_saving":          {"ar": "حفظ",                       "en": "Save"},
    "importing_validate":    {"ar": "🔄 جاري التحقق من الرابط...","en": "🔄 Validating URL..."},
    "importing_download":    {"ar": "⬇️ جاري تحميل الملف...",   "en": "⬇️ Downloading file..."},
    "importing_process":     {"ar": "⚙️ جاري معالجة الملف...",   "en": "⚙️ Processing file..."},
    "importing_save":        {"ar": "💾 جاري حفظ الملف...",     "en": "💾 Saving file..."},
    "importing_success":     {"ar": "✅ تم الاستيراد بنجاح",     "en": "✅ Imported successfully"},
    "importing_failed":      {"ar": "❌ فشل الاستيراد",          "en": "❌ Import failed"},
    "importing_working":     {"ar": "⏳ جاري العمل...",          "en": "⏳ Working..."},

    # Files section
    "compatible_with":       {"ar": "ملفات متوافقة مع",         "en": "Files compatible with"},
    "only_compatible":       {"ar": "فقط الملفات المطابقة لصيغة الأداة", "en": "Only files matching the tool's format"},
    "search_files":          {"ar": "البحث في الملفات…",         "en": "Search files…"},
    "all_formats_opt":       {"ar": "جميع الصيغ",                "en": "All formats"},
    "search_btn":            {"ar": "بحث",                       "en": "Search"},
    "clear_btn":             {"ar": "مسح",                       "en": "Clear"},

    # File card actions
    "view_btn":              {"ar": "عرض",                       "en": "View"},
    "download_btn":          {"ar": "تحميل",                     "en": "Download"},
    "select_btn":            {"ar": "✓ اختر",                   "en": "✓ Select"},
    "favorite_btn":          {"ar": "المفضلة",                   "en": "Favorite"},
    "no_compatible_files":   {"ar": "لا توجد ملفات متوافقة مع هذه الأداة.", "en": "No files compatible with this tool."},
    "upload_with_format":    {"ar": "ارفع ملفاً بصيغة",           "en": "Upload a file in format"},

    # Converter screen 3
    "converter_tool_lbl":    {"ar": "الأداة",                    "en": "Tool"},
    "converter_file_lbl":    {"ar": "الملف",                     "en": "File"},
    "change_file":           {"ar": "تغيير الملف",               "en": "Change File"},
    "go_home":               {"ar": "البداية",                   "en": "Home"},

    # Footer
    "footer_copyright":      {"ar": "© 2026 Talk to Doc - جميع الحقوق محفوظة", "en": "© 2026 Talk to Doc - All rights reserved"},
    "footer_privacy":        {"ar": "سياسة الخصوصية",            "en": "Privacy Policy"},
    "footer_terms":          {"ar": "شروط الاستخدام",            "en": "Terms of Use"},
    "footer_support":        {"ar": "الدعم الفني",               "en": "Support"},

    # JS messages
    "js_choose_tool_first":  {"ar": "اختر أداة تحويل أولاً",     "en": "Choose a conversion tool first"},
    "js_panel_load_failed":  {"ar": "فشل تحميل لوحة التحويل",    "en": "Failed to load converter panel"},
    "js_invalid_url":        {"ar": "❌ الرجاء إدخال رابط صحيح",  "en": "❌ Please enter a valid URL"},
    "js_url_not_valid":      {"ar": "❌ الرابط غير صالح. تأكد من صحة الرابط", "en": "❌ Invalid URL. Please check the link"},
    "js_fetch_failed":       {"ar": "فشل السحب",                 "en": "Fetch failed"},
    "js_import_failed":      {"ar": "حدث خطأ أثناء سحب الملف",   "en": "Error while fetching the file"},
    "js_import_success":     {"ar": "✅ تم سحب الملف بنجاح",     "en": "✅ File fetched successfully"},
    "js_timeout":            {"ar": "⏰ انتهت المهلة الزمنية. حاول مرة أخرى", "en": "⏰ Timeout. Please try again"},
    "js_unknown":            {"ar": "غير معروف",                 "en": "Unknown"},
    "js_files_too_large":    {"ar": "❌ ملفات كبيرة جداً",       "en": "❌ Files too large"},
    "js_upload_success_one": {"ar": "✅ تم رفع الملف بنجاح ☁️",  "en": "✅ File uploaded successfully ☁️"},
    "js_upload_success_many":{"ar": "✅ تم رفع",                 "en": "✅ Uploaded"},
    "js_upload_success_end": {"ar": "ملفات بنجاح ☁️",           "en": "files successfully ☁️"},
    "js_upload_failed":      {"ar": "❌ فشل الرفع — حاول مجدداً","en": "❌ Upload failed — try again"},
    "js_delete_confirm":     {"ar": "هل أنت متأكد من حذف هذا الملف؟", "en": "Are you sure you want to delete this file?"},
    "js_delete_success":     {"ar": "✅ تم حذف الملف بنجاح",     "en": "✅ File deleted successfully"},
    "js_delete_failed":      {"ar": "فشل حذف الملف",             "en": "Delete failed"},
    "js_rows_unit":          {"ar": "صف",                        "en": "rows"},
    "js_cols_unit":          {"ar": "عمود",                      "en": "columns"},
    "js_sheets_unit":        {"ar": "ورقة",                      "en": "sheets"},
    "js_pages_unit":         {"ar": "صفحة",                      "en": "pages"},
    "js_file_name_lbl":      {"ar": "اسم الملف",                 "en": "File name"},
    "js_format_lbl":         {"ar": "الصيغة",                    "en": "Format"},

    # ── Tool descriptions (18 tools) ──────────────────────────────────────────
    "desc_excel_to_pdf":  {"ar": "تحويل جداول البيانات Excel إلى ملفات PDF احترافية.",
                           "en": "Convert Excel spreadsheets to professional PDF files."},
    "desc_pdf_to_excel":  {"ar": "استخراج الجداول من PDF إلى شيت Excel قابل للتعديل.",
                           "en": "Extract tables from PDF into editable Excel sheets."},
    "desc_word_to_excel": {"ar": "تحويل النصوص والبيانات من Word إلى Excel.",
                           "en": "Convert text and data from Word to Excel."},
    "desc_pdf_to_word":   {"ar": "تحويل مستندات PDF إلى Word قابلة للتعديل.",
                           "en": "Convert PDF documents to editable Word files."},
    "desc_excel_to_word": {"ar": "تصدير بيانات Excel إلى ملف Word منظم.",
                           "en": "Export Excel data into a structured Word document."},
    "desc_word_to_pdf":   {"ar": "تحويل مستندات DOCX إلى PDF سهل القراءة.",
                           "en": "Convert DOCX documents to easy-to-read PDF."},
    "desc_img_to_pdf":    {"ar": "تجميع الصور داخل مستند PDF واحد.",
                           "en": "Combine images into a single PDF document."},
    "desc_xls_to_pdf":    {"ar": "تحويل صيغ XLS القديمة إلى PDF.",
                           "en": "Convert legacy XLS files to PDF."},
    "desc_png_to_pdf":    {"ar": "تحويل صور PNG عالية الدقة إلى PDF.",
                           "en": "Convert high-resolution PNG images to PDF."},
    "desc_png_to_excel":  {"ar": "استخراج الجداول من صور PNG إلى Excel.",
                           "en": "Extract tables from PNG images into Excel."},
    "desc_xlsx_to_pdf":   {"ar": "تحويل XLSX الحديث إلى PDF متناسق.",
                           "en": "Convert modern XLSX files to consistent PDF."},
    "desc_ppt_to_pdf":    {"ar": "تحويل عروض PowerPoint إلى PDF.",
                           "en": "Convert PowerPoint presentations to PDF."},
    "desc_pdf_to_jpg":    {"ar": "استخراج صفحات PDF إلى صور JPG.",
                           "en": "Extract PDF pages as JPG images."},
    "desc_jpg_to_excel":  {"ar": "تحويل الجداول المصورة JPG إلى Excel.",
                           "en": "Convert JPG table images into Excel."},
    "desc_pdf_to_png":    {"ar": "حفظ صفحات PDF كصور PNG عالية الجودة.",
                           "en": "Save PDF pages as high-quality PNG images."},
    "desc_excel_to_csv":  {"ar": "تحويل Excel إلى صيغة CSV.",
                           "en": "Convert Excel to CSV format."},
    "desc_jpg_to_pdf":    {"ar": "تحويل صور JPG إلى مستند PDF.",
                           "en": "Convert JPG images to a PDF document."},
    "desc_excel_to_jpg":  {"ar": "تحويل الجداول والرسوم إلى صورة JPG.",
                           "en": "Convert tables and charts to a JPG image."},

    # ══════════════════════════════════════════════════════════════════════════
    # ── Convert Panel (Screen 3) ──────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    "converter_description":   {"ar": "حوّل ملفك بضغطة واحدة",         "en": "Convert your file with one click"},
    "converting_title":        {"ar": "جارٍ تحويل الملف",              "en": "Converting file"},
    "processing":              {"ar": "جاري المعالجة…",               "en": "Processing…"},
    "reading":                 {"ar": "قراءة",                          "en": "Read"},
    "analyzing":               {"ar": "تحليل",                          "en": "Analyze"},
    "converting_short":        {"ar": "تحويل",                          "en": "Convert"},
    "saving":                  {"ar": "حفظ",                            "en": "Save"},
    "conversion_success":      {"ar": "تم التحويل بنجاح!",              "en": "Conversion succeeded!"},
    "rows":                    {"ar": "صف",                             "en": "Rows"},
    "columns":                 {"ar": "عمود",                           "en": "Columns"},
    "time":                    {"ar": "المدة",                          "en": "Time"},
    "download_converted":      {"ar": "تحميل الملف الناتج",             "en": "Download converted file"},
    "new_conversion":          {"ar": "تحويل ملف آخر",                  "en": "Convert another file"},
    "retry_conversion":        {"ar": "حاول مجدداً",                    "en": "Try again"},

    # JS messages for convert panel
    "conv_starting":           {"ar": "بدء التحويل…",                   "en": "Starting conversion…"},
    "conv_reading_file":       {"ar": "جاري قراءة الملف…",              "en": "Reading file…"},
    "conv_analyzing_data":     {"ar": "جاري تحليل البيانات…",           "en": "Analyzing data…"},
    "conv_converting_data":    {"ar": "جاري تحويل البيانات…",           "en": "Converting data…"},
    "conv_saving_file":        {"ar": "جاري إنشاء وحفظ الملف…",         "en": "Creating and saving file…"},
    "conv_processing_default": {"ar": "جاري المعالجة…",                 "en": "Processing…"},
    "conv_completed_success":  {"ar": "اكتمل التحويل بنجاح",            "en": "Conversion completed successfully"},
    "conv_error_title":        {"ar": "خطأ في التحويل",                 "en": "Conversion error"},
    "conv_error_detail":       {"ar": "تعذر إتمام عملية التحويل.",      "en": "Could not complete the conversion."},
    "conv_connection_lost":    {"ar": "انقطع الاتصال",                  "en": "Connection lost"},
    "conv_connection_lost_detail": {"ar": "تعذر الاتصال بخدمة التحويل. تحقق من الاتصال وحاول مجدداً.",
                                    "en": "Could not reach the conversion service. Check your connection and try again."},
    "conv_start_failed":       {"ar": "تعذر بدء التحويل",               "en": "Could not start conversion"},
    "conv_start_failed_detail":{"ar": "حدث خطأ أثناء إنشاء اتصال التحويل. حاول مجدداً.",
                                "en": "An error occurred while opening the conversion stream. Please try again."},
    "conv_invalid_response":   {"ar": "استجابة غير صالحة",              "en": "Invalid response"},
    "conv_invalid_response_detail": {"ar": "تعذر قراءة نتيجة التحويل.", "en": "Could not read the conversion result."},
    "conv_overall_completed":  {"ar": "اكتمل",                          "en": "Completed"},
    "conv_overall_converting": {"ar": "جاري التحويل",                   "en": "Converting"},
    "conv_overall_ready":      {"ar": "جاهز للتحويل",                   "en": "Ready to convert"},
    "conv_overall_start":      {"ar": "البدء",                          "en": "Start"},
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
        return True

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
