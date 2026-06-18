#!/bin/sh
# Script de instalación del CRM Gestora de Fondos en un servidor Alpine Linux (vía SSH).
# Crea un virtualenv aislado, instala dependencias del sistema y de Python,
# configura el .env, aplica migraciones y (opcionalmente) carga datos demo.
#
# Uso:
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# Variables de entorno opcionales para personalizar la instalación:
#   APP_DIR     Ruta del proyecto (por defecto: directorio del propio script, un nivel arriba)
#   VENV_DIR    Ruta del virtualenv (por defecto: $APP_DIR/venv)
#   PYTHON_BIN  Binario de Python a usar (por defecto: python3)
#   SEED_DEMO   "yes"/"no" — cargar datos demo tras migrar (por defecto: pregunta de forma interactiva)

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

log()  { printf '\033[1;32m[install]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[install]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[install]\033[0m %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Este script necesita privilegios de root (apk add). Ejecuta con sudo/doas o como root."

log "Proyecto: $APP_DIR"
cd "$APP_DIR"

# 1. Dependencias del sistema (Alpine usa apk + musl, mysqlclient necesita compilar contra MariaDB)
log "Instalando dependencias del sistema con apk..."
apk update
apk add --no-cache \
    python3 \
    py3-pip \
    py3-virtualenv \
    gcc \
    musl-dev \
    python3-dev \
    mariadb-dev \
    mariadb-connector-c-dev \
    pkgconfig \
    build-base \
    git

# 2. Virtualenv
if [ ! -d "$VENV_DIR" ]; then
    log "Creando virtualenv en $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
else
    log "Virtualenv ya existe en $VENV_DIR, se reutiliza."
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

log "Actualizando pip e instalando dependencias de Python (requirements.txt)..."
pip install --upgrade pip wheel
pip install -r requirements.txt

# 3. Fichero .env
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.example" ]; then
        cp "$APP_DIR/.env.example" "$APP_DIR/.env"
        warn ".env creado a partir de .env.example. EDITA $APP_DIR/.env con las credenciales reales (DB, SECRET_KEY, ALLOWED_HOSTS) antes de continuar en producción."
    else
        die "No existe .env ni .env.example. Crea $APP_DIR/.env manualmente antes de continuar."
    fi
else
    log ".env ya existe, no se sobrescribe."
fi

# 4. Migraciones
log "Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# 5. Estáticos
log "Recolectando ficheros estáticos..."
python manage.py collectstatic --noinput

# 6. Datos demo (opcional)
SEED_DEMO="${SEED_DEMO:-}"
if [ -z "$SEED_DEMO" ]; then
    printf '¿Cargar datos demo (participadas/inversores/usuarios de ejemplo)? [y/N] '
    read -r ans
    case "$ans" in
        [yY]*) SEED_DEMO="yes" ;;
        *) SEED_DEMO="no" ;;
    esac
fi
if [ "$SEED_DEMO" = "yes" ]; then
    log "Cargando datos demo..."
    python manage.py seed_demo_data
fi

deactivate

log "Instalación completada."
log "Para arrancar manualmente en modo desarrollo:"
log "  cd $APP_DIR && . venv/bin/activate && python manage.py runserver 0.0.0.0:8000"
log ""
log "Para producción con Gunicorn + servicio OpenRC, ejecuta además:"
log "  $SCRIPT_DIR/setup_service.sh"
