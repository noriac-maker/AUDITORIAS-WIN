"""Extractor de evidencias: lee la TRANSCRIPCIÓN de la llamada y propone el valor de cada uno de los 15
criterios, la frase que lo respalda y una confianza. Si no halla evidencia devuelve REVISAR.

Principios (del informe, sección 7.4):
  * La señal que decide un criterio está en la conversación, no en el contexto de la llamada.
  * Dos criterios (Registro en Inconcert / portabilidad) dependen de datos del CRM, no del audio:
    se alimentan con `datos_sistema`; si no llegan, el bot NO inventa y devuelve REVISAR.
  * 'Información correcta' solo verifica COMPLETITUD (precio, velocidad, instalación...), no exactitud
    frente al catálogo: su confianza está acotada.
  * Estas reglas son un punto de partida SIN validar con audios reales. Mídelas con `evaluacion.py`.
"""
import re
import unicodedata
from . import config as C


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


_ROL = re.compile(r"^\s*(asesor|asesora|agente|ejecutivo|ejecutiva|vendedor|a)\s*[:\-–]\s*(.*)$", re.I)
_ROL_C = re.compile(r"^\s*(cliente|c)\s*[:\-–]\s*(.*)$", re.I)


def parsear(texto):
    """Devuelve turnos [{i, rol('A'|'C'|'?'), raw, n}]. Sin etiquetas de hablante, rol '?'."""
    turnos = []
    for linea in texto.splitlines():
        if not linea.strip():
            continue
        m, mc = _ROL.match(linea), _ROL_C.match(linea)
        if m:
            turnos.append({"rol": "A", "raw": m.group(2).strip()})
        elif mc:
            turnos.append({"rol": "C", "raw": mc.group(2).strip()})
        elif turnos:
            turnos[-1]["raw"] += " " + linea.strip()
        else:
            turnos.append({"rol": "?", "raw": linea.strip()})
    for i, t in enumerate(turnos):
        t["i"], t["n"] = i, _norm(t["raw"])
    return turnos


def _p(*alts):
    return re.compile(r"(?:%s)" % "|".join(alts))


