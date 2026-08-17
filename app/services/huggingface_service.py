# app/services/huggingface_service.py
import os
from huggingface_hub import InferenceClient

class HuggingFaceService:
    def __init__(self):
        self.client = InferenceClient(
            provider="fal-ai",  # أو أي provider متاح
            api_key=os.environ.get("HF_TOKEN")
        )
    
    async def generate_response(self, prompt: str, model: str = "Qwen/Qwen2.5-72B-Instruct"):
        """توليد رد باستخدام نموذج Hugging Face"""
        response = self.client.text_generation(
            prompt,
            model=model,
            max_new_tokens=1024,
            temperature=0.7
        )
        return response
