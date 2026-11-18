"""Validación del contrato de voz de WIN contra el audio (transcripción) y la plantilla del cliente.
Regla de aprobación para subir la venta al sistema de ventas:
  APROBADO  = cumplimiento del contrato >= 70 %, claridad de las respuestas del cliente >= 80 % y cláusulas críticas cumplidas.
  OBSERVADO = pasa el 70 % pero la claridad es < 80 % o una crítica quedó parcial: lo decide el supervisor.
  RECHAZADO = cumplimiento < 70 % o una cláusula crítica (SÍ ACEPTO / autorización de datos) no se cumple.
La claridad es una MEDIDA APROXIMADA (respuestas del cliente con palabras reconocibles); falta validarla con audios reales."""
import re
from . import extractor, pauta as P

UMBRAL_CONTRATO, UMBRAL_CLARIDAD = 70.0, 80.0
_N = extractor._norm
_ACEPTA = "Le agradeceré que diga fuerte y claramente que SÍ ACEPTA los términos de la presente contratación"
_PRIV = "¿Declara conocer la Política de Privacidad y autoriza de forma previa, expresa, informada e inequívoca el tratamiento de datos personales?"
_COM = "¿Acepta el envío de comunicaciones comerciales, publicitarias y encuestas?"
CLAUSULAS = [
    dict(nombre="Resumen previo del servicio", tipo="lectura", critica=0, peso=1.0, obligatorias="{mbps}",
         texto_referencia="Antes de iniciar con la lectura de su contrato vamos a hacerle un resumen del servicio que está adquiriendo el día de hoy: internet de {mbps} Mbps"),
    dict(nombre="Apertura del contrato", tipo="lectura", critica=0, peso=1.0, obligatorias="contrata",
         texto_referencia="Contrato de voz de servicio de internet fijo postpago. Hoy en la ciudad de usted contrata con WIN, para ello me brinda los siguientes datos"),
    dict(nombre="Datos del cliente (según la plantilla)", tipo="datos", critica=0, peso=3.0, obligatorias="",
         texto_referencia="Nombre completo, documento de identidad, lugar y fecha de nacimiento, correo electrónico, teléfono y dirección de instalación"),
    dict(nombre="Descripción del servicio", tipo="lectura", critica=0, peso=2.0, obligatorias="fibra,comodato,indeterminado,{mbps}",
         texto_referencia="El servicio de internet fijo postpago de WIN es ilimitado, 100% fibra óptica, con velocidad simétrica de {mbps} Mbps de carga y descarga, aseguramos {asegurada} Mbps de carga y descarga, incluye un equipo terminal router y conector en comodato, deberá devolverlos en buenas condiciones, caso contrario pagará su valor. El contrato tendrá plazo indeterminado, el contrato podrá ser resuelto de acuerdo a la normativa de condiciones de uso"),
    dict(nombre="Precio, promoción y reconexión", tipo="lectura", critica=0, peso=2.0, obligatorias="79,promocional,reconexion,4.58",
         texto_referencia="El precio mensual es de S/ 79 incluye IGV, pagará a un precio promocional de S/ 1 incluye IGV por 2 meses, vencido este plazo se aplicarán las condiciones regulares de su plan contratado. La tarifa de reconexión es de S/ 4.58 incluye IGV"),
    dict(nombre="Facturación y vencimiento", tipo="lectura", critica=0, peso=1.5, obligatorias="11,28",
         texto_referencia="La fecha de facturación es el 11 de cada mes y la fecha de vencimiento es el 28 del mismo mes"),
    dict(nombre="Pedido de aceptación", tipo="lectura", critica=0, peso=1.0, obligatorias="acepta", texto_referencia=_ACEPTA),
    dict(nombre="Cliente responde: SÍ ACEPTO", tipo="resp_si", critica=1, peso=2.0, obligatorias="", texto_referencia=_ACEPTA),
    dict(nombre="Tratamiento de datos personales (ARCO)", tipo="lectura", critica=0, peso=1.5, obligatorias="arco",
         texto_referencia="Para culminar, WIN realizará el tratamiento de datos personales para gestiones relacionadas con el servicio, se almacenarán sus datos en nuestro Banco de Datos de clientes de acuerdo a la normativa vigente. Podrá ejercer sus derechos ARCO escribiendo al correo protecciondedatos@win.pe. Para más información, visite win.pe/protección-de-datos"),
    dict(nombre="Pregunta: Política de Privacidad", tipo="lectura", critica=0, peso=1.0, obligatorias="privacidad", texto_referencia=_PRIV),
    dict(nombre="Cliente responde: autoriza (SÍ)", tipo="resp_si", critica=1, peso=2.0, obligatorias="", texto_referencia=_PRIV),
    dict(nombre="Pregunta: comunicaciones comerciales", tipo="lectura", critica=0, peso=1.0, obligatorias="comerciales", texto_referencia=_COM),
    dict(nombre="Cliente responde: comunicaciones (SÍ o NO)", tipo="resp_libre", critica=0, peso=1.0, obligatorias="", texto_referencia=_COM),
]
_U = {w: i for i, w in enumerate("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciseis diecisiete dieciocho diecinueve veinte veintiuno veintidos veintitres veinticuatro veinticinco veintiseis veintisiete veintiocho veintinueve".split())}
_U.update(un=1, una=1, veintiun=21)
_D = {w: (i + 3) * 10 for i, w in enumerate("treinta cuarenta cincuenta sesenta setenta ochenta noventa".split())}
_C = dict(cien=100, ciento=100, doscientos=200, trescientos=300, cuatrocientos=400, quinientos=500, seiscientos=600, setecientos=700, ochocientos=800, novecientos=900)
_MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
_CONOCIDAS = set("""si no acepto acepta claro correcto ok vale bueno buenas buenos tardes dias noches hola gracias de la el los las un una que y en con por
para es soy mi me su se lo al del nombre dni correo gmail arroba punto com numero telefono vivo calle avenida zona quiero internet plan declaro conozco
autorizo politica privacidad comunicaciones mbps megas soles mes meses dos tres uno cero exacto afirmativo adelante cierto asi todo esta estoy""".split())
_INAUD = re.compile(r"\[(inaudible|ininteligible|ruido|musica|música|silencio)[^\]]*\]|\(inaudible\)|\?\?\?")
_AFIRM = re.compile(r"\b(si|acepto|acepta|declaro|conozco|autorizo|correcto|claro|de acuerdo|afirmativo|adelante)\b")


