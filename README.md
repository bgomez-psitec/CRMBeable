# CRM Gestora de Fondos

Aplicación Django de gestión de fundraising para una gestora de fondos de venture capital: participadas, rondas de inversión, M&A, colaboraciones, inversores, presentaciones, bandeja de email e informes.

Construida como port fiel y productivo del prototipo funcional `CRM_Gestora_ES_V1.html` (SPA en un único HTML/JS/CSS con datos mock), reemplazando el almacenamiento en memoria por persistencia real en MySQL, autenticación real y control de acceso por roles aplicado en servidor.

## Características

- **Participadas**: listado/grid con búsqueda, agrupación (fondo/etapa/país) y filtro "con ronda abierta"; ficha de detalle con KPIs y tres módulos integrados: Rondas, M&A y Colaboraciones. El formulario incluye selección múltiple de sectores, autocompletado de país con listado predefinido y todos los campos en español.
- **Rondas de Inversión**: ficha con KPIs (objetivo, invertido, pipeline ponderado/no ponderado, descartado), vista de matriz (tabla) y vista de pipeline tipo kanban con **drag & drop** (JS nativo) para cambiar el estado de cada presentación. Incluye **stepper visual de fases** con flechas tipo chevron que muestra la fase activa del proceso.
- **M&A — Pipeline de venta**: módulo integrado en cada participada para gestionar procesos de venta de la compañía a posibles compradores.
  - Procesos M&A (equivalente a una ronda): precio pedido, mejor oferta, pipeline ponderado. Incluye **stepper visual de fases** con chevrons. Los campos NDA y DD han sido eliminados del flujo.
  - Compradores con ficha propia, cronología de interacciones y contactos.
  - Pipeline kanban con estados propios (Identificado → Contactado → Reunión → Oferta recibida → Negociación | Vendido / Descartado) y precio de oferta por contacto.
  - Catálogo de estados M&A configurable desde Ajustes.
- **Colaboraciones**: módulo integrado en cada participada para hacer seguimiento de posibles clientes, proveedores y partners de desarrollo de negocio.
  - Seguimiento por tipo de relación (cliente potencial, proveedor potencial, partner tecnológico, partner comercial).
  - Cronología de interacciones por colaboración.
  - Vista global de colaboraciones con filtro por estado.
  - Cronología de contactos del Colaborador con **filtros por contexto** (Todos / Ronda de Inversión / Proceso M&A / Colaboraciones) y eliminación de cualquier entrada.
  - Catálogo de estados de colaboración configurable desde Ajustes.
- **Inversores**: listado/grid con búsqueda y agrupación (tipo/país); ficha de detalle con cronología combinada de contactos (registros manuales + interacciones ligadas a presentaciones), contactos y presentaciones asociadas. La cronología incluye **filtros por contexto** (Todos / Ronda de Inversión / Proceso M&A / Colaboraciones) y permite eliminar cualquier entrada (incluyendo emails).
- **Presentaciones (introductions)**: vista global con búsqueda y filtro por estado.
- **Bandeja de entrada**: gestión de emails recibidos con flujo guiado en 3 pasos:
  1. **Detección automática de contacto** — busca el remitente (`from_email`) en la base de datos de contactos de Inversores y Colaboradores. Si se encuentra, se autoselecciona y aparece un banner verde de confirmación. Si no existe, ofrece la opción de crearlo como nuevo contacto de un Inversor o Colaborador sin salir de la pantalla.
  2. **Selección de Participada** — filtra las participadas disponibles.
  3. **Selección de proceso** — muestra las Rondas de Inversión o Procesos M&A activos de esa participada para vincular el email a la cronología correcta.
  - Los emails guardados quedan identificados como `Bandeja de entrada` en la cronología de contactos.
  - Eliminación de emails desde la bandeja y desde la cronología de contactos.
- **Informes**: KPIs agregados de rondas abiertas/cerradas, comunicaciones por ronda y contactados en la última semana.
- **Usuarios** (solo admin): alta/edición de usuarios, rol, MFA, participadas asignadas.
- **Ajustes**: edición de perfil y de los catálogos configurables (estados de presentación, fases de ronda, etapas de relación, estados M&A, estados de colaboración).
- **Control de acceso por roles (RBAC) aplicado en servidor**, no solo en la interfaz:
  - **admin**: acceso total a todas las participadas, inversores, M&A, colaboraciones, informes y administración.
  - **empleado**: acceso restringido a sus participadas asignadas (y a los inversores/presentaciones/M&A/colaboraciones relacionados).
  - **ceo**: acceso restringido a su propia participada.
- **Autenticación demo** (login + "quick login" de un clic por cada usuario demo), pensada como punto de partida a sustituir por Auth0 en una fase posterior.
- **Formato numérico español**: todos los importes se muestran con separador de miles `.` y decimales `,` mediante un filtro de template propio (`euros`).

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
  models.py          Participadas, rondas, inversores, presentaciones, M&A, colaboraciones, catálogos
  permissions.py     Lógica de visibilidad por rol (RBAC), reutilizada en todas las vistas
  utils.py           Lógica de negocio portada del prototipo (pipeline ponderado, resumen de email, M&A weighted)
  forms.py           Formularios Django para participadas, rondas, procesos M&A, colaboraciones, usuarios
  views.py / urls.py Una vista por pantalla
  templatetags/
    crm_filters.py   Filtro `euros` para formateo numérico español (1.234.567,00)
  management/commands/seed_demo_data.py   Carga de datos demo
