# Document Intelligence Platform — وثيقة التصميم الشاملة

> الإصدار 1.0 | بناءً على Smart Spreadsheet Platform الحالية

---

## 1. Architecture الكاملة

### مبدأ التصميم: Modular Microservices داخل Monolith

النظام يعتمد **Modular Monolith** في المرحلة الأولى، مع إمكانية فصل كل Service إلى Microservice مستقل لاحقاً دون إعادة كتابة.

```
┌─────────────────────────────────────────────────────────────────┐
│                     API Gateway (FastAPI)                        │
│              Authentication · Rate Limiting · Routing            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Web UI      │  │  REST API    │  │  WebSocket   │
│  (Jinja2+    │  │  v1 / v2    │  │  (Job Status)│
│   HTMX)      │  │             │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
┌─────────┐         ┌─────────────┐        ┌─────────────┐
│Document │         │  Job Queue  │        │  Model      │
│Pipeline │         │  (Internal) │        │  Registry   │
│Manager  │         │             │        │             │
└────┬────┘         └─────────────┘        └─────────────┘
     │
     ▼  يمر عبر هذه الخدمات بالترتيب:
┌────────────────────────────────────────────────────────────────┐
│                        Service Layer                            │
│                                                                │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │  OCR    │ │  Layout  │ │  Table   │ │  Classification  │  │
│  │ Service │ │Detection │ │Detection │ │    Service       │  │
│  └─────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│                                                                │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   NER   │ │ Cleaning │ │Conversion│ │     Search       │  │
│  │ Service │ │ Service  │ │ Service  │ │    Service       │  │
│  └─────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
│                                                                │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │Feedback │ │ Dataset  │ │Training  │ │   Analytics      │  │
│  │ Service │ │ Builder  │ │ Service  │ │    Service       │  │
│  └─────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└────────────────────────────────────────────────────────────────┘
     │
     ▼
┌────────────────────────────────────────────────────────────────┐
│                      Infrastructure Layer                       │
│                                                                │
│   PostgreSQL  ·  File Storage  ·  Vector Store  ·  Cache       │
└────────────────────────────────────────────────────────────────┘
```

### نموذج المعالجة (Document Processing Flow)

```
Upload
  │
  ▼
[1] File Validation & Storage
  │
  ▼
[2] Document Classification Service
  │   → يحدد: Invoice / Contract / CV / Report / ...
  │   → يختار Pipeline المناسبة
  ▼
[3] Layout Detection Service
  │   → Paragraphs, Headers, Tables, Images, ...
  │   → يحفظ Bounding Boxes
  ▼
[4] OCR Service  (إذا كان الملف صورة أو PDF مسح ضوئي)
  │   → PaddleOCR للعربي والإنجليزي
  │   → تصحيح تلقائي
  ▼
[5] Table Detection Service
  │   → Table Transformer (TATR)
  │   → استخراج الخلايا المدمجة والعلاقات
  ▼
[6] Entity Extraction (NER) Service
  │   → GLiNER / ModernBERT
  │   → حسب نوع المستند
  ▼
[7] Cleaning Service
  │   → توحيد التواريخ، العملات، الأرقام
  │   → إزالة التكرارات
  ▼
[8] AI Suggestions Engine
  │   → يعرض اقتراحات للمستخدم
  ▼
[9] Transformation / Export
  │   → Excel, Word, PDF, JSON, CSV, ...
  ▼
[10] Feedback & Dataset Builder
       → تسجيل كل تعديل
       → بناء Dataset للتدريب
```

---

## 2. هيكل المجلدات

