# Publicar el sistema con una URL (GitHub → Render)

Resultado: entras desde cualquier celular o PC a `https://auditoria-win.onrender.com` (o tu dominio), con usuario y clave,
sin abrir código ni ejecutar nada. Cada vez que subes cambios a GitHub, se actualiza solo.

## 1. Subir el código a GitHub (una sola vez)
1. En github.com → **New repository** → nombre `auditoria-win` → **Private** (recomendado) → Create.
2. En la carpeta del proyecto:
```
git init
git add .
git commit -m "Sistema de auditoría WIN"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/auditoria-win.git
git push -u origin main
```
GitHub Actions ejecutará las 19 pruebas automáticamente en cada push (pestaña **Actions**).

## 2. Publicar en Render (gratis para probar)
1. Entra a render.com → **New → Blueprint** → conecta tu cuenta de GitHub → elige `auditoria-win`.
2. Render lee `render.yaml`. Te pedirá `AUDITORIA_USUARIOS`; escribe por ejemplo:
   `admin=UnaClaveLarga|admin;maria=OtraClave|auditor`  (rol **admin** puede editar la pauta; **auditor** revisa).
3. **Apply**. En 2–3 minutos tendrás la URL. Compártela con tu equipo.
4. En el celular: abre la URL → menú del navegador → **Añadir a pantalla de inicio**: se instala como app con el logo de WIN.

## 3. Importante antes de vender
- **Persistencia:** en el plan gratis el disco se borra al redesplegar y el servicio «duerme» tras 15 min sin uso (el primer acceso tarda ~30 s).
  Para producción usa el plan **Starter** y activa el bloque `disk` de `render.yaml` (así las auditorías nuevas se conservan).
  Para muchos usuarios simultáneos o historial grande, el siguiente paso es migrar SQLite a PostgreSQL.
- **Privacidad (Ley 29733):** mantén el repositorio **privado** y no subas audios ni datos reales de clientes a GitHub.
  Los audios se transcriben en el navegador del usuario y no se envían al servidor.
- **Seguridad:** HTTPS lo pone Render. Cambia las claves de `AUDITORIA_USUARIOS` cuando alguien deje el equipo.
- **Transcripción de audio:** el navegador descarga la librería (jsDelivr) y el modelo Whisper (Hugging Face) la primera vez: necesita internet.
  En celulares antiguos usa la calidad «Rápida».

## Otras plataformas
El `Dockerfile` funciona igual en Railway, Fly.io, Koyeb o un VPS: define `AUDITORIA_USUARIOS`, `AUDITORIA_SECRET` y monta un volumen en `/data`.