def _numeros(t):
    toks, out, i = t.split(), [], 0
    while i < len(toks):
        if toks[i] not in _U and toks[i] not in _D and toks[i] not in _C and toks[i] != "mil":
            out.append(toks[i]); i += 1; continue
        total = cur = stage = 0; mil = False; j = i
        while j < len(toks):
            w = toks[j]
            if w == "mil" and not mil: total, cur, stage, mil = (cur or 1) * 1000, 0, 0, True
            elif w in _C and stage == 0: cur += _C[w]; stage = 1
            elif w in _D and stage <= 1: cur += _D[w]; stage = 2
            elif w == "y" and stage == 2 and j + 1 < len(toks) and 1 <= _U.get(toks[j + 1], 0) <= 9: pass
            elif w in _U and (stage <= 1 or (stage == 2 and toks[j - 1] == "y")): cur += _U[w]; stage = 3
            else: break
            j += 1
        if j == i: out.append(toks[i]); i += 1; continue
        out.append(str(total + cur)); i = j
    return " ".join(out)


def _prep(t): return _numeros(_N(t))
def _colapsa(s): return re.sub(r"(?<=\d)[\s.,\-/]+(?=\d)", "", s)
def _toks(n): return {t[:6] for t in re.findall(r"[a-z0-9]+", n) if (len(t) > 2 and t not in P._STOP) or t.isdigit()}
def _frase(s, n=170): return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def _tiene(o, n):
    if re.fullmatch(r"[\d.,]+", o):
        d = re.sub(r"\D", "", o); return bool(re.search(rf"(?<!\d){d}(?!\d)", _colapsa(n)))
    return _N(o) in n


def parsear_plantilla(texto):
    pl = {}
    for linea in (texto or "").splitlines():
        l = re.sub(r"^[^\w]+", "", linea.strip())
        if ":" not in l: continue
        k, v = (x.strip() for x in l.split(":", 1)); kn = _N(k)
        if not v: continue
        for campo, claves in (("nombre", ("nombre",)), ("dni", ("dni", "documento")), ("nacimiento", ("nacimiento",)), ("correo", ("correo", "email")),
                              ("telefono", ("telefono", "celular", "numero")), ("direccion", ("direccion",)), ("plan", ("internet", "mbps", "plan"))):
            if any(c in kn for c in claves): pl.setdefault(campo, v); break
    m = re.search(r"(\d{2,4})\s*mbps", _N(pl.get("plan", "")))
    if m: pl["mbps"] = int(m.group(1))
    return pl


ETQ = dict(nombre="Nombres completos", dni="DNI", nacimiento="Lugar y fecha de nacimiento", correo="Correo electrónico", telefono="Teléfono", direccion="Dirección", plan="Internet contratado")