```
smart-spreadsheet-platform/
│
├── main.py                          # FastAPI entry point (موجود)
├── pyproject.toml
├── uv.lock
│
├── app/
│   ├── core/                        # موجود — لا يُعدَّل
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── ...
│   │
│   ├── application/                 # Use cases (موجود)
│   │
│   ├── infrastructure/
│   │   ├── database/
│   │   │   ├── models.py            # موجود — يُوسَّع
│   │   │   └── models_intelligence.py  ← جديد: نماذج AI
│   │   ├── repositories/            # موجود
│   │   └── ai/                      ← جديد: تحميل النماذج
│   │       ├── model_registry.py
│   │       ├── model_loader.py
│   │       └── model_cache.py
│   │
│   ├── services/                    ← جديد: AI Services
│   │   ├── __init__.py
│   │   ├── pipeline/
│   │   │   ├── pipeline_manager.py     # يختار Pipeline حسب نوع المستند
│   │   │   ├── pipelines/
│   │   │   │   ├── invoice_pipeline.py
│   │   │   │   ├── contract_pipeline.py
│   │   │   │   ├── cv_pipeline.py
│   │   │   │   ├── report_pipeline.py
│   │   │   │   ├── form_pipeline.py
│   │   │   │   └── generic_pipeline.py
│   │   │   └── base_pipeline.py
│   │   │
│   │   ├── ocr/
│   │   │   ├── ocr_service.py          # PaddleOCR wrapper
│   │   │   ├── ocr_corrector.py        # تصحيح أخطاء OCR
│   │   │   └── language_detector.py
│   │   │
│   │   ├── classification/
│   │   │   ├── document_classifier.py  # ModernBERT / zero-shot
│   │   │   └── classifier_rules.py     # قواعد fallback
│   │   │
│   │   ├── layout/
│   │   │   ├── layout_detector.py      # LayoutParser / YOLO
│   │   │   ├── region_extractor.py
│   │   │   └── bbox_utils.py
│   │   │
│   │   ├── table/
│   │   │   ├── table_detector.py       # TATR
│   │   │   ├── cell_extractor.py
│   │   │   ├── merge_detector.py       # خلايا مدمجة
│   │   │   └── excel_reconstructor.py  # إعادة بناء Excel
│   │   │
│   │   ├── ner/
│   │   │   ├── ner_service.py          # GLiNER
│   │   │   ├── entity_schemas.py       # تعريف الكيانات لكل نوع
│   │   │   └── post_processor.py
│   │   │
│   │   ├── cleaning/
│   │   │   ├── cleaning_service.py
│   │   │   ├── rules/
│   │   │   │   ├── date_normalizer.py
│   │   │   │   ├── currency_normalizer.py
│   │   │   │   ├── number_normalizer.py
│   │   │   │   ├── duplicate_remover.py
│   │   │   │   └── anomaly_detector.py
│   │   │   └── column_suggester.py
│   │   │
│   │   ├── search/
│   │   │   ├── embedding_service.py    # sentence-transformers
│   │   │   ├── vector_store.py         # pgvector أو FAISS
│   │   │   └── semantic_search.py
│   │   │
│   │   ├── suggestions/
│   │   │   └── suggestion_engine.py    # AI Suggestions بعد الرفع
│   │   │
│   │   ├── feedback/
│   │   │   └── feedback_service.py
│   │   │
│   │   ├── dataset/
│   │   │   └── dataset_builder.py
│   │   │
│   │   ├── training/
│   │   │   ├── training_service.py
│   │   │   ├── experiment_tracker.py
│   │   │   └── evaluator.py
│   │   │
│   │   ├── analytics/
│   │   │   └── analytics_service.py
│   │   │
│   │   └── assistant/
│   │       └── ai_assistant.py         # واجهة AI Assistant
│   │
│   ├── jobs/                        ← جديد: نظام Jobs الداخلي
│   │   ├── job_queue.py             # AsyncIO-based queue
│   │   ├── job_worker.py
│   │   ├── job_models.py
│   │   └── job_router.py            # WebSocket للحالة
│   │
│   └── presentation/
│       ├── web/                     # موجود — يُوسَّع
│       │   ├── auth.py
│       │   ├── dashboard.py
│       │   ├── files.py
│       │   ├── converter.py
│       │   ├── cleaner.py
│       │   ├── merger.py
│       │   ├── settings.py
│       │   ├── admin.py
│       │   ├── intelligence.py      ← جديد: Document Intelligence
│       │   ├── search.py            ← جديد: Semantic Search
│       │   ├── training.py          ← جديد: Training Center
│       │   ├── datasets.py          ← جديد: Dataset Manager
│       │   ├── models_ui.py         ← جديد: Model Manager
│       │   └── analytics.py        ← جديد: Analytics
│       │
│       └── api/
│           └── v1/                  # موجود — يُوسَّع
│               ├── auth.py
│               ├── files.py
│               ├── converter.py
│               ├── intelligence.py  ← جديد
│               ├── pipeline.py      ← جديد
│               ├── search.py        ← جديد
│               ├── training.py      ← جديد
│               ├── datasets.py      ← جديد
│               └── models.py        ← جديد
│
├── templates/
│   ├── ... (موجودة)
│   ├── intelligence/               ← جديد
│   │   ├── analyze.html
│   │   ├── result.html
│   │   └── suggestions.html
│   ├── search/                     ← جديد
│   ├── training/                   ← جديد
│   ├── datasets/                   ← جديد
│   ├── models/                     ← جديد
│   └── analytics/                  ← جديد
│
├── ai_models/                      ← جديد: النماذج المحلية
│   ├── classification/
│   ├── layout/
│   ├── table/
│   ├── ner/
│   ├── ocr/
│   └── embeddings/
│
├── data/                           # SQLite dev
├── uploads/
├── outputs/
└── docs/
    └── document-intelligence-platform.md  ← هذا الملف
```

---

## 3. قاعدة البيانات الجديدة — جميع الجداول

### الجداول الموجودة (تبقى كما هي)
- `users` — المستخدمون
- `files` — الملفات المرفوعة
- `operation_logs` — سجل العمليات
- `workflows` — سير العمل

### الجداول الجديدة

