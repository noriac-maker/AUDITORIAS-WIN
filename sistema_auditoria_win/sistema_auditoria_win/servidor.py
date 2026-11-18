"""Servidor web del sistema (solo biblioteca estándar). Local:  python servidor.py   -> http://127.0.0.1:8000
Nube (Render, Railway, Fly…): variables  PORT, DB_PATH, AUDITORIA_USUARIOS, AUDITORIA_SECRET  (ver DESPLIEGUE.md)."""
import argparse, json, mimetypes, os, re, secrets, shutil, tempfile, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from auditoria import asr, auth as A, config as C, db, motor, pauta as P, servicio

AQUI = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(AQUI, "web")
DB = os.environ.get("DB_PATH", os.path.join(AQUI, "auditorias.db"))
SEED = os.path.join(AQUI, "datos", "auditorias_seed.db")
AUTH = A.Auth()
INTENTOS = {}


class Error(Exception):
    def __init__(self, msg, codigo=400):
        super().__init__(msg)
        self.codigo = codigo


def meta():
    return dict(criterios=C.CRITERIOS, valores=list(C.VALORES), pilares=C.PILARES,
                umbrales=dict(deficiente=C.UMBRAL_DEFICIENTE, excelente=C.UMBRAL_EXCELENTE, margen=C.MARGEN_RIESGO,
                              tau=C.TAU_CONFIANZA), asr=asr.disponible())


