"""Motor de reglas determinista (no es ML). Reproduce al 100 % el cálculo de la ficha corregida.
Pilar = 1 − (criterios en NO)/(criterios del pilar). 'No Aplica' no es quiebre y sigue en el denominador
(regla vigente). La regla 'alternativa' lo saca del denominador (análisis de sensibilidad)."""
from . import config as C


def calcular(valores, regla="vigente"):
    """valores: {id_criterio: 'SI'|'NO'|'No Aplica'|'Sin contacto'} con los 15 criterios.
    Devuelve pilares (0-100), nota (0-100), nivel, quiebres y si es auditable."""
    faltan = [c["id"] for c in C.CRITERIOS if c["id"] not in valores]
    if faltan:
        raise ValueError(f"Faltan criterios: {faltan}")
    malos = {k: v for k, v in valores.items() if v not in C.VALORES}
    if malos:
        raise ValueError(f"Valores no permitidos: {malos}")
    if any(v == "Sin contacto" for v in valores.values()):
        return dict(auditable=False, pilares={p: None for p in C.PILARES}, nota=None, nivel=None,
                    quiebres={p: None for p in C.PILARES}, total_quiebres=None, regla=regla)
    pilares, quiebres = {}, {}
    for p in C.PILARES:
        ids = [c["id"] for c in C.CRITERIOS if c["pilar"] == p]
        q = sum(1 for i in ids if valores[i] == "NO")
        den = len(ids) if regla == "vigente" else sum(1 for i in ids if valores[i] != "No Aplica")
        pilares[p] = 100.0 if den == 0 else 100.0 * (1 - q / den)
        quiebres[p] = q
    nota = sum(C.PILARES[p]["peso"] * pilares[p] for p in C.PILARES)
    return dict(auditable=True, pilares=pilares, nota=nota, nivel=C.nivel_de(nota),
                quiebres=quiebres, total_quiebres=sum(quiebres.values()), regla=regla)


def rango_con_incertidumbre(valores_bot, regla="vigente"):
    """El bot marca REVISAR cuando no halla evidencia. Se calcula la nota en el peor caso (REVISAR=NO)
    y el mejor caso (REVISAR=SI): si el nivel cambia entre ambos, el caso es de riesgo."""
    peor = {i: ("NO" if v == C.REVISAR else v) for i, v in valores_bot.items()}
    mejor = {i: ("SI" if v == C.REVISAR else v) for i, v in valores_bot.items()}
    return calcular(peor, regla), calcular(mejor, regla)
