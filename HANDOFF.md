# CRM de Gestora de Fondos — Documento de Handoff Técnico

Especificación para llevar el prototipo a producción.

| | |
|---|---|
| **Versión** | V1 |
| **Fecha** | Junio 2026 |
| **Autor** | David Lopez |
| **Para** | Bruno Gomez |

---

## 01. Resumen del proyecto

CRM especializado para una gestora de fondos / venture capital. No es un CRM de ventas: gestiona el **fundraising de las participadas**, la **relación con inversores** y el **seguimiento de oportunidades** (qué inversor está en qué fase de qué ronda).

Existe un **prototipo HTML completo y funcional** (`CRM_Gestora_ES_V1.html`) que define el diseño, los flujos y todas las reglas de negocio. Sirve como especificación visual exacta. Falta construir la infraestructura real: base de datos persistente, autenticación, e integración con Outlook.

---

## 02. Parámetros del proyecto

| Parámetro | Valor |
|---|---|
| Idioma de la aplicación | Español |
| Nº de usuarios estimado | [10–30] |
| Nº de inversores en base de datos | [~1.000] |
| Nº de participadas | 10-30 |
| Presupuesto aproximado | [indicar] |
| Plazo objetivo | [4–6 semanas] |
| Alojamiento de datos (región) | [UE / Europa] |
| Cumplimiento normativo | [RGPD / GDPR] |

---

## 03. Decisiones tecnológicas

Recomendación de partida. Fijar la columna **"Tu elección"** con el stack definitivo.

| Componente | Recomendado | Alternativas | Tu elección |
|---|---|---|---|
| Lenguaje de programación | — | — | [Python] |
| Framework de desarrollo | — | — | [Django] |
| Base de datos | Supabase (Postgres) | Firebase, AWS RDS | [Mysql] |
| Autenticación + MFA | Supabase Auth | Auth0, Clerk, Entra ID | [Auth0] |
| Frontend | React + Next.js | Vue, Svelte | [bootstrap] |
| Hosting | Vercel | Netlify, AWS | [selfhosted] |
| Integración email | Microsoft Graph API | Gmail API, IMAP | [Microsoft Graph API] |
| Resumen de emails (IA) | API de Claude | OpenAI, local | [ ] |
| Control de versiones | GitHub | GitLab, Bitbucket | [GitHub] |

---

## 04. Modelo de datos

Tablas principales (derivadas del prototipo). La tabla crítica es **presentaciones**: ahí vive todo el histórico de "qué inversor, en qué ronda, en qué estado".

### `participadas` — portfolio companies
`id · nombre · código_interno · fondo (BIKF/BISEF/BIGINF) · país · provincia · sectores[] · status · TRL · MRL · time_to_market · revenue_status · última_valoración · fecha_valoración`

### `rondas` — una participada tiene N rondas
`id · participada_id · tipo · objetivo (€) · estado_fase · status · fecha_inicio · fecha_cierre`

### `inversores`
`id · nombre · tipo · estado_público · país · áreas_inversión[] · etapas[] · tickets[] · sectores[] · AUM · relación · notas`

### `contactos` — N por inversor y por participada
`id · inversor_id / participada_id · nombre · cargo · email · teléfono`

### `presentaciones` — el corazón del CRM (introductions)
`id · participada_id · ronda_id · inversor_id · estado · ticket · fecha · quién_hizo_intro · próximo_paso · próxima_fecha · notas`

### `interacciones` — cronología de contactos
`id · presentación_id · fecha · tipo (email/llamada/reunión/nota/cambio_estado) · resumen`

### `usuarios`
`id · nombre · email · rol (admin/empleado/ceo) · participadas_asignadas[] · participada_id (CEO) · mfa · activo`

---

## 05. Roles y permisos

> ⚠️ **Crítico de seguridad:** los permisos deben aplicarse en la base de datos (Row Level Security), no solo ocultando elementos en pantalla como hace el prototipo.

- **Admin** — acceso total: todas las participadas, inversores, configuración y gestión de usuarios.
- **Empleado de la firma** — acceso a las participadas que se le asignen; puede añadir inversores, registrar reuniones y editar el pipeline.
- **CEO de participada** — solo su propia empresa: sus inversores, su pipeline, sus reuniones. **No ve** otras participadas, ni datos de la firma, ni conversaciones de otras empresas.

---

## 06. Integración con Outlook

Flujo objetivo: un email llega → el sistema lo asocia a un inversor y una ronda → genera un **resumen automático de máx. 3 líneas** → el usuario confirma → se guarda en la cronología de interacciones con fecha.

- Registrar una app en **Azure / Microsoft Entra** y usar **Microsoft Graph API** (requiere permisos de tu IT).
- Fase 1: botón "guardar email" (pegar/seleccionar correo). Fase 2 (avanzada): recepción automática vía webhooks de Graph.
- El resumen lo genera la API de IA elegida en el apartado 03.

---

## 07. Fases del proyecto

| Fase | Descripción | Duración estimada |
|---|---|---|
| 1 | Stack + modelo de datos | [3–4 días] |
| 2 | Autenticación, MFA y permisos (RLS) | [2–3 días] |
| 3 | Conectar frontend a la base de datos | [1–2 semanas] |
| 4 | Integración con Outlook | [3–5 días] |
| 5 | Pruebas, migración de datos y despliegue | [1 semana] |

---

## 08. Checklist de arranque

- [ ] Confirmar el stack en el apartado 03
- [ ] Crear cuentas (base de datos, hosting, repositorio)
- [ ] Crear el esquema de base de datos del apartado 04
- [ ] Implementar login + MFA + permisos por rol (RLS)
- [ ] Migrar el diseño del prototipo a frontend real
- [ ] Registrar app en Azure para Outlook
- [ ] Cargar inversores y participadas reales
- [ ] Pruebas con usuarios piloto y despliegue

---

## 09. Datos de conexion a la base de datos Mysql

'NAME': 'CRMBeable_dev'
'USER': 'DataContaBL'
'PASSWORD': 'temporal'
'HOST': '192.168.85.50'
'PORT': '32769'

*Documento de handoff · CRM de Gestora · Adjuntar junto al archivo `CRM_Gestora_ES_V1.html`*
