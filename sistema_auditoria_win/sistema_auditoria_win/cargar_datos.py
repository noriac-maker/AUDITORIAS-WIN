"""Carga datos/BBDD_procesada_WIN.xlsx en auditorias.db y valida el motor de reglas contra el Excel.
Uso:  python cargar_datos.py [ruta_excel] [ruta_db]
Privacidad (Ley 29733): DNI del asesor enmascarado; nombre, teléfono y DNI del cliente NO se cargan."""
import os, sys
import pandas as pd
from auditoria import config as C, db, motor

AQUI = os.path.dirname(os.path.abspath(__file__))


def _s(v):
    return None if pd.isna(v) else str(v).strip()


def cargar(xlsx=None, ruta_db=None, verbose=True):
    xlsx = xlsx or os.path.join(AQUI, "datos", "BBDD_procesada_WIN.xlsx")
    ruta_db = ruta_db or os.path.join(AQUI, "datos", "auditorias_seed.db")
    if os.path.exists(ruta_db):
        os.remove(ruta_db)
    d = pd.read_excel(xlsx, sheet_name="datos_procesados")
    con = db.conectar(ruta_db)
    db.inicializar(con)
    dif_max, nivel_ok = 0.0, 0
    for _, r in d.iterrows():
        sup = db.id_catalogo(con, "supervisor", _s(r["SUPERVISOR"]))
        mon = db.id_catalogo(con, "monitor", _s(r["MONITOR DE CALIDAD"]))
        cam = db.id_catalogo(con, "campana", _s(r["CAMPAÑA"]))
        dni = str(int(r["DNI Asesor"])) if not pd.isna(r["DNI Asesor"]) else ""
        con.execute("INSERT OR IGNORE INTO asesor(usuario,nombre,dni_enmascarado,id_supervisor) VALUES(?,?,?,?)",
                    (_s(r["ID Usuario"]), _s(r["Nombre Asesor"]), "****" + dni[-4:] if dni else None, sup))
        ase = con.execute("SELECT id_asesor FROM asesor WHERE usuario=?", (_s(r["ID Usuario"]),)).fetchone()[0]
        idl = str(int(r["ID DE GRABACION"]))
        venta = 1 if _s(r["Venta Concretada"]) == "SI" else 0
        con.execute("""INSERT INTO llamada VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            idl, ase, cam, str(r["FECHA DE MONITOREO"])[:10], str(r["FECHA DE LA LLAMADA"])[:10], _s(r["SEMANA"]),
            None if pd.isna(r["TMO (SEG.)"]) else float(r["TMO (SEG.)"]), _s(r["LLAMADA"]),
            _s(r["TIPIFICACION AGENTE (INCONCERT)"]), venta, _s(r["Plan ofrecido"]), _s(r["COMPOSICION DE VENTA"]),
            _s(r["Distrito"]), _s(r["TIPO DE CLIENTE"]), _s(r["DESCRIPCIÓN DE LA LLAMADA"]), "simulada"))
        vals = {c["id"]: _s(r[c["columna"]]) for c in C.CRITERIOS}
        res = motor.calcular(vals)
        # validación contra el cálculo del Excel (escala 0-1)
        dif = abs(res["nota"] / 100 - float(r["Nota Final"]))
        dif_max = max(dif_max, dif)
        nivel_ok += res["nivel"] == r["Nivel de calidad"]
        p = res["pilares"]
        cur = con.execute("""INSERT INTO auditoria(id_llamada,id_monitor,fecha,auditable,p_conquistar,p_conocer,
            p_convencer,p_concretar,nota,nivel,estado,origen) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (idl, mon, str(r["FECHA DE MONITOREO"])[:10], 1, p["IMPACTA"], p["DESCUBRE"], p["SOLUCIONA"],
             p["CONSOLIDA"], res["nota"], res["nivel"], "VALIDADA", "historico"))
        ida = cur.lastrowid
        for c in C.CRITERIOS:
            obs = _s(r["Observación " + c["columna"]]) if ("Observación " + c["columna"]) in r.index else None
            if obs is None:
                for k in r.index:                      # encabezados de observación con ligeras variaciones
                    if k.startswith("Observación") and c["columna"].split(" (")[0] in k:
                        obs = _s(r[k]); break
            con.execute("INSERT INTO auditoria_criterio(id_auditoria,id_criterio,valor_final,observacion) VALUES(?,?,?,?)",
                        (ida, c["id"], vals[c["id"]], obs))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0]
    if verbose:
        print(f"Cargadas {n} auditorías, {con.execute('SELECT COUNT(*) FROM auditoria_criterio').fetchone()[0]} criterios.")
        print(f"Validación del motor frente al Excel: diferencia máxima de nota = {dif_max:.2e}; nivel coincide en {nivel_ok}/{len(d)}.")
    assert dif_max < 1e-9 and nivel_ok == len(d), "El motor no reproduce el Excel"
    con.close()
    return ruta_db


if __name__ == "__main__":
    cargar(*(sys.argv[1:3]))
