"""Servicio de auditoría: bot -> motor de reglas -> control de confianza -> revisión humana -> indicadores."""
import json
import re
import time
from . import config as C, contrato, db, extractor, motor, pauta as P

MIN_MUESTRA_ASESOR = 5   # mínimo de auditorías antes de recomendar coaching individual (informe 7.6.3)


# ------------------------------------------------------------------ auditar (sin guardar)
def auditar(transcripcion, es_venta=None, datos_sistema=None, regla="vigente", clausulas=None):
    ext = extractor.extraer(transcripcion, es_venta, datos_sistema)
    crit = ext["criterios"]
    valores = {i: c["valor"] for i, c in crit.items()}
    out = dict(criterios=[dict(id=i, nombre=C.POR_ID[i]["nombre"], pilar=C.POR_ID[i]["pilar"], **crit[i]) for i in sorted(crit)],
               es_venta=ext["es_venta"], venta_inferida=ext["venta_inferida"], lectura_contrato=ext["lectura_contrato"],
               regla=regla)
    out["pauta"] = P.evaluar(clausulas, transcripcion) if (clausulas and ext["es_venta"] and not ext["sin_contacto"]) else None
    if ext["sin_contacto"]:
        out.update(auditable=False, nota=None, nota_min=None, nota_max=None, nivel=None, pilares=None,
                   confianza=0.9, ruta="RESPALDO_MANUAL", motivos=["Sin contacto: no hay conversación evaluable"],
                   n_revisar=0)
        return out
    peor, mejor = motor.rango_con_incertidumbre(valores, regla)
    nota = peor["nota"]
    n_rev = sum(1 for v in valores.values() if v == C.REVISAR)
    conf = min(c["confianza"] for c in crit.values())
    motivos = []
    if n_rev:
        motivos.append(f"{n_rev} criterio(s) sin evidencia suficiente (REVISAR)")
    if peor["nivel"] != mejor["nivel"]:
        motivos.append(f"El nivel depende de los criterios sin resolver ({peor['nivel']} a {mejor['nivel']})")
    if peor["nivel"] == "Deficiente":
        motivos.append("Riesgo: nivel propuesto Deficiente")
    for u in (C.UMBRAL_DEFICIENTE, C.UMBRAL_EXCELENTE):
        if abs(nota - u) < C.MARGEN_RIESGO:
            motivos.append(f"Nota a menos de {C.MARGEN_RIESGO:g} puntos del umbral {u:g}")
            break
    if conf < C.TAU_CONFIANZA and not n_rev:
        motivos.append(f"Confianza mínima {conf:.2f} < {C.TAU_CONFIANZA}")
    out.update(auditable=True, nota=nota, nota_min=peor["nota"], nota_max=mejor["nota"], nivel=peor["nivel"],
               pilares=peor["pilares"], confianza=conf, n_revisar=n_rev, motivos=motivos,
               ruta="RESPALDO_MANUAL" if motivos else "VALIDAR_PROPUESTA")
    return out


# ------------------------------------------------------------------ registrar y revisar
def _asesor(con, nombre, supervisor=None):
    r = con.execute("SELECT id_asesor FROM asesor WHERE nombre=?", (nombre,)).fetchone()
    if r:
        return r[0]
    sup = db.id_catalogo(con, "supervisor", supervisor) if supervisor else None
    usuario = "nuevo_" + re.sub(r"\W+", "_", nombre.lower())
    return con.execute("INSERT INTO asesor(usuario,nombre,id_supervisor) VALUES(?,?,?)", (usuario, nombre, sup)).lastrowid


