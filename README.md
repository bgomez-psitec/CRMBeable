# CRM Gestora de Fondos

Aplicación Django de gestión de fundraising para una gestora de fondos de venture capital: participadas, rondas de inversión, inversores, presentaciones (introductions), bandeja de email e informes.

Construida como port fiel y productivo del prototipo funcional `CRM_Gestora_ES_V1.html` (SPA en un único HTML/JS/CSS con datos mock), reemplazando el almacenamiento en memoria por persistencia real en MySQL, autenticación real y control de acceso por roles aplicado en servidor.

## Características

- **Participadas**: listado/grid con búsqueda, agrupación (fondo/etapa/país) y filtro "con ronda abierta"; ficha de detalle con KPIs (objetivo, invertido, pipeline ponderado) y rondas asociadas.
- **Rondas**: ficha de ronda con KPIs (objetivo, invertido, pipeline ponderado/no ponderado, descartado), vista de matriz (tabla) y vista de pipeline tipo kanban con **drag & drop** (JS nativo) para cambiar el estado de cada presentación.
- **Inversores**: listado/grid con búsqueda y agrupación (tipo/país); ficha de detalle con cronología combinada de contactos (registros manuales + interacciones ligadas a presentaciones), contactos y presentaciones asociadas.
- **Presentaciones (introductions)**: vista global con búsqueda y filtro por estado.
- **Bandeja de entrada**: gestión de emails recibidos con **resumen automático heurístico** (sin IA externa, basado en reglas/regex), sugerencia de inversor por dominio de email del remitente, y guardado del resumen como interacción de una presentación o como registro de contacto del inversor.
- **Informes**: KPIs agregados de rondas abiertas/cerradas, comunicaciones por ronda y contactados en la última semana.
- **Usuarios** (solo admin): alta/edición de usuarios, rol, MFA, participadas asignadas.
- **Ajustes**: edición de perfil y de los catálogos configurables (estados de presentación, fases de ronda, etapas de relación).
- **Control de acceso por roles (RBAC) aplicado en servidor**, no solo en la interfaz:
  - **admin**: acceso total a todas las participadas, inversores, informes y administración.
  - **empleado**: acceso restringido a sus participadas asignadas (y a los inversores/presentaciones relacionados).
  - **ceo**: acceso restringido a su propia participada.
- **Autenticación demo** (login + "quick login" de un clic por cada usuario demo), pensada como punto de partida a sustituir por Auth0 en una fase posterior.

## Stack técnico

- **Backend**: Python 3 + Django 5.2 (arquitectura MPA, sin API REST ni SPA).
- **Base de datos**: MySQL (vía `mysqlclient`).
- **Frontend**: Bootstrap 5 (`django-bootstrap5`) + Bootstrap Icons, con JavaScript vanilla puntual solo donde es imprescindible (drag & drop del kanban).
- **Configuración**: `django-environ`, variables sensibles en `.env` (no versionado).
- **Autenticación**: sistema de usuarios propio (`accounts.User`, extiende `AbstractUser`) con login/quick-login demo. Auth0 y Microsoft Graph (Outlook) quedan como integraciones previstas para una fase posterior.

## Estructura del proyecto

```
crmgestora/         Configuración del proyecto Django (settings, urls)
accounts/           App de usuarios y autenticación (modelo User, roles, login/logout)
crm/                App principal del dominio (modelos, vistas, permisos, utilidades)
  models.py          Participadas, rondas, inversores, presentaciones, interacciones, bandeja, catálogos
  permissions.py     Lógica de visibilidad por rol (RBAC), reutilizada en todas las vistas
  utils.py           Lógica de negocio portada del prototipo (pipeline ponderado, resumen de email, etc.)
  views.py / urls.py Una vista por pantalla
  management/commands/seed_demo_data.py   Carga de datos demo
templates/           Plantillas Django (layout base + una por pantalla)
static/              Estáticos del proyecto
requirements.txt     Dependencias Python
.env.example         Plantilla de variables de entorno
```

## Modelo de roles

| Rol      | Alcance de visibilidad                                  |
|----------|-----------------------------------------------------------|
| admin    | Todas las participadas, inversores, presentaciones, informes y administración |
| empleado | Solo las participadas que tiene asignadas (`assigned_companies`) |
| ceo      | Solo su propia participada (`company`)                   |

La lógica vive en `crm/permissions.py` y se aplica filtrando los querysets en cada vista (no mediante grupos/permisos estándar de Django), ya que el filtrado es por instancia de participada.

## Puesta en marcha

1. Crear y activar un entorno virtual, e instalar dependencias:
   ```bash
   python -m venv venv
   venv\Scripts\activate          # Windows
   pip install -r requirements.txt
   ```
