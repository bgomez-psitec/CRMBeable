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

## Estado del proyecto / próximos pasos

- ✅ Modelo de datos, RBAC, todas las pantallas del prototipo portadas a Django con persistencia real en MySQL.
- ✅ Resumen heurístico de emails (sin IA externa), igual que el prototipo.
- ⏳ **Auth0**: pendiente de integrar para sustituir el login demo actual (variables ya previstas en `.env.example`).
- ⏳ **Microsoft Graph (Outlook)**: pendiente de integrar para sincronizar la bandeja de entrada con buzones reales (variables ya previstas en `.env.example`); actualmente la bandeja se gestiona de forma manual.

## Origen del proyecto

El diseño, los flujos y las reglas de negocio replicados en esta aplicación están definidos en el prototipo funcional `CRM_Gestora_ES_V1.html` entregado por el cliente, y el stack y los requisitos generales en `HANDOFF.md`.
