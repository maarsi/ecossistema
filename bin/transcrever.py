from transformers import pipeline
import sys

arquivo = sys.argv[1] if len(sys.argv) > 1 else "/home/mateus/teste_audio.wav"
print("carregando whisper-large-v3 na GPU (1a vez baixa ~3 GB)...")
asr = pipeline("automatic-speech-recognition",
               model="openai/whisper-large-v3",
               device="cuda", torch_dtype="float16",
               chunk_length_s=30, stride_length_s=5,
               generate_kwargs={"language": "pt", "task": "transcribe"})
print("transcrevendo:", arquivo)
out = asr(arquivo)
print("\n=== TRANSCRICAO ===")
print(out["text"])
