"""Evalúa el extractor contra evaluaciones humanas: Precision/Recall/F1 por criterio, Kappa, MAE de la nota,
matriz de confusión del nivel, Recall de Deficiente y efectividad (nivel correcto y |Δnota| <= 5).
Uso:  python -m auditoria.evaluacion ejemplos/transcripciones_demo.json
Formato del JSON: lista de {transcripcion, es_venta, datos_sistema, gold:{clave_criterio: valor}}.
Con audios reales se espera >= 300 ventas con evaluación humana verificada (informe 7.6.5)."""
import json
import sys
from collections import Counter
from . import config as C, motor, servicio

CLASES = ["SI", "NO", "No Aplica"]
CLAVE_ID = {c["clave"]: c["id"] for c in C.CRITERIOS}


def _kappa(pares):
    n = len(pares)
    if not n:
        return None
    po = sum(a == b for a, b in pares) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def evaluar(casos):
    pares, por_crit, filas = [], {c["id"]: [] for c in C.CRITERIOS}, []
    for caso in casos:
        gold = {CLAVE_ID[k]: v for k, v in caso["gold"].items()}
        r = servicio.auditar(caso["transcripcion"], caso.get("es_venta"), caso.get("datos_sistema"))
        bot = {c["id"]: c["valor"] for c in r["criterios"]}
        for i in gold:
            por_crit[i].append((gold[i], bot[i]))
            pares.append((gold[i], bot[i]))
        if "Sin contacto" in gold.values():
            filas.append(dict(id=caso.get("id"), nota_gold=None, nota_bot=None, nivel_gold=None, nivel_bot=r["nivel"],
                              ok=(not r["auditable"])))
            continue
        g = motor.calcular(gold)
        filas.append(dict(id=caso.get("id"), nota_gold=g["nota"], nota_bot=r["nota"], nivel_gold=g["nivel"],
                          nivel_bot=r["nivel"], ruta=r["ruta"],
                          ok=(r["nivel"] == g["nivel"] and abs(r["nota"] - g["nota"]) <= 5)))
    metr_crit = []
    for c in C.CRITERIOS:
        pp = por_crit[c["id"]]
        f1s = []
        for k in CLASES:
            tp = sum(1 for g, b in pp if g == k and b == k)
            fp = sum(1 for g, b in pp if g != k and b == k)
            fn = sum(1 for g, b in pp if g == k and b != k)
            if tp + fn:
                p = tp / (tp + fp) if tp + fp else 0
                rc = tp / (tp + fn)
                f1s.append(2 * p * rc / (p + rc) if p + rc else 0)
        metr_crit.append(dict(criterio=c["nombre"], exactitud=round(sum(g == b for g, b in pp) / len(pp), 3) if pp else None,
                              f1_macro=round(sum(f1s) / len(f1s), 3) if f1s else None,
                              pct_revisar=round(sum(b == C.REVISAR for _, b in pp) / len(pp), 3) if pp else None))
    aud = [f for f in filas if f["nota_gold"] is not None]
    defic = [f for f in aud if f["nivel_gold"] == "Deficiente"]
    return dict(
        n=len(casos), kappa=None if not pares else round(_kappa(pares), 3),
        exactitud_criterios=round(sum(g == b for g, b in pares) / len(pares), 3),
        tasa_revisar=round(sum(b == C.REVISAR for _, b in pares) / len(pares), 3),
        mae_nota=round(sum(abs(f["nota_gold"] - f["nota_bot"]) for f in aud) / len(aud), 2) if aud else None,
        efectividad=round(sum(f["ok"] for f in filas) / len(filas), 3),
        recall_deficiente=(round(sum(1 for f in defic if f["nivel_bot"] == "Deficiente") / len(defic), 3) if defic else None),
        por_criterio=metr_crit, casos=filas,
        metas=dict(efectividad=">= 0.835", recall_deficiente=">= 0.90", kappa=">= 0.60", mae_nota="<= 5"))


if __name__ == "__main__":
    res = evaluar(json.load(open(sys.argv[1], encoding="utf-8")))
    print(json.dumps({k: v for k, v in res.items() if k not in ("por_criterio", "casos")}, indent=1, ensure_ascii=False))
    for m in res["por_criterio"]:
        print(f"  {m['criterio']:<40} exactitud={m['exactitud']}  F1={m['f1_macro']}  REVISAR={m['pct_revisar']}")
    for c in res["casos"]:
        print("  ", c)
