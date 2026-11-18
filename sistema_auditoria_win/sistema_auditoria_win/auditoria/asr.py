"""Transcripción de audio (ASR) y cálculo de WER. Requiere `pip install faster-whisper` (opcional)."""
import re

_modelo = None


def disponible():
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcribir(ruta_audio, modelo="small", idioma="es"):
    """Devuelve texto plano. Whisper no separa hablantes: el auditor (o un módulo de diarización) debe
    etiquetar ASESOR:/CLIENTE: para que el extractor pueda atribuir cada frase."""
    global _modelo
    if not disponible():
        raise RuntimeError("faster-whisper no está instalado: pip install faster-whisper")
    from faster_whisper import WhisperModel
    if _modelo is None:
        _modelo = WhisperModel(modelo, device="cpu", compute_type="int8")
    segs, _ = _modelo.transcribe(ruta_audio, language=idioma, vad_filter=True)
    return "\n".join(s.text.strip() for s in segs)


def wer(referencia, hipotesis):
    """Tasa de error de palabras (distancia de edición a nivel de palabra)."""
    r = re.findall(r"\w+", referencia.lower())
    h = re.findall(r"\w+", hipotesis.lower())
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rw in enumerate(r, 1):
        cur = [i]
        for j, hw in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rw != hw)))
        prev = cur
    return prev[-1] / len(r)