```sql
-- =============================================
-- 1. Document Analysis Results
-- =============================================
CREATE TABLE document_analyses (
    id              SERIAL PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                    -- pending | running | completed | failed
    doc_type        VARCHAR(50),
                    -- invoice | contract | cv | report | form | ...
    doc_type_confidence  FLOAT,
    language        VARCHAR(10),
    page_count      INTEGER,
    has_tables      BOOLEAN DEFAULT FALSE,
    has_images      BOOLEAN DEFAULT FALSE,
    has_handwriting BOOLEAN DEFAULT FALSE,
    layout_data     JSONB,     -- Bounding boxes لكل عنصر
    raw_text        TEXT,      -- نص OCR الكامل
    summary         TEXT,
    processing_ms   INTEGER,
    error_message   TEXT,
    pipeline_used   VARCHAR(100),
    model_versions  JSONB,     -- {"ocr": "v1.2", "layout": "v2.0", ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 2. Layout Elements
-- =============================================
CREATE TABLE layout_elements (
    id              SERIAL PRIMARY KEY,
    analysis_id     INTEGER NOT NULL REFERENCES document_analyses(id) ON DELETE CASCADE,
    page_number     INTEGER NOT NULL,
    element_type    VARCHAR(30) NOT NULL,
                    -- paragraph | header | footer | table | image |
                    -- chart | logo | signature | qr_code | barcode |
                    -- list | page_number | column | margin
    x1 FLOAT, y1 FLOAT, x2 FLOAT, y2 FLOAT,  -- Bounding box
    confidence      FLOAT,
    content         TEXT,        -- النص المستخرج إن وُجد
    meta            JSONB,       -- بيانات إضافية حسب النوع
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 3. Extracted Tables
-- =============================================
CREATE TABLE extracted_tables (
    id              SERIAL PRIMARY KEY,
    analysis_id     INTEGER NOT NULL REFERENCES document_analyses(id) ON DELETE CASCADE,
    layout_element_id INTEGER REFERENCES layout_elements(id),
    page_number     INTEGER NOT NULL,
    row_count       INTEGER,
    col_count       INTEGER,
    has_header      BOOLEAN DEFAULT TRUE,
    has_merged_cells BOOLEAN DEFAULT FALSE,
    spans_pages     BOOLEAN DEFAULT FALSE,
    table_data      JSONB NOT NULL,   -- [{row: 0, col: 0, value: ..., colspan: 1, rowspan: 1}]
    headers         JSONB,            -- أسماء الأعمدة المستخرجة
    confidence      FLOAT,
    excel_output_path TEXT,           -- مسار ملف Excel الناتج
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 4. Extracted Entities (NER)
-- =============================================
CREATE TABLE extracted_entities (
    id              SERIAL PRIMARY KEY,
    analysis_id     INTEGER NOT NULL REFERENCES document_analyses(id) ON DELETE CASCADE,
    entity_type     VARCHAR(50) NOT NULL,
                    -- invoice_number | supplier | customer | date |
                    -- tax | currency | total | email | phone |
                    -- name | skill | party | amount | ...
    value           TEXT NOT NULL,
    normalized_value TEXT,            -- القيمة بعد التطبيع
    confidence      FLOAT,
    page_number     INTEGER,
    x1 FLOAT, y1 FLOAT, x2 FLOAT, y2 FLOAT,  -- موقع في الصفحة
    context         TEXT,             -- النص المحيط
    verified        BOOLEAN DEFAULT FALSE,    -- هل صوَّب المستخدم؟
    corrected_value TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 5. Cleaning Jobs & Results
-- =============================================
CREATE TABLE cleaning_jobs (
    id              SERIAL PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES files(id),
    analysis_id     INTEGER REFERENCES document_analyses(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    rules_applied   JSONB,            -- ["remove_empty_rows", "normalize_dates", ...]
    stats           JSONB,            -- {"removed_rows": 5, "fixed_dates": 12, ...}
    output_file_id  INTEGER REFERENCES files(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- =============================================
-- 6. AI Suggestions
-- =============================================
CREATE TABLE ai_suggestions (
    id              SERIAL PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    analysis_id     INTEGER REFERENCES document_analyses(id),
    suggestion_type VARCHAR(50) NOT NULL,
                    -- extract_tables | convert_excel | extract_email |
                    -- extract_phones | summarize | search | clean_data
    title           VARCHAR(200),
    description     TEXT,
    action_params   JSONB,            -- بارامترات لتنفيذ الاقتراح مباشرة
    priority        INTEGER DEFAULT 0,
    accepted        BOOLEAN,          -- هل قبِل المستخدم؟
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 7. User Feedback
-- =============================================
CREATE TABLE user_feedback (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    file_id         INTEGER REFERENCES files(id),
    analysis_id     INTEGER REFERENCES document_analyses(id),
    entity_id       INTEGER REFERENCES extracted_entities(id),
    feedback_type   VARCHAR(30) NOT NULL,
                    -- entity_correction | table_correction |
                    -- classification_correction | ocr_correction | rating
    original_value  TEXT,
    corrected_value TEXT,
    field_name      VARCHAR(100),
    doc_type        VARCHAR(50),
    language        VARCHAR(10),
    rating          SMALLINT,         -- 1-5
    comment         TEXT,
    meta            JSONB,
    used_in_training BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 8. Dataset
-- =============================================
CREATE TABLE datasets (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    dataset_type    VARCHAR(30) NOT NULL,
                    -- ocr | classification | ner | layout | table
    version         VARCHAR(20),
    status          VARCHAR(20) DEFAULT 'building',
                    -- building | ready | training | archived
    sample_count    INTEGER DEFAULT 0,
    split_train     FLOAT DEFAULT 0.8,
    split_val       FLOAT DEFAULT 0.1,
    split_test      FLOAT DEFAULT 0.1,
    meta            JSONB,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE dataset_samples (
    id              SERIAL PRIMARY KEY,
    dataset_id      INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    file_id         INTEGER REFERENCES files(id),
    analysis_id     INTEGER REFERENCES document_analyses(id),
    feedback_id     INTEGER REFERENCES user_feedback(id),
    split           VARCHAR(10) DEFAULT 'train',  -- train | val | test
    input_path      TEXT NOT NULL,    -- مسار الملف الأصلي
    output_path     TEXT,             -- مسار الملف المحول
    labels          JSONB NOT NULL,   -- التسميات
    bounding_boxes  JSONB,
    doc_type        VARCHAR(50),
    language        VARCHAR(10),
    ocr_output      TEXT,
    entities        JSONB,
    corrections     JSONB,
    training_status VARCHAR(20) DEFAULT 'pending',
                    -- pending | used | excluded
    version         VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 9. AI Models Registry
-- =============================================
CREATE TABLE ai_model_registry (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    model_type      VARCHAR(30) NOT NULL,
                    -- ocr | classification | ner | layout | table |
                    -- embedding | cleaning
    version         VARCHAR(30) NOT NULL,
    source          VARCHAR(50),      -- huggingface | local | onnx
    model_path      TEXT,             -- مسار محلي
    hf_model_id     VARCHAR(200),     -- HuggingFace model ID
    is_active       BOOLEAN DEFAULT FALSE,
    is_default      BOOLEAN DEFAULT FALSE,
    size_mb         FLOAT,
    languages       JSONB,            -- ["ar", "en"]
    metrics         JSONB,            -- {"accuracy": 0.95, "f1": 0.93}
    description     TEXT,
    config          JSONB,
    loaded_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 10. Training Experiments
-- =============================================
CREATE TABLE training_experiments (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    model_type      VARCHAR(30) NOT NULL,
    base_model_id   INTEGER REFERENCES ai_model_registry(id),
    dataset_id      INTEGER REFERENCES datasets(id),
    status          VARCHAR(20) DEFAULT 'pending',
                    -- pending | running | completed | failed | cancelled
    hyperparams     JSONB NOT NULL,   -- {"lr": 0.001, "epochs": 10, ...}
    metrics         JSONB,            -- {"accuracy": ..., "f1": ..., "loss": ...}
    best_metric     FLOAT,
    epochs_run      INTEGER DEFAULT 0,
    total_epochs    INTEGER,
    output_model_id INTEGER REFERENCES ai_model_registry(id),
    log_path        TEXT,
    error_message   TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_by      INTEGER REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================
-- 11. Document Embeddings (Semantic Search)
-- =============================================
CREATE TABLE document_embeddings (
    id              SERIAL PRIMARY KEY,
    file_id         INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    analysis_id     INTEGER REFERENCES document_analyses(id),
    chunk_index     INTEGER NOT NULL,  -- رقم القطعة النصية
    chunk_text      TEXT NOT NULL,
    embedding       VECTOR(768),       -- pgvector (أو JSONB كبديل)
    page_number     INTEGER,
    doc_type        VARCHAR(50),
    language        VARCHAR(10),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops);

-- =============================================
-- 12. Internal Job Queue
-- =============================================
CREATE TABLE processing_jobs (
    id              SERIAL PRIMARY KEY,
    job_type        VARCHAR(50) NOT NULL,
                    -- analysis | ocr | classification | layout |
                    -- table | ner | cleaning | embedding | training
    file_id         INTEGER REFERENCES files(id),
    analysis_id     INTEGER REFERENCES document_analyses(id),
    experiment_id   INTEGER REFERENCES training_experiments(id),
    status          VARCHAR(20) NOT NULL DEFAULT 'queued',
                    -- queued | running | completed | failed | cancelled
    priority        SMALLINT DEFAULT 5,   -- 1 (عالي) - 10 (منخفض)
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error_message   TEXT,
    retry_count     SMALLINT DEFAULT 0,
    max_retries     SMALLINT DEFAULT 3,
    worker_id       VARCHAR(100),
    queued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);
CREATE INDEX ON processing_jobs (status, priority, queued_at);
```