RX = dict(
    saludo_g=_p(r"\bbuenos dias\b", r"\bbuenas tardes\b", r"\bbuenas noches\b", r"\bhola\b", r"\bbuen dia\b"),
    saludo_id=_p(r"mi nombre", r"le habla", r"le saluda", r"me comunico", r"le llamo de", r"habla con", r"le atiende",
                 r"soy \w+ de", r"de win"),
    saludo_am=_p(r"como esta", r"como se encuentra", r"con gusto", r"un gusto", r"encantad", r"espero que este bien",
                 r"como le va", r"gusto en saludar"),
    cobertura=_p(r"cobertura", r"factibilidad", r"su direccion", r"direccion de instalacion", r"en que distrito",
                 r"distrito", r"disponibilidad en su zona", r"en su zona"),
    oferta=_p(r"mbps", r"megas", r"soles", r"s/\s?\d", r"por mes", r"mensual"),
    act_pos=_p(r"con gusto", r"claro que si", r"por supuesto", r"le recomiendo", r"le puedo ofrecer", r"puedo ayudarle",
               r"le ayudo", r"me encargo", r"tenemos una promocion", r"aprovech", r"encantad"),
    act_neg=_p(r"no se puede", r"no puedo hacer nada", r"ya le dije", r"ya le explique", r"no es mi problema",
               r"no me corresponde", r"que quiere que haga", r"no tengo tiempo", r"apurese", r"no se nada"),
    sondeo=_p(r"que servicio tiene", r"con que operador", r"cuanto paga", r"cuantas personas", r"cuantos dispositivos",
              r"cuantos equipos", r"para que (lo )?usa", r"que (lo )?usa", r"teletrabajo", r"juegos", r"series",
              r"que velocidad tiene", r"que le gustaria", r"que es lo mas importante", r"que busca",
              r"cual es su necesidad", r"actualmente", r"cuantos pisos", r"vive solo", r"con quien vive"),
    escucha=_p(r"entiendo", r"comprendo", r"si le entiendo", r"perfecto", r"por lo que me comenta", r"tiene razon",
               r"ya veo", r"asi es", r"me dice que", r"segun lo que menciona", r"\bclaro\b"),
    interrumpe=re.compile(r"\[interrumpe\]|\(se superponen\)|\[superposicion\]|\[interrupcion\]"),
    imagina=_p(r"imagina", r"imagine", r"imaginese"),
    beneficio=_p(r"velocidad", r"fibra optica", r"wifi", r"win tv", r"canales", r"sin cortes", r"estabilidad", r"ahorr",
                 r"disfrut", r"beneficio", r"pelicula", r"series", r"teletrabajo", r"clases", r"estable", r"simultane"),
    recomienda=_p(r"le recomiendo", r"ideal para usted", r"se ajusta", r"la mejor opcion", r"le conviene",
                  r"adecuado para", r"le sugiero", r"el plan que mejor"),
    objecion=_p(r"\bcaro\b", r"elevado", r"costoso", r"precio (es )?(alto|elevado)", r"lo voy a pensar", r"lo pienso",
                r"ya tengo", r"contrato vigente", r"no me interesa", r"consultar", r"mas adelante", r"mas barato",
                r"competencia", r"no confio", r"por ahora no", r"no necesito", r"lo comparo", r"comparar"),
    manejo=_p(r"entiendo", r"comprendo", r"que le preocupa", r"cual es su preocupacion", r"descuento", r"promocion",
              r"rebate", r"beneficio", r"ahorro", r"le puedo (ofrecer|dar)", r"instalacion gratis", r"sin costo",
              r"que le parece", r"permitame", r"le explico"),
    asegura=_p(r"esta de acuerdo", r"le parece bien", r"queda confirmad", r"le confirmo", r"me confirma",
               r"entonces queda", r"alguna duda", r"alguna consulta", r"le quedo claro", r"esta conforme", r"correcto\?"),
    cierre=_p(r"procedemos", r"\bprocedo\b", r"le parece si", r"lo registramos", r"registramos", r"agendamos",
              r"agendo", r"cerramos", r"lo contratamos", r"quiere que lo", r"desea que lo", r"hacemos la solicitud",
              r"iniciamos", r"dejamos listo", r"coordinamos la instalacion", r"cuando le conviene", r"que dia le",
              r"le parece que lo"),
    abierto=_p(r"cualquier cosa", r"nos llama", r"usted nos avisa", r"cuando decida", r"me avisa", r"si desea nos llama",
               r"quedo atento"),
    prevalida=_p(r"es usted el titular", r"titular", r"su dni", r"numero de dni", r"nombre completo", r"apellidos",
                 r"direccion de instalacion", r"correo", r"email", r"numero de contacto", r"celular",
                 r"fecha de nacimiento", r"referencia"),
    thanks=_p(r"gracias", r"agradezco"),
    adios=_p(r"que tenga", r"buen dia", r"buenas tardes", r"buenas noches", r"excelente dia", r"hasta luego",
             r"un gusto", r"estamos a su disposicion", r"a la orden", r"cuidese", r"que este muy bien"),
    acepta=_p(r"\bacepto\b", r"si,? quiero", r"de acuerdo", r"procedan", r"adelante", r"lo tomo",
              r"quiero contratar", r"si,? procede", r"hagamoslo", r"contratelo"),
    portab=_p(r"portabilidad", r"portar", r"mantener mi numero", r"conservar mi numero", r"cambio de operador"),
    lectura=_p(r"lectura del contrato", r"le voy a leer", r"terminos y condiciones", r"acepta los terminos",
               r"declara que", r"autoriza", r"grabacion"),
)
INFO = dict(
    precio=_p(r"soles", r"s/\s?\d", r"precio", r"cuesta", r"mensual"),
    velocidad=_p(r"mbps", r"megas", r"velocidad"),
    instalacion=_p(r"instalacion", r"tecnico", r"visita"),
    permanencia=_p(r"permanencia", r"contrato de", r"meses", r"plazo"),
    facturacion=_p(r"recibo", r"factura", r"fecha de pago", r"ciclo", r"primer recibo", r"cargo"),
    equipos=_p(r"router", r"decodificador", r"modem", r"equipo"),
)


def _frase(t, n=170):
    s = t["raw"]
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _buscar(turnos, rx):
    return [t for t in turnos if rx.search(t["n"])]


