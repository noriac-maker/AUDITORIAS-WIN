"use strict";
/* ============ utilidades ============ */
const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (n, d = 1) => n == null ? "—" : Number(n).toFixed(d);
const cls = v => String(v || "").replace(/[\s_]+/g, m => m === " " ? "" : m);
const pill = (v, t) => `<span class="pill ${cls(v)}">${esc(t ?? String(v).replace(/_/g, " "))}</span>`;
const tc = s => String(s || "").toLowerCase().replace(/(^|\s)\S/g, m => m.toUpperCase());
const iniciales = n => String(n || "?").split(/\s+/).slice(0, 2).map(x => x[0]).join("").toUpperCase();
const fdate = s => { if (!s) return ""; const [y, m, d] = String(s).slice(0, 10).split("-"); return d ? `${d}/${m}/${y}` : s; };
const colNota = n => n == null ? "var(--mut)" : n < 70 ? "var(--bad)" : n < 85 ? "#F59E0B" : "var(--ok)";
const nivCol = { Deficiente: "var(--bad)", Aceptable: "#F59E0B", Excelente: "var(--ok)" };
const ICO = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>', users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6"/><path d="M16 4.5a3.5 3.5 0 010 7M18 14c2.2.6 3.5 2.5 3.5 6"/>',
  chart: '<path d="M4 20V11M10 20V4M16 20v-6M22 20H2"/>', plus: '<path d="M12 5v14M5 12h14"/>', inbox: '<path d="M4 13l3-8h10l3 8v6H4z"/><path d="M4 13h5l1 2h4l1-2h5"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>', file: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>', up: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>', out: '<path d="M9 4H5a2 2 0 00-2 2v12a2 2 0 002 2h4M16 8l4 4-4 4M20 12H9"/>',
  left: '<path d="M15 6l-6 6 6 6"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>', moon: '<path d="M21 13A9 9 0 1111 3a7 7 0 0010 10z"/>',
  alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>', check: '<path d="M5 12l5 5 9-10"/>', trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>'
};
const ico = n => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${ICO[n] || ""}</svg>`;
const S = { user: null, rol: null, auth: true, meta: null, theme: null };
let RT = 0, TOAST;

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({ error: "Respuesta inválida del servidor" }));
  if (r.status === 401 && path !== "/api/login") { S.user = null; vLogin(); throw new Error("Sesión expirada"); }
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function toast(m, err) { clearTimeout(TOAST); $$(".toast").forEach(e => e.remove()); const d = document.createElement("div"); d.className = "toast" + (err ? " err" : ""); d.textContent = m; document.body.appendChild(d); TOAST = setTimeout(() => d.remove(), err ? 6500 : 3200); }
function modal(html) { const m = document.createElement("div"); m.className = "mask"; m.innerHTML = `<div class="modal">${html}</div>`; m.onclick = e => { if (e.target === m) m.remove(); }; document.body.appendChild(m); return m; }
const view = h => { const v = $("#view"); if (v) { v.innerHTML = h; window.scrollTo(0, 0); } };
const skel = () => `<div class="grid g3"><div class="card"><div class="sk" style="width:60%"></div><div class="sk mt" style="height:34px"></div></div><div class="card"><div class="sk" style="width:50%"></div><div class="sk mt" style="height:34px"></div></div><div class="card"><div class="sk" style="width:70%"></div><div class="sk mt" style="height:34px"></div></div></div>`;
const volver = (href, txt) => `<a class="back" href="${href}">${ico("left")} ${txt}</a>`;

/* ============ gráficos ============ */
function gauge(n, etq) {
  const v = Math.max(0, Math.min(100, n || 0)), arco = "M10 64A50 50 0 0 1 110 64";
  return `<svg class="gauge" viewBox="0 0 120 78" role="img" aria-label="Nota ${fmt(n)}"><path d="${arco}" fill="none" stroke="var(--line)" stroke-width="11" stroke-linecap="round"/><path d="${arco}" fill="none" stroke="${colNota(n)}" stroke-width="11" stroke-linecap="round" pathLength="100" stroke-dasharray="${v} 100"/><text x="60" y="58" text-anchor="middle" font-size="26" font-weight="800" fill="var(--ink)">${n == null ? "—" : fmt(n)}</text><text x="60" y="74" text-anchor="middle" font-size="8" fill="var(--mut)">${esc(etq || "")}</text></svg>`;
}
function donut(segs) {
  let off = 25;
  const c = segs.map(([v, col]) => { const s = `<circle cx="21" cy="21" r="15.9155" fill="none" stroke="${col}" stroke-width="6" stroke-dasharray="${v} ${100 - v}" stroke-dashoffset="${off}"/>`; off -= v; return s; }).join("");
  return `<svg class="donut" viewBox="0 0 42 42"><circle cx="21" cy="21" r="15.9155" fill="none" stroke="var(--line)" stroke-width="6"/>${c}</svg>`;
}
function hbars(items, { max = 100, suf = "%" } = {}) {
  return items.map(i => `<div class="hb"><span title="${esc(i.label)}">${esc(i.label)}${i.sub ? ` <small>${esc(i.sub)}</small>` : ""}</span><div class="bar"><i style="width:${Math.max(0, Math.min(100, i.value / max * 100))}%;background:${i.color || "var(--brand)"}"></i></div><b>${fmt(i.value)}${suf}</b></div>`).join("") || '<div class="empty">Sin datos</div>';
}
let GID = 0;
function linea(pts) {
  if (!pts.length) return '<div class="empty">Sin datos</div>';
  const id = "g" + (++GID), W = 560, H = 210, p = 34, ys = pts.map(x => x.y);
  const lo = Math.max(0, Math.floor((Math.min(...ys, 70) - 6) / 5) * 5), hi = Math.min(100, Math.ceil((Math.max(...ys, 85) + 3) / 5) * 5);
  const X = i => p + (pts.length === 1 ? (W - 2 * p) / 2 : i * (W - 2 * p) / (pts.length - 1)), Y = v => H - 30 - (v - lo) / (hi - lo || 1) * (H - 54);
  const ref = [[70, "var(--bad)"], [85, "var(--ok)"]].filter(([v]) => v > lo && v < hi).map(([v, c]) => `<line x1="${p}" x2="${W - p + 10}" y1="${Y(v)}" y2="${Y(v)}" stroke="${c}" stroke-dasharray="4 4" opacity=".55"/><text x="${p - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="10.5" fill="var(--mut)">${v}</text>`).join("");
  const d = pts.map((x, i) => `${i ? "L" : "M"}${X(i)},${Y(x.y)}`).join(" ");
  const area = `${d} L${X(pts.length - 1)},${H - 30} L${X(0)},${H - 30} Z`;
  const every = Math.ceil(pts.length / 6);
  const dots = pts.map((x, i) => `<circle cx="${X(i)}" cy="${Y(x.y)}" r="4.5" fill="var(--card)" stroke="${colNota(x.y)}" stroke-width="2.5"><title>${esc(x.t || x.x)}: ${fmt(x.y)}</title></circle>${pts.length <= 8 ? `<text x="${X(i)}" y="${Y(x.y) - 10}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ink)">${fmt(x.y, 0)}</text>` : ""}${i % every === 0 ? `<text x="${X(i)}" y="${H - 9}" text-anchor="middle" font-size="10.5" fill="var(--mut)">${esc(x.x)}</text>` : ""}`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img"><defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#F08012" stop-opacity=".28"/><stop offset="1" stop-color="#F08012" stop-opacity="0"/></linearGradient></defs>${ref}<path d="${area}" fill="url(#${id})"/><path d="${d}" fill="none" stroke="var(--brand)" stroke-width="2.8" stroke-linejoin="round"/>${dots}</svg>`;
}
const nivelLeyenda = d => `<div class="leg">${[["Deficiente", d.pct_deficiente], ["Aceptable", d.pct_aceptable], ["Excelente", d.pct_excelente]].map(([k, v]) => `<span><span class="dot" style="background:${nivCol[k]}"></span>${k} <b>${v}%</b></span>`).join("")}</div>`;
const nivelDonut = d => donut([[d.pct_deficiente, nivCol.Deficiente], [d.pct_aceptable, nivCol.Aceptable], [d.pct_excelente, nivCol.Excelente]]);

/* ============ ASESOR (perfil e historial) ============ */
async function vAsesor(ctx, id) {
  const d = await api("/api/asesor/" + id); if (!ctx.ok()) return;
  const a = d.asesor, dif = d.nota != null && d.equipo != null ? d.nota - d.equipo : null;
  view(`${esSup() ? volver("#/asesores", "Asesores") : ""}
   <div class="card"><div class="row" style="gap:18px;align-items:center"><div class="av ${d.nivel || "nn"}" style="width:64px;height:64px;font-size:22px;border-radius:18px">${esc(iniciales(a.nombre))}</div>
    <div style="flex:1;min-width:200px"><h1 style="margin:0">${esc(tc(a.nombre))}</h1><div class="mini">Supervisor: ${esc(tc(a.supervisor || "—"))} · DNI ${esc(a.dni || "—")}</div><div class="row" style="margin-top:8px">${d.nivel ? pill(d.nivel) : ""}${d.muestra_pequena ? pill("warn", "muestra pequeña") : ""}</div></div>
    ${gauge(d.nota, "nota promedio")}</div></div>
   ${d.muestra_pequena ? `<div class="banner w mt">${ico("alert")}<div>Este asesor tiene solo <b>${d.n}</b> venta(s) auditada(s) (mínimo recomendado: ${d.min_muestra}). Úsalo como alerta; no sostiene una conclusión individual.</div></div>` : ""}
   <div class="grid g4 mt"><div class="card kpi"><div class="l">Ventas auditadas</div><div class="v">${d.n}</div><div class="s">${d.historial.length} llamadas en total</div></div>
    <div class="card kpi"><div class="l">Frente al equipo</div><div class="v" style="color:${dif == null ? "inherit" : dif < 0 ? "var(--bad)" : "var(--ok)"}">${dif == null ? "—" : (dif > 0 ? "+" : "") + fmt(dif)}</div><div class="s">equipo ${fmt(d.equipo)}</div></div>
    <div class="card kpi"><div class="l">Deficiente (&lt; 70)</div><div class="v" style="color:var(--bad)">${d.pct_deficiente}%</div></div>
    <div class="card kpi"><div class="l">Excelente (≥ 85)</div><div class="v" style="color:var(--ok)">${d.pct_excelente}%</div></div></div>
   <div class="grid gs mt"><div class="card"><h2>Evolución de la nota</h2>${linea(d.evolucion.map(e => ({ x: fdate(e.fecha).slice(0, 5), y: e.nota, t: fdate(e.fecha) })))}<p class="mini" style="margin:6px 0 0">Una marca por venta auditada. Líneas punteadas: 70 (deficiente) y 85 (excelente).</p></div>
    <div class="card"><h2>Cumplimiento por pilar</h2>${hbars(d.pilares.map(p => ({ label: p.modelo, sub: `${p.peso} pts`, value: p.cumplimiento, color: p.cumplimiento < 85 ? "#F59E0B" : "var(--ok)" })))}</div></div>
   <div class="card mt"><h2>Qué reforzar</h2>${d.coaching.length ? d.coaching.map(c => `<div class="cl"><div class="h"><b>${esc(c.nombre)}</b>${pill("NO", c.no + " de " + c.aplicables + " en NO")}</div><div class="mini">${esc(c.pilar)} · el equipo falla ${fmt(c.equipo)}% de las veces; este asesor ${fmt(c.pct_no)}%</div></div>`).join("") : '<div class="empty">Sin quiebres en las ventas auditadas.</div>'}</div>
   <div class="card mt"><h2>Historial de auditorías</h2>${d.historial.length ? d.historial.map(h => `<div class="item" style="cursor:default"><div class="mn"><div class="tt">Llamada ${esc(h.llamada)}</div><div class="mini">${fdate(h.fecha)} · ${h.venta ? "Venta" : "Sin venta"}</div></div>
    <div class="nt" style="color:${colNota(h.nota)}">${fmt(h.nota)}</div><div class="sd">${h.nivel ? pill(h.nivel) : ""}${pill(h.estado)}${h.pauta ? pill(h.pauta.replace(" ", ""), "Pauta: " + h.pauta.toLowerCase()) : ""}</div></div>`).join("") : '<div class="empty">Sin auditorías</div>'}</div>`);
}


/* ============ audio ============ */
const AUD = { canales: null, ncan: 0, worker: null, nombre: "" };
async function cargarAudio(file) {
  AUD.nombre = ""; AUD.file = file; $("#dn").textContent = file.name; $("#di").textContent = "Leyendo audio…";
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext, c = new Ctx({ sampleRate: 16000 }), buf = await c.decodeAudioData(await file.arrayBuffer()); c.close();
    AUD.ncan = Math.min(buf.numberOfChannels, 2); AUD.canales = Array.from({ length: AUD.ncan }, (_, i) => buf.getChannelData(i).slice());
    const m = Math.floor(buf.duration / 60), s = Math.round(buf.duration % 60);
    $("#di").textContent = `${m} min ${s} s · ${(file.size / 1048576).toFixed(1)} MB · ${AUD.ncan === 2 ? "estéreo" : "mono"}`;
    $("#aopt").hidden = false; $("#trw").hidden = false; $("#csw").hidden = AUD.ncan < 2; $("#ast").textContent = buf.duration > 900 ? "Audio largo: puede tardar varios minutos." : "";
  } catch (e) { AUD.canales = null; $("#di").textContent = "No se pudo leer este audio. Prueba con MP3, WAV o M4A."; $("#aopt").hidden = true; $("#trw").hidden = true; }
}
function transcribir() {
  if (!AUD.canales) return;
  const sel = AUD.ncan === 2 ? $("#csel").value : "mix", sep = AUD.ncan === 2 && sel !== "mix", asesor = sep ? +sel : null;
  let canales = AUD.canales.map(c => c.slice());
  if (!sep) { const n = canales[0].length, mono = new Float32Array(n); for (let i = 0; i < n; i++) { let t = 0; for (const c of canales) t += c[i]; mono[i] = t / canales.length; } canales = [mono]; }
  if (AUD.worker) AUD.worker.terminate();
  const prog = $("#prog"), bar = $("#progi"), st = $("#ast"); prog.hidden = false; bar.style.width = "3%"; $("#btr").disabled = true; st.textContent = "Cargando motor de transcripción…";
  const fin = (msg, err) => { $("#btr").disabled = false; prog.hidden = true; if (msg) { st.textContent = msg; if (err) toast(msg, 1); } };
  const falla = async m => {
    if (S.meta && S.meta.asr && AUD.file) {
      try { st.textContent = "Usando la transcripción del servidor…"; const r = await fetch("/api/transcribir", { method: "POST", headers: { "X-Filename": AUD.file.name }, body: AUD.file }), j = await r.json(); if (!r.ok) throw new Error(j.error);
        $("#tx").value = j.texto; AUD.nombre = "whisper-servidor"; $("#txh").textContent = "Transcripción del servidor (sin hablantes). Usa «Etiquetar alternando» o edítala."; fin("Transcripción lista.", 0); return; } catch (e) { m = e.message; }
    }
    fin("No se pudo transcribir en el navegador: " + m + ". Pega la transcripción manualmente o revisa tu conexión a internet.", 1);
  };
  try {
    const w = new Worker("/asr-worker.js", { type: "module" }); AUD.worker = w;
    w.onmessage = e => { const d = e.data;
      if (d.tipo === "descarga") { bar.style.width = Math.max(3, d.pct * .5) + "%"; st.textContent = `Descargando modelo… ${Math.round(d.pct)}% (solo la primera vez)`; }
      else if (d.tipo === "estado") { bar.style.width = "70%"; st.textContent = d.texto; }
      else if (d.tipo === "listo") { bar.style.width = "100%"; AUD.nombre = "whisper"; $("#tx").value = Transcripcion.unirCanales(d.resultados, asesor);
        const etq = Transcripcion.tieneEtiquetas($("#tx").value); $("#txh").textContent = etq ? "Hablantes separados por canal. Revisa la transcripción antes de analizar." : "Audio mono: no se separaron los hablantes. Usa «Etiquetar alternando» o edita las líneas ASESOR:/CLIENTE:.";
        fin("Transcripción lista. Revísala y pulsa «Analizar llamada».", 0); toast("Transcripción lista"); }
      else if (d.tipo === "error") falla(d.mensaje); };
    w.onerror = e => falla(e.message || "no se pudo cargar el motor");
    w.postMessage({ canales, modelo: $("#msel").value }, canales.map(c => c.buffer));
  } catch (e) { falla(e.message); }
}


/* ============ v3: dos interfaces (supervisor / asesor) ============ */
Object.assign(ICO, {
  ok: '<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>', x: '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
  bell: '<path d="M6 8a6 6 0 0112 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 004 0"/>', bulb: '<path d="M9 18h6M10 21h4M12 3a6 6 0 00-4 10c1 1 1 2 1 3h6c0-1 0-2 1-3a6 6 0 00-4-10z"/>',
  target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>', chev: '<path d="M9 6l6 6-6 6"/>', shield: '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0014 0M12 18v3"/>', sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>'
});
const esSup = () => S.rol === "admin";
const EST = { APROBADO: ["Aprobada", "ok", "ok", "El contrato se leyó correctamente. Esta venta puede subirse al sistema de ventas."], OBSERVADO: ["Observada", "alert", "warn", "El bot tiene dudas. El supervisor debe revisarla y decidir."], RECHAZADO: ["Rechazada", "x", "bad", "No cumple el contrato. No se puede subir al sistema de ventas: corrige y vuelve a enviar."] };
const pillE = e => pill(e, (EST[e] || [e])[0]);
const ph = (t, s, right = "") => `<div class="ph"><div><h1>${t}</h1><p class="sub">${s}</p></div><span class="sp"></span>${right}</div>`;
const kc = (l, v, i, tone, sub, delta = "") => `<div class="kc"><div class="kh"><span>${l}</span><div class="kic ${tone}">${ico(i)}</div></div><div class="kv">${v}</div>${delta}<div class="ks">${sub}</div></div>`;
const pc = (t, body, extra = "") => `<div class="pc"><div class="pt"><h2>${t}</h2>${extra}</div><div class="pb">${body}</div></div>`;
const meter = (t, v, min, exp) => `<div class="card mtr"><div class="ml">${t}</div><div class="mv" style="color:${v == null ? "var(--mut)" : min == null || v >= min ? "var(--ok)" : "var(--bad)"}">${v == null ? "—" : fmt(v, 0) + "%"}</div><div class="mbar"><i style="width:${v || 0}%"></i>${min != null ? `<u style="left:${min}%"></u>` : ""}</div><div class="mini">${min != null ? `Mínimo ${min}%. ` : ""}${exp}</div></div>`;
const NAVS = { admin: [["asesores", "users", "Asesores"], ["resumen", "chart", "Resumen"], ["ventas", "inbox", "Ventas enviadas"], ["contrato", "file", "Contrato"], ["reglas", "info", "Cómo se califica"]],
  asesor: [["subir", "up", "Subir venta"], ["ventas", "inbox", "Mis ventas"], ["mi", "chart", "Mi desempeño"], ["reglas", "info", "Cómo se valida"]] };

function shell() {
  const nav = NAVS[esSup() ? "admin" : "asesor"], rt = esSup() ? "Supervisor" : "Asesor";
  const tools = `<button class="ib js-tema" title="Cambiar tema" aria-label="Cambiar tema">${ico("sun")}</button><button class="ib js-salir" title="Cerrar sesión" aria-label="Cerrar sesión">${ico("out")}</button>`;
  $("#root").innerHTML = `<div class="shell"><aside class="sidebar"><a class="brandb" href="#/${nav[0][0]}"><img src="/assets/logo.png" alt="WIN"><div><b>Auditoría de calidad</b><small>WIN · Ventas por llamada</small></div></a>
    <nav class="snav">${nav.map(([k, i, t]) => `<a href="#/${k}" data-k="${k}">${ico(i)}<span>${t}</span>${k === "ventas" && esSup() ? '<span class="badge" data-pend hidden></span>' : ""}</a>`).join("")}</nav>
    <div class="hcard"><div class="hic">${ico("shield")}</div><b>${esSup() ? "Un solo criterio para todos" : "Sube tu venta y listo"}</b><p>${esSup() ? "Cada venta se valida contra el contrato con las mismas reglas." : "El bot revisa la lectura del contrato; no esperas a nadie."}</p><a class="btn sm sec" href="#/reglas">${esSup() ? "Ver cómo se califica" : "Ver cómo se valida"}</a></div>
    <div class="who"><div class="av nn" style="width:40px;height:40px;font-size:13px;border-radius:12px">${esc(iniciales(S.user))}</div><div class="sp"><b>${esc(tc(S.user))}</b><small>${rt}</small></div>${tools}</div></aside><div class="page" id="view"></div></div>
    <header class="top"><div class="in"><a class="brand" href="#/${nav[0][0]}"><img src="/assets/logo.png" alt="WIN"><div>Auditoría de calidad</div></a><div class="tools">${tools}</div></div></header>
    <nav class="bnav">${nav.map(([k, i, t], n) => `<a href="#/${k}" data-k="${k}" class="${!esSup() && n === 0 ? "mid" : ""}">${!esSup() && n === 0 ? `<span class="c">${ico(i)}</span>` : ico(i)}<span>${t.replace("Ventas enviadas", "Ventas").replace("Cómo se califica", "Reglas").replace("Cómo se valida", "Reglas")}</span>${k === "ventas" && esSup() ? '<span class="badge" data-pend hidden></span>' : ""}</a>`).join("")}</nav>`;
  $$(".js-tema").forEach(b => b.onclick = () => { const t = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = t; try { localStorage.setItem("tema", t); } catch (e) { } });
  $$(".js-salir").forEach(b => b.onclick = async () => { await fetch("/api/logout", { method: "POST" }); S.user = null; location.hash = ""; vLogin(); });
}
async function badgePend() { if (!esSup()) return; try { const r = await api("/api/resumen"), n = r.validaciones.por_revisar; $$("[data-pend]").forEach(b => { b.hidden = !n; b.textContent = n; }); } catch (e) { } }

function vLogin() {
  const T = [["up", "Sube tu audio", "Un solo lugar para cada venta"], ["shield", "Validación automática", "El bot revisa el contrato"], ["ok", "Aprobación clara", "Sabes si se puede subir"], ["chart", "Reportes del equipo", "Calidad por asesor"]];
  $("#root").innerHTML = `<div class="lg"><div class="lgl"><img src="/assets/icon-192.png" alt="WIN"><h1>Cada venta, <em>validada</em> contra el contrato.</h1><p>Sube el audio y tu plantilla del cliente: el bot revisa la lectura del contrato y los datos, y te dice si la venta puede subir al sistema.</p>
    <div class="lgt">${T.map(([i, t, d]) => `<div class="lti"><div class="hic">${ico(i)}</div><b>${t}</b><span>${d}</span></div>`).join("")}</div></div>
    <div class="lgr"><div class="card"><h1 style="font-size:26px">Bienvenido</h1><p class="sub">Ingresa con tu usuario para continuar.</p>
    <form id="lf" style="display:grid;gap:14px"><label class="f">Usuario<input id="lu" autocomplete="username" autocapitalize="characters" required></label><label class="f">Contraseña<input id="lp" type="password" autocomplete="current-password" required></label>
    <div id="le" class="mini" style="color:var(--bad);min-height:18px"></div><button class="btn block" type="submit">Ingresar</button></form><p class="mini" style="margin:16px 0 0">Asesores: usa tu nombre completo en mayúsculas.</p></div></div></div>`;
  $("#lu").focus();
  $("#lf").onsubmit = async e => { e.preventDefault(); try { const r = await api("/api/login", { usuario: $("#lu").value, clave: $("#lp").value }); S.user = r.usuario; S.rol = r.rol; S.ida = r.id_asesor; arrancar(); } catch (x) { $("#le").textContent = x.message; } };
}

const R = { resumen: vResumen, asesores: vAsesores, asesor: vAsesor, ventas: vVentas, venta: vVenta, subir: vSubir, mi: c => vAsesor(c, S.ida), contrato: vContrato, reglas: vReglas };
const PERMITE = { admin: ["resumen", "asesores", "asesor", "ventas", "venta", "contrato", "reglas"], asesor: ["subir", "mi", "ventas", "venta", "reglas"] };
const ACT = { asesor: "asesores", venta: "ventas" };
async function router() {
  if (!S.user) return;
  let [k, arg] = location.hash.replace(/^#\/?/, "").split("/");
  if (!PERMITE[esSup() ? "admin" : "asesor"].includes(k)) { k = esSup() ? "asesores" : "subir"; }
  const my = ++RT, ctx = { ok: () => my === RT };
  $$("[data-k]").forEach(a => a.classList.toggle("on", a.dataset.k === (ACT[k] || k)));
  view(skel());
  try { await R[k](ctx, arg); } catch (e) { if (ctx.ok() && e.message !== "Sesión expirada") view(`<div class="card"><h2>No se pudo cargar</h2><p>${esc(e.message)}</p></div>`); }
  if (ctx.ok()) badgePend();
}
window.addEventListener("hashchange", router);

/* ---------- RESUMEN (supervisor) ---------- */
async function vResumen(ctx) {
  const [d, as, vs, rs] = await Promise.all([api("/api/dashboard?ventas=1"), api("/api/asesores?orden=nota_asc"), api("/api/validaciones"), api("/api/resumen")]); if (!ctx.ok()) return;
  const sem = d.semanal, dif = sem.length > 1 ? sem[sem.length - 1].nota - sem[0].nota : null, V = rs.validaciones, bajos = as.asesores.filter(a => a.nota != null && a.nota < 70);
  const pil = [...d.pilares].sort((a, b) => a.cumplimiento - b.cumplimiento)[0], cr = d.criterios[0], apr = V.enviadas ? Math.round(100 * V.aprobadas / V.enviadas) : null;
  const DESC = { Conquistar: "cómo abre la llamada: saludo, cobertura y actitud", Conocer: "cómo detecta la necesidad: preguntas, escucha y beneficios", Convencer: "cómo resuelve dudas e informa bien", Concretar: "cómo cierra: pedido de cierre, registros y despedida" };
  const lect = [`La nota promedio es <b>${d.nota}</b> sobre 100 (${d.nota >= 85 ? "Excelente" : d.nota >= 70 ? "Aceptable" : "Deficiente"}; la meta es 85 o más).`,
    dif != null ? `Desde la primera semana la nota ${dif < 0 ? "<b>bajó " + fmt(Math.abs(dif)) + " puntos</b>" : "<b>subió " + fmt(dif) + " puntos</b>"} (de ${sem[0].nota} a ${sem[sem.length - 1].nota}).` : "",
    `El pilar más débil es <b>${pil.modelo}</b> (${pil.cumplimiento}%): ${DESC[pil.modelo]}.`, `El criterio que más se incumple es <b>«${esc(cr.nombre)}»</b>: falla en ${cr.pct_no}% de las ventas donde aplica.`,
    `<b>${bajos.length}</b> asesor(es) tienen nota deficiente (menos de 70).`].filter(Boolean);
  view(`${ph("Resumen del equipo", "Cómo van la calidad de las llamadas de venta y la validación de contratos. Los datos históricos son simulados.", `<span class="chip2">Julio 2026 · datos simulados</span>`)}
  <div class="stack"><div class="kg">
   ${kc("Nota promedio de calidad", d.nota, "target", "o", "Promedio de 0 a 100 de las ventas auditadas. Meta: 85 o más.", dif == null ? "" : `<div class="kd ${dif < 0 ? "dn" : "up"}">${dif < 0 ? "▼" : "▲"} ${fmt(Math.abs(dif))} desde la 1.ª semana</div>`)}
   ${kc("Ventas con nota baja", d.pct_deficiente + "%", "alert", "r", `${Math.round(d.n * d.pct_deficiente / 100)} de ${d.n} ventas tienen nota menor a 70.`)}
   ${kc("Contratos aprobados por el bot", apr == null ? "—" : apr + "%", "shield", "g", V.enviadas ? `${V.aprobadas} de ${V.enviadas} ventas enviadas por los asesores.` : "Aún no hay ventas enviadas por los asesores.")}
   ${kc("Esperan tu decisión", V.por_revisar, "bell", "b", "Ventas observadas: el bot dudó y necesita que tú decidas.")}</div>
  ${V.por_revisar ? `<div class="alertc">${ico("bell")}<div style="flex:1"><b>${V.por_revisar} venta(s) esperan tu decisión</b><div class="mini">El bot las marcó como observadas (cliente poco entendible o cláusula dudosa).</div></div><a class="btn sm" href="#/ventas">Revisar ahora</a></div>` : ""}
  ${pc("Lectura rápida", `<ul class="rl">${lect.map(t => `<li><span class="hic">${ico("bulb")}</span><span>${t}</span></li>`).join("")}</ul>`)}
  <div class="two2">${pc("Asesores que necesitan apoyo", as.asesores.filter(a => a.nota != null).slice(0, 5).map(a => `<a class="cr" href="#/asesor/${a.id}"><div class="av ${a.nivel}" style="width:42px;height:42px">${esc(iniciales(a.nombre))}</div><div class="mn"><b>${esc(tc(a.nombre))}</b><div class="mini">${a.n} ventas auditadas · ${a.d} con nota baja</div></div><div style="text-align:right"><b style="font-size:20px;color:${colNota(a.nota)}">${fmt(a.nota)}</b><div>${pill(a.nivel)}</div></div></a>`).join("") + `<p class="mini" style="margin:12px 0 0">Cada asesor tiene pocas ventas auditadas: úsalo como alerta, no como ranking definitivo.</p>`, `<a class="btn ghost sm" href="#/asesores">Ver todos</a>`)}
   ${pc("Ventas enviadas recientemente", vs.length ? vs.slice(0, 5).map(v => `<a class="cr" href="#/venta/${v.id}"><div class="mn"><b>${esc(tc(v.asesor))}</b><div class="mini">Cliente: ${esc(tc(v.cliente || "—"))} · contrato ${fmt(v.pct_contrato, 0)}%</div></div>${pillE(v.final)}</a>`).join("") : '<div class="empty">Todavía no hay ventas enviadas.<br><span class="mini">Cuando un asesor suba una venta, aparecerá aquí con su estado.</span></div>', `<a class="btn ghost sm" href="#/ventas">Ver todas</a>`)}</div>
  <div class="two2">${pc("Calidad por pilar", `<p class="mini" style="margin-top:0">Qué tan bien se cumple cada etapa de la llamada (0 a 100).</p>${d.pilares.map(p => `<div style="margin:14px 0"><div class="row" style="justify-content:space-between"><b>${p.modelo}</b><b style="color:${colNota(p.cumplimiento)}">${p.cumplimiento}%</b></div><div class="nbar" style="max-width:none"><i style="width:${p.cumplimiento}%;background:${colNota(p.cumplimiento)}"></i></div><div class="mini" style="margin-top:4px">${DESC[p.modelo][0].toUpperCase() + DESC[p.modelo].slice(1)} · vale ${p.peso} puntos</div></div>`).join("")}`)}
   ${pc("Nivel de las ventas", `<div class="row" style="gap:24px;flex-wrap:nowrap">${nivelDonut(d)}<div style="flex:1">${nivelLeyenda(d)}</div></div><p class="mini">Excelente: 85 o más · Aceptable: de 70 a 84 · Deficiente: menos de 70.</p>
    <div class="tip" style="margin-top:14px"><div class="hic">${ico("bulb")}</div><div><b>Consejo</b><div class="mini" style="color:var(--ink)">Refuerza «${pil.modelo}» con tu equipo: es el pilar con menor cumplimiento.</div></div></div>`)}</div></div>`);
}

/* ---------- ASESORES (supervisor) ---------- */
const FA = { q: "", supervisor: "", orden: "nombre" };
async function vAsesores(ctx) {
  if (!S.meta) S.meta = await api("/api/meta"); if (!ctx.ok()) return;
  const fl = S.meta.filtros;
  view(`${ph("Asesores", "Elige un asesor para ver su historial, su nota y qué debe reforzar.")}
  <div class="bar2"><div class="sr">${ico("search")}<input id="aq" placeholder="Buscar asesor por nombre…" value="${esc(FA.q)}" autocomplete="off"></div>
   <select id="as"><option value="">Todos los supervisores</option>${fl.supervisores.map(x => `<option value="${esc(x)}" ${x === FA.supervisor ? "selected" : ""}>${esc(tc(x))}</option>`).join("")}</select>
   <select id="ao">${[["nombre", "Ordenar: nombre (A–Z)"], ["nota_asc", "Ordenar: nota más baja"], ["nota_desc", "Ordenar: nota más alta"], ["def", "Ordenar: más ventas con nota baja"]].map(([v, t]) => `<option value="${v}" ${FA.orden === v ? "selected" : ""}>${t}</option>`).join("")}</select></div>
  <div id="al">${skel()}</div>`);
  const carga = async () => {
    const r = await api("/api/asesores?" + new URLSearchParams(Object.entries(FA).filter(([, v]) => v))); if (!ctx.ok()) return;
    $("#al").innerHTML = `<div class="pc"><div class="lh"><span>Asesor</span><span class="hm">Supervisor</span><span class="hm">Ventas auditadas</span><span>Nota promedio</span><span class="hm">Estado</span><span class="hm"></span></div>
    ${r.asesores.map(a => `<a class="lr" href="#/asesor/${a.id}"><div class="who2"><div class="av ${a.nivel || "nn"}">${esc(iniciales(a.nombre))}</div><div style="min-width:0"><div class="nm">${esc(tc(a.nombre))}</div><div class="mini">${esc(tc(a.campana || ""))}${a.pend ? " · " + a.pend + " pendiente(s)" : ""}</div></div></div>
      <div class="hm">${esc(tc(a.supervisor || "—"))}</div><div class="hm">${a.n}</div><div><b style="font-size:19px;color:${colNota(a.nota)}">${fmt(a.nota)}</b><div class="nbar"><i style="width:${a.nota || 0}%;background:${colNota(a.nota)}"></i></div></div>
      <div class="hm">${a.nivel ? pill(a.nivel) : '<span class="mini">Sin ventas</span>'}</div><div class="hm ch">${ico("chev")}</div></a>`).join("") || '<div class="empty">Ningún asesor coincide con la búsqueda.</div>'}</div>
    <p class="mini" style="margin:14px 4px 0">${r.total} asesores · la nota es el promedio de sus ventas auditadas (0 a 100).</p>`;
  };
  let tm; $("#aq").oninput = e => { FA.q = e.target.value; clearTimeout(tm); tm = setTimeout(carga, 250); }; $("#as").onchange = e => { FA.supervisor = e.target.value; carga(); }; $("#ao").onchange = e => { FA.orden = e.target.value; carga(); };
  carga();
}

/* ---------- VENTAS ENVIADAS / MIS VENTAS ---------- */
let FV = "";
async function vVentas(ctx) {
  const lista = await api("/api/validaciones" + (FV ? "?estado=" + FV : "")), todas = FV ? await api("/api/validaciones") : lista; if (!ctx.ok()) return;
  const n = e => todas.filter(v => v.final === e).length, T = [["", "Todas", todas.length], ["APROBADO", "Aprobadas", n("APROBADO")], ["OBSERVADO", "Observadas", n("OBSERVADO")], ["RECHAZADO", "Rechazadas", n("RECHAZADO")]];
  view(`${ph(esSup() ? "Ventas enviadas" : "Mis ventas", esSup() ? "Ventas que los asesores subieron y el bot validó contra el contrato. Decide las observadas." : "Las ventas que subiste y el resultado de la validación.", esSup() ? "" : `<a class="btn" href="#/subir">${ico("plus")} Subir venta</a>`)}
  <div class="tabs">${T.map(([k, t, c]) => `<button data-e="${k}" class="${FV === k ? "on" : ""}">${t} (${c})</button>`).join("")}</div>
  <div class="pc"><div class="lh vr"><span>${esSup() ? "Asesor" : "Cliente"}</span><span class="hm">Fecha</span><span>Estado</span><span class="hm">Contrato</span><span class="hm">Cliente entendible</span><span class="hm"></span></div>
  ${lista.map(v => `<a class="lr vr" href="#/venta/${v.id}"><div><div class="nm">${esc(tc(esSup() ? v.asesor : (v.cliente || "Cliente")))}</div><div class="mini">${esSup() ? "Cliente: " + esc(tc(v.cliente || "—")) : "Venta #" + v.id}</div></div><div class="hm">${esc(String(v.fecha).slice(0, 16))}</div><div>${pillE(v.final)}</div><div class="hm"><b>${fmt(v.pct_contrato, 0)}%</b></div><div class="hm"><b>${v.claridad == null ? "—" : fmt(v.claridad, 0) + "%"}</b></div><div class="hm ch">${ico("chev")}</div></a>`).join("") || `<div class="empty">${FV ? "No hay ventas con ese estado." : "Todavía no hay ventas enviadas."}${esSup() ? "" : `<br><a class="btn mt" href="#/subir">${ico("plus")} Subir mi primera venta</a>`}</div>`}</div>`);
  $$(".tabs button").forEach(b => b.onclick = () => { FV = b.dataset.e; vVentas(ctx); });
}

/* ---------- DETALLE DE UNA VENTA ---------- */
async function vVenta(ctx, id) {
  const d = await api("/api/validacion/" + id); if (!ctx.ok()) return;
  const r = d.resultado, e = EST[d.final], cl = r.clausulas, resp = cl.filter(c => c.tipo.startsWith("resp")), lect = cl.filter(c => !c.tipo.startsWith("resp")), decidida = d.decision && d.decision !== d.estado;
  const tx = esc(d.transcripcion || "").replace(/^(ASESOR[A]?:|AGENTE:)/gmi, '<span class="a">$1</span>').replace(/^(CLIENTE:)/gmi, '<span class="c">$1</span>');
  view(`<a class="back" href="#/ventas">${ico("left")} ${esSup() ? "Ventas enviadas" : "Mis ventas"}</a>${ph("Venta #" + d.id_validacion, `Cliente: ${esc(tc(d.cliente || "—"))} · enviada por ${esc(tc(d.asesor))} el ${esc(String(d.fecha).slice(0, 16))}`)}
  <div class="stack"><div class="vb ${e[2]}"><div class="vic">${ico(e[1])}</div><div><h2>${e[0].toUpperCase()}</h2><p>${decidida ? `Decisión del supervisor (${esc(d.revisado_por)}): ${e[0].toLowerCase()}.${d.motivo_decision ? " " + esc(d.motivo_decision) : ""}` : e[3]}</p>${r.motivos.length ? `<ul class="m">${r.motivos.map(m => `<li>${esc(m)}</li>`).join("")}</ul>` : ""}</div></div>
  ${esSup() && d.estado === "OBSERVADO" && !d.decision ? `<div class="card"><h2>Tu decisión</h2><p class="mini" style="margin-top:-6px">Escucha el audio si es necesario y decide si la venta puede subir al sistema de ventas.</p><label class="f">Comentario (opcional)<input id="dm" placeholder="Ej.: escuché el audio y el cliente aceptó"></label><div class="row mt"><button class="btn" id="dok">Aprobar venta</button><button class="btn sec" id="dno">Rechazar venta</button></div></div>` : ""}
  <div class="grid g3" style="gap:20px">${meter("Cumplimiento del contrato", r.pct_contrato, r.umbrales.contrato, "Qué parte del contrato leyó el asesor.")}${meter("Respuestas del cliente que se entienden", r.claridad, r.umbrales.claridad, "Respuestas claras del cliente en la llamada.")}${meter("Datos del cliente leídos bien", r.pct_datos, null, "Coinciden con la plantilla que subió el asesor.")}</div>
  ${pc("Respuestas clave del cliente", resp.map(c => `<div class="cr"><div class="mn"><b>${esc(c.nombre.replace("Cliente responde: ", ""))}</b>${c.evidencia ? `<div class="ev">Dijo: <q>${esc(c.evidencia)}</q></div>` : ""}${c.faltantes.length ? `<div class="ev">${esc(c.faltantes[0])}</div>` : ""}</div>${c.estado === "CUMPLE" ? pill(c.valor, c.valor === "SI" ? "Dijo SÍ" : "Dijo NO") : pill("NO_CUMPLE", "No confirmado")}</div>`).join(""))}
  <div class="two2">${pc("Datos del cliente: plantilla vs. lo leído", r.datos.length ? r.datos.map(x => `<div class="cr"><div class="mn"><b>${esc(x.etiqueta)}</b><div class="mini">${esc(x.esperado)}</div></div>${pill(x.estado, { CORRECTO: "Leído bien", PARCIAL: "Parcial", NO_LEIDO: "No coincide" }[x.estado])}</div>`).join("") : '<div class="empty">No se recibió plantilla.</div>')}
   ${pc("Lectura del contrato", lect.map(c => `<div class="cr"><div class="mn"><b>${esc(c.nombre)}${c.critica ? ' <span class="mini">· crítica</span>' : ""}</b>${c.evidencia ? `<div class="ev">Dijo: <q>${esc(c.evidencia)}</q></div>` : ""}${c.faltantes.length ? `<div class="ev">Falta: ${esc(c.faltantes.join(", "))}</div>` : ""}</div>${pill(c.estado, { CUMPLE: "Cumple", PARCIAL: "Parcial", NO_CUMPLE: "No cumple" }[c.estado])}</div>`).join(""))}</div>
  <div class="card"><details class="tr"><summary>Ver transcripción completa</summary><div class="tx" style="margin-top:12px">${tx}</div></details></div></div>`);
  if ($("#dok")) { const dec = async x => { try { await api(`/api/validacion/${id}/decidir`, { decision: x, motivo: $("#dm").value }); toast("Decisión guardada"); vVenta(ctx, id); badgePend(); } catch (er) { toast(er.message, 1); } }; $("#dok").onclick = () => dec("APROBADO"); $("#dno").onclick = () => dec("RECHAZADO"); }
}

/* ---------- SUBIR VENTA (asesor): audio y transcripción en un solo apartado ---------- */
async function vSubir(ctx) {
  view(`${ph("Subir una venta", "Sube el audio y tu plantilla del cliente. El bot valida la lectura del contrato y te dice si la venta puede subir al sistema de ventas.")}
  <div class="two2" style="align-items:start"><div class="stack">
   <div class="card"><div class="steps"><span class="n">1</span><h2 style="margin:0">Audio de la venta</h2></div><p class="mini" style="margin-top:0">Sube el audio y la transcripción aparece abajo, lista para revisar. También puedes pegarla a mano.</p>
    <input type="file" id="audio" accept="audio/*,.mp3,.wav,.m4a,.ogg,.aac,.flac,.webm" hidden>
    <div class="drop" id="drop" tabindex="0" role="button">${ico("up")}<b id="dn">Toca para elegir el audio o arrástralo aquí</b><span class="mini" id="di">MP3, WAV, M4A u OGG · se transcribe en tu navegador, el audio no se sube</span></div>
    <div class="fl mt" id="aopt" hidden><label class="f">Calidad de transcripción<select id="msel"><option value="Xenova/whisper-tiny">Rápida</option><option value="Xenova/whisper-base" selected>Equilibrada</option><option value="Xenova/whisper-small">Precisa (más lenta)</option></select></label>
     <label class="f" id="csw" hidden>Audio estéreo: canal del asesor<select id="csel"><option value="0">Izquierdo = asesor</option><option value="1">Derecho = asesor</option><option value="mix">Mezclar (sin separar)</option></select></label></div>
    <div class="row mt" id="trw" hidden><button class="btn" id="btr">Transcribir audio</button><span class="mini" id="ast"></span></div><div class="prog" id="prog" hidden><i id="progi"></i></div>
    <h3 style="margin:22px 0 8px">Transcripción</h3><textarea id="tx" style="min-height:230px" placeholder="ASESOR: Antes de iniciar con la lectura de su contrato…&#10;CLIENTE: Sí, acepto."></textarea>
    <div class="row" style="margin-top:8px"><span class="mini sp" id="txh">Con líneas «ASESOR:» y «CLIENTE:» el bot identifica quién dijo cada cosa.</span><button class="btn sec sm" id="balt">Etiquetar alternando</button><button class="btn sec sm" id="binv">Invertir</button></div></div>
   <div class="card"><div class="steps"><span class="n">2</span><h2 style="margin:0">Plantilla del cliente</h2></div><p class="mini" style="margin-top:0">Pégala tal como la copias (nombres, DNI, nacimiento, correo, teléfono, dirección e internet). El bot comprueba que leíste los datos correctos.</p>
    <textarea id="pl" style="min-height:190px" placeholder="Nombres completos: …&#10;DNI: …&#10;Lugar y fecha nacimiento: …&#10;Correo electrónico: …&#10;Número de teléfono: …&#10;Dirección: …&#10;Internet MBPS: …"></textarea></div>
   <button class="btn block" id="go" style="min-height:54px;font-size:16px">Validar con el contrato</button></div>
  <div class="stack"><div class="card"><h2>Qué revisa el bot</h2><ol class="rl" style="counter-reset:n">${["Que leíste todo el contrato, en orden y con las cifras correctas.", "Que los datos del cliente coinciden con tu plantilla.", "Que el cliente dijo «sí acepto» y respondió las dos preguntas finales.", "Que el contrato cumple al menos 70% y al menos 80% de las respuestas del cliente se entienden."].map((t, i) => `<li><span class="hic">${i + 1}</span><span>${t}</span></li>`).join("")}</ol></div>
   <div class="card"><h2>Probar con una venta de ejemplo</h2><p class="mini" style="margin-top:-6px">Carga una venta de muestra para ver cómo responde el bot.</p><select id="ej"><option value="">Elegir un ejemplo…</option></select></div></div></div>`);
  api("/api/ejemplos-ventas").then(ej => { window.EV = ej; if ($("#ej")) $("#ej").innerHTML += ej.map((e, i) => `<option value="${i}">${esc(e.titulo)}</option>`).join(""); }).catch(() => { });
  $("#ej").onchange = e => { const x = (window.EV || [])[e.target.value]; if (x) { $("#tx").value = x.transcripcion; $("#pl").value = x.plantilla; } };
  $("#balt").onclick = () => { $("#tx").value = Transcripcion.alternar($("#tx").value); }; $("#binv").onclick = () => { $("#tx").value = Transcripcion.invertir($("#tx").value); };
  const drop = $("#drop"), inp = $("#audio");
  drop.onclick = () => inp.click(); drop.onkeydown = e => { if (e.key === "Enter" || e.key === " ") inp.click(); };
  drop.ondragover = e => { e.preventDefault(); drop.classList.add("on"); }; drop.ondragleave = () => drop.classList.remove("on");
  drop.ondrop = e => { e.preventDefault(); drop.classList.remove("on"); if (e.dataTransfer.files[0]) cargarAudio(e.dataTransfer.files[0]); };
  inp.onchange = e => { if (e.target.files[0]) cargarAudio(e.target.files[0]); }; $("#btr").onclick = transcribir;
  $("#go").onclick = async () => { try { $("#go").disabled = true; $("#go").textContent = "Validando…"; const r = await api("/api/validar", { transcripcion: $("#tx").value, plantilla: $("#pl").value }); toast("Venta validada"); location.hash = "#/venta/" + r.id; } catch (e) { toast(e.message, 1); $("#go").disabled = false; $("#go").textContent = "Validar con el contrato"; } };
}

/* ---------- CONTRATO (supervisor) ---------- */
async function vContrato(ctx) {
  const r = await api("/api/pauta"); if (!ctx.ok()) return; const T = { lectura: "Lo lee el asesor", datos: "Datos del cliente", resp_si: "Responde el cliente: debe ser SÍ", resp_libre: "Responde el cliente: SÍ o NO" };
  view(`${ph("Contrato que valida el bot", "Estas son las partes del contrato de voz que el asesor debe leer. El bot las busca en la llamada y marca si se cumplieron.")}
  <div class="stack"><div class="tip"><div class="hic">${ico("info")}</div><div>Las cifras <b>{mbps}</b> y <b>{asegurada}</b> salen de la plantilla de cada cliente (la velocidad asegurada es el 70% de la contratada).</div></div>
  ${pc("Partes del contrato", r.clausulas.map((c, i) => `<div class="cr"><span class="hic" style="background:var(--brand-soft);color:var(--brand-d);width:32px;height:32px;border-radius:10px;font-weight:800;flex:none">${i + 1}</span><div class="mn"><b>${esc(c.nombre)}</b> ${c.critica ? pill("NO", "Crítica") : ""}<div class="mini" style="margin:3px 0 6px"><span class="chip2">${T[c.tipo] || c.tipo}</span> · pesa ${c.peso}</div><div style="font-size:13.5px;line-height:1.55">${esc(c.texto_referencia)}</div></div></div>`).join(""))}</div>`);
}

/* ---------- REGLAS ---------- */
async function vReglas(ctx) {
  if (!S.meta) S.meta = await api("/api/meta"); if (!ctx.ok()) return; const m = S.meta;
  view(`${ph(esSup() ? "Cómo se califica" : "Cómo se valida", "Las reglas que usa el sistema, explicadas sin tecnicismos.")}
  <div class="stack">${pc("Validación del contrato: ¿la venta puede subir al sistema de ventas?", `<div class="grid g3" style="gap:16px">${[["APROBADO", "Cumple 70% o más del contrato, al menos 80% de las respuestas del cliente se entienden y el cliente dijo «sí acepto» y autorizó el uso de sus datos."], ["OBSERVADO", "Cumple 70% o más, pero el cliente se entiende poco o algo quedó a medias. El supervisor escucha y decide."], ["RECHAZADO", "Cumple menos de 70%, o el cliente no dijo «sí acepto», o no autorizó el uso de sus datos. Hay que corregir y volver a enviar."]].map(([e, t]) => `<div class="card" style="box-shadow:none">${pillE(e)}<p style="margin:10px 0 0;font-size:13.5px">${t}</p></div>`).join("")}</div>`)}
  ${pc("Nota de calidad de la llamada (0 a 100)", `<p class="mini" style="margin-top:0">Se calcula con 15 criterios agrupados en 4 pilares. Un criterio incumplido resta puntos a su pilar. Excelente: 85 o más · Aceptable: 70 a 84 · Deficiente: menos de 70.</p>${Object.entries(m.pilares).map(([k, p]) => `<div class="cr"><div class="mn"><b>${p.modelo}</b><div class="mini">${m.criterios.filter(c => c.pilar === k).map(c => esc(c.nombre)).join(" · ")}</div></div><b>${Math.round(p.peso * 100)} pts</b></div>`).join("")}`)}
  ${pc("Qué falta validar", `<ul class="m"><li>La validación del contrato se probó con conversaciones de ejemplo; falta probarla con audios reales de ventas.</li><li>«Respuestas del cliente que se entienden» es una medida aproximada hasta contrastarla con audios reales.</li><li>Las 600 llamadas históricas del resumen son datos simulados.</li></ul>`)}</div>`);
}

/* ============ arranque ============ */
async function arrancar() {
  shell(); S.meta = null;
  try { S.meta = await api("/api/meta"); } catch (e) { return; }
  const h = location.hash.replace(/^#\/?/, "");
  if (!h) location.hash = "#/" + (esSup() ? "asesores" : "subir"); else router();
  badgePend();
}
(async () => {
  try { const yo = await fetch("/api/yo").then(r => r.json()); S.auth = yo.auth; if (yo.usuario) { S.user = yo.usuario; S.rol = yo.rol; S.ida = yo.id_asesor; arrancar(); } else vLogin(); }
  catch (e) { $("#root").innerHTML = '<div class="lg"><div class="lgr"><div class="card">No se pudo conectar con el servidor.</div></div></div>'; }
})();