def registrar(con, resultado, transcripcion, contexto=None, motor_asr=None):
    """Guarda la propuesta del bot como PRE_LLENADA. No fija nota final: la fija el auditor."""
    ctx = contexto or {}
    id_llamada = (ctx.get("id_llamada") or "").strip() or f"NEW-{int(time.time()*1000)}"
    if con.execute("SELECT 1 FROM llamada WHERE id_llamada=?", (id_llamada,)).fetchone():
        raise ValueError(f"Ya existe la llamada {id_llamada}")
    ase = _asesor(con, (ctx.get("asesor") or "ASESOR SIN REGISTRAR").strip().upper(), ctx.get("supervisor"))
    cam = db.id_catalogo(con, "campana", (ctx.get("campana") or "SIN CAMPAÑA").strip().upper())
    hoy = time.strftime("%Y-%m-%d")
    con.execute("""INSERT INTO llamada(id_llamada,id_asesor,id_campana,fecha_monitoreo,fecha_llamada,tmo_seg,
        venta_concretada,plan_ofrecido,origen) VALUES(?,?,?,?,?,?,?,?,'nueva')""",
        (id_llamada, ase, cam, ctx.get("fecha") or hoy, ctx.get("fecha") or hoy, ctx.get("tmo_seg"),
         1 if resultado.get("es_venta") else 0, ctx.get("plan")))
    con.execute("INSERT INTO transcripcion(id_llamada,texto,motor_asr) VALUES(?,?,?)",
                (id_llamada, transcripcion, motor_asr or "texto_manual"))
    cur = con.execute("""INSERT INTO auditoria(id_llamada,auditable,nota_bot,nota_bot_min,nota_bot_max,nivel_bot,confianza,
        ruta,motivos_ruta,estado,origen,regla,pauta_pct,pauta_veredicto) VALUES(?,?,?,?,?,?,?,?,?,'PRE_LLENADA','bot',?,?,?)""",
        (id_llamada, int(resultado["auditable"]), resultado["nota"], resultado["nota_min"], resultado["nota_max"],
         resultado["nivel"], resultado["confianza"], resultado["ruta"], json.dumps(resultado["motivos"], ensure_ascii=False),
         resultado["regla"], (resultado.get("pauta") or {}).get("pct"), (resultado.get("pauta") or {}).get("veredicto")))
    ida = cur.lastrowid
    for k in (resultado.get("pauta") or {}).get("clausulas", []):
        con.execute("INSERT INTO auditoria_pauta VALUES(?,?,?,?,?,?,?,?)", (ida, k["id_clausula"], k["nombre"], k["estado"],
                    k["puntaje"], k["evidencia"], ", ".join(k["faltantes"]), k["critica"]))
    for c in resultado["criterios"]:
        con.execute("""INSERT INTO auditoria_criterio(id_auditoria,id_criterio,valor_bot,confianza_bot,evidencia,observacion)
            VALUES(?,?,?,?,?,?)""", (ida, c["id"], c["valor"], c["confianza"], c["evidencia"], c["razon"]))
    con.commit()
    return ida


def revisar(con, id_auditoria, valores, usuario, motivo="", regla=None):
    """El auditor confirma o corrige. valores = {id_criterio: valor} (los 15). Cada cambio queda en el historial
    y la nota se recalcula con el motor de reglas. Los REVISAR deben quedar resueltos."""
    a = con.execute("SELECT * FROM auditoria WHERE id_auditoria=?", (id_auditoria,)).fetchone()
    if not a:
        raise ValueError("Auditoría no encontrada")
    if not (usuario or "").strip():
        raise ValueError("Indica el usuario auditor")
    valores = {int(k): v for k, v in valores.items()}
    if any(v not in C.VALORES for v in valores.values()):
        raise ValueError("Valor no permitido; usa SI, NO, No Aplica o Sin contacto")
    filas = {r["id_criterio"]: r for r in con.execute("SELECT * FROM auditoria_criterio WHERE id_auditoria=?", (id_auditoria,))}
    final = {}
    for i in filas:
        actual = filas[i]["valor_final"] or filas[i]["valor_bot"]
        v = valores.get(i, actual)
        if v == C.REVISAR:
            raise ValueError(f"Resuelve el criterio «{C.POR_ID[i]['nombre']}»: aún está en REVISAR")
        final[i] = v
    cambios, corregida = 0, False
    for i, v in final.items():
        f = filas[i]
        actual = f["valor_final"] or f["valor_bot"]
        if v != actual:
            con.execute("""INSERT INTO auditoria_historial(id_auditoria,id_criterio,valor_anterior,valor_nuevo,usuario,motivo)
                VALUES(?,?,?,?,?,?)""", (id_auditoria, i, actual, v, usuario, motivo))
            cambios += 1
        if f["valor_bot"] not in (None, C.REVISAR) and v != f["valor_bot"]:
            corregida = True
        con.execute("UPDATE auditoria_criterio SET valor_final=? WHERE id_auditoria=? AND id_criterio=?", (v, id_auditoria, i))
    res = motor.calcular(final, regla or a["regla"])
    p = res["pilares"]
    estado = "CORREGIDA" if corregida else ("VALIDADA" if a["origen"] == "bot" else a["estado"])
    con.execute("""UPDATE auditoria SET auditable=?,p_conquistar=?,p_conocer=?,p_convencer=?,p_concretar=?,nota=?,nivel=?,
        estado=?,regla=? WHERE id_auditoria=?""",
        (int(res["auditable"]), p["IMPACTA"], p["DESCUBRE"], p["SOLUCIONA"], p["CONSOLIDA"], res["nota"], res["nivel"],
         estado, regla or a["regla"], id_auditoria))
    con.commit()
    return dict(id_auditoria=id_auditoria, cambios=cambios, estado=estado, nota=res["nota"], nivel=res["nivel"], pilares=p)