templates/           Plantillas Django (layout base + una por pantalla)
static/              Estáticos del proyecto
requirements.txt     Dependencias Python
.env.example         Plantilla de variables de entorno
```

## Modelo de datos — módulos principales

| Módulo | Modelos clave |
|---|---|
| Fundraising | `Round`, `Introduction`, `Interaction`, `EstadoPresentacion`, `FaseRonda`, `RoundFaseLog` |
| M&A | `ProcesoMA`, `ContactoMA`, `InteraccionMA`, `Comprador`, `EstadoMA`, `FaseMA`, `ProcesoMAFaseLog` |
| Colaboraciones | `Colaboracion`, `InteraccionColaboracion`, `Colaborador`, `ColaboradorLog`, `EstadoColaboracion` |
| Inversores | `Investor`, `InvestorContact`, `InvestorLog`, `EtapaRelacion` |
| Bandeja | `InboxMessage` (FKs a `Investor`, `Colaborador`, `Round`, `ProcesoMA`) |

## Modelo de roles

| Rol      | Alcance de visibilidad                                  |
|----------|-----------------------------------------------------------|
| admin    | Todas las participadas, inversores, M&A, colaboraciones, informes y administración |
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
4. Cargar datos demo (participadas, inversores, presentaciones, compradores M&A, colaboraciones, usuarios, bandeja de entrada):
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

> El puerto por defecto es **8001** (no el 8000 habitual) precisamente para no chocar con otra aplicación Gunicorn que ya esté corriendo en el mismo servidor. El servicio se registra además con nombre y usuario de sistema propios (`crmgestora`), por lo que no interfiere con servicios OpenRC de otras apps.

Tras `setup_service.sh`, el servicio se gestiona con las herramientas estándar de OpenRC:

```bash
rc-service crmgestora status
rc-service crmgestora restart
tail -f logs/gunicorn-error.log
```

`Gunicorn` escucha por defecto solo en `127.0.0.1:8001`; en producción se recomienda poner **Nginx** (u otro proxy inverso) por delante para TLS y para servir directamente la carpeta `staticfiles/` generada por `collectstatic`.

### Actualizar producción (`scripts/deploy.sh`)

Una vez la app está instalada y corriendo como servicio, **`scripts/deploy.sh`** automatiza traer los cambios nuevos de GitHub:

1. Comprueba que no haya cambios locales sin commitear.
2. Hace `git fetch` + `git merge --ff-only` de la rama configurada.
3. Reinstala dependencias solo si `requirements.txt` cambió.
4. Ejecuta `migrate` y `collectstatic`.
5. Reinicia el servicio OpenRC.

```bash
cd /ruta/a/CRMBeable
chmod +x scripts/deploy.sh
sudo ./scripts/deploy.sh
```

| Variable       | Por defecto | Descripción                                              |
|----------------|-------------|------------------------------------------------------------|
| `APP_DIR`      | carpeta del proyecto | Ruta donde vive el código                         |
| `VENV_DIR`     | `$APP_DIR/venv`      | Ruta del virtualenv                               |
| `GIT_REMOTE`   | `origin`             | Remoto git a usar                                 |
| `GIT_BRANCH`   | `main`               | Rama a desplegar                                  |
| `SERVICE_NAME` | `crmgestora`         | Nombre del servicio OpenRC a reiniciar            |
| `SKIP_RESTART` | `no`                 | `yes` para actualizar código/BD sin reiniciar el servicio |

## Estado del proyecto / próximos pasos

- ✅ Modelo de datos, RBAC, todas las pantallas del prototipo portadas a Django con persistencia real en MySQL.
- ✅ Resumen heurístico de emails (sin IA externa), igual que el prototipo.
- ✅ Módulo M&A con pipeline kanban de venta, compradores, procesos e interacciones. Campos NDA y DD eliminados.
- ✅ Módulo Colaboraciones con seguimiento de clientes/proveedores/partners por participada.
- ✅ Formato numérico español (`.` miles, `,` decimales) en todos los importes.
- ✅ Stepper visual de fases (chevrons) en fichas de Ronda y Proceso M&A.
- ✅ Todos los labels de formularios en español (sin acentos, espacios como `_`).
- ✅ Autocompletado de país con listado predefinido en Participadas, Inversores y Colaboradores.
- ✅ Selección múltiple de sectores en el formulario de Participadas.
- ✅ Filtros de cronología por contexto (Ronda / M&A / Colaboraciones) en fichas de Inversor y Colaborador.
- ✅ Bandeja de entrada rediseñada: detección automática de contacto, selección en cascada Participada → Proceso, creación de nuevo contacto inline, identificación `Bandeja de entrada` en cronología, eliminación de emails.
- ⏳ **Auth0**: pendiente de integrar para sustituir el login demo actual (variables ya previstas en `.env.example`).
- ⏳ **Microsoft Graph (Outlook)**: pendiente de integrar para sincronizar la bandeja de entrada con buzones reales (variables ya previstas en `.env.example`); actualmente la bandeja se gestiona de forma manual.

## Origen del proyecto

El diseño, los flujos y las reglas de negocio replicados en esta aplicación están definidos en el prototipo funcional `CRM_Gestora_ES_V1.html` entregado por el cliente, y el stack y los requisitos generales en `HANDOFF.md`.
