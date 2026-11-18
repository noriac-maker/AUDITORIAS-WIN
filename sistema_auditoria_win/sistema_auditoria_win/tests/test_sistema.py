"""Pruebas de extremo a extremo. Ejecutar:  python -m unittest discover -s tests -v"""
import json, os, sys, tempfile, threading, unittest, urllib.request, urllib.error
from http.server import ThreadingHTTPServer

AQUI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, AQUI)
import cargar_datos, servidor
from auditoria import config as C, db, extractor, motor, servicio, asr, evaluacion, auth as A, pauta as P, contrato as K

EJ = json.load(open(os.path.join(AQUI, "ejemplos", "transcripciones_demo.json"), encoding="utf-8"))
VENTAS = json.load(open(os.path.join(AQUI, "ejemplos", "ventas_demo.json"), encoding="utf-8"))
TMP = tempfile.mkdtemp()
DB = os.path.join(TMP, "t.db")


class TestMotor(unittest.TestCase):
    def test_nota_y_niveles(self):
        v = {c["id"]: "SI" for c in C.CRITERIOS}
        self.assertEqual(motor.calcular(v)["nota"], 100)
        v[8] = v[11] = "NO"
        r = motor.calcular(v)
        self.assertAlmostEqual(r["nota"], 0.2 * 100 + 0.2 * 100 + 0.35 * (200 / 3) + 0.25 * 80)
        self.assertEqual(r["nivel"], "Aceptable")

    def test_no_aplica_y_regla_alternativa(self):
        v = {c["id"]: "No Aplica" for c in C.CRITERIOS}
        v[1] = "NO"
        self.assertGreater(motor.calcular(v)["nota"], 90)               # vigente: No Aplica = cumplido
        self.assertLess(motor.calcular(v, "alternativa")["pilares"]["IMPACTA"], 1)  # alternativa: 1 criterio evaluable, en NO

    def test_sin_contacto_y_validaciones(self):
        v = {c["id"]: "SI" for c in C.CRITERIOS}; v[3] = "Sin contacto"
        r = motor.calcular(v); self.assertFalse(r["auditable"]); self.assertIsNone(r["nota"])
        with self.assertRaises(ValueError): motor.calcular({1: "SI"})
        v[3] = "TAL VEZ"
        with self.assertRaises(ValueError): motor.calcular(v)

    def test_umbrales(self):
        self.assertEqual(C.nivel_de(69.99), "Deficiente"); self.assertEqual(C.nivel_de(70), "Aceptable")
        self.assertEqual(C.nivel_de(84.99), "Aceptable"); self.assertEqual(C.nivel_de(85), "Excelente")


class TestExtractor(unittest.TestCase):
    def test_ejemplos_de_referencia(self):
        res = evaluacion.evaluar(EJ)
        self.assertGreaterEqual(res["efectividad"], 0.8)

    def test_no_inventa_datos_del_crm(self):
        r = servicio.auditar(EJ[0]["transcripcion"], True)  # sin datos_sistema
        self.assertEqual({c["id"]: c["valor"] for c in r["criterios"]}[13], C.REVISAR)
        self.assertEqual(r["ruta"], "RESPALDO_MANUAL")
        self.assertGreater(r["nota_max"], r["nota_min"] - 1e-9)

    def test_sin_contacto(self):
        r = servicio.auditar(EJ[4]["transcripcion"])
        self.assertFalse(r["auditable"]); self.assertEqual(r["ruta"], "RESPALDO_MANUAL")

    def test_sin_etiquetas_limita_confianza(self):
        txt = " ".join(t.split(": ", 1)[1] for t in EJ[0]["transcripcion"].splitlines())
        r = servicio.auditar(txt, True, EJ[0]["datos_sistema"])
        self.assertTrue(all(c["confianza"] <= 0.55 for c in r["criterios"] if c["valor"] != "No Aplica" and c["id"] not in (13, 14)))

    def test_deficiente_siempre_a_respaldo(self):
        r = servicio.auditar(EJ[3]["transcripcion"], False)
        self.assertEqual(r["nivel"], "Deficiente"); self.assertEqual(r["ruta"], "RESPALDO_MANUAL")

    def test_wer(self):
        self.assertEqual(asr.wer("a b c d", "a b c d"), 0)
        self.assertEqual(asr.wer("a b c d", "a x c d"), 0.25)


class TestDatosYApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cargar_datos.cargar(ruta_db=DB, verbose=False)
        servidor.DB = DB
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), servidor.Handler)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def call(self, path, body=None):
        req = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            return json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            return dict(json.load(e), http=e.code)

    def test_1_carga_reproduce_informe(self):
        con = db.conectar(DB)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM auditoria").fetchone()[0], 600)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM auditoria_criterio").fetchone()[0], 9000)
        self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
        cols = [r[1] for t in ("asesor", "llamada") for r in con.execute(f"PRAGMA table_info({t})")]
        self.assertFalse({"telefono", "dni", "nombre_cliente"} & set(cols))        # privacidad
        self.assertTrue(all(r[0].startswith("****") for r in con.execute("SELECT dni_enmascarado FROM asesor")))
        d = self.call("/api/dashboard")
        self.assertEqual((d["n"], d["nota"], d["pct_deficiente"], d["pct_aceptable"], d["pct_excelente"]),
                         (180, 85.8, 13.3, 27.2, 59.4))                          # cifras de la Tabla 0 / 12

    def test_2_filtros(self):
        self.assertEqual(self.call("/api/dashboard?ventas=0")["n"], 600)
        self.assertEqual(self.call("/api/dashboard?campana=NOEXISTE")["n"], 0)
        self.assertEqual(self.call("/api/dashboard?desde=2026-07-20")["n"] < 180, True)
        a = self.call("/api/meta")["filtros"]["asesores"][0]
        self.assertEqual(self.call("/api/dashboard?asesor=" + urllib.request.quote(a))["asesores"][0]["muestra_pequena"], True)

    def test_3_flujo_bot_auditor(self):
        e = EJ[1]
        r = self.call("/api/auditoria", dict(transcripcion=e["transcripcion"], es_venta=True, datos_sistema=e["datos_sistema"],
                                             contexto=dict(id_llamada="T-1", asesor="Ana Prueba", campana="desborde")))
        ida = r["id_auditoria"]
        self.assertEqual(self.call("/api/auditoria", dict(transcripcion=e["transcripcion"], contexto=dict(id_llamada="T-1")))["http"], 400)
        self.assertIn("T-1", [c["llamada"] for c in self.call("/api/cola")])
        d = self.call(f"/api/auditoria/{ida}")
        self.assertEqual((d["estado"], d["nota"]), ("PRE_LLENADA", None))
        self.assertEqual(self.call(f"/api/auditoria/{ida}/revisar", dict(valores={}, usuario=""))["http"], 400)   # sin usuario
        nota_bot = d["nota_bot"]
        # el bot dejó en REVISAR saludo, actitud y alternativa: el auditor debe resolverlos
        self.assertEqual(self.call(f"/api/auditoria/{ida}/revisar", dict(valores={"15": "SI"}, usuario="aud1"))["http"], 400)
        rv = self.call(f"/api/auditoria/{ida}/revisar",
                       dict(valores={"1": "SI", "3": "NO", "7": "NO", "15": "SI"}, usuario="aud1", motivo="prueba"))
        self.assertEqual((rv["estado"], rv["cambios"]), ("CORREGIDA", 4))   # 3 REVISAR resueltos + 1 corrección real
        self.assertAlmostEqual(rv["nota"], nota_bot + 0.20 * 100 / 3 + 0.25 * 20, places=6)   # saludo (IMPACTA 1/3) + despedida (CONSOLIDA 1/5)
        d = self.call(f"/api/auditoria/{ida}")
        self.assertEqual(len(d["historial"]), 4); self.assertEqual({h["usuario"] for h in d["historial"]}, {"aud1"})
        self.assertNotIn("T-1", [c["llamada"] for c in self.call("/api/cola")])
        bot = self.call("/api/dashboard?ventas=0")["bot"]
        self.assertEqual(bot["n_revisadas"], 1); self.assertLess(bot["acierto_criterio"], 100)
        self.assertEqual(self.call(f"/api/auditorias?estado=CORREGIDA")["total"], 1)

    def test_4_revisar_exige_resolver_revisar(self):
        r = self.call("/api/auditoria", dict(transcripcion=EJ[0]["transcripcion"], es_venta=True, contexto=dict(id_llamada="T-2")))
        rv = self.call(f"/api/auditoria/{r['id_auditoria']}/revisar", dict(valores={}, usuario="aud1"))
        self.assertEqual(rv["http"], 400); self.assertIn("REVISAR", rv["error"])
        ok = self.call(f"/api/auditoria/{r['id_auditoria']}/revisar", dict(valores={"13": "SI", "14": "SI"}, usuario="aud1"))
        self.assertEqual(ok["estado"], "VALIDADA"); self.assertEqual(ok["nota"], 100)

    def test_5_errores_y_seguridad(self):
        self.assertEqual(self.call("/api/auditar", dict(transcripcion="  "))["http"], 400)
        self.assertEqual(self.call("/api/auditoria/99999")["http"], 404)
        self.assertEqual(self.call("/api/calcular", dict(valores={"1": "SI"}))["http"], 400)
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(self.base + "/..%2f..%2fservidor.py")
        self.assertEqual(cm.exception.code, 404)
        self.assertIn(b"<html", urllib.request.urlopen(self.base + "/").read().lower())

    def test_6_asesores_y_perfil(self):
        r = self.call("/api/asesores?orden=def")
        self.assertGreaterEqual(r["total"], 60)
        a = r["asesores"][0]
        self.assertEqual((a["n"], a["nivel"], a["muestra_pequena"]), (3, "Deficiente", True))
        self.assertEqual(self.call("/api/asesores?q=" + urllib.request.quote(a["nombre"][:6]))["asesores"][0]["id"], a["id"])
        pf = self.call(f"/api/asesor/{a['id']}")
        self.assertEqual((pf["n"], len(pf["historial"]), len(pf["evolucion"])), (3, 10, 3))
        self.assertTrue(pf["coaching"]); self.assertTrue(84 < pf["equipo"] < 87)
        self.assertEqual(self.call("/api/asesor/99999")["http"], 404)
        self.assertGreaterEqual(self.call("/api/resumen")["ventas"], 180)

    def test_7_contrato(self):
        self.assertEqual(K._numeros("setenta y nueve soles"), "79 soles")
        self.assertEqual(K._numeros("mil novecientos noventa y dos"), "1992")
        self.assertEqual(K._numeros("cuatro siete cero cinco"), "4 7 0 5")
        pl = K.parsear_plantilla(VENTAS[0]["plantilla"])
        self.assertEqual((pl["mbps"], pl["dni"]), (750, "47058798"))
        for v in VENTAS:
            r = K.evaluar(K.CLAUSULAS, v["transcripcion"], v["plantilla"])
            self.assertEqual(r["estado"], v["esperado"], v["id"])
        a = K.evaluar(K.CLAUSULAS, VENTAS[0]["transcripcion"], VENTAS[0]["plantilla"])
        self.assertTrue(a["puede_subir"]); self.assertEqual((a["pct_contrato"], a["claridad"], a["pct_datos"]), (100.0, 100.0, 100.0))
        malo = VENTAS[0]["transcripcion"].replace("47058798", "47058700")                    # DNI mal leído
        d = K.evaluar(K.CLAUSULAS, malo, VENTAS[0]["plantilla"])["datos"]
        self.assertEqual(next(x for x in d if x["campo"] == "dni")["estado"], "NO_LEIDO")
        sin = "\n".join(l for l in VENTAS[0]["transcripcion"].splitlines() if "Sí, acepto" not in l)   # el cliente nunca dice «sí acepto»
        self.assertEqual(K.evaluar(K.CLAUSULAS, sin, VENTAS[0]["plantilla"])["estado"], "RECHAZADO")
        self.assertIsNone(K.evaluar(K.CLAUSULAS, " ".join(l.split(": ", 1)[1] for l in VENTAS[0]["transcripcion"].splitlines()), VENTAS[0]["plantilla"])["claridad"])

    def test_7b_api_ventas(self):
        aid = self.call("/api/asesores")["asesores"][0]["id"]
        r = self.call("/api/validar", dict(id_asesor=aid, transcripcion=VENTAS[2]["transcripcion"], plantilla=VENTAS[2]["plantilla"]))
        self.assertEqual(r["estado"], "OBSERVADO")
        self.assertEqual(self.call("/api/validar", dict(id_asesor=aid, transcripcion="ASESOR: hola", plantilla=""))["http"], 400)
        self.assertEqual(self.call("/api/resumen")["validaciones"]["por_revisar"], 1)
        self.assertEqual(self.call(f"/api/validacion/{r['id']}/decidir", dict(decision="APROBADO", motivo="Escuché el audio"))["final"], "APROBADO")
        self.assertEqual(self.call("/api/validaciones?estado=APROBADO")[0]["id"], r["id"])
        self.assertEqual(self.call("/api/resumen")["validaciones"]["por_revisar"], 0)
        self.assertEqual(self.call(f"/api/validacion/{r['id']}")["final"], "APROBADO")

    def test_8_login_por_rol(self):
        servidor.AUTH = A.Auth(); servidor.AUTH.agregar("SUPERVISOR", "60431749", "admin"); servidor.INTENTOS.clear()
        con = db.conectar(DB); filas = con.execute("SELECT id_asesor, nombre FROM asesor ORDER BY id_asesor LIMIT 2").fetchall(); con.close()
        (i1, n1), (i2, n2) = [(f[0], f[1]) for f in filas]
        def req(path, body=None, cookie=None):
            h = {"Content-Type": "application/json"}
            if cookie: h["Cookie"] = cookie
            rq = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
            try:
                r = urllib.request.urlopen(rq); return r.status, json.load(r), r.headers
            except urllib.error.HTTPError as e:
                return e.code, json.load(e), e.headers
        ck = lambda h: h["Set-Cookie"].split(";")[0]
        try:
            self.assertEqual(req("/api/dashboard")[0], 401)
            self.assertEqual(req("/api/login", dict(usuario="SUPERVISOR", clave="mal"))[0], 401)
            self.assertEqual(req("/api/login", dict(usuario=n1, clave="otra"))[0], 401)
            st, d, h = req("/api/login", dict(usuario="supervisor", clave="60431749")); self.assertEqual((st, d["rol"]), (200, "admin")); sup = ck(h)
            st, d, h = req("/api/login", dict(usuario=n1.lower(), clave=n1)); self.assertEqual((st, d["rol"], d["id_asesor"]), (200, "asesor", i1)); ase = ck(h)
            self.assertIn("HttpOnly", h["Set-Cookie"])
            self.assertEqual(req("/api/yo", cookie=ase)[1]["id_asesor"], i1)
            self.assertEqual(req("/api/dashboard", cookie=sup)[0], 200)
            for ruta in ("/api/dashboard", "/api/asesores", "/api/resumen", f"/api/asesor/{i2}"):
                self.assertEqual(req(ruta, cookie=ase)[0], 403, ruta)                      # el asesor no ve a otros ni al equipo
            self.assertEqual(req(f"/api/asesor/{i1}", cookie=ase)[0], 200)
            self.assertEqual(req("/api/dashboard", cookie=ase[:-3] + "xyz")[0], 401)
            st, v, _ = req("/api/validar", dict(id_asesor=i2, transcripcion=VENTAS[0]["transcripcion"], plantilla=VENTAS[0]["plantilla"]), cookie=ase)
            self.assertEqual((st, v["estado"]), (200, "APROBADO"))
            self.assertEqual(req(f"/api/validacion/{v['id']}", cookie=ase)[0], 200)
            self.assertEqual([x["id_asesor"] for x in req("/api/validaciones", cookie=ase)[1]], [i1])  # se guardó a su nombre, no al de id_asesor enviado
            st, v2, _ = req("/api/validar", dict(id_asesor=i2, transcripcion=VENTAS[1]["transcripcion"], plantilla=VENTAS[1]["plantilla"]), cookie=sup)
            self.assertEqual(req(f"/api/validacion/{v2['id']}", cookie=ase)[0], 404)         # venta ajena
            self.assertEqual(req(f"/api/validacion/{v['id']}/decidir", dict(decision="RECHAZADO"), cookie=ase)[0], 403)
            self.assertEqual(req("/healthz")[0], 200)
            for _ in range(8): req("/api/login", dict(usuario="x", clave="y"))
            self.assertEqual(req("/api/login", dict(usuario="SUPERVISOR", clave="60431749"))[0], 429)
        finally:
            servidor.AUTH = A.Auth(); servidor.INTENTOS.clear()

    def test_9_estaticos(self):
        for r, t in (("/", b"<html"), ("/app.js", b"function"), ("/app.css", b"--brand"), ("/manifest.webmanifest", b"WIN"), ("/transcripcion.js", b"unirCanales")):
            self.assertIn(t, urllib.request.urlopen(self.base + r).read(), r)
        self.assertEqual(urllib.request.urlopen(self.base + "/assets/logo.png").headers["Content-Type"], "image/png")


if __name__ == "__main__":
    unittest.main()