# ------------------------------------------------------------------ consultas
_FROM = """FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada
  LEFT JOIN asesor ase ON ase.id_asesor=l.id_asesor LEFT JOIN supervisor s ON s.id_supervisor=ase.id_supervisor
  LEFT JOIN campana c ON c.id_campana=l.id_campana LEFT JOIN monitor m ON m.id_monitor=a.id_monitor"""


def _where(f, base=("a.nota IS NOT NULL", "a.auditable=1")):
    w, p = list(base), []
    if str(f.get("ventas", "1")) not in ("0", "false", "False", ""):
        w.append("l.venta_concretada=1")
    for k, col, op in (("desde", "l.fecha_monitoreo", ">="), ("hasta", "l.fecha_monitoreo", "<="),
                       ("campana", "c.nombre", "="), ("supervisor", "s.nombre", "="), ("asesor", "ase.nombre", "=")):
        if f.get(k):
            w.append(f"{col} {op} ?"); p.append(f[k])
    return " AND ".join(w), p


def filtros(con):
    q = lambda sql: [r[0] for r in con.execute(sql)]
    fm = con.execute("SELECT MIN(fecha_monitoreo), MAX(fecha_monitoreo) FROM llamada").fetchone()
    return dict(campanas=q("SELECT nombre FROM campana ORDER BY 1"), supervisores=q("SELECT nombre FROM supervisor ORDER BY 1"),
                asesores=q("SELECT nombre FROM asesor ORDER BY 1"), fecha_min=fm[0], fecha_max=fm[1])