---

## 4. العلاقات بين الجداول

```
files (1) ──────────── (N) document_analyses
files (1) ──────────── (N) ai_suggestions
files (1) ──────────── (N) cleaning_jobs
files (1) ──────────── (N) document_embeddings
files (1) ──────────── (N) user_feedback
files (1) ──────────── (N) dataset_samples

document_analyses (1) ──── (N) layout_elements
document_analyses (1) ──── (N) extracted_tables
document_analyses (1) ──── (N) extracted_entities
document_analyses (1) ──── (N) ai_suggestions
document_analyses (1) ──── (N) document_embeddings
document_analyses (1) ──── (N) user_feedback

layout_elements (1) ─────── (1) extracted_tables  [اختياري]

datasets (1) ───────────── (N) dataset_samples
datasets (1) ───────────── (N) training_experiments

training_experiments (N) ── (1) ai_model_registry  [base_model]
training_experiments (1) ── (1) ai_model_registry  [output_model]

user_feedback (N) ────────── (N) dataset_samples  [عبر feedback_id]

processing_jobs ──────────── يرتبط بـ files, document_analyses, training_experiments
```

---

## 5. APIs الجديدة

### Document Intelligence API

```
POST   /api/v1/intelligence/analyze/{file_id}
       → يبدأ تحليل مستند كامل (Pipeline)
       → يعيد job_id للمتابعة عبر WebSocket

GET    /api/v1/intelligence/analysis/{analysis_id}
       → نتائج التحليل الكاملة

GET    /api/v1/intelligence/analysis/{analysis_id}/layout
       → عناصر Layout مع Bounding Boxes

GET    /api/v1/intelligence/analysis/{analysis_id}/tables
       → الجداول المستخرجة

GET    /api/v1/intelligence/analysis/{analysis_id}/entities
       → الكيانات المستخرجة

POST   /api/v1/intelligence/analysis/{analysis_id}/entities/{entity_id}/correct
       → تصحيح كيان → يُسجَّل في Feedback

GET    /api/v1/intelligence/suggestions/{file_id}
       → اقتراحات AI للملف

POST   /api/v1/intelligence/suggestions/{suggestion_id}/accept
       → قبول اقتراح وتنفيذه
```

