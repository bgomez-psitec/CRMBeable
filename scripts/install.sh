#!/bin/sh
# =============================================================================
#  CRM Gestora de Fondos — Script de instalación para Alpine Linux 3.23
# =============================================================================
#
# Qué hace este script:
#   1. Instala las dependencias del sistema necesarias (apk)
#   2. Crea un virtualenv aislado para este proyecto (no interfiere con otros)
#   3. Instala las dependencias Python (requirements.txt)
#   4. Pregunta de forma interactiva los datos de conexión a la BD y genera .env
#   5. Valida la conexión a MySQL/MariaDB antes de continuar
#   6. Aplica migraciones y recolecta estáticos
#   7. (Opcional) Carga datos demo
#
# Uso:
#   chmod +x scripts/install.sh
#   sudo ./scripts/install.sh
#
# Variables de entorno para instalación desatendida (CI/CD):
#   APP_DIR      Ruta del proyecto     (por defecto: un nivel arriba del script)
#   VENV_DIR     Ruta del virtualenv   (por defecto: $APP_DIR/venv)
#   PYTHON_BIN   Binario de Python     (por defecto: python3)
#   SEED_DEMO    yes/no                (por defecto: pregunta interactiva)
#
#   Variables de BD para modo no-interactivo:
#   DB_NAME / DB_USER / DB_PASSWORD / DB_HOST / DB_PORT
#   ALLOWED_HOSTS / SECRET_KEY

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# ── Colores ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
RESET='\033[0m'

log()     { printf "${GREEN}[✔]${RESET} %s\n" "$1"; }
info()    { printf "${CYAN}[→]${RESET} %s\n" "$1"; }
warn()    { printf "${YELLOW}[!]${RESET} %s\n" "$1"; }
die()     { printf "${RED}[✘]${RESET} %s\n" "$1" >&2; exit 1; }
header()  { printf "\n${BOLD}${CYAN}━━━  %s  ━━━${RESET}\n" "$1"; }
ask()     { printf "${BOLD}%s${RESET}" "$1"; }

# ── Comprobaciones previas ────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "Este script necesita privilegios de root. Ejecútalo con: sudo $0"
[ -f "$APP_DIR/manage.py" ]      || die "No se encontró manage.py en $APP_DIR. ¿Es la ruta correcta?"
[ -f "$APP_DIR/requirements.txt" ] || die "No se encontró requirements.txt en $APP_DIR."

# ── Banner ────────────────────────────────────────────────────────────────────
printf "\n"
printf "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${RESET}\n"
printf "${BOLD}${CYAN}║   CRM Gestora de Fondos — Instalación        ║${RESET}\n"
printf "${BOLD}${CYAN}║   Alpine Linux 3.23 · Django + MySQL          ║${RESET}\n"
printf "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${RESET}\n\n"
info "Directorio del proyecto : $APP_DIR"
info "Directorio del virtualenv: $VENV_DIR"

# =============================================================================
#  PASO 1 — Dependencias del sistema
# =============================================================================
header "PASO 1 — Dependencias del sistema"

info "Actualizando índice de paquetes (apk update)..."
apk update -q

info "Instalando paquetes necesarios..."
apk add --no-cache -q \
    python3 \
    py3-pip \
    py3-virtualenv \
    gcc \
    musl-dev \
    python3-dev \
    mariadb-dev \
    mariadb-connector-c-dev \
    pkgconf \
    build-base \
    git \
    curl

log "Dependencias del sistema instaladas."
info "Python: $("$PYTHON_BIN" --version 2>&1)"

# =============================================================================
#  PASO 2 — Virtualenv aislado
# =============================================================================
header "PASO 2 — Entorno virtual Python (venv)"

if [ -d "$VENV_DIR" ]; then
    warn "Ya existe un virtualenv en $VENV_DIR — se reutiliza."
    warn "Si quieres uno limpio, bórralo primero: rm -rf $VENV_DIR"