def verificar_datos(pl, texto):
    n = _prep(texto); dig = _colapsa(n); comp = n.replace(" ", ""); tk = _toks(n)
    cov = lambda v: (lambda t: len(t & tk) / len(t) if t else 0)(_toks(_prep(v)))
    def num(d):
        d = re.sub(r"\D", "", str(d)); return 1.0 if d and re.search(rf"(?<!\d){d}(?!\d)", dig) else (0.5 if len(d) >= 6 and d[-6:] in dig else 0.0)
    res = []
    for campo in ETQ:
        v = pl.get(campo)
        if not v: continue
        if campo in ("nombre", "direccion"): sc = cov(v)
        elif campo in ("dni", "telefono"): sc = num(v)
        elif campo == "nacimiento":
            m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})\s*(.*)", v) or (lambda m: m and (m.group(3), m.group(2), m.group(1), m.group(4)) and re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})\s*(.*)", v))
            if m and re.match(r"\d{4}", m.group(1)): y, mo, d, lug = m.groups()
            elif m: d, mo, y, lug = m.groups()
            else: y = None
            sc = cov(v) if y is None else sum([num(y), float(_MESES[int(mo) - 1] in n), num(int(d)), cov(lug) if lug.strip() else 1.0]) / 4
        elif campo == "correo":
            loc, _, dom = v.lower().partition("@"); letras, digs = re.sub(r"\d", "", loc), re.sub(r"\D", "", loc)
            sc = sum([letras in comp, num(digs) if digs else 1.0, dom.split(".")[0] in comp]) / 3
        else:
            nums = re.findall(r"\d+", v); resto = re.sub(r"\d+", "", v)
            sc = (num(nums[0]) + cov(resto)) / 2 if nums else cov(v)
        res.append(dict(campo=campo, etiqueta=ETQ[campo], esperado=v, puntaje=round(sc, 2),
                        estado="CORRECTO" if sc >= .85 else "PARCIAL" if sc >= .5 else "NO_LEIDO"))
    return res


def claridad(turnos):
    cli = [t for t in turnos if t["rol"] == "C"]
    if not cli: return None
    ok = sum(1 for t in cli if t["n"].strip() and not _INAUD.search(t["raw"].lower()) and any(w in _CONOCIDAS for w in re.findall(r"[a-z]+", t["n"])))
    return round(100 * ok / len(cli), 1)


def _buscar(sents, ref):
    mejor, i0, w0 = 0.0, None, 0
    for i in range(len(sents)):
        for w in (1, 2, 3, 4):
            if i + w > len(sents): break
            t = set().union(*(s["tk"] for s in sents[i:i + w])); c = len(ref & t) / len(ref) if ref else 0
            if c > mejor: mejor, i0, w0 = c, i, w
    return mejor, i0, w0


