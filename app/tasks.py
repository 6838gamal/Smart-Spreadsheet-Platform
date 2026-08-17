# app/tasks.py
from app.celery_app import celery_app
from app.services.speech_service import SpeechService

@celery_app.task(bind=True)
def process_audio_task(self, audio_bytes: bytes, file_id: int):
    """معالجة صوتية طويلة مع تتبع التقدم"""
    self.update_state(state='PROGRESS', meta={'current': 0, 'total': 100})
    
    # تحويل الصوت
    audio = preprocess_audio(audio_bytes)
    self.update_state(state='PROGRESS', meta={'current': 30, 'total': 100})
    
    # تحويل إلى نص
    service = SpeechService()
    result = await service.speech_to_text(audio)
    self.update_state(state='PROGRESS', meta={'current': 70, 'total': 100})
    
    # فهرسة النص
    await index_transcription(file_id, result['text'])
    
    return {"status": "completed", "transcription": result['text']}