class _Ctx:
    def __init__(self, turnos, es_venta, sis):
        self.T = turnos
        etiquetado = any(t["rol"] in "AC" for t in turnos)
        self.etiquetado = etiquetado
        self.A = [t for t in turnos if t["rol"] == "A"] if etiquetado else turnos
        self.C = [t for t in turnos if t["rol"] == "C"] if etiquetado else []
        self.es_venta = es_venta
        self.sis = sis or {}
        self.hay_oferta = bool(_buscar(self.A, RX["oferta"]))


def _r(valor, conf, evid=None, razon=""):
    return dict(valor=valor, confianza=round(conf, 2), evidencia=evid, razon=razon)


def _cap(res, ctx):
    """Sin etiquetas de hablante no se puede atribuir la frase al asesor: se limita la confianza."""
    if not ctx.etiquetado and res["valor"] not in ("No Aplica",):
        res["confianza"] = min(res["confianza"], 0.55)
        res["razon"] = (res["razon"] + " (transcripción sin etiquetas ASESOR/CLIENTE)").strip()
    return res


# ---------------------------------------------------------------- criterios
def c_saludo(x):
    ini = x.A[:2]
    g, idn, am = (_buscar(ini, RX[k]) for k in ("saludo_g", "saludo_id", "saludo_am"))
    if g and idn:
        return _r("SI", 0.90 if am else 0.80, _frase(g[0]), "Saludo + presentación" + (" + trato cercano" if am else ""))
    if not g:
        return _r("NO", 0.80, _frase(ini[0]) if ini else None, "No saluda en sus primeras intervenciones")
    return _r(C.REVISAR, 0.50, _frase(g[0]), "Saluda pero no se presenta: evaluar cercanía")


def c_cobertura(x):
    h = _buscar(x.A, RX["cobertura"])
    if h:
        return _r("SI", 0.85, _frase(h[0]), "Valida zona/dirección/cobertura")
    if x.hay_oferta:
        return _r("NO", 0.70, None, "Ofrece sin validar cobertura ni dirección")
    return _r(C.REVISAR, 0.40, None, "Sin evidencia de validación")


def c_actitud(x):
    neg, pos = _buscar(x.A, RX["act_neg"]), _buscar(x.A, RX["act_pos"])
    if neg:
        return _r("NO", 0.85, _frase(neg[0]), "Frase de actitud negativa o evasiva")
    if len(pos) >= 2:
        return _r("SI", 0.85, _frase(pos[0]), f"{len(pos)} expresiones de actitud comercial positiva")
    if len(pos) == 1:
        return _r("SI", 0.65, _frase(pos[0]), "Una sola expresión positiva")
    return _r(C.REVISAR, 0.40, None, "Sin marcadores claros de actitud")


def c_sondeo(x):
    h = _buscar(x.A, RX["sondeo"])
    if len(h) >= 2:
        return _r("SI", 0.88, _frase(h[0]), f"{len(h)} preguntas de sondeo")
    if len(h) == 1:
        return _r(C.REVISAR, 0.50, _frase(h[0]), "Solo una pregunta de sondeo: sondeo incompleto")
    return _r("NO", 0.75 if x.hay_oferta else 0.60, None, "No indaga necesidades antes de ofrecer")


def c_escucha(x):
    if any(RX["interrumpe"].search(t["raw"].lower()) for t in x.T):
        return _r("NO", 0.85, None, "Se marcó una interrupción al cliente")
    h = _buscar(x.A, RX["escucha"])
    if len(h) >= 2:
        return _r("SI", 0.85, _frase(h[0]), f"{len(h)} muestras de escucha/parafraseo")
    if len(h) == 1:
        return _r("SI", 0.65, _frase(h[0]), "Una muestra de escucha")
    return _r("NO", 0.65, None, "Sin parafraseo ni validación de lo dicho por el cliente") if len(x.C) >= 3 \
        else _r(C.REVISAR, 0.40, None, "Conversación corta para decidir")


