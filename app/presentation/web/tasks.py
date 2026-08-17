# app/presentation/web/tasks.py
from celery.result import AsyncResult
from app.celery_app import celery_app

@app.post("/api/v1/tasks/process-audio")
async def start_audio_processing(file_id: int, audio: bytes = File(...)):
    """بدء معالجة الصوت كمهمة غير متزامنة"""
    task = process_audio_task.delay(audio, file_id)
    return {"task_id": task.id, "status": "processing"}

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """الحصول على حالة المهمة"""
    task = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.info if task.status == "PROGRESS" else None,
        "result": task.result if task.status == "SUCCESS" else None
    }
