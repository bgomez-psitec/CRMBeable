#!/bin/sh
# Configura el CRM Gestora de Fondos como servicio OpenRC en Alpine Linux,
# sirviéndolo con Gunicorn detrás (recomendado poner Nginx delante como proxy inverso
# para TLS y estáticos, no incluido en este script).
#
# Requiere haber ejecutado antes scripts/install.sh.
#
# Uso:
#   chmod +x scripts/setup_service.sh
#   ./scripts/setup_service.sh
#
# Variables de entorno opcionales:
#   APP_DIR   Ruta del proyecto (por defecto: directorio del propio script, un nivel arriba)
#   VENV_DIR  Ruta del virtualenv (por defecto: $APP_DIR/venv)
#   APP_USER  Usuario del sistema bajo el que correrá el servicio (por defecto: crmgestora)
#   BIND_ADDR Dirección:puerto donde escucha Gunicorn (por defecto: 127.0.0.1:8001)
#   WORKERS   Número de workers de Gunicorn (por defecto: 3)
#
# Nota: si en el servidor ya corre otra aplicación con Gunicorn, este script usa
# por defecto el puerto 8001 (en vez del 8000 habitual) y un nombre de servicio/usuario
# propios ("crmgestora") precisamente para no interferir con ella. Ajusta BIND_ADDR
# si el 8001 también estuviera ocupado.

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
APP_DIR="${APP_DIR:-$(dirname "$SCRIPT_DIR")}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
APP_USER="${APP_USER:-crmgestora}"
BIND_ADDR="${BIND_ADDR:-127.0.0.1:8001}"
WORKERS="${WORKERS:-3}"
SERVICE_NAME="crmgestora"

log()  { printf '\033[1;32m[service]\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m[service]\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31m[service]\033[0m %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Este script necesita privilegios de root (creación de usuario y servicio OpenRC)."
[ -d "$VENV_DIR" ] || die "No existe el virtualenv en $VENV_DIR. Ejecuta antes scripts/install.sh."

# Aviso (no bloqueante) si el puerto ya está en uso por otro proceso/servicio,
# para no pisar la aplicación que ya corre con Gunicorn en este servidor.
PORT="${BIND_ADDR##*:}"
if command -v netstat >/dev/null 2>&1; then
    if netstat -tln 2>/dev/null | grep -q ":$PORT "; then
        warn "El puerto $PORT ya está en uso por otro proceso. Cambia BIND_ADDR antes de continuar (ej: BIND_ADDR=127.0.0.1:8002 ./scripts/setup_service.sh)."
    fi
fi

# 1. Usuario de sistema dedicado (sin login, sin home interactivo)
if ! id "$APP_USER" >/dev/null 2>&1; then
    log "Creando usuario de sistema '$APP_USER'..."
    addgroup -S "$APP_USER" 2>/dev/null || true
    adduser -S -D -H -G "$APP_USER" -s /sbin/nologin "$APP_USER"
else
    log "Usuario '$APP_USER' ya existe."
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# 2. Script de arranque de Gunicorn
RUN_SCRIPT="$APP_DIR/scripts/run_gunicorn.sh"
cat > "$RUN_SCRIPT" <<EOF
#!/bin/sh
cd "$APP_DIR"
. "$VENV_DIR/bin/activate"
exec gunicorn crmgestora.wsgi:application \\
    --bind "$BIND_ADDR" \\
    --workers "$WORKERS" \\
    --access-logfile "$APP_DIR/logs/gunicorn-access.log" \\
    --error-logfile "$APP_DIR/logs/gunicorn-error.log"
EOF
chmod +x "$RUN_SCRIPT"
mkdir -p "$APP_DIR/logs"
chown -R "$APP_USER:$APP_USER" "$APP_DIR/logs"

# 3. Servicio OpenRC
INIT_FILE="/etc/init.d/$SERVICE_NAME"
cat > "$INIT_FILE" <<EOF
#!/sbin/openrc-run

name="$SERVICE_NAME"
description="CRM Gestora de Fondos (Django + Gunicorn)"
command="$RUN_SCRIPT"
command_user="$APP_USER:$APP_USER"
command_background=true
pidfile="/run/\${RC_SVCNAME}.pid"
output_log="$APP_DIR/logs/gunicorn-stdout.log"
error_log="$APP_DIR/logs/gunicorn-stderr.log"

depend() {
    need net
    after firewall
}
EOF
chmod +x "$INIT_FILE"

log "Habilitando e iniciando el servicio '$SERVICE_NAME'..."
rc-update add "$SERVICE_NAME" default
rc-service "$SERVICE_NAME" restart

log "Servicio instalado. Escuchando en $BIND_ADDR (proceso bajo el usuario '$APP_USER')."
log "Comandos útiles:"
log "  rc-service $SERVICE_NAME status|restart|stop"
log "  tail -f $APP_DIR/logs/gunicorn-error.log"
log ""
log "Recuerda poner Nginx (u otro proxy) delante para TLS y servir $APP_DIR/staticfiles en /static/."