def dashboard(con, f):
    w, p = _where(f)
    k = con.execute(f"""SELECT COUNT(*) n, AVG(a.nota) nota, SUM(a.nivel='Deficiente') d, SUM(a.nivel='Aceptable') ac,
        SUM(a.nivel='Excelente') e, AVG(a.p_conquistar) p1, AVG(a.p_conocer) p2, AVG(a.p_convencer) p3, AVG(a.p_concretar) p4
        {_FROM} WHERE {w}""", p).fetchone()
    n = k["n"] or 0
    pct = lambda x: round(100 * (x or 0) / n, 1) if n else 0
    quiebres = con.execute(f"""SELECT AVG(q) FROM (SELECT SUM(ac.valor_final='NO') q {_FROM}
        JOIN auditoria_criterio ac ON ac.id_auditoria=a.id_auditoria WHERE {w} GROUP BY a.id_auditoria)""", p).fetchone()[0]
    pend = con.execute("SELECT COUNT(*), SUM(ruta='RESPALDO_MANUAL') FROM auditoria WHERE estado='PRE_LLENADA'").fetchone()
    pilares = [dict(pilar=pl, modelo=d["modelo"], peso=int(d["peso"] * 100),
                    cumplimiento=round(k[f"p{d['id']}"] or 0, 1)) for pl, d in C.PILARES.items()]
    semanal = [dict(semana=r["sem"], nota=round(r["nota"], 1), n=r["n"]) for r in con.execute(
        f"""SELECT date(l.fecha_monitoreo,'weekday 0','-6 days') sem, AVG(a.nota) nota, COUNT(*) n {_FROM}
            WHERE {w} GROUP BY sem ORDER BY sem""", p)]
    sups = [dict(nombre=r["nombre"], nota=round(r["nota"], 1), n=r["n"]) for r in con.execute(
        f"""SELECT s.nombre nombre, AVG(a.nota) nota, COUNT(*) n {_FROM} WHERE {w} GROUP BY s.nombre ORDER BY nota""", p)]
    ases = [dict(id=r["id"], nombre=r["nombre"], nota=round(r["nota"], 1), n=r["n"], deficientes=r["d"],
                 muestra_pequena=r["n"] < MIN_MUESTRA_ASESOR) for r in con.execute(
        f"""SELECT ase.id_asesor id, ase.nombre nombre, AVG(a.nota) nota, COUNT(*) n, SUM(a.nivel='Deficiente') d {_FROM}
            WHERE {w} GROUP BY ase.id_asesor ORDER BY nota LIMIT 10""", p)]
    crit = [dict(id=r["id_criterio"], nombre=C.POR_ID[r["id_criterio"]]["nombre"], pilar=C.POR_ID[r["id_criterio"]]["pilar"],
                 pct_no=round(100 * r["no"] / r["ap"], 1) if r["ap"] else 0, aplicables=r["ap"]) for r in con.execute(
        f"""SELECT ac.id_criterio, SUM(ac.valor_final='NO') no, SUM(ac.valor_final IN ('SI','NO')) ap {_FROM}
            JOIN auditoria_criterio ac ON ac.id_auditoria=a.id_auditoria WHERE {w} GROUP BY ac.id_criterio""", p)]
    crit.sort(key=lambda x: -x["pct_no"])
    return dict(n=n, nota=round(k["nota"] or 0, 1), pct_deficiente=pct(k["d"]), pct_aceptable=pct(k["ac"]),
                pct_excelente=pct(k["e"]), quiebres_prom=round(quiebres or 0, 2),
                pendientes=pend[0] or 0, pendientes_respaldo=pend[1] or 0, pilares=pilares, semanal=semanal,
                supervisores=sups, asesores=ases, criterios=crit, min_muestra=MIN_MUESTRA_ASESOR, bot=stats_bot(con))


def stats_bot(con):
    """Rendimiento real del bot medido contra las revisiones del auditor (alimenta el reentrenamiento)."""
    revisadas = con.execute("""SELECT * FROM auditoria WHERE origen='bot' AND estado IN ('VALIDADA','CORREGIDA')""").fetchall()
    n = len(revisadas)
    if not n:
        return dict(n_revisadas=0)
    cmp_ = con.execute("""SELECT COUNT(*) t, SUM(ac.valor_bot=ac.valor_final) ok FROM auditoria_criterio ac
        JOIN auditoria a ON a.id_auditoria=ac.id_auditoria WHERE a.origen='bot' AND a.estado IN ('VALIDADA','CORREGIDA')
        AND ac.valor_bot!='REVISAR'""").fetchone()
    efect = sum(1 for a in revisadas if a["nota_bot"] is not None and a["nota"] is not None
                and a["nivel_bot"] == a["nivel"] and abs(a["nota_bot"] - a["nota"]) <= 5)
    resp = sum(1 for a in revisadas if a["ruta"] == "RESPALDO_MANUAL")
    min_sis = (n - resp) * C.MIN_VALIDACION + resp * C.MIN_AUDITORIA_MANUAL
    min_man = n * C.MIN_AUDITORIA_MANUAL
    por_crit = [dict(id=r["id_criterio"], nombre=C.POR_ID[r["id_criterio"]]["nombre"], correcciones=r["c"]) for r in con.execute(
        """SELECT h.id_criterio, COUNT(*) c FROM auditoria_historial h JOIN auditoria a ON a.id_auditoria=h.id_auditoria
           WHERE a.origen='bot' GROUP BY h.id_criterio ORDER BY c DESC LIMIT 5""")]
    return dict(n_revisadas=n, acierto_criterio=round(100 * (cmp_["ok"] or 0) / cmp_["t"], 1) if cmp_["t"] else None,
                efectividad=round(100 * efect / n, 1), tasa_respaldo=round(100 * resp / n, 1),
                sin_cambios=round(100 * sum(1 for a in revisadas if a["estado"] == "VALIDADA") / n, 1),
                minutos_sistema=round(min_sis, 1), minutos_manual=round(min_man, 1),
                ahorro_soles=round((min_man - min_sis) * C.COSTO_MIN_AUDITOR, 2), mas_corregidos=por_crit,
                nota="Tiempos = supuestos del informe (Tabla 24) hasta medirlos en el piloto")