class Handler(BaseHTTPRequestHandler):
    server_version = "AuditoriaWIN/2.0"

    def log_message(self, fmt, *a):
        pass

    def _json(self, obj, codigo=200, headers=None):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self._seguridad()
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def _seguridad(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")

    def _cuerpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 60 * 1024 * 1024:
            raise Error("Archivo demasiado grande (máx. 60 MB)", 413)
        return self.rfile.read(n) if n else b""

    def _body_json(self):
        raw = self._cuerpo()
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            raise Error("JSON inválido")

    def _sesion(self):
        """(usuario, rol) o None. Sin autenticación configurada => usuario local con rol admin."""
        if not AUTH.activa:
            return ("local", "admin", None)
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == "sess":
                return AUTH.leer(v)
        return None

    def _ip(self):
        return (self.headers.get("X-Forwarded-For") or self.client_address[0]).split(",")[0].strip()

    def _despachar(self, metodo):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        ruta = u.path
        if metodo == "GET" and ruta == "/healthz":
            return self._json({"ok": True})
        if metodo == "GET" and not ruta.startswith("/api/"):
            return self._estatico(ruta)
        con = db.conectar(DB)
        try:
            res = self._api(metodo, ruta, q, con)
            if isinstance(res, tuple):
                self._json(res[0], 200, res[1])
            else:
                self._json(res)
        except Error as e:
            self._json({"error": str(e)}, e.codigo)
        except ValueError as e:
            self._json({"error": str(e)}, 400)
        except Exception as e:  # noqa
            self._json({"error": f"Error interno: {e}"}, 500)
        finally:
            con.close()

    def do_GET(self):
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def _estatico(self, ruta):
        ruta = "/index.html" if ruta in ("/", "") else ruta
        f = os.path.normpath(os.path.join(WEB, ruta.lstrip("/")))
        if not f.startswith(WEB) or not os.path.isfile(f):
            return self._json({"error": "No encontrado"}, 404)
        with open(f, "rb") as fh:
            b = fh.read()
        self.send_response(200)
        tipo = mimetypes.guess_type(f)[0] or "text/plain"
        if f.endswith(".webmanifest"):
            tipo = "application/manifest+json"
        self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith(("text", "application/j")) else ""))
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "public, max-age=3600" if "/assets/" in ruta else "no-cache")
        self._seguridad()
        self.end_headers()
        self.wfile.write(b)

    # ---- API
    def _api(self, m, ruta, q, con):
        # --- sesión
        if ruta == "/api/login" and m == "POST":
            ip, ahora = self._ip(), time.time()
            hist = [t for t in INTENTOS.get(ip, []) if ahora - t < 300]
            if len(hist) >= 8:
                raise Error("Demasiados intentos. Espera 5 minutos.", 429)
            b = self._body_json(); u, clave = (b.get("usuario") or "").strip(), (b.get("clave") or "").strip()
            sup = next((x for x in (u, u.upper()) if x in AUTH.usuarios and AUTH.verificar(x, clave)), None)
            ase = None if sup else con.execute("SELECT id_asesor, nombre FROM asesor WHERE UPPER(nombre)=?", (u.upper(),)).fetchone()
            if ase and not secrets.compare_digest(clave.upper().encode(), ase["nombre"].upper().encode()):
                ase = None
            if not (sup or ase):
                INTENTOS[ip] = hist + [ahora]
                raise Error("Usuario o clave incorrectos", 401)
            usr, rol, ida = (sup, AUTH.usuarios[sup][2], None) if sup else (ase["nombre"], "asesor", ase["id_asesor"])
            seguro = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
            return ({"usuario": usr, "rol": rol, "id_asesor": ida},
                    {"Set-Cookie": f"sess={AUTH.token(usr, rol, ida)}; HttpOnly; SameSite=Lax; Path=/; Max-Age={AUTH.ttl}{seguro}"})
        if ruta == "/api/logout" and m == "POST":
            return ({"ok": True}, {"Set-Cookie": "sess=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"})
        ses = self._sesion()
        if ruta == "/api/yo":
            return dict(auth=AUTH.activa, usuario=ses[0] if ses else None, rol=ses[1] if ses else None, id_asesor=ses[2] if ses else None)
        if not ses:
            raise Error("Inicia sesión para continuar", 401)
        usuario, rol, mi_id = ses
        if rol == "asesor":    # el asesor solo ve su espacio
            permitido = ruta in ("/api/meta", "/api/validar", "/api/pauta", "/api/ejemplos-ventas") or ruta in (f"/api/asesor/{mi_id}", "/api/validaciones") \
                or re.fullmatch(r"/api/validacion/\d+", ruta)
            if not permitido:
                raise Error("No tienes acceso a esta sección", 403)
            if ruta == "/api/validaciones":
                q["asesor"] = str(mi_id)
            if ruta == "/api/pauta" and m != "GET":
                raise Error("No tienes acceso a esta sección", 403)
        if ruta in ("/api/validar", "/api/validaciones") or ruta.startswith("/api/validacion/"):
            if m == "POST" and ruta == "/api/validar":
                b = self._body_json()
                return servicio.validar(con, mi_id if rol == "asesor" else int(b.get("id_asesor") or 0), b.get("transcripcion"), b.get("plantilla"))
            mo = re.fullmatch(r"/api/validacion/(\d+)/decidir", ruta)
            if mo and m == "POST":
                if rol != "admin":
                    raise Error("Solo el supervisor puede decidir", 403)
                b = self._body_json()
                return servicio.decidir(con, int(mo.group(1)), b.get("decision"), usuario, b.get("motivo", ""))
            mo = re.fullmatch(r"/api/validacion/(\d+)", ruta)
            if mo and m == "GET":
                d = servicio.validacion(con, int(mo.group(1)))
                if not d or (rol == "asesor" and d["id_asesor"] != mi_id):
                    raise Error("Venta no encontrada", 404)
                return d
            if ruta == "/api/validaciones" and m == "GET":
                return servicio.validaciones(con, int(q["asesor"]) if q.get("asesor") else None, q.get("estado"))
        if ruta == "/api/ejemplos-ventas":
            with open(os.path.join(AQUI, "ejemplos", "ventas_demo.json"), encoding="utf-8") as fh:
                return json.load(fh)

        if m == "GET":
            if ruta == "/api/meta":
                return dict(meta(), filtros=servicio.filtros(con))
            if ruta == "/api/resumen":
                return servicio.resumen(con)
            if ruta == "/api/dashboard":
                return servicio.dashboard(con, q)
            if ruta == "/api/asesores":
                return servicio.asesores(con, q)
            if ruta == "/api/pauta":
                return dict(clausulas=servicio.pauta_listar(con), ejemplo=servicio.resumen(con)["pauta_ejemplo"])
            if ruta == "/api/auditorias":
                return servicio.listar(con, dict(q, ventas=q.get("ventas", "0")), q.get("estado"), q.get("q"),
                                       min(int(q.get("limite", 50)), 200), int(q.get("desplazamiento", 0)))
            if ruta == "/api/cola":
                return servicio.cola(con)
            if ruta == "/api/ejemplos":
                with open(os.path.join(AQUI, "ejemplos", "transcripciones_demo.json"), encoding="utf-8") as fh:
                    return [{k: v for k, v in e.items() if k != "gold"} for e in json.load(fh)]
            mo = re.fullmatch(r"/api/asesor/(\d+)", ruta)
            if mo:
                d = servicio.perfil_asesor(con, int(mo.group(1)))
                if not d:
                    raise Error("Asesor no encontrado", 404)
                return d
            mo = re.fullmatch(r"/api/auditoria/(\d+)", ruta)
            if mo:
                d = servicio.detalle(con, int(mo.group(1)))
                if not d:
                    raise Error("Auditoría no encontrada", 404)
                return d
            raise Error("Ruta no encontrada", 404)
        # --- POST
        if ruta == "/api/auditar":
            b = self._body_json()
            if not (b.get("transcripcion") or "").strip():
                raise Error("Pega o carga la transcripción de la llamada")
            return servicio.auditar(b["transcripcion"], b.get("es_venta"), b.get("datos_sistema"), b.get("regla", "vigente"),
                                    servicio.pauta_listar(con, True))
        if ruta == "/api/auditoria":
            b = self._body_json()
            res = servicio.auditar(b.get("transcripcion", ""), b.get("es_venta"), b.get("datos_sistema"), b.get("regla", "vigente"),
                                   servicio.pauta_listar(con, True))
            ida = servicio.registrar(con, res, b["transcripcion"], b.get("contexto"), b.get("motor_asr"))
            return dict(id_auditoria=ida, ruta=res["ruta"])
        mo = re.fullmatch(r"/api/auditoria/(\d+)/revisar", ruta)
        if mo:
            b = self._body_json()
            return servicio.revisar(con, int(mo.group(1)), b.get("valores", {}), usuario if AUTH.activa else (b.get("usuario") or usuario),
                                    b.get("motivo", ""), b.get("regla"))
        if ruta == "/api/calcular":
            b = self._body_json()
            return motor.calcular({int(k): v for k, v in b["valores"].items()}, b.get("regla", "vigente"))
        if ruta == "/api/pauta":
            if rol != "admin":
                raise Error("Solo un administrador puede editar la pauta", 403)
            servicio.pauta_guardar(con, self._body_json().get("clausulas"))
            return dict(clausulas=servicio.pauta_listar(con), ejemplo=False)
        if ruta == "/api/pauta/probar":
            b = self._body_json()
            if not (b.get("transcripcion") or "").strip():
                raise Error("Pega una transcripción para probar la pauta")
            return P.evaluar(b.get("clausulas") or servicio.pauta_listar(con, True), b["transcripcion"])
        if ruta == "/api/pauta/importar":
            c = P.desde_texto(self._body_json().get("texto"))
            if not c:
                raise Error("No se encontraron cláusulas: pega una por línea (mínimo 3 palabras)")
            return dict(clausulas=c)
        if ruta == "/api/transcribir":
            if not asr.disponible():
                raise Error("Este servidor no tiene transcripción. Usa la transcripción del navegador o pega el texto.", 501)
            ext = os.path.splitext(self.headers.get("X-Filename", "audio.wav"))[1] or ".wav"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as t:
                t.write(self._cuerpo())
            try:
                return dict(texto=asr.transcribir(t.name), motor="faster-whisper")
            finally:
                os.unlink(t.name)
        raise Error("Ruta no encontrada", 404)


def preparar_db(ruta):
    os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
    if not os.path.exists(ruta):
        if os.path.exists(SEED):
            shutil.copy(SEED, ruta)
        else:
            import cargar_datos
            cargar_datos.cargar(ruta_db=ruta)
    con = db.conectar(ruta); db.inicializar(con); con.close()


def main():
    global DB, AUTH
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 8000)))
    ap.add_argument("--db", default=DB)
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    a = ap.parse_args()
    DB = a.db
    AUTH = A.Auth(os.environ.get("AUDITORIA_USUARIOS", ""), os.environ.get("AUDITORIA_SECRET"))
    if "SUPERVISOR" not in AUTH.usuarios:      # acceso del supervisor: usuario SUPERVISOR y su DNI como clave (cámbiala con AUDITORIA_CLAVE_SUPERVISOR)
        AUTH.agregar("SUPERVISOR", os.environ.get("AUDITORIA_CLAVE_SUPERVISOR", "60431749"), "admin")
    preparar_db(DB)
    srv = ThreadingHTTPServer((a.host, a.puerto), Handler)
    print(f"Sistema listo en http://{a.host}:{a.puerto}  ·  login: {'activo' if AUTH.activa else 'desactivado (local)'}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