def c_beneficios(x):
    im = _buscar(x.A, RX["imagina"])
    if im:
        return _r("SI", 0.92, _frase(im[0]), "Usa la técnica «imagina que…»")
    todas = {m for t in x.A for m in RX["beneficio"].findall(t["n"])}
    if len(todas) >= 2:
        t0 = _buscar(x.A, RX["beneficio"])[0]
        return _r("SI", 0.78, _frase(t0), "Menciona varios beneficios, sin «imagina que»")
    if len(todas) == 1:
        return _r(C.REVISAR, 0.50, _frase(_buscar(x.A, RX["beneficio"])[0]), "Un solo beneficio mencionado")
    return _r("NO", 0.75, None, "Ofrece sin explicar beneficios") if x.hay_oferta else _r(C.REVISAR, 0.40, None, "Sin oferta ni beneficios")


def c_alternativa(x):
    rec = _buscar(x.A, RX["recomienda"])
    if rec and x.hay_oferta:
        return _r("SI", 0.85, _frase(rec[0]), "Recomienda un plan con detalle de velocidad/precio")
    if x.hay_oferta:
        return _r(C.REVISAR, 0.50, None, "Ofrece plan sin recomendar ni comparar")
    return _r(C.REVISAR, 0.40, None, "No hay oferta de plan: ¿aplica el criterio?")


def c_objeciones(x):
    cli = [t for t in x.C if RX["objecion"].search(t["n"])]
    if not cli:
        return _r("No Aplica", 0.80, None, "El cliente no presentó objeciones")
    pos = cli[0]["i"]
    resp = [t for t in x.A if t["i"] > pos][:3]
    h = {m for t in resp for m in RX["manejo"].findall(t["n"])}
    evid = _frase(resp[0]) if resp else None
    pregunta = any("?" in t["raw"] for t in resp)
    if len(h) >= 2:
        return _r("SI", 0.85 + (0.05 if pregunta else 0), evid, "Indaga y responde la objeción con argumentos/beneficios")
    if len(h) == 1:
        return _r("SI", 0.65, evid, "Respuesta mínima a la objeción")
    return _r("NO", 0.80, evid, "Acepta la objeción sin manejarla")


def c_aseguramiento(x):
    if x.es_venta is False:
        return _r("No Aplica", 0.80, None, "Sin venta: no hay decisión que asegurar")
    h = _buscar(x.A, RX["asegura"])
    if h:
        return _r("SI", 0.85, _frase(h[0]), "Confirma la decisión del cliente")
    return _r("NO", 0.70, None, "No confirma acuerdo ni resuelve dudas")


def c_informacion(x):
    if x.es_venta is False:   # en la base histórica, 92 % de las llamadas sin venta lo marcan «No Aplica»
        return _r("No Aplica", 0.65, None, "Llamada sin venta: normalmente no aplica")
    ok = [k for k, rx in INFO.items() if _buscar(x.A, rx)]
    falta = [k for k in INFO if k not in ok]
    ev = _frase(_buscar(x.A, INFO[ok[0]])[0]) if ok else None
    if len(ok) >= 4:
        return _r("SI", 0.78, ev, "Información completa (" + ", ".join(ok) + "). Exactitud no verificada contra catálogo")
    if len(ok) == 3:
        return _r("SI", 0.62, ev, "Información casi completa; falta: " + ", ".join(falta))
    return _r("NO", 0.70, ev, "Información incompleta; falta: " + ", ".join(falta)) if x.hay_oferta \
        else _r(C.REVISAR, 0.40, None, "Sin oferta que evaluar")


def c_cierre(x):
    n = len(x.A)
    cola = x.A[int(n * 0.4):] if n >= 3 else x.A
    h = _buscar(cola, RX["cierre"])
    if h:
        return _r("SI", 0.88, _frase(h[-1]), "Solicita compromiso / agenda el cierre")
    ab = _buscar(cola, RX["abierto"])
    if ab:
        return _r("NO", 0.85, _frase(ab[-1]), "Deja la llamada abierta sin compromiso")
    return _r("NO", 0.70, None, "No hay pedido de cierre")


def c_prevalidacion(x):
    if x.es_venta is False:
        return _r("No Aplica", 0.90, None, "Solo aplica a ventas")
    h = {m for t in x.A for m in RX["prevalida"].findall(t["n"])}
    if len(h) >= 2:
        return _r("SI", 0.85, _frase(_buscar(x.A, RX["prevalida"])[0]), f"Valida {len(h)} datos del titular")
    if len(h) == 1:
        return _r(C.REVISAR, 0.50, _frase(_buscar(x.A, RX["prevalida"])[0]), "Valida un solo dato")
    return _r("NO", 0.75, None, "No valida datos del titular")


