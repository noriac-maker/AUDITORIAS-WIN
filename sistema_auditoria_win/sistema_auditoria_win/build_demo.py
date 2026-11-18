"""Genera una demo de un solo archivo HTML (datos incrustados, solo lectura) a partir de la base y la interfaz."""
import json, re, base64, sqlite3, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from auditoria import config as C, contrato, db, servicio
con = db.conectar("datos/auditorias_seed.db"); db.inicializar(con)
cod = {"SI": "S", "NO": "N", "No Aplica": "A"}
filas = []
for a in con.execute("""SELECT a.id_auditoria id, a.id_llamada ll, l.fecha_monitoreo f, l.id_asesor ase, c.nombre cam, l.venta_concretada v, a.nota,
        a.p_conquistar p1, a.p_conocer p2, a.p_convencer p3, a.p_concretar p4 FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada
        JOIN campana c ON c.id_campana=l.id_campana ORDER BY a.id_auditoria"""):
    cs = "".join(cod.get(r[0], "A") for r in con.execute("SELECT valor_final FROM auditoria_criterio WHERE id_auditoria=? ORDER BY id_criterio", (a["id"],)))
    filas.append([a["id"], str(a["ll"]), a["f"], a["ase"], a["cam"], a["v"], round(a["nota"], 4), *[round(a[k], 3) for k in ("p1", "p2", "p3", "p4")], cs])
ases = [dict(id=r["id_asesor"], nombre=r["nombre"], dni=r["dni_enmascarado"], supervisor=r["sup"]) for r in con.execute(
    "SELECT a.*, s.nombre sup FROM asesor a JOIN supervisor s ON s.id_supervisor=a.id_supervisor")]
pauta = servicio.pauta_listar(con, True)
ventas = json.load(open("ejemplos/ventas_demo.json", encoding="utf-8"))
resultados = {v["id"]: contrato.evaluar(pauta, v["transcripcion"], v["plantilla"]) for v in ventas}
orden = [("VENTA-A", 2, "2026-11-10 09:12"), ("VENTA-C", 5, "2026-11-10 11:40"), ("VENTA-B", 8, "2026-11-10 12:05"), ("VENTA-A", 11, "2026-11-11 08:30"), ("VENTA-C", 14, "2026-11-11 09:55"), ("VENTA-A", 17, "2026-11-11 10:20")]
byid = {v["id"]: v for v in ventas}
validaciones = []
for i, (vid, ida, f) in enumerate(orden, 1):
    r = resultados[vid]
    validaciones.append(dict(id=i, id_asesor=ases[ida]["id"], fecha=f, cliente=r["cliente"], estado=r["estado"], transcripcion=byid[vid]["transcripcion"], resultado=r,
                             **(dict(decision="APROBADO", revisado_por="SUPERVISOR", motivo="Escuché el audio: el cliente aceptó") if i == 5 else {})))
fm = con.execute("SELECT MIN(fecha_monitoreo), MAX(fecha_monitoreo) FROM llamada").fetchone()
q = lambda s: [r[0] for r in con.execute(s)]
DEMO = dict(criterios=C.CRITERIOS, pilares=C.PILARES, filas=filas, asesores=ases, pauta=pauta, ventas=ventas, resultados=resultados, validaciones=validaciones, ejemplos=[], auditar={},
            filtros=dict(campanas=q("SELECT nombre FROM campana ORDER BY 1"), supervisores=q("SELECT nombre FROM supervisor ORDER BY 1"),
                         asesores=q("SELECT nombre FROM asesor ORDER BY 1"), fecha_min=fm[0], fecha_max=fm[1]))
rd = lambda p: open(p, encoding="utf-8").read()
logo = "data:image/png;base64," + base64.b64encode(open("web/assets/icon-192.png", "rb").read()).decode()
app = rd("web/app.js")
app = re.sub(r"#/(asesor|venta)/\$\{", r"#\1-${", app).replace('"#/venta/"', '"#venta-"').replace("#/", "#")
app = app.replace('.split("/")', '.split("-")').replace("/assets/logo.png", logo).replace("/assets/icon-192.png", logo)
html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Auditoría de calidad · WIN (demo)</title><style>{rd("web/app.css")}
.demo{{background:var(--brand);color:#fff;text-align:center;font-size:12px;font-weight:700;padding:5px 8px}}</style>
<script>try{{var t=localStorage.getItem("tema");if(t)document.documentElement.dataset.theme=t;else if(matchMedia("(prefers-color-scheme:dark)").matches)document.documentElement.dataset.theme="dark"}}catch(e){{}}</script></head>
<body><div class="demo">Demo · datos simulados · Supervisor: SUPERVISOR / 60431749 · Asesor: HUGO GARCIA NUNEZ / HUGO GARCIA NUNEZ</div><div id="root"></div>
<script>window.DEMO={json.dumps(DEMO, ensure_ascii=False, separators=(",", ":"))};</script><script>{rd("demo/demo-api.js")}</script>
<script>{rd("web/transcripcion.js")}</script><script>{app}</script></body></html>"""
os.makedirs("/mnt/user-data/outputs", exist_ok=True)
open("/mnt/user-data/outputs/demo_auditoria_win.html", "w", encoding="utf-8").write(html)
print(len(html) // 1024, "KB")
