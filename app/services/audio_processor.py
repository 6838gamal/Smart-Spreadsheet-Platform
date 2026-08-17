# app/services/audio_processor.py
import subprocess
import tempfile

async def preprocess_audio(audio_bytes: bytes) -> bytes:
    """
    تحويل الصوت إلى 16kHz mono WAV باستخدام FFmpeg
    """
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=True) as input_file:
        input_file.write(audio_bytes)
        input_file.flush()
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=True) as output_file:
            cmd = [
                'ffmpeg',
                '-i', input_file.name,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                output_file.name
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            
            with open(output_file.name, 'rb') as f:
                return f.read()