else
    info "Creando virtualenv en $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    log "Virtualenv creado."
fi

# Activar venv
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

info "Actualizando pip y wheel..."
pip install --upgrade pip wheel --quiet
info "Instalando dependencias Python (requirements.txt)..."
pip install -r "$APP_DIR/requirements.txt" --quiet
log "Dependencias Python instaladas."
log "Paquetes principales:"
pip show django mysqlclient gunicorn 2>/dev/null | grep -E "^Name:|^Version:" | awk '{print "    " $0}'

# =============================================================================
#  PASO 3 — Configuración de la base de datos y .env
# =============================================================================
header "PASO 3 — Configuración de la base de datos"

ENV_FILE="$APP_DIR/.env"
CONFIGURE_DB=true

if [ -f "$ENV_FILE" ]; then
    warn "Ya existe un fichero .env en $ENV_FILE"
    ask "  ¿Quieres reconfigurarlo con nuevos datos de BD? [s/N] "
    read -r resp
    case "$resp" in
        [sS]*) CONFIGURE_DB=true  ;;
        *)     CONFIGURE_DB=false ;;
    esac
fi

if [ "$CONFIGURE_DB" = "true" ]; then
    printf "\n"
    info "Introduce los datos de conexión a MySQL/MariaDB para este proyecto."
    info "Puedes pulsar Enter para aceptar el valor por defecto entre corchetes.\n"

    # DB_HOST
    ask "  Host de la BD [127.0.0.1]: "
    read -r _db_host
    DB_HOST="${_db_host:-${DB_HOST:-127.0.0.1}}"

    # DB_PORT
    ask "  Puerto de la BD [3306]: "
    read -r _db_port
    DB_PORT="${_db_port:-${DB_PORT:-3306}}"

    # DB_NAME
    ask "  Nombre de la base de datos [crmgestora]: "
    read -r _db_name
    DB_NAME="${_db_name:-${DB_NAME:-crmgestora}}"

    # DB_USER
    ask "  Usuario de la BD [crmgestora]: "
    read -r _db_user
    DB_USER="${_db_user:-${DB_USER:-crmgestora}}"

    # DB_PASSWORD (sin eco)
    ask "  Contraseña de la BD: "
    stty -echo 2>/dev/null || true
    read -r DB_PASSWORD
    stty echo 2>/dev/null || true
    printf "\n"

    # ALLOWED_HOSTS
    ask "  ALLOWED_HOSTS (IP/dominio del servidor, separados por coma) [localhost,127.0.0.1]: "
    read -r _hosts
    ALLOWED_HOSTS="${_hosts:-${ALLOWED_HOSTS:-localhost,127.0.0.1}}"

    # SECRET_KEY — generar una aleatoria
    SECRET_KEY="$(python3 -c "import secrets, string; \
        chars = string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)'; \
        print(''.join(secrets.choice(chars) for _ in range(60)))")"

    info "Escribiendo $ENV_FILE..."
    cat > "$ENV_FILE" <<ENVEOF
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${ALLOWED_HOSTS}

DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}

# Microsoft Graph (Outlook) - integración futura
MS_GRAPH_CLIENT_ID=
MS_GRAPH_CLIENT_SECRET=
MS_GRAPH_TENANT_ID=

