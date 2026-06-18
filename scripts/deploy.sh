#!/bin/sh
# Script de despliegue/actualización en producción (Alpine Linux + OpenRC + Gunicorn).
# Descarga los últimos cambios de GitHub, instala dependencias nuevas si las hubiera,
# aplica migraciones pendientes, recolecta estáticos y reinicia el servicio web.
#
# Pensado para ejecutarse tras scripts/install.sh + scripts/setup_service.sh,
# cada vez que haya que llevar a producción los cambios subidos a la rama principal.
#
# Uso:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
#
# Variables de entorno opcionales:
#   APP_DIR       Ruta del proyecto (por defecto: directorio del propio script, un nivel arriba)
#   VENV_DIR      Ruta del virtualenv (por defecto: $APP_DIR/venv)
#   GIT_REMOTE    Remoto a usar (por defecto: origin)
#   GIT_BRANCH    Rama a desplegar (por defecto: main)
#   SERVICE_NAME  Nombre del servicio OpenRC a reiniciar (por defecto: crmgestora)
#   SKIP_RESTART  "yes" para no reiniciar el servicio al final (por defecto: no)

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SERVICE_NAME="${SERVICE_NAME:-crmgestora}"
SKIP_RESTART="${SKIP_RESTART:-no}"

log()  { printf '\033[1;32m[deploy]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[deploy]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[deploy]\033[0m %s\n' "$1" >&2; exit 1; }

[ -d "$APP_DIR/.git" ] || die "No hay un repositorio git en $APP_DIR. Clónalo con 'git clone' antes de desplegar."
[ -d "$VENV_DIR" ] || die "No existe el virtualenv en $VENV_DIR. Ejecuta antes scripts/install.sh."

cd "$APP_DIR"

# 1. Comprobar que no hay cambios locales sin commitear que el pull pudiera pisar.
if [ -n "$(git status --porcelain)" ]; then
    die "Hay cambios locales sin commitear en $APP_DIR. Resuélvelos (commit/stash) antes de desplegar para no perder trabajo."
fi

# 2. Descargar y aplicar los últimos cambios (fast-forward únicamente, nunca reescribe historia local)
log "Descargando cambios de $GIT_REMOTE/$GIT_BRANCH..."
BEFORE_REV="$(git rev-parse HEAD)"
git fetch "$GIT_REMOTE" "$GIT_BRANCH"
git checkout "$GIT_BRANCH"
git merge --ff-only "$GIT_REMOTE/$GIT_BRANCH"
AFTER_REV="$(git rev-parse HEAD)"

if [ "$BEFORE_REV" = "$AFTER_REV" ]; then
    log "Ya estaba actualizado (sin cambios nuevos en $GIT_REMOTE/$GIT_BRANCH)."
else
    log "Actualizado: $BEFORE_REV -> $AFTER_REV"
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

# 3. Reinstalar dependencias solo si requirements.txt cambió en este despliegue
if [ "$BEFORE_REV" != "$AFTER_REV" ] && git diff --name-only "$BEFORE_REV" "$AFTER_REV" | grep -q '^requirements.txt$'; then
    log "requirements.txt ha cambiado, actualizando dependencias..."
    pip install --upgrade pip wheel
    pip install -r requirements.txt
else
    log "Sin cambios en requirements.txt, se omite reinstalación de dependencias."
fi

# 4. Migraciones de base de datos (idempotente: no hace nada si ya están aplicadas)
log "Aplicando migraciones pendientes..."
python manage.py migrate --noinput

# 5. Estáticos
log "Recolectando ficheros estáticos..."
python manage.py collectstatic --noinput

deactivate

# 6. Reiniciar el servicio web para servir los cambios
if [ "$SKIP_RESTART" = "yes" ]; then
    warn "SKIP_RESTART=yes, no se reinicia el servicio. Recuerda reiniciarlo manualmente."
else
    if command -v rc-service >/dev/null 2>&1 && [ -f "/etc/init.d/$SERVICE_NAME" ]; then
        log "Reiniciando servicio '$SERVICE_NAME'..."
        if [ "$(id -u)" -eq 0 ]; then
            rc-service "$SERVICE_NAME" restart
        else
            sudo rc-service "$SERVICE_NAME" restart
        fi
        log "Servicio reiniciado."
    else
        warn "No se encontró el servicio OpenRC '$SERVICE_NAME' (¿ejecutaste scripts/setup_service.sh?). No se reinicia nada automáticamente."
    fi
fi

log "Despliegue completado."
