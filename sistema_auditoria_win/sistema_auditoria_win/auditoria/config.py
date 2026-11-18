"""Configuración central: criterios, pilares, pesos, umbrales y supuestos.
Todo el sistema lee de aquí; si la ficha de monitoreo cambia, se cambia solo este archivo."""

VALORES = ("SI", "NO", "No Aplica", "Sin contacto")
REVISAR = "REVISAR"          # valor provisional del bot cuando no halla evidencia

# (id, clave, nombre, pilar_ficha, columna en la base procesada, solo_venta)
_CRITERIOS = [
    (1,  "saludo",        "Saludo amigable-cercano",             "IMPACTA",   "Saludo amigable-cercano", False),
    (2,  "cobertura",     "Validación comercial y cobertura",    "IMPACTA",   "Validación comercial y cobertura", False),
    (3,  "actitud",       "Actitud comercial",                   "IMPACTA",   "Actitud Comercial", False),
    (4,  "sondeo",        "Preguntas de sondeo",                 "DESCUBRE",  "Preguntas de Sondeo", False),
    (5,  "escucha",       "Escucha activa",                      "DESCUBRE",  "Escucha activa", False),
    (6,  "beneficios",    "Beneficios WIN (imagina que…)",       "DESCUBRE",  "Beneficios WIN (imagina que …)", False),
    (7,  "alternativa",   "Ofrece la mejor alternativa",         "DESCUBRE",  "Ofrece la mejor alternativa", False),
    (8,  "objeciones",    "Indagación y manejo de objeciones",   "SOLUCIONA", "Indagación y Manejo de Objeciones", False),
    (9,  "aseguramiento", "Aseguramiento",                       "SOLUCIONA", "Aseguramiento", False),
    (10, "informacion",   "Información correcta o completa",     "SOLUCIONA", "Información correcta o completa", False),
    (11, "cierre",        "Dirige al cierre",                    "CONSOLIDA", "Dirige al Cierre", False),
    (12, "prevalidacion", "Pre validación de datos del titular", "CONSOLIDA", "Pre validación de datos de titular", True),
    (13, "inconcert",     "Registro en Inconcert",               "CONSOLIDA", "Registro en Inconcert", True),
    (14, "portabilidad",  "Registro correcto de portabilidad",   "CONSOLIDA", "Registro correcto de portabilidad (WinForce / CRM Experiencia)", False),
    (15, "despedida",     "Despedida cordial",                   "CONSOLIDA", "Despedida cordial", True),
]
CRITERIOS = [dict(id=i, clave=k, nombre=n, pilar=p, columna=c, solo_venta=s) for i, k, n, p, c, s in _CRITERIOS]
POR_ID = {c["id"]: c for c in CRITERIOS}

# pilar de la ficha -> (nombre del modelo, peso)
PILARES = {
    "IMPACTA":   {"modelo": "Conquistar", "peso": 0.20, "id": 1},
    "DESCUBRE":  {"modelo": "Conocer",    "peso": 0.20, "id": 2},
    "SOLUCIONA": {"modelo": "Convencer",  "peso": 0.35, "id": 3},
    "CONSOLIDA": {"modelo": "Concretar",  "peso": 0.25, "id": 4},
}
UMBRAL_DEFICIENTE = 70.0     # < 70
UMBRAL_EXCELENTE = 85.0      # >= 85
MARGEN_RIESGO = 5.0          # nota a menos de 5 pts de un umbral => revisión humana
TAU_CONFIANZA = 0.60         # confianza mínima del criterio más dudoso

# Supuestos económicos del informe (Tabla 24). Se reemplazan con mediciones del piloto.
MIN_AUDITORIA_MANUAL = 14.89
MIN_VALIDACION = 2.54
COSTO_MIN_AUDITOR = 0.3346   # S/ por minuto

def nivel_de(nota):
    if nota is None:
        return None
    return "Deficiente" if nota < UMBRAL_DEFICIENTE else ("Aceptable" if nota < UMBRAL_EXCELENTE else "Excelente")