# Auth0 - integración futura
AUTH0_DOMAIN=
AUTH0_CLIENT_ID=
AUTH0_CLIENT_SECRET=
ENVEOF
    chmod 600 "$ENV_FILE"
    log ".env generado (permisos 600 — solo lectura para root)."

    # ── Validar conexión antes de continuar ───────────────────────────────────
    printf "\n"
    info "Validando conexión a la base de datos..."
    cd "$APP_DIR"

    DB_CHECK=$(python3 -c "
import sys
try:
    import MySQLdb
    conn = MySQLdb.connect(
        host='${DB_HOST}', port=${DB_PORT},
        user='${DB_USER}', password='${DB_PASSWORD}',
        db='${DB_NAME}', charset='utf8mb4', connect_timeout=5
    )
    conn.close()
    print('OK')
except Exception as e:
    print('ERROR: ' + str(e))
    sys.exit(1)
" 2>&1 || true)

    if [ "$DB_CHECK" = "OK" ]; then
        log "Conexión a la BD exitosa (${DB_HOST}:${DB_PORT}/${DB_NAME})."
    else
        printf "${RED}"
        printf "\n  ✘ No se pudo conectar a la base de datos:\n"
        printf "    %s\n" "$DB_CHECK"
        printf "${RESET}\n"
        warn "Revisa los datos introducidos. El fichero .env ha sido creado"
        warn "pero puede contener credenciales incorrectas."
        warn "Corrígelo manualmente en: $ENV_FILE"
        warn "y luego continúa con:  cd $APP_DIR && ./scripts/install.sh"
        exit 1
    fi
else
    log ".env existente — se mantiene sin cambios."
    cd "$APP_DIR"
    # Leer variables del .env existente para el resto del script
    # shellcheck disable=SC1090
    . "$ENV_FILE" 2>/dev/null || true
fi

# =============================================================================
#  PASO 4 — Migraciones
# =============================================================================
header "PASO 4 — Migraciones de base de datos"

cd "$APP_DIR"
info "Aplicando migraciones..."
python manage.py migrate --noinput
log "Migraciones aplicadas."

# =============================================================================
#  PASO 5 — Estáticos
# =============================================================================
header "PASO 5 — Ficheros estáticos"

info "Recolectando ficheros estáticos (collectstatic)..."
python manage.py collectstatic --noinput --clear -v 0
log "Estáticos recolectados en: $(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','crmgestora.settings'); \
import django; django.setup(); from django.conf import settings; print(settings.STATIC_ROOT)")"

# =============================================================================
#  PASO 6 — Datos demo (opcional)
# =============================================================================
header "PASO 6 — Datos demo"

SEED_DEMO="${SEED_DEMO:-}"
if [ -z "$SEED_DEMO" ]; then
    ask "¿Cargar datos demo (participadas, inversores, usuarios de ejemplo)? [s/N] "
    read -r _ans
    case "$_ans" in
        [sS]*) SEED_DEMO="yes" ;;
        *)     SEED_DEMO="no"  ;;
    esac
fi

if [ "$SEED_DEMO" = "yes" ]; then
    info "Cargando datos demo..."
    python manage.py seed_demo_data
    log "Datos demo cargados."
else
    info "Datos demo omitidos."
fi

deactivate

# =============================================================================
#  RESUMEN
# =============================================================================
printf "\n"
printf "${GREEN}${BOLD}╔══════════════════════════════════════════════╗${RESET}\n"
printf "${GREEN}${BOLD}║   ✔  Instalación completada con éxito        ║${RESET}\n"
printf "${GREEN}${BOLD}╚══════════════════════════════════════════════╝${RESET}\n\n"

printf "  ${BOLD}Proyecto:${RESET}    $APP_DIR\n"
printf "  ${BOLD}Virtualenv:${RESET}  $VENV_DIR\n"
printf "  ${BOLD}Config BD:${RESET}   $ENV_FILE\n\n"

printf "  ${BOLD}Próximos pasos:${RESET}\n\n"
printf "  1. Arrancar en desarrollo:\n"
printf "     ${CYAN}cd $APP_DIR && . venv/bin/activate && python manage.py runserver 0.0.0.0:8000${RESET}\n\n"
printf "  2. Configurar como servicio en producción (Gunicorn + OpenRC):\n"
printf "     ${CYAN}sudo $SCRIPT_DIR/setup_service.sh${RESET}\n\n"
printf "  3. Para desplegar cambios futuros desde GitHub:\n"
printf "     ${CYAN}sudo $SCRIPT_DIR/deploy.sh${RESET}\n\n"
