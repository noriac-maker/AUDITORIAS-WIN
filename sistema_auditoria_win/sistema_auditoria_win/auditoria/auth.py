"""Autenticación simple por cookie firmada. Usuarios por variable de entorno:
AUDITORIA_USUARIOS="admin=Clave1|admin;maria=Clave2|auditor"   (rol: admin puede editar la pauta)
Sin usuarios y en localhost => sin login (desarrollo)."""
import base64, hashlib, hmac, json, os, secrets, time

ITER = 150_000


class Auth:
    def __init__(self, definicion="", secreto=None, ttl=12 * 3600):
        self.usuarios = {}
        for par in filter(None, (definicion or "").split(";")):
            if "=" not in par:
                continue
            u, resto = par.split("=", 1)
            clave, _, rol = resto.rpartition("|") if "|" in resto else (resto, "", "auditor")
            self.agregar(u.strip(), clave, rol.strip() or "auditor")
        self.secreto = (secreto or secrets.token_hex(32)).encode()
        self.ttl = ttl

    @property
    def activa(self):
        return bool(self.usuarios)

    def agregar(self, usuario, clave, rol="auditor"):
        sal = secrets.token_bytes(16)
        self.usuarios[usuario] = (sal, hashlib.pbkdf2_hmac("sha256", clave.encode(), sal, ITER), rol)

    def verificar(self, usuario, clave):
        d = self.usuarios.get(usuario)
        hh = hashlib.pbkdf2_hmac("sha256", (clave or "").encode(), d[0] if d else b"x" * 16, ITER)
        return bool(d) and hmac.compare_digest(hh, d[1])

    def token(self, usuario, rol=None, ida=None):
        cuerpo = base64.urlsafe_b64encode(json.dumps({"u": usuario, "r": rol or self.usuarios[usuario][2], "i": ida,
                                                      "e": int(time.time()) + self.ttl}).encode()).decode()
        return cuerpo + "." + hmac.new(self.secreto, cuerpo.encode(), hashlib.sha256).hexdigest()

    def leer(self, token):
        try:
            cuerpo, firma = token.rsplit(".", 1)
            if not hmac.compare_digest(firma, hmac.new(self.secreto, cuerpo.encode(), hashlib.sha256).hexdigest()):
                return None
            d = json.loads(base64.urlsafe_b64decode(cuerpo))
            ok = d["e"] > time.time() and (d["r"] == "asesor" or d["u"] in self.usuarios)
            return (d["u"], d["r"], d.get("i")) if ok else None
        except Exception:
            return None