### Pipeline API

```
GET    /api/v1/pipeline/types
       → أنواع المستندات المدعومة مع Pipelines المتاحة

POST   /api/v1/pipeline/run
       → تشغيل Pipeline محددة على ملف
       Body: { file_id, pipeline_type, options }

GET    /api/v1/pipeline/jobs/{job_id}
       → حالة Job

WS     /ws/jobs/{job_id}
       → متابعة حالة الـ Job لحظة بلحظة
```

### Search API

```
POST   /api/v1/search
       Body: { query, filters: { doc_type, language, date_range } }
       → Semantic Search عبر جميع الملفات

POST   /api/v1/search/embed/{file_id}
       → إنشاء Embeddings لملف (بعد التحليل)

GET    /api/v1/search/similar/{file_id}
       → الملفات المشابهة
```

### Training & Dataset API

```
GET    /api/v1/datasets
POST   /api/v1/datasets
GET    /api/v1/datasets/{id}
DELETE /api/v1/datasets/{id}

GET    /api/v1/datasets/{id}/samples
POST   /api/v1/datasets/{id}/samples/add_from_feedback
POST   /api/v1/datasets/{id}/export

GET    /api/v1/training/experiments
POST   /api/v1/training/experiments
GET    /api/v1/training/experiments/{id}
POST   /api/v1/training/experiments/{id}/start
POST   /api/v1/training/experiments/{id}/cancel
GET    /api/v1/training/experiments/{id}/metrics
```

### Model Manager API

```
GET    /api/v1/models
       → جميع النماذج المسجلة

POST   /api/v1/models/{id}/activate
       → تفعيل نموذج كـ active

POST   /api/v1/models/{id}/set-default
       → تعيين كـ default لنوعه

POST   /api/v1/models/download
       Body: { hf_model_id, model_type }
       → تحميل نموذج من HuggingFace

GET    /api/v1/models/{id}/metrics
```

### Feedback API

```
POST   /api/v1/feedback
       → تسجيل feedback جديد

GET    /api/v1/feedback/pending
       → feedback لم يُضَف لـ Dataset بعد

POST   /api/v1/feedback/bulk-add-to-dataset
       Body: { feedback_ids, dataset_id }
```

### Analytics API

```
GET    /api/v1/analytics/overview
GET    /api/v1/analytics/files?period=30d
GET    /api/v1/analytics/operations
GET    /api/v1/analytics/ocr-accuracy
GET    /api/v1/analytics/table-extraction
GET    /api/v1/analytics/user-satisfaction
```

---

## 6. تسلسل معالجة المستند (خطوة بخطوة)

### الخطوة 1: Upload & Validation
```python
- استقبال الملف عبر /api/v1/files/upload
- التحقق من النوع والحجم
- حفظ في uploads/ وتسجيل في جدول files
- إنشاء processing_job من نوع "analysis"
- إرجاع job_id فوراً (async)
```

### الخطوة 2: Document Classification
```python
# services/classification/document_classifier.py
input:  مسار الملف + أول صفحة كصورة
models: ModernBERT (zero-shot classification) + قواعد keyword
output: doc_type + confidence

أمثلة الكشف:
- كلمات: "فاتورة", "Invoice", "Tax" → invoice
- كلمات: "عقد", "Contract", "Parties" → contract
- هيكل: جدول واسع + row headers → spreadsheet
- صورة وجه + بيانات شخصية → id/passport
```

### الخطوة 3: Layout Detection
```python
# services/layout/layout_detector.py
input:  صور الصفحات (PDF → صور عبر pdf2image)
models: LayoutParser (Detectron2) أو YOLO مدرَّب على PubLayNet
output: قائمة layout_elements مع إحداثيات

يُحفظ في: جدول layout_elements
```

### الخطوة 4: OCR
```python
# services/ocr/ocr_service.py
input:  مناطق النص من Layout Detection
models: PaddleOCR (ar + en)
output: نص لكل منطقة

يُحفظ في: layout_elements.content + document_analyses.raw_text

تصحيح تلقائي: ocr_corrector.py
- استبدال أحرف متشابهة
- تصحيح الأرقام العربية/الهندية
- دمج الكلمات المقطوعة
```

### الخطوة 5: Table Detection & Extraction
```python
# services/table/table_detector.py
input:  صور الصفحات
models: Table Transformer (TATR) من Microsoft
output: مواقع الجداول + بنية الخلايا

# services/table/cell_extractor.py
- تحديد الخلايا المدمجة (rowspan/colspan)
- استخراج القيم عبر OCR
- بناء DataFrame

# services/table/excel_reconstructor.py
- إعادة بناء Excel بدقة (openpyxl)
- الحفاظ على الدمج والترويسات
```

