# app/services/speech_service.py
import os
import base64
from huggingface_hub import InferenceClient

class SpeechService:
    def __init__(self):
        self.client = InferenceClient(
            provider="fal-ai",
            api_key=os.environ.get("HF_TOKEN")
        )
    
    async def speech_to_text(self, audio_bytes: bytes) -> dict:
        """
        تحويل الصوت إلى نص باستخدام Whisper
        """
        # تحويل الصوت إلى base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # استدعاء API
        response = self.client.automatic_speech_recognition(
            audio_base64,
            model="openai/whisper-large-v3",
            parameters={
                "return_timestamps": True,
                "temperature": 0.0
            }
        )
        
        return {
            "text": response.get("text", ""),
            "chunks": response.get("chunks", [])  # مع الطوابع الزمنية
        }