def listar(con, f, estado=None, q=None, limite=50, desplazamiento=0):
    w, p = _where(f, base=("1=1",))
    if str(f.get("ventas", "1")) in ("0", "false", "False", ""):
        pass
    if estado:
        w += " AND a.estado=?"; p.append(estado)
    if q:
        w += " AND (a.id_llamada LIKE ? OR ase.nombre LIKE ?)"; p += [f"%{q}%", f"%{q}%"]
    tot = con.execute(f"SELECT COUNT(*) {_FROM} WHERE {w}", p).fetchone()[0]
    rows = [dict(r) for r in con.execute(f"""SELECT a.id_auditoria id, a.id_llamada llamada, l.fecha_monitoreo fecha,
        ase.nombre asesor, c.nombre campana, s.nombre supervisor, l.venta_concretada venta, a.nota, a.nivel, a.nota_bot,
        a.nivel_bot, a.estado, a.origen, a.ruta {_FROM} WHERE {w} ORDER BY a.id_auditoria DESC LIMIT ? OFFSET ?""",
        p + [limite, desplazamiento])]
    return dict(total=tot, filas=rows)


def cola(con):
    return [dict(r) for r in con.execute(f"""SELECT a.id_auditoria id, a.id_llamada llamada, ase.nombre asesor, c.nombre campana,
        a.nota_bot, a.nota_bot_min, a.nota_bot_max, a.nivel_bot, a.confianza, a.ruta, a.motivos_ruta, a.fecha
        {_FROM} WHERE a.estado='PRE_LLENADA' ORDER BY (a.ruta='RESPALDO_MANUAL') DESC, a.id_auditoria""")]


def detalle(con, ida):
    a = con.execute(f"""SELECT a.*, l.fecha_llamada, l.tmo_seg, l.tipo_llamada, l.tipificacion, l.venta_concretada, l.plan_ofrecido,
        l.descripcion, l.origen origen_llamada, ase.nombre asesor, s.nombre supervisor, c.nombre campana, m.nombre monitor
        {_FROM} WHERE a.id_auditoria=?""", (ida,)).fetchone()
    if not a:
        return None
    d = dict(a)
    d["motivos_ruta"] = json.loads(a["motivos_ruta"]) if a["motivos_ruta"] else []
    d["criterios"] = [dict(r, nombre=C.POR_ID[r["id_criterio"]]["nombre"], pilar=C.POR_ID[r["id_criterio"]]["pilar"])
                      for r in con.execute("SELECT * FROM auditoria_criterio WHERE id_auditoria=? ORDER BY id_criterio", (ida,))]
    d["historial"] = [dict(r, criterio=C.POR_ID[r["id_criterio"]]["nombre"]) for r in con.execute(
        "SELECT * FROM auditoria_historial WHERE id_auditoria=? ORDER BY id_hist DESC", (ida,))]
    t = con.execute("SELECT texto, motor_asr FROM transcripcion WHERE id_llamada=? ORDER BY id_transcripcion DESC",
                    (a["id_llamada"],)).fetchone()
    d["transcripcion"] = t["texto"] if t else None
    d["pauta"] = [dict(r) for r in con.execute("SELECT * FROM auditoria_pauta WHERE id_auditoria=? ORDER BY rowid", (ida,))]
    return d