### الخطوة 6: Entity Extraction
```python
# services/ner/ner_service.py
input:  raw_text + doc_type
models: GLiNER (يدعم zero-shot NER)

حسب doc_type يُحدَّد schema الكيانات:
- invoice    → InvoiceEntitySchema
- contract   → ContractEntitySchema
- cv         → CVEntitySchema
- ...

output: قائمة extracted_entities
```

### الخطوة 7: Cleaning
```python
# services/cleaning/cleaning_service.py
يعمل على البيانات المستخرجة:
- توحيد التواريخ → ISO 8601
- توحيد العملات → {"amount": 100, "currency": "USD"}
- توحيد الأرقام → إزالة الفواصل الزائدة
- إزالة الصفوف الفارغة
- كشف القيم الشاذة (IQR method)
- اقتراح أسماء الأعمدة
```

### الخطوة 8: Suggestions Engine
```python
# services/suggestions/suggestion_engine.py
بعد اكتمال التحليل يُنشئ اقتراحات تلقائية:

if has_tables:
    → "استخراج الجداول إلى Excel"
if doc_type == "invoice":
    → "استخراج بيانات الفاتورة كـ JSON"
if has_emails:
    → "استخراج عناوين البريد الإلكتروني"
...
```

### الخطوة 9: Embedding & Search Index
```python
# services/search/embedding_service.py
model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- تقسيم النص إلى chunks (512 token)
- إنشاء embedding لكل chunk
- حفظ في document_embeddings
```

### الخطوة 10: Feedback Recording
```python
# كل تعديل يقوم به المستخدم:
- تصحيح كيان → user_feedback (entity_correction)
- تعديل جدول → user_feedback (table_correction)
- تقييم النتيجة → user_feedback (rating)

→ dataset_builder.py يضيفها تلقائياً لـ Dataset المناسب
```

---

## 7. Pipeline لكل نوع مستند

### Invoice Pipeline
```
Upload → Classification(invoice) → Layout → OCR →
Table Detection → NER[InvoiceSchema] → Cleaning →
Suggestions[extract_to_json, convert_excel] → Export
```
**InvoiceSchema**: invoice_number, supplier, customer, date, tax,
currency, total, line_items[product, qty, price, total]

### Contract Pipeline
```
Upload → Classification(contract) → Layout → OCR →
NER[ContractSchema] → Cleaning →
Suggestions[extract_parties, extract_dates] → Export
```
**ContractSchema**: parties[], effective_date, expiry_date,
governing_law, amount, penalties[], obligations[]

### CV Pipeline
```
Upload → Classification(cv) → Layout → OCR →
NER[CVSchema] → Cleaning →
Suggestions[export_json, export_csv] → Export
```
**CVSchema**: name, email, phone, address, skills[],
experience[{company, role, start, end}], education[], languages[]

### Bank Statement Pipeline
```
Upload → Classification(bank_statement) → Layout → OCR →
Table Detection → NER[BankSchema] → Cleaning →
Suggestions[analyze_transactions, export_excel] → Export
```

### Medical Report Pipeline
```
Upload → Classification(medical_report) → Layout → OCR →
NER[MedicalSchema] → Cleaning →
Suggestions[export_json] → Export
```

### Generic Pipeline (Unknown)
```
Upload → Classification(unknown) → Layout → OCR →
Table Detection (if any) → Basic NER → Cleaning →
Suggestions[convert, search] → Export
```

---

## 8. تصميم نظام التدريب

```
┌─────────────────────────────────────┐
│           Training Center            │
│                                     │
│  1. اختيار Dataset                  │
│  2. اختيار النموذج الأساسي          │
│  3. ضبط Hyperparameters             │
│  4. تشغيل Training Job (Background)  │
│  5. مراقبة Metrics لحظة بلحظة       │
│  6. تقييم النتائج                   │
│  7. نشر النموذج أو رفضه             │
└─────────────────────────────────────┘
```

### Training Service
```python
# services/training/training_service.py
class TrainingService:
    async def create_experiment(model_type, dataset_id, hyperparams)
    async def start_training(experiment_id)    # يُنفَّذ في Background
    async def get_metrics(experiment_id)
    async def evaluate(experiment_id, test_split)
    async def deploy_model(experiment_id)      # يُسجَّل في Registry

# services/training/experiment_tracker.py
- يحفظ metrics كل epoch
- يرسم learning curves
- يقارن بين Experiments
```

### نماذج Fine-tuning المدعومة
| النوع | النموذج الأساسي | المهمة |
|-------|----------------|--------|
| classification | distilbert-base-multilingual | text-classification |
| ner | gliner-large | token-classification |
| layout | detectron2-PubLayNet | object-detection |
| table | microsoft/table-transformer | table-detection |
| embedding | MiniLM-L12-v2 | sentence-similarity |

---

## 9. تصميم Dataset Builder

```python
# services/dataset/dataset_builder.py

class DatasetBuilder:
    """يجمع تلقائياً من ثلاثة مصادر:"""

    def add_from_analysis(analysis_id)
    # من نتائج التحليل المؤكدة

    def add_from_feedback(feedback_ids)
    # من تصحيحات المستخدمين

    def add_manual(input_path, labels)
    # إضافة يدوية

    def split(train=0.8, val=0.1, test=0.1)
    def export(format="jsonl")  # JSONL / HuggingFace Datasets
    def get_stats()
    # sample_count, label_distribution, languages, ...
```