def evaluar(clausulas, transcripcion, plantilla=""):
    turnos = extractor.parsear(transcripcion or ""); etiq = any(t["rol"] in "AC" for t in turnos)
    pl = parsear_plantilla(plantilla); mbps = pl.get("mbps")
    sub = {"{mbps}": str(mbps or ""), "{asegurada}": str(round(mbps * 0.7)) if mbps else ""}
    fill = lambda s: re.sub(r"\{\w+\}", lambda m: sub.get(m.group(0), ""), s or "")
    fuente = [t for t in turnos if t["rol"] == "A"] if etiq else turnos
    sents = [dict(turno=t["i"], raw=o.strip(), n=_prep(o), rol=t["rol"]) for t in turnos if t in fuente for o in re.split(r"(?<=[.!?])\s+|\n", t["raw"]) if o.strip()]
    for s in sents: s["tk"] = _toks(s["n"])
    adv = " ".join(t["raw"] for t in fuente); res, datos = [], verificar_datos(pl, adv)
    pct_datos = round(100 * sum(d["puntaje"] for d in datos) / len(datos), 1) if datos else 0.0
    for c in clausulas:
        base = dict(id_clausula=c.get("id_clausula"), nombre=c["nombre"], critica=int(c.get("critica", 0)), peso=float(c.get("peso", 1)), tipo=c.get("tipo") or "lectura", evidencia=None, faltantes=[], valor=None)
        tipo = base["tipo"]
        if tipo == "datos":
            est = "CUMPLE" if pct_datos >= 85 else "PARCIAL" if pct_datos >= 50 else "NO_CUMPLE"
            res.append(dict(base, estado=est, puntaje=round(pct_datos / 100, 2), faltantes=[d["etiqueta"] for d in datos if d["estado"] != "CORRECTO"] or ([] if datos else ["Falta la plantilla del cliente"])))
            continue
        ref = _toks(_prep(fill(c["texto_referencia"])))
        mejor, i0, w0 = _buscar(sents, ref)
        if tipo == "lectura":
            reg = sents[max(0, i0 - 1): i0 + w0 + 1] if i0 is not None else []
            nreg = " ".join(s["n"] for s in reg)
            oblig = [o.strip() for o in fill(c.get("obligatorias")).split(",") if o.strip()]
            falt = [o for o in oblig if not _tiene(o, nreg)]
            est = "CUMPLE" if mejor >= .70 and not falt else "PARCIAL" if mejor >= .40 else "NO_CUMPLE"
            res.append(dict(base, estado=est, puntaje=round(mejor, 2), faltantes=falt,
                            evidencia=_frase(" ".join(s["raw"] for s in sents[i0:i0 + w0])) if mejor >= .40 else None))
            continue
        # respuestas del cliente a una pregunta/pedido del asesor
        if mejor < .50:
            res.append(dict(base, estado="NO_CUMPLE", puntaje=0.0, faltantes=["El asesor no hizo la pregunta"])); continue
        last = sents[i0 + w0 - 1]
        if etiq:
            sig = turnos[last["turno"] + 1] if last["turno"] + 1 < len(turnos) else None      # la respuesta es la intervención inmediata
            txt = sig["raw"] if sig and sig["rol"] == "C" else ""
        else:
            k = i0 + w0; txt = sents[k]["raw"] if k < len(sents) else ""
        n = _N(txt); inaud = bool(_INAUD.search(txt.lower())) or not any(w in _CONOCIDAS for w in re.findall(r"[a-z]+", n))
        afirma = bool(_AFIRM.search(n)) and not re.match(r"\s*no\b", n); niega = bool(re.match(r"\s*no\b", n))
        if not txt.strip(): est, f, val = "NO_CUMPLE", "El cliente no respondió", None
        elif inaud: est, f, val = "NO_CUMPLE", "Respuesta del cliente no entendible", None
        elif tipo == "resp_si": est, f, val = ("CUMPLE", "", "SI") if afirma else ("NO_CUMPLE", "El cliente respondió NO", "NO")
        else: est, f, val = ("CUMPLE", "", "SI" if afirma else "NO") if (afirma or niega) else ("NO_CUMPLE", "Respuesta no identificable", None)
        if not etiq and est == "CUMPLE": est, f = "PARCIAL", "Sin etiquetas ASESOR/CLIENTE: respuesta no atribuida con certeza"
        res.append(dict(base, estado=est, puntaje=1.0 if est == "CUMPLE" else .5 if est == "PARCIAL" else 0.0, faltantes=[f] if f else [], evidencia=_frase(txt) if txt else None, valor=val))
    tot = sum(r["peso"] for r in res) or 1
    pct = round(100 * sum(r["peso"] * {"CUMPLE": 1, "PARCIAL": .5, "NO_CUMPLE": 0}[r["estado"]] for r in res) / tot, 1)
    cl = claridad(turnos) if etiq else None
    crit = [r for r in res if r["critica"]]; motivos = []
    falla = [r["nombre"] for r in crit if r["estado"] == "NO_CUMPLE"]; parcial = [r["nombre"] for r in crit if r["estado"] == "PARCIAL"]
    if pct < UMBRAL_CONTRATO: motivos.append(f"Cumplimiento del contrato {pct}% (mínimo {UMBRAL_CONTRATO:g}%)")
    if falla: motivos.append("No se cumplió: " + ", ".join(falla))
    if cl is None: motivos.append("No se pudo medir la claridad del cliente (transcripción sin etiquetas o sin respuestas)")
    elif cl < UMBRAL_CLARIDAD: motivos.append(f"Solo {cl}% de las respuestas del cliente se entienden (mínimo {UMBRAL_CLARIDAD:g}%)")
    if parcial: motivos.append("Cumplimiento parcial en: " + ", ".join(parcial))
    if not datos: motivos.append("Falta la plantilla del cliente")
    estado = "RECHAZADO" if (pct < UMBRAL_CONTRATO or falla or not datos) else "OBSERVADO" if (cl is None or cl < UMBRAL_CLARIDAD or parcial) else "APROBADO"
    return dict(estado=estado, puede_subir=estado == "APROBADO", pct_contrato=pct, claridad=cl, pct_datos=pct_datos, clausulas=res, datos=datos, motivos=motivos,
                cliente=pl.get("nombre"), umbrales=dict(contrato=UMBRAL_CONTRATO, claridad=UMBRAL_CLARIDAD))
