# app/presentation/web/models.py
@app.get("/api/v1/models/available")
async def get_available_models():
    """
    قراءة النماذج المتاحة من إعدادات النظام
    """
    # يمكن قراءة من ملف إعدادات أو قاعدة بيانات
    models = [
        {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "🧠 Qwen 2.5 72B"},
        {"id": "meta-llama/Llama-3-70B-Instruct", "name": "🦙 Llama 3 70B"},
        {"id": "mistralai/Mixtral-8x7B-Instruct", "name": "🌪️ Mixtral 8x7B"},
        {"id": "openai/whisper-large-v3", "name": "🎤 Whisper v3 (ASR)"},
        {"id": "bm25", "name": "📊 BM25 (بحث تقليدي)"},
    ]
    return {"models": models}