### بنية Dataset Sample (JSONL)
```json
{
  "id": "abc123",
  "input_path": "uploads/file.pdf",
  "doc_type": "invoice",
  "language": "ar",
  "ocr_text": "...",
  "labels": {
    "classification": "invoice",
    "entities": [
      {"type": "invoice_number", "value": "INV-001", "start": 10, "end": 17}
    ],
    "tables": [{"rows": 5, "cols": 4, "data": [...]}]
  },
  "bounding_boxes": [...],
  "split": "train",
  "version": "1.0",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

## 10. تصميم Model Manager

```
┌───────────────────────────────────────┐
│           Model Manager               │
│                                       │
│  ┌─────────┐  ┌──────────┐           │
│  │ OCR     │  │ Layout   │           │
│  │ Models  │  │ Models   │           │
│  │ v1 ✓   │  │ v2 ✓    │           │
│  │ v2 (new)│  │ v1      │           │
│  └─────────┘  └──────────┘           │
│                                       │
│  ┌─────────┐  ┌──────────┐           │
│  │ NER     │  │ Table    │           │
│  │ Models  │  │ Models   │           │
│  └─────────┘  └──────────┘           │
│                                       │
│  Actions: Activate | Download |       │
│           Rollback | Compare |        │
│           Delete                      │
└───────────────────────────────────────┘
```

```python
# infrastructure/ai/model_registry.py
class ModelRegistry:
    def get_active(model_type) → AIModel
    def get_all(model_type) → List[AIModel]
    def activate(model_id)
    def rollback(model_type)    # يُفعِّل السابق
    def download_from_hf(hf_id, model_type)
    def register_trained(experiment_id)

# infrastructure/ai/model_loader.py
class ModelLoader:
    # Lazy loading + caching في الذاكرة
    # يحمِّل النموذج عند أول طلب
    # يُحرِّر من الذاكرة عند عدم الاستخدام لـ 30 دقيقة
```

---

## 11. تصميم لوحة التحكم (Analytics Dashboard)

### البطاقات الرئيسية
```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ إجمالي الملفات│  │  معدل نجاح  │  │ متوسط وقت   │  │  تقييم      │
│    1,247     │  │   OCR 94%    │  │ المعالجة 3s  │  │  المستخدم   │
│  ↑ 12% أسبوع │  │  ↑ 2%       │  │  ↓ 0.5s      │  │   4.2/5     │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

### الرسوم البيانية
1. **توزيع أنواع المستندات** (Pie Chart)
2. **الملفات المعالجة يومياً** (Line Chart - 30 يوم)
3. **أكثر العمليات استخداماً** (Bar Chart)
4. **دقة الاستخراج حسب النوع** (Heatmap)
5. **معدل قبول الاقتراحات** (Gauge)
6. **التصحيحات حسب نوع الكيان** (Bar Chart)

### قسم الأخطاء والتنبيهات
- آخر 10 أخطاء
- نماذج تحتاج تحديثاً
- Dataset جاهز للتدريب

---

## 12. نظام Jobs الداخلي (بدون Celery/Redis)

```python
# app/jobs/job_queue.py
import asyncio
from collections import deque

class InternalJobQueue:
    """
    AsyncIO-based priority queue
    قابل للاستبدال بـ Celery+Redis لاحقاً بدون تغيير الواجهة
    """
    def __init__(self, max_workers=4):
        self.queue = asyncio.PriorityQueue()
        self.workers = []
        self.max_workers = max_workers

    async def enqueue(self, job_type, payload, priority=5, file_id=None)
    async def start_workers()
    async def _process_job(job)
    async def get_status(job_id) → JobStatus
    async def cancel(job_id)

# app/jobs/job_worker.py
# كل worker يُنفِّذ Job واحدة في الوقت الواحد
# يُسجِّل النتائج في processing_jobs
# يُرسِّل تحديثات عبر WebSocket

# تشغيل Workers في lifespan الـ FastAPI:
@asynccontextmanager
async def lifespan(app):
    await job_queue.start_workers()
    yield
    await job_queue.shutdown()
```

---

## 13. خطة التنفيذ التدريجية (Roadmap)

### المرحلة 0 — الحالة الراهنة ✅
- منصة تحويل ملفات كاملة
- OCR أساسي
- واجهة Jinja2 + HTMX
- Auth + Users

---

### المرحلة 1 — Foundation (4-6 أسابيع)
**الهدف**: بنية تحتية AI دون كسر أي ميزة موجودة

- [ ] إنشاء جداول DB الجديدة (Migration)
- [ ] Internal Job Queue (AsyncIO)
- [ ] WebSocket لمتابعة Jobs
- [ ] Model Registry + Model Loader
- [ ] تحميل أول نموذج: PaddleOCR (تحسين الـ OCR الموجود)
- [ ] صفحة Document Analysis (بدون AI بعد — تحضير UI)

**المخرج**: البنية جاهزة، OCR محسَّن

---

### المرحلة 2 — Smart Document (6-8 أسابيع)
**الهدف**: الفهم الذكي الأساسي

