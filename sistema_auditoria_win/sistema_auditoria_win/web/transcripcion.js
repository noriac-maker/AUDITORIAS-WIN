/* Ayudas puras de transcripción (sin DOM): se usan en la app y se prueban con node. */
(function (root) {
  const ROL = /^\s*(ASESOR|ASESORA|AGENTE|EJECUTIV[OA]|VENDEDOR|CLIENTE)\s*:/i;
  function tieneEtiquetas(t) { return /^\s*(ASESOR|ASESORA|AGENTE|CLIENTE)\s*:/im.test(t || ""); }
  /** resultados: [[{ini,fin,texto}]] por canal. canalAsesor: índice del canal del asesor o null (mono / mezcla). */
  function unirCanales(resultados, canalAsesor) {
    if (resultados.length === 1 || canalAsesor == null) {
      return resultados[0].map(s => s.texto).filter(Boolean).join("\n");
    }
    const seg = [];
    resultados.forEach((canal, i) => canal.forEach(s => {
      if (s.texto) seg.push({ ini: s.ini || 0, rol: i === canalAsesor ? "ASESOR" : "CLIENTE", texto: s.texto });
    }));
    seg.sort((a, b) => a.ini - b.ini);
    const lineas = [];
    for (const s of seg) {
      const u = lineas[lineas.length - 1];
      if (u && u.rol === s.rol) u.texto += " " + s.texto; else lineas.push({ ...s });
    }
    return lineas.map(l => `${l.rol}: ${l.texto}`).join("\n");
  }
  function alternar(texto) {
    if (tieneEtiquetas(texto)) return texto;
    return texto.split(/\n+/).filter(l => l.trim()).map((l, i) => `${i % 2 ? "CLIENTE" : "ASESOR"}: ${l.trim()}`).join("\n");
  }
  function invertir(texto) {
    return texto.split("\n").map(l => /^\s*ASESOR[A]?\s*:/i.test(l) ? l.replace(/^\s*ASESOR[A]?\s*:/i, "CLIENTE:")
      : /^\s*CLIENTE\s*:/i.test(l) ? l.replace(/^\s*CLIENTE\s*:/i, "ASESOR:") : l).join("\n");
  }
  const api = { tieneEtiquetas, unirCanales, alternar, invertir };
  if (typeof module !== "undefined") module.exports = api; else root.Transcripcion = api;
})(typeof self !== "undefined" ? self : this);