# ------------------------------------------------------------------ asesores, perfil, resumen, pauta
_OK = "l.venta_concretada=1 AND a.nota IS NOT NULL AND a.auditable=1"


def asesores(con, f):
    w, p = ["1=1"], []
    if f.get("q"):
        w.append("ase.nombre LIKE ?"); p.append(f"%{f['q']}%")
    if f.get("supervisor"):
        w.append("s.nombre=?"); p.append(f["supervisor"])
    if f.get("campana"):
        w.append("c.nombre=?"); p.append(f["campana"])
    orden = {"nota_asc": "nota IS NULL, nota ASC", "nota_desc": "nota DESC", "def": "d DESC, nota ASC"}.get(f.get("orden"), "ase.nombre")
    rows = con.execute(f"""SELECT ase.id_asesor id, ase.nombre nombre, ase.dni_enmascarado dni, s.nombre supervisor,
        MAX(c.nombre) campana, COUNT(DISTINCT l.id_llamada) llamadas,
        SUM(CASE WHEN {_OK} THEN 1 ELSE 0 END) n, AVG(CASE WHEN {_OK} THEN a.nota END) nota,
        SUM(CASE WHEN {_OK} AND a.nivel='Deficiente' THEN 1 ELSE 0 END) d, MAX(l.fecha_monitoreo) ultima,
        SUM(CASE WHEN a.estado='PRE_LLENADA' THEN 1 ELSE 0 END) pend
        FROM asesor ase LEFT JOIN supervisor s ON s.id_supervisor=ase.id_supervisor
        LEFT JOIN llamada l ON l.id_asesor=ase.id_asesor LEFT JOIN campana c ON c.id_campana=l.id_campana
        LEFT JOIN auditoria a ON a.id_llamada=l.id_llamada WHERE {" AND ".join(w)}
        GROUP BY ase.id_asesor ORDER BY {orden}""", p).fetchall()
    out = [dict(r, nota=None if r["nota"] is None else round(r["nota"], 1), nivel=C.nivel_de(r["nota"]),
                muestra_pequena=(r["n"] or 0) < MIN_MUESTRA_ASESOR) for r in rows]
    return dict(total=len(out), asesores=out, min_muestra=MIN_MUESTRA_ASESOR)


