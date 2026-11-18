"""Pauta de contrato: cláusulas que el asesor debe decir en la lectura del contrato. El bot compara la
transcripción con cada cláusula (cobertura de términos en una ventana de 1-3 oraciones del asesor) y reporta
CUMPLE / PARCIAL / NO_CUMPLE con la frase de evidencia. Se reporta aparte de la Nota Final (como «Lectura del contrato»).
La pauta es editable desde la aplicación; la que viene por defecto es un EJEMPLO que debe reemplazarse."""
import re
from . import extractor

EJEMPLO = [
    dict(nombre="Aviso de grabación y aceptación", critica=1, peso=1.0, obligatorias="grabada",
         texto_referencia="Le informo que esta llamada está siendo grabada con fines de calidad y como constancia de su contratación, ¿está de acuerdo?"),
    dict(nombre="Identificación del titular", critica=1, peso=1.0, obligatorias="titular",
         texto_referencia="Confirmo que usted es el titular del servicio, me indica su nombre completo y su número de documento de identidad"),
    dict(nombre="Plan y velocidad contratada", critica=1, peso=1.0, obligatorias="mbps",
         texto_referencia="Usted está contratando el plan de internet con velocidad de megas mbps"),
    dict(nombre="Precio mensual y facturación", critica=1, peso=1.0, obligatorias="soles",
         texto_referencia="El precio mensual del plan es de soles y se factura mensualmente con su recibo"),
    dict(nombre="Permanencia o plazo", critica=0, peso=1.0, obligatorias="",
         texto_referencia="El contrato tiene una permanencia o plazo mínimo de meses"),
    dict(nombre="Instalación y equipos", critica=0, peso=1.0, obligatorias="instalacion",
         texto_referencia="La instalación se realiza en su domicilio por un técnico y se entrega router y equipos"),
    dict(nombre="Aceptación expresa del cliente", critica=1, peso=1.5, obligatorias="acepta",
         texto_referencia="¿Acepta usted expresamente las condiciones del contrato que le he leído?"),
    dict(nombre="Canales de atención y reclamos", critica=0, peso=0.5, obligatorias="",
         texto_referencia="Para consultas o reclamos puede comunicarse con nuestros canales de atención al cliente"),
]
_STOP = set("""de la el en y a los las un una por con para que es se su al lo del como mas pero sus le ya o fue este si
entre cuando muy sin sobre tambien me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese
eso ante ellos e esto mi antes algunos que unos yo otro otras otra el tanto esa estos mucho quienes nada muchos cual
poco ella estar estas algunas algo nosotros usted ustedes ser son esta le indico indica""".split())


def _stem(t):
    return t[:6]


def _toks(n):
    return {_stem(t) for t in re.findall(r"[a-z0-9]+", n) if len(t) > 2 and t not in _STOP}


def _oraciones(turnos):
    out = []
    for t in turnos:
        for o in re.split(r"(?<=[.!?])\s+|\n", t["raw"]):
            if o.strip():
                out.append((o.strip(), extractor._norm(o)))
    return out


def evaluar(clausulas, transcripcion):
    """clausulas: lista de dict (nombre, texto_referencia, obligatorias, critica, peso, id_clausula?)."""
    turnos = extractor.parsear(transcripcion or "")
    ases = [t for t in turnos if t["rol"] == "A"] or turnos
    sents = _oraciones(ases)
    res = []
    for c in clausulas:
        ref = _toks(extractor._norm(c["texto_referencia"]))
        oblig = [extractor._norm(x).strip() for x in re.split(r"[,;]", c.get("obligatorias") or "") if x.strip()]
        mejor, texto, norm_w = 0.0, None, ""
        for i in range(len(sents)):
            for w in (1, 2, 3):
                ven = sents[i:i + w]
                if len(ven) < w:
                    break
                tk = set().union(*(_toks(n) for _, n in ven))
                cov = len(ref & tk) / len(ref) if ref else 0
                if cov > mejor:
                    mejor, texto, norm_w = cov, " ".join(o for o, _ in ven), " ".join(n for _, n in ven)
        falt = [o for o in oblig if o not in norm_w] if texto else oblig
        if mejor >= 0.70 and not falt:
            est = "CUMPLE"
        elif mejor >= 0.40:
            est = "PARCIAL"
        else:
            est = "NO_CUMPLE"
        res.append(dict(id_clausula=c.get("id_clausula"), nombre=c["nombre"], estado=est, puntaje=round(mejor, 2),
                        evidencia=(texto if mejor >= 0.40 else None), faltantes=falt, critica=int(c.get("critica", 0)),
                        peso=float(c.get("peso", 1))))
    tot = sum(r["peso"] for r in res) or 1
    pct = 100 * sum(r["peso"] * {"CUMPLE": 1, "PARCIAL": .5, "NO_CUMPLE": 0}[r["estado"]] for r in res) / tot
    crit = [r for r in res if r["critica"]]
    if any(r["estado"] == "NO_CUMPLE" for r in crit) or pct < 60:
        ver = "NO CONFORME"
    elif any(r["estado"] == "PARCIAL" for r in crit) or pct < 80:
        ver = "OBSERVADO"
    else:
        ver = "CONFORME"
    return dict(clausulas=res, pct=round(pct, 1), veredicto=ver,
                criticas_fallidas=[r["nombre"] for r in crit if r["estado"] != "CUMPLE"])


def desde_texto(texto):
    """Convierte la pauta pegada como texto (una cláusula por línea o párrafo) en cláusulas editables."""
    out = []
    for linea in re.split(r"\n\s*\n|\n", texto or ""):
        l = re.sub(r"^\s*(\d+[\.\)]|[-•*])\s*", "", linea).strip()
        if len(l.split()) >= 3:
            nombre = " ".join(l.split()[:6]).rstrip(",.;:")
            out.append(dict(nombre=nombre, texto_referencia=l, obligatorias="", critica=0, peso=1.0))
    return out
