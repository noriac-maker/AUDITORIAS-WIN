# Auditoría de calidad en llamadas de venta · WIN

Sistema semiautomático (CRISP-DM): lee la llamada (audio o transcripción), **prellena los 15 criterios con evidencia**,
verifica la **pauta de contrato**, calcula la nota con **reglas deterministas**, **deriva al auditor** los casos dudosos o de riesgo
y guarda todo con trazabilidad. Funciona en PC y celular.

## Pantallas
Login → **Asesores** (lista) → perfil del asesor (historial y auditorías) · **Menú principal** con accesos a: Dashboard, Nueva auditoría
(audio o texto), Cola de revisión, Auditorías, Pauta de contrato y Reglas y estado.

## Ejecutar en local
```
python servidor.py        # http://127.0.0.1:8000  (sin login en local)
python -m unittest discover -s tests -v
```
## Publicar con una URL desde GitHub
Ver **DESPLIEGUE.md** (GitHub + Render, `Dockerfile` y `render.yaml` incluidos). Usuarios: variable `AUDITORIA_USUARIOS`.

## Estructura
| Ruta | Qué hace |
|---|---|
| `auditoria/config.py` | 15 criterios, pilares, pesos, umbrales (único lugar a editar si cambia la ficha) |
| `auditoria/motor.py` | Motor de reglas (validado 600/600 contra el Excel) |
| `auditoria/extractor.py` | Propone cada criterio + evidencia + confianza, o REVISAR |
| `auditoria/pauta.py` | Compara la lectura del contrato con la pauta (cumple / parcial / no cumple) |
| `auditoria/servicio.py` | auditar → registrar → revisar → asesores, perfil, dashboard |
| `auditoria/auth.py` | Login por cookie firmada, roles admin/auditor |
| `auditoria/evaluacion.py` | Mide el extractor contra evaluaciones humanas (F1, Kappa, MAE, Recall de Deficiente) |
| `servidor.py` · `web/` | API + aplicación (app.js, app.css, worker de transcripción) |
| `datos/` | Excel de origen y base semilla `auditorias_seed.db` |

## Qué está validado y qué no
- ✅ Motor de reglas = Excel (600/600). Base, historial, login/roles, pauta (mecánica), asesores y perfil: 19 pruebas automáticas.
- ⚠️ **Sin validar con llamadas reales:** el extractor y la comparación con la pauta. Las conversaciones de ejemplo las escribió el equipo.
- ⚠️ La pauta incluida es un **ejemplo**: reemplazarla por la real (Pauta de contrato → Importar desde texto).
- ⚠️ La transcripción en el navegador (Whisper) se implementó pero **no pudo probarse con un audio real** en el entorno de desarrollo (sin internet).
- Registro en Inconcert y portabilidad vienen del CRM, no del audio: sin ese dato el bot deja REVISAR.