def _sistema(x, clave, nombre):
    v = x.sis.get(clave)
    if v is True:
        return _r("SI", 0.95, None, f"Dato del sistema: {nombre} registrado")
    if v is False:
        return _r("NO", 0.95, None, f"Dato del sistema: {nombre} NO registrado")
    return None


def c_inconcert(x):
    if x.es_venta is False:
        return _r("No Aplica", 0.90, None, "Solo aplica a ventas")
    return _sistema(x, "registro_inconcert", "Inconcert") or _r(
        C.REVISAR, 0.30, None, "Depende del CRM/Inconcert, no de la conversación: falta el dato del sistema")


def c_portabilidad(x):
    if x.sis.get("es_portabilidad") is False:
        return _r("No Aplica", 0.80, None, "La venta no es portabilidad")
    s = _sistema(x, "registro_portabilidad", "portabilidad")
    if s:
        return s
    if not _buscar(x.T, RX["portab"]) and x.es_venta is False:
        return _r("No Aplica", 0.60, None, "No se habló de portabilidad")
    return _r(C.REVISAR, 0.30, None, "Depende de WinForce/CRM: falta el dato del sistema")


def c_despedida(x):
    if x.es_venta is False:
        return _r("No Aplica", 0.90, None, "Solo aplica a ventas")
    fin = x.A[-2:]
    g, a = _buscar(fin, RX["thanks"]), _buscar(fin, RX["adios"])
    if g and a:
        return _r("SI", 0.90, _frase(fin[-1]), "Agradece y se despide cordialmente")
    if g or a:
        return _r("SI", 0.70, _frase((g or a)[0]), "Despedida parcial")
    return _r("NO", 0.80, _frase(fin[-1]) if fin else None, "Cierra sin agradecer ni despedirse")


FUNCIONES = {1: c_saludo, 2: c_cobertura, 3: c_actitud, 4: c_sondeo, 5: c_escucha, 6: c_beneficios, 7: c_alternativa,
             8: c_objeciones, 9: c_aseguramiento, 10: c_informacion, 11: c_cierre, 12: c_prevalidacion,
             13: c_inconcert, 14: c_portabilidad, 15: c_despedida}


def inferir_venta(turnos):
    cli = [t for t in turnos if t["rol"] == "C"]
    ases = [t for t in turnos if t["rol"] == "A"]
    return bool(_buscar(cli[-4:], RX["acepta"]) and (_buscar(ases, RX["cierre"]) or _buscar(ases, RX["asegura"])))


def extraer(transcripcion, es_venta=None, datos_sistema=None):
    """Devuelve {criterios:{id:{valor,confianza,evidencia,razon}}, es_venta, venta_inferida,
    sin_contacto, lectura_contrato, turnos}."""
    turnos = parsear(transcripcion or "")
    palabras = sum(len(t["raw"].split()) for t in turnos)
    ases = [t for t in turnos if t["rol"] == "A"]
    cli = [t for t in turnos if t["rol"] == "C"]
    etiquetado = bool(ases or cli)
    if palabras < 25 or (etiquetado and (not cli or not ases)):
        return dict(criterios={c["id"]: _r("Sin contacto", 0.90, None, "No hubo conversación evaluable")
                               for c in C.CRITERIOS},
                    es_venta=es_venta, venta_inferida=False, sin_contacto=True, lectura_contrato=None, turnos=len(turnos))
    inferida = es_venta is None
    if inferida:
        es_venta = inferir_venta(turnos)
    ctx = _Ctx(turnos, es_venta, datos_sistema)
    crit = {i: _cap(f(ctx), ctx) for i, f in FUNCIONES.items()}
    lectura = None
    if es_venta:
        h = _buscar(ctx.A, RX["lectura"])
        lectura = dict(valor="SI" if h else "NO", evidencia=_frase(h[0]) if h else None)
    return dict(criterios=crit, es_venta=es_venta, venta_inferida=inferida, sin_contacto=False,
                lectura_contrato=lectura, turnos=len(turnos))
