"""Base centralizada SQLite (3FN, integridad referencial activa). Modelo físico de la Tabla 23 del informe."""
import sqlite3
from . import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS supervisor(id_supervisor INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS monitor(id_monitor INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS campana(id_campana INTEGER PRIMARY KEY, nombre TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS asesor(
  id_asesor INTEGER PRIMARY KEY, usuario TEXT UNIQUE, nombre TEXT NOT NULL, dni_enmascarado TEXT,
  id_supervisor INTEGER REFERENCES supervisor(id_supervisor));
CREATE TABLE IF NOT EXISTS llamada(
  id_llamada TEXT PRIMARY KEY,
  id_asesor INTEGER REFERENCES asesor(id_asesor), id_campana INTEGER REFERENCES campana(id_campana),
  fecha_monitoreo TEXT, fecha_llamada TEXT, semana TEXT, tmo_seg REAL, tipo_llamada TEXT,
  tipificacion TEXT, venta_concretada INTEGER NOT NULL DEFAULT 0, plan_ofrecido TEXT,
  composicion_venta TEXT, distrito TEXT, tipo_cliente TEXT, descripcion TEXT,
  origen TEXT NOT NULL DEFAULT 'simulada');
CREATE TABLE IF NOT EXISTS transcripcion(
  id_transcripcion INTEGER PRIMARY KEY AUTOINCREMENT, id_llamada TEXT NOT NULL REFERENCES llamada(id_llamada),
  texto TEXT NOT NULL, motor_asr TEXT, wer REAL, fecha TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS pilar(id_pilar INTEGER PRIMARY KEY, nombre_ficha TEXT, nombre_modelo TEXT, peso REAL);
CREATE TABLE IF NOT EXISTS criterio(
  id_criterio INTEGER PRIMARY KEY, id_pilar INTEGER REFERENCES pilar(id_pilar), nombre TEXT, solo_venta INTEGER);
CREATE TABLE IF NOT EXISTS auditoria(
  id_auditoria INTEGER PRIMARY KEY AUTOINCREMENT,
  id_llamada TEXT NOT NULL REFERENCES llamada(id_llamada),
  id_monitor INTEGER REFERENCES monitor(id_monitor),
  fecha TEXT DEFAULT CURRENT_TIMESTAMP,
  auditable INTEGER NOT NULL DEFAULT 1,
  p_conquistar REAL, p_conocer REAL, p_convencer REAL, p_concretar REAL,
  nota REAL, nivel TEXT,
  nota_bot REAL, nota_bot_min REAL, nota_bot_max REAL, nivel_bot TEXT, confianza REAL,
  ruta TEXT, motivos_ruta TEXT,
  estado TEXT NOT NULL DEFAULT 'VALIDADA',
  origen TEXT NOT NULL DEFAULT 'historico',
  regla TEXT NOT NULL DEFAULT 'vigente');
CREATE TABLE IF NOT EXISTS auditoria_criterio(
  id_auditoria INTEGER REFERENCES auditoria(id_auditoria), id_criterio INTEGER REFERENCES criterio(id_criterio),
  valor_bot TEXT, confianza_bot REAL, valor_final TEXT, evidencia TEXT, observacion TEXT,
  PRIMARY KEY(id_auditoria, id_criterio));
CREATE TABLE IF NOT EXISTS auditoria_historial(
  id_hist INTEGER PRIMARY KEY AUTOINCREMENT, id_auditoria INTEGER REFERENCES auditoria(id_auditoria),
  id_criterio INTEGER REFERENCES criterio(id_criterio), valor_anterior TEXT, valor_nuevo TEXT,
  usuario TEXT, fecha TEXT DEFAULT CURRENT_TIMESTAMP, motivo TEXT);
CREATE TABLE IF NOT EXISTS pauta_clausula(
  id_clausula INTEGER PRIMARY KEY AUTOINCREMENT, orden INTEGER, nombre TEXT NOT NULL, texto_referencia TEXT NOT NULL,
  obligatorias TEXT DEFAULT '', critica INTEGER DEFAULT 0, peso REAL DEFAULT 1, activa INTEGER DEFAULT 1, tipo TEXT DEFAULT 'lectura');
CREATE TABLE IF NOT EXISTS validacion(
  id_validacion INTEGER PRIMARY KEY AUTOINCREMENT, id_asesor INTEGER REFERENCES asesor(id_asesor), fecha TEXT DEFAULT CURRENT_TIMESTAMP,
  estado TEXT, pct_contrato REAL, claridad REAL, pct_datos REAL, cliente TEXT, resultado TEXT, transcripcion TEXT, plantilla TEXT,
  decision TEXT, revisado_por TEXT, motivo_decision TEXT, fecha_decision TEXT);
CREATE TABLE IF NOT EXISTS auditoria_pauta(
  id_auditoria INTEGER REFERENCES auditoria(id_auditoria), id_clausula INTEGER, nombre TEXT, estado TEXT,
  puntaje REAL, evidencia TEXT, faltantes TEXT, critica INTEGER, PRIMARY KEY(id_auditoria,id_clausula));
CREATE TABLE IF NOT EXISTS config(clave TEXT PRIMARY KEY, valor TEXT);
CREATE INDEX IF NOT EXISTS ix_aud_llamada ON auditoria(id_llamada);
CREATE INDEX IF NOT EXISTS ix_aud_estado ON auditoria(estado);
CREATE INDEX IF NOT EXISTS ix_llamada_asesor ON llamada(id_asesor);
"""


def conectar(ruta):
    con = sqlite3.connect(ruta, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _migrar(con):
    cols = {r[1] for r in con.execute("PRAGMA table_info(auditoria)")}
    for c, t in (("pauta_pct", "REAL"), ("pauta_veredicto", "TEXT")):
        if c not in cols:
            con.execute(f"ALTER TABLE auditoria ADD COLUMN {c} {t}")
    if "tipo" not in {r[1] for r in con.execute("PRAGMA table_info(pauta_clausula)")}:
        con.execute("ALTER TABLE pauta_clausula ADD COLUMN tipo TEXT DEFAULT 'lectura'")


def inicializar(con):
    con.executescript(SCHEMA)
    _migrar(con)
    from . import contrato
    if con.execute("SELECT COUNT(*) FROM pauta_clausula").fetchone()[0] == 0:
        for i, c in enumerate(contrato.CLAUSULAS, 1):
            con.execute("INSERT INTO pauta_clausula(orden,nombre,texto_referencia,obligatorias,critica,peso,tipo) VALUES(?,?,?,?,?,?,?)",
                        (i, c["nombre"], c["texto_referencia"], c["obligatorias"], c["critica"], c["peso"], c["tipo"]))
        con.execute("INSERT OR REPLACE INTO config VALUES('pauta_ejemplo','0')")
    for p, d in C.PILARES.items():
        con.execute("INSERT OR IGNORE INTO pilar VALUES(?,?,?,?)", (d["id"], p, d["modelo"], d["peso"]))
    for c in C.CRITERIOS:
        con.execute("INSERT OR IGNORE INTO criterio VALUES(?,?,?,?)",
                    (c["id"], C.PILARES[c["pilar"]]["id"], c["nombre"], int(c["solo_venta"])))
    con.commit()


def id_catalogo(con, tabla, nombre):
    """Devuelve el id de un catálogo (supervisor/monitor/campana), creándolo si no existe."""
    col = {"supervisor": "id_supervisor", "monitor": "id_monitor", "campana": "id_campana"}[tabla]
    r = con.execute(f"SELECT {col} FROM {tabla} WHERE nombre=?", (nombre,)).fetchone()
    if r:
        return r[0]
    return con.execute(f"INSERT INTO {tabla}(nombre) VALUES(?)", (nombre,)).lastrowid
