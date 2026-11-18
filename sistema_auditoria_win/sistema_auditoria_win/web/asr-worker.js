/* Transcripción en el navegador (Whisper vía transformers.js). El audio NO sale del equipo del usuario;
   solo se descarga el modelo la primera vez (queda en caché). Requiere internet para cargar la librería y el modelo. */
import { pipeline } from "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.0.2";

let asr = null, actual = null;
self.onmessage = async (e) => {
  const { canales, modelo } = e.data;
  try {
    if (!asr || actual !== modelo) {
      const archivos = {};
      asr = await pipeline("automatic-speech-recognition", modelo, {
        progress_callback: (p) => {
          if (p.status === "progress" && p.file) {
            archivos[p.file] = p.progress;
            const v = Object.values(archivos);
            self.postMessage({ tipo: "descarga", pct: v.reduce((a, b) => a + b, 0) / v.length });
          }
        },
      });
      actual = modelo;
    }
    const resultados = [];
    for (let i = 0; i < canales.length; i++) {
      self.postMessage({ tipo: "estado", texto: canales.length > 1 ? `Transcribiendo canal ${i + 1} de ${canales.length}…` : "Transcribiendo audio…" });
      const out = await asr(canales[i], { language: "spanish", task: "transcribe", chunk_length_s: 30, stride_length_s: 5, return_timestamps: true });
      resultados.push(out.chunks && out.chunks.length
        ? out.chunks.map(c => ({ ini: (c.timestamp && c.timestamp[0]) || 0, fin: (c.timestamp && c.timestamp[1]) || 0, texto: c.text.trim() }))
        : [{ ini: 0, fin: 0, texto: (out.text || "").trim() }]);
    }
    self.postMessage({ tipo: "listo", resultados });
  } catch (err) {
    self.postMessage({ tipo: "error", mensaje: String((err && err.message) || err) });
  }
};