def perfil_asesor(con, ida):
    a = con.execute("""SELECT ase.id_asesor id, ase.nombre, ase.dni_enmascarado dni, s.nombre supervisor
        FROM asesor ase LEFT JOIN supervisor s ON s.id_supervisor=ase.id_supervisor WHERE ase.id_asesor=?""", (ida,)).fetchone()
    if not a:
        return None
    base = f"""FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada WHERE l.id_asesor=? AND {_OK}"""
    k = con.execute(f"""SELECT COUNT(*) n, AVG(a.nota) nota, SUM(a.nivel='Deficiente') d, SUM(a.nivel='Aceptable') ac,
        SUM(a.nivel='Excelente') e, AVG(a.p_conquistar) p1, AVG(a.p_conocer) p2, AVG(a.p_convencer) p3, AVG(a.p_concretar) p4
        {base}""", (ida,)).fetchone()
    n = k["n"] or 0
    equipo = con.execute(f"SELECT AVG(a.nota) FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada WHERE {_OK}").fetchone()[0]
    glob = {r[0]: r[1] for r in con.execute(f"""SELECT ac.id_criterio, 100.0*SUM(ac.valor_final='NO')/NULLIF(SUM(ac.valor_final IN ('SI','NO')),0)
        FROM auditoria_criterio ac JOIN auditoria a ON a.id_auditoria=ac.id_auditoria JOIN llamada l ON l.id_llamada=a.id_llamada
        WHERE {_OK} GROUP BY ac.id_criterio""")}
    crit = []
    for r in con.execute(f"""SELECT ac.id_criterio, SUM(ac.valor_final='NO') no, SUM(ac.valor_final IN ('SI','NO')) ap
        FROM auditoria_criterio ac JOIN auditoria a ON a.id_auditoria=ac.id_auditoria JOIN llamada l ON l.id_llamada=a.id_llamada
        WHERE l.id_asesor=? AND {_OK} GROUP BY ac.id_criterio""", (ida,)):
        pct = 100 * r["no"] / r["ap"] if r["ap"] else 0
        crit.append(dict(id=r["id_criterio"], nombre=C.POR_ID[r["id_criterio"]]["nombre"], pilar=C.POR_ID[r["id_criterio"]]["pilar"],
                         no=r["no"], aplicables=r["ap"], pct_no=round(pct, 1), equipo=round(glob.get(r["id_criterio"]) or 0, 1)))
    crit.sort(key=lambda x: (-x["no"], -x["pct_no"]))
    coaching = [c for c in crit if c["no"] > 0][:3]
    evol = [dict(id=r["id"], fecha=r["fecha"], nota=round(r["nota"], 1), nivel=r["nivel"]) for r in con.execute(
        f"""SELECT a.id_auditoria id, l.fecha_monitoreo fecha, a.nota, a.nivel {base} ORDER BY l.fecha_monitoreo, a.id_auditoria""", (ida,))]
    hist = [dict(r) for r in con.execute("""SELECT a.id_auditoria id, a.id_llamada llamada, l.fecha_monitoreo fecha,
        l.venta_concretada venta, a.nota, a.nivel, a.estado, a.ruta, a.nota_bot, a.pauta_veredicto pauta
        FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada WHERE l.id_asesor=?
        ORDER BY l.fecha_monitoreo DESC, a.id_auditoria DESC""", (ida,))]
    pct = lambda x: round(100 * (x or 0) / n, 1) if n else 0
    return dict(asesor=dict(a), n=n, nota=None if not n else round(k["nota"], 1), equipo=None if equipo is None else round(equipo, 1),
                pct_deficiente=pct(k["d"]), pct_aceptable=pct(k["ac"]), pct_excelente=pct(k["e"]), nivel=C.nivel_de(k["nota"]),
                pilares=[dict(pilar=pl, modelo=d["modelo"], peso=int(d["peso"] * 100), cumplimiento=round(k[f"p{d['id']}"] or 0, 1))
                         for pl, d in C.PILARES.items()],
                evolucion=evol, criterios=crit, coaching=coaching, historial=hist,
                muestra_pequena=n < MIN_MUESTRA_ASESOR, min_muestra=MIN_MUESTRA_ASESOR)


def resumen(con):
    q = lambda sql: con.execute(sql).fetchone()[0] or 0
    return dict(asesores=q("SELECT COUNT(*) FROM asesor"), ventas=q(f"SELECT COUNT(*) FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada WHERE {_OK}"),
                nota=round(q(f"SELECT AVG(a.nota) FROM auditoria a JOIN llamada l ON l.id_llamada=a.id_llamada WHERE {_OK}"), 1),
                auditorias=q("SELECT COUNT(*) FROM auditoria"), pendientes=q("SELECT COUNT(*) FROM auditoria WHERE estado='PRE_LLENADA'"),
                clausulas=q("SELECT COUNT(*) FROM pauta_clausula WHERE activa=1"),
                pauta_ejemplo=False, validaciones=stats_validaciones(con))


def pauta_listar(con, solo_activas=False):
    w = "WHERE activa=1" if solo_activas else ""
    return [dict(r) for r in con.execute(f"SELECT * FROM pauta_clausula {w} ORDER BY orden, id_clausula")]