- [ ] Document Classification Service (ModernBERT/distilbert zero-shot)
- [ ] Layout Detection Service (LayoutParser)
- [ ] Pipeline Manager
- [ ] Generic Pipeline
- [ ] AI Suggestions Engine (قواعد بسيطة أولاً)
- [ ] صفحة عرض نتائج التحليل

**المخرج**: كل ملف يحصل على: نوع + layout + اقتراحات

---

### المرحلة 3 — Table Intelligence (4-6 أسابيع)
**الهدف**: استخراج جداول احترافي

- [ ] Table Transformer (TATR) integration
- [ ] Cell Extractor + Merge Detector
- [ ] Excel Reconstructor المحسَّن
- [ ] دمج مع Pipeline الموجودة (PDF → Excel يصبح أذكى)

**المخرج**: استخراج جداول بدقة عالية مع دعم الخلايا المدمجة

---

### المرحلة 4 — Entity Extraction (4-6 أسابيع)
**الهدف**: NER لأهم أنواع المستندات

- [ ] GLiNER integration
- [ ] Invoice Pipeline
- [ ] CV Pipeline
- [ ] Contract Pipeline
- [ ] واجهة تصحيح الكيانات

**المخرج**: استخراج بيانات منظمة من الفواتير والـ CVs والعقود

---

### المرحلة 5 — Feedback & Dataset (3-4 أسابيع)
**الهدف**: جمع البيانات للتدريب

- [ ] Feedback Recording في كل تفاعل
- [ ] Dataset Builder
- [ ] Dataset Manager UI

**المخرج**: Dataset يتنمو تلقائياً مع كل استخدام

---

### المرحلة 6 — Semantic Search (3-4 أسابيع)
**الهدف**: البحث داخل آلاف الملفات

- [ ] sentence-transformers integration
- [ ] pgvector أو FAISS
- [ ] Embedding Service
- [ ] Search UI + API

**المخرج**: "ابحث في جميع الفواتير عن شركة X"

---

### المرحلة 7 — Training Center (6-8 أسابيع)
**الهدف**: Fine-tuning النماذج على بياناتك

- [ ] Training Service (HuggingFace Trainer)
- [ ] Experiment Tracker
- [ ] Training Center UI
- [ ] Model Manager UI
- [ ] Rollback & Versioning

**المخرج**: منصة تتعلم وتتحسن من بياناتك

---

### المرحلة 8 — Analytics & AI Assistant (4 أسابيع)
**الهدف**: رؤية كاملة + واجهة محادثة

- [ ] Analytics Dashboard
- [ ] AI Assistant (أوامر نصية بسيطة)
- [ ] Smart Cleaning Engine المتقدم

**المخرج**: منصة Document Intelligence متكاملة

---

### المرحلة 9 — Advanced (مستقبل)
- RAG على النماذج المحلية (Llama / Mistral)
- Audio Intelligence (Whisper)
- Video Intelligence
- Workflow Automation
- Multi-tenant SaaS

---

## 14. اقتراحات للتفوق على Smallpdf / iLovePDF

### نقاط التميز المقترحة

| المجال | Smallpdf/iLovePDF | منصتك |
|--------|-------------------|-------|
| OCR | أساسي | PaddleOCR عربي/إنجليزي عالي الجودة |
| فهم المستند | لا يوجد | تصنيف + استخراج كيانات |
| الجداول | تحويل بسيط | إعادة بناء كاملة مع دمج الخلايا |
| البحث | لا يوجد | Semantic Search داخل الملفات |
| الخصوصية | Cloud فقط | يعمل محلياً 100% (no external APIs) |
| التخصيص | لا يوجد | Fine-tuning على بياناتك |
| العربية | ضعيف | دعم أصيل للعربية |
| Dataset | لا يوجد | يبني Dataset تلقائياً |

### ميزات حصرية مقترحة

1. **"Document Memory"**: النظام يتذكر أنماط مستنداتك ويقترح تلقائياً
2. **"Batch Intelligence"**: تحليل مئات الملفات دفعة واحدة + تقرير مجمَّع
3. **"Document Comparison"**: مقارنة نسختين من عقد/وثيقة وإبراز الفروق
4. **"Template Learning"**: يتعلم قالب فاتورتك تحديداً لا القالب العام
5. **"Audit Trail"**: سجل كامل لكل تعديل على المستند (مناسب للقانون والمحاسبة)
6. **"Export to Any Format"**: تصدير الكيانات إلى JSON/CSV/Excel/XML/Webhook
7. **"Arabic-First"**: أداء OCR وNER متفوق على النصوص العربية والمختلطة

---

## النماذج المفتوحة المصدر المقترحة (بدون رسوم)

| الخدمة | النموذج | المصدر |
|--------|---------|--------|
| OCR | PaddleOCR v4 | paddlepaddle/PaddleOCR |
| Layout | LayoutParser + Detectron2 | Layout-Parser/layout-parser |
| Table | Table Transformer | microsoft/table-transformer |
| Classification | distilbert-multilingual | HuggingFace |
| NER | GLiNER-large-v2.1 | urchade/gliner_large |
| Embedding | paraphrase-multilingual-MiniLM-L12-v2 | sentence-transformers |
| Language Detection | lingua-py | pemistahl/lingua-py |
| OCR Correction | Custom rules | local |
| Anomaly Detection | scikit-learn IsolationForest | local |

---

*وثيقة حية — تُحدَّث مع كل مرحلة تنفيذ*