2. Copiar `.env.example` a `.env` y rellenar las credenciales reales (base de datos, `SECRET_KEY`, etc.). **Nunca commitear `.env`**.
3. Aplicar migraciones:
   ```bash
   python manage.py migrate
   ```
4. Cargar datos demo (participadas, inversores, presentaciones, usuarios, bandeja de entrada):
   ```bash
   python manage.py seed_demo_data
   ```
5. Arrancar el servidor de desarrollo:
   ```bash
   python manage.py runserver
   ```
6. Acceder a la pantalla de login y usar el "quick login" para entrar como cualquiera de los usuarios demo (admin / empleado / ceo) sin necesidad de contraseña.

## Despliegue en servidor (Alpine Linux)

El directorio `scripts/` incluye dos scripts pensados para desplegar la aplicación en un servidor Alpine Linux por SSH, usando `virtualenv` y sin dependencias de Docker:

- **`scripts/install.sh`**: instala las dependencias del sistema necesarias vía `apk` (Python, herramientas de compilación y cabeceras de MariaDB para `mysqlclient`), crea el virtualenv, instala `requirements.txt`, genera `.env` a partir de `.env.example` si no existe, aplica migraciones, recolecta estáticos y permite cargar los datos demo.
- **`scripts/setup_service.sh`**: crea un usuario de sistema dedicado, registra la aplicación como **servicio OpenRC** (el init system de Alpine) sirviéndola con **Gunicorn**, y la deja arrancando en cada boot.

Uso típico, conectado por SSH al servidor:

```bash
git clone https://github.com/bgomez-psitec/CRMBeable.git
cd CRMBeable
chmod +x scripts/install.sh scripts/setup_service.sh

# 1. Instala dependencias del sistema, crea el virtualenv y prepara la app
sudo ./scripts/install.sh
# -> Edita .env con las credenciales reales de MySQL, SECRET_KEY, ALLOWED_HOSTS, etc.

# 2. (Opcional, recomendado en producción) Registra el servicio OpenRC con Gunicorn
sudo ./scripts/setup_service.sh
```

Variables de entorno que aceptan ambos scripts para personalizar la instalación (todas opcionales):

| Variable    | Script            | Por defecto         | Descripción                                  |
|-------------|--------------------|----------------------|-----------------------------------------------|
| `APP_DIR`   | ambos              | carpeta del proyecto | Ruta donde vive el código                     |
| `VENV_DIR`  | ambos              | `$APP_DIR/venv`      | Ruta del virtualenv                           |
| `PYTHON_BIN`| `install.sh`       | `python3`            | Binario de Python a usar                      |
| `SEED_DEMO` | `install.sh`       | (pregunta)           | `yes`/`no`, cargar datos demo sin preguntar    |
| `APP_USER`  | `setup_service.sh` | `crmgestora`         | Usuario de sistema bajo el que corre Gunicorn |
| `BIND_ADDR` | `setup_service.sh` | `127.0.0.1:8001`     | Dirección/puerto donde escucha Gunicorn       |
| `WORKERS`   | `setup_service.sh` | `3`                  | Número de workers de Gunicorn                 |

> El puerto por defecto es **8001** (no el 8000 habitual) precisamente para no chocar con otra aplicación Gunicorn que ya esté corriendo en el mismo servidor. El servicio se registra además con nombre y usuario de sistema propios (`crmgestora`), por lo que no interfiere con servicios OpenRC de otras apps. Si el 8001 también estuviera ocupado, indica otro puerto libre con `BIND_ADDR=127.0.0.1:8002 ./scripts/setup_service.sh`.

Tras `setup_service.sh`, el servicio se gestiona con las herramientas estándar de OpenRC:

```bash
rc-service crmgestora status
rc-service crmgestora restart
tail -f logs/gunicorn-error.log
```

`Gunicorn` escucha por defecto solo en `127.0.0.1:8000`; en producción se recomienda poner **Nginx** (u otro proxy inverso) por delante para TLS y para servir directamente la carpeta `staticfiles/` generada por `collectstatic`. No se incluye configuración de Nginx en este repositorio.

## Estado del proyecto / próximos pasos

- ✅ Modelo de datos, RBAC, todas las pantallas del prototipo portadas a Django con persistencia real en MySQL.
- ✅ Resumen heurístico de emails (sin IA externa), igual que el prototipo.
- ⏳ **Auth0**: pendiente de integrar para sustituir el login demo actual (variables ya previstas en `.env.example`).
- ⏳ **Microsoft Graph (Outlook)**: pendiente de integrar para sincronizar la bandeja de entrada con buzones reales (variables ya previstas en `.env.example`); actualmente la bandeja se gestiona de forma manual.

## Origen del proyecto

El diseño, los flujos y las reglas de negocio replicados en esta aplicación están definidos en el prototipo funcional `CRM_Gestora_ES_V1.html` entregado por el cliente, y el stack y los requisitos generales en `HANDOFF.md`.