def pauta_guardar(con, clausulas):
    if not clausulas:
        raise ValueError("La pauta debe tener al menos una cláusula")
    con.execute("DELETE FROM pauta_clausula")
    for i, c in enumerate(clausulas, 1):
        if not (c.get("nombre") or "").strip() or not (c.get("texto_referencia") or "").strip():
            raise ValueError(f"La cláusula {i} necesita nombre y texto de referencia")
        con.execute("INSERT INTO pauta_clausula(orden,nombre,texto_referencia,obligatorias,critica,peso,activa,tipo) VALUES(?,?,?,?,?,?,?,?)",
                    (i, c["nombre"].strip(), c["texto_referencia"].strip(), (c.get("obligatorias") or "").strip(),
                     int(bool(c.get("critica"))), float(c.get("peso") or 1), int(c.get("activa", 1)), c.get("tipo") or "lectura"))
    con.execute("INSERT OR REPLACE INTO config VALUES('pauta_ejemplo','0')")
    con.commit()


# ------------------------------------------------------------------ validación de ventas contra el contrato
def validar(con, id_asesor, transcripcion, plantilla):
    if not (transcripcion or "").strip():
        raise ValueError("Falta la transcripción del audio de la venta")
    if not contrato.parsear_plantilla(plantilla):
        raise ValueError("Falta la plantilla del cliente (nombre, DNI, nacimiento, correo, teléfono, dirección e internet)")
    if not con.execute("SELECT 1 FROM asesor WHERE id_asesor=?", (id_asesor,)).fetchone():
        raise ValueError("Asesor no encontrado")
    res = contrato.evaluar(pauta_listar(con, True), transcripcion, plantilla)
    cur = con.execute("""INSERT INTO validacion(id_asesor,estado,pct_contrato,claridad,pct_datos,cliente,resultado,transcripcion,plantilla)
        VALUES(?,?,?,?,?,?,?,?,?)""", (id_asesor, res["estado"], res["pct_contrato"], res["claridad"], res["pct_datos"], res["cliente"],
                                       json.dumps(res, ensure_ascii=False), transcripcion, plantilla))
    con.commit()
    return dict(res, id=cur.lastrowid)


def validaciones(con, id_asesor=None, estado=None, limite=60):
    w, p = ["1=1"], []
    if id_asesor:
        w.append("v.id_asesor=?"); p.append(id_asesor)
    if estado:
        w.append("COALESCE(v.decision,v.estado)=?"); p.append(estado)
    return [dict(r) for r in con.execute(f"""SELECT v.id_validacion id, v.id_asesor, ase.nombre asesor, v.fecha, v.cliente, v.estado, v.decision,
        COALESCE(v.decision,v.estado) final, v.pct_contrato, v.claridad, v.pct_datos FROM validacion v JOIN asesor ase ON ase.id_asesor=v.id_asesor
        WHERE {" AND ".join(w)} ORDER BY v.id_validacion DESC LIMIT ?""", p + [limite])]


def validacion(con, vid):
    r = con.execute("""SELECT v.*, ase.nombre asesor FROM validacion v JOIN asesor ase ON ase.id_asesor=v.id_asesor WHERE v.id_validacion=?""", (vid,)).fetchone()
    if not r:
        return None
    d = dict(r); d["resultado"] = json.loads(d["resultado"]); d["final"] = d["decision"] or d["estado"]
    return d


def decidir(con, vid, decision, usuario, motivo=""):
    if decision not in ("APROBADO", "RECHAZADO"):
        raise ValueError("Decisión no válida")
    if not con.execute("SELECT 1 FROM validacion WHERE id_validacion=?", (vid,)).fetchone():
        raise ValueError("Validación no encontrada")
    con.execute("UPDATE validacion SET decision=?, revisado_por=?, motivo_decision=?, fecha_decision=CURRENT_TIMESTAMP WHERE id_validacion=?",
                (decision, usuario, motivo, vid))
    con.commit()
    return dict(id=vid, final=decision)


def stats_validaciones(con):
    q = lambda w: con.execute(f"SELECT COUNT(*) FROM validacion WHERE {w}").fetchone()[0]
    return dict(enviadas=q("1=1"), aprobadas=q("COALESCE(decision,estado)='APROBADO'"), rechazadas=q("COALESCE(decision,estado)='RECHAZADO'"),
                por_revisar=q("estado='OBSERVADO' AND decision IS NULL"))
