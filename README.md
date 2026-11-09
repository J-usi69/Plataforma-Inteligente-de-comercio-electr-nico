# FashionStore

Plataforma inteligente de comercio electrónico para una cadena de tiendas de ropa: catálogo con vestidor virtual (RA), reserva de prendas para prueba física, compra presencial o digital, inventario centralizado por sucursal e inteligencia artificial (recomendación, chatbot y reportes).

Trabajo del **Primer Examen Parcial — Sistemas de Información 2** (Grupo 13, UAGRM). El enunciado completo, los casos de uso (CU-01 a CU-34) y el análisis de paquetes están en `docs/` — léelo antes de tocar código, ahí está el detalle de cada flujo.

**Para probar el sistema:** [credenciales](#credenciales-de-prueba), [qué hace cada rol en la web y en la app](#guía-de-uso-por-rol) y [cómo probarlo](#cómo-probar).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI + SQLAlchemy + Alembic |
| Web | Angular (standalone) |
| Móvil | Flutter/Dart |
| Base de datos | PostgreSQL, alojada en **Supabase** (compartida por todo el equipo) |
| Infraestructura local | Docker (backend + frontend, conectados directo a Supabase) |
| Despliegue | Railway (backend y web; se despliega solo con cada push a `main`) y Supabase (base de datos) |

## Estado actual del proyecto

### Base de datos
Esquema completo (25 tablas) ya aplicado en Supabase: usuarios/personal separados, RBAC (rol/permiso/rol_permiso), bitácora de auditoría, catálogo (prenda/variante/talla/color/categoría/temporada/colección), inventario por sucursal + histórico de movimientos, reservas (funcionan como "carrito" del cliente, no hay tabla `carrito` separada), ventas/pagos, e interacción con IA. Modelos SQLAlchemy verificados 1:1 con la base real (`alembic --autogenerate` sin diffs).

### Backend (FastAPI) — casos de uso implementados y probados
- **CU-01 a CU-03**: registro/login/logout con JWT, roles y permisos embebidos en el token.
- **CU-04**: gestión de roles y permisos (RBAC).
- **CU-05**: gestión de personal (encargados/cajeros por sucursal).
- **CU-06**: gestión de sucursales y ciudades.
- **CU-07**: gestión de proveedores.
- **CU-08**: catálogo de prendas (CRUD + filtros por categoría/colección/búsqueda).
- **CU-09**: catálogos maestros — categorías, tallas y colores.
- **CU-10**: temporadas y colecciones (con validación de coherencia de fechas).
- **CU-11**: variantes de prenda (talla + color, con generación automática de código de barras).
- **CU-12**: consulta de catálogo por parte del cliente, con filtros por categoría, colección, temporada, talla y color.
- **CU-13**: consultar disponibilidad de stock de una variante por sucursal (agrupable por ciudad).
- **CU-14**: vestidor virtual — el cliente sube una foto y el backend genera una imagen suya "probándose" la prenda usando IA (Replicate, modelo `prunaai/p-image-try-on`). Requiere que la prenda tenga `imagen_url` cargada y `REPLICATE_API_TOKEN` configurado en el `.env` (ver sección de credenciales).
- **CU-15**: reservar una o varias prendas en una sucursal, con validación de stock disponible y actualización automática de `inventario_sucursal` (descuenta `stock_disponible`, incrementa `stock_reservado`).
- **CU-16**: consultar y cancelar reservas propias (libera el stock reservado; no permite cancelar una reserva que ya no está pendiente).

También implementado (CU-17 a CU-25, a cargo de Jhonny): roles y permisos, personal, proveedores, temporadas/colecciones, gestión de reservas recibidas por sucursal (Encargado), ventas presenciales y digitales con pago electrónico (Stripe, modo test), historial de compras del cliente, y el movimiento automático de inventario al reservar/cancelar/vender.

- **CU-23**: emisión de comprobante de venta, con **descarga real en PDF** (además de la opción de imprimir) tanto desde "Mis Compras" del Cliente como desde la Caja del Cajero.
- **CU-26**: rol **Encargado** puede registrar movimientos manuales de inventario (ingreso, devolución, merma, ajuste) sobre las variantes de su propia sucursal, con rechazo de salidas que superen el stock disponible.
- **CU-27**: consulta de **inventario global** para el Administrador — existencias consolidadas de todas las sucursales, filtrables por ciudad y por categoría, con marca de quiebre de stock.
- **CU-28**: recomendaciones de prendas por IA (Gemini) para el Cliente, a partir de su historial de compras/reservas y el catálogo activo; si Gemini no responde a tiempo, cae en un fallback con las prendas más vendidas.
- **CU-29**: asistente conversacional (chatbot) con IA (Groq), disponible **incluso sin sesión iniciada** — funciona igual para un visitante que para un Cliente logueado (a un logueado además se le guarda el historial de interacción). Mantiene memoria de la conversación (se manda el historial de turnos en cada mensaje) y su prompt está anclado a datos reales del negocio (moneda en Bolivianos, reserva sin costo) para no inventar precios ni políticas.
- **CU-30**: generación de reportes en lenguaje natural por IA (Mistral) para el Administrador, reusando los mismos endpoints de reportes predefinidos.
- **CU-31/CU-32**: reportes predefinidos (ventas por sucursal, prendas más vendidas, quiebres de stock, inventario global) con **descarga en CSV**, y dashboard de indicadores con datos reales agregados en el backend.
- **CU-33/CU-34**: rol **Proveedor** con login propio — registra sus propios productos (quedan inactivos hasta que el Administrador los valida) e informa disponibilidad futura de stock; el Administrador puede consultar ese historial para planificar reposición.
- **Notificaciones push** (Firebase Cloud Messaging, solo app móvil): se disparan solas, sin que el usuario tenga que refrescar nada, cuando cambia el estado de una reserva (confirmada / atendida / no-show por vencimiento), cuando se aprueba un pago, cuando el Administrador reactiva una prenda o colección dada de baja (aviso a todos los Clientes), y cuando un Proveedor informa disponibilidad (aviso a los Administradores). Un fallo al enviar un push nunca rompe el flujo que lo disparó — queda solo logueado.

### Inteligencia Artificial: por qué 3 proveedores distintos

El módulo de IA no usa un solo proveedor — cada función tiene el suyo, para que el límite gratuito (rate limit) de uno no tumbe a los demás:

| Función | Proveedor | Por qué |
|---|---|---|
| Recomendaciones (CU-28) | **Gemini** (`gemini-3.6-flash`) | Se llama poco (una vez por carga de catálogo), no necesita el tier más generoso. |
| Chatbot (CU-29) | **Groq** (`openai/gpt-oss-120b`) | Es la función que más se llama (cada mensaje del chat), así que necesita el proveedor con más cuota gratis. |
| Reportes por IA (CU-30) | **Mistral** (`mistral-small-latest`) | Solo lo usa el Administrador ocasionalmente. |

Las tres integraciones son HTTP directo (`httpx`) contra la API de cada proveedor, sin SDK — ver `backend/app/services/ia_service.py`. Si a un proveedor le falta la API key en el `.env` o la llamada falla, esa función responde con un mensaje de "no disponible por ahora" (o el fallback de prendas más vendidas, en el caso de recomendaciones) en vez de romper el resto del sistema.

**El chatbot es la única función de IA que también funciona sin haber iniciado sesión** (recomendaciones y reportes sí necesitan estar logueado) — así un visitante puede preguntar sobre tallas, disponibilidad o el proceso de reserva antes de crear una cuenta. El asistente recibe el historial de la conversación en cada mensaje (no tiene memoria del lado del servidor) y su prompt está anclado a datos reales del negocio (moneda en Bolivianos, reserva gratuita) para no inventar precios ni políticas que no existen.

### Flujo por rol de usuario

Qué hace cada rol, en la web y en la app, y cómo probarlo: ver la [Guía de uso por rol](#guía-de-uso-por-rol).

### Frontend web (Angular)
Login/registro funcionales contra la API real, interceptor de autenticación JWT, dashboard administrativo con listados (roles, personal, sucursales, proveedores, catálogo, reportes/dashboard), panel propio de Proveedor, asistente conversacional flotante (disponible sin sesión iniciada), catálogo con tarjetas de producto clickeables, servicios `AuthService`/`ApiService`/`BusinessService`.

### App móvil (Flutter)
Login/registro/perfil funcionales contra la API real, listado de sucursales, catálogo de prendas con filtros por talla/color y tarjetas de producto clickeables (abren el detalle completo: categoría, descripción, variantes, accesos directos a 3D RA/Reservar/Comprar), reserva de variante en sucursal (`/reservar`) y gestión de "Mis Reservas" (`/reservas`), vestidor virtual (`/vestidor-ar`, con IA generativa o AR en vivo; la web también lo tiene), carrusel de recomendaciones y pantalla de chat con el asistente (`/asistente`, funciona sin sesión iniciada), y notificaciones push nativas vía Firebase Cloud Messaging (se registra el token del dispositivo al iniciar sesión).

### Diagramas y documentación
- `docs/diseno_logico.md` — diseño lógico de las 25 tablas en formato visual (header + PK + FKs).
- `docs/modelo_datos_logico.md` — mismo modelo en tablas markdown simples, con las decisiones de diseño explicadas.
- `docs/ea-scripts/diagrama_clases.js` — script para generar el diagrama de clases UML en Enterprise Architect.

## Estructura del repositorio

```
database/
  schema.sql                 # DDL de referencia (documenta el diseño original)
  init-seeds.sql              # Datos semilla (solo para el Postgres local opcional)
docs/
  diseno_logico.md             # Diseño lógico visual de las 25 tablas
  modelo_datos_logico.md        # Modelo lógico en tablas markdown
  ea-scripts/
    diagrama_clases.js           # Script para regenerar el diagrama de clases en EA
backend/
  Dockerfile
  app/
    core/config.py               # Settings (lee el .env de la raíz)
    core/security.py              # JWT, hashing de contraseñas
    db/session.py                  # Engine, SessionLocal, Base declarativa
    models/                         # Modelos SQLAlchemy (fuente de verdad del esquema)
    schemas/                         # Schemas Pydantic (request/response por módulo)
    services/                         # ia_service.py, push_service.py, reportes_service.py (lógica reusable)
    api/v1/endpoints/                 # Un archivo por caso de uso/módulo (auth, prendas, roles, ia, notificaciones, etc.)
    main.py                            # App FastAPI (CORS + router /api/v1)
  alembic/                              # Migraciones (ver backend/README.md para el flujo)
  tests/                                 # Tests de CU-01 a CU-08 + IA + notificaciones
  requirements.txt
frontend-web/                            # Angular
  Dockerfile
  nginx.conf
  src/app/core/                           # AuthService, ApiService, BusinessService, interceptor JWT
  src/app/features/                        # Un folder por módulo: auth, catalogo, reservas, ventas, admin, asistente, proveedor
mobile-app/                                # Flutter
  android/app/google-services.json          # Config de Firebase para notificaciones push
  lib/core/                                  # Config (Env), ApiService, PushNotificationService, router (RouteObserver)
  lib/features/                               # auth, catalogo, reservas, sucursales, ventas, vestidor_ar, asistente
docker-compose.yml                            # backend + frontend (conectados a Supabase vía .env)
```

## Configuración inicial (para cada integrante del equipo)

### 1. Variables de entorno

Crea un archivo `.env` en la **raíz del repositorio** (al lado de `docker-compose.yml`, no se sube a git) con este contenido:

```env
# --- Base de datos (Supabase Postgres, via Session Pooler - IPv4 compatible) ---
DATABASE_URL=postgresql://postgres.hypxydlpejdvlaqoiagj:Antonio1305%7C00%7C@aws-0-sa-east-1.pooler.supabase.com:5432/postgres

# --- Supabase API ---
SUPABASE_URL=https://hypxydlpejdvlaqoiagj.supabase.co
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# --- Backend FastAPI ---
JWT_SECRET_KEY=cambia-esto-por-una-clave-larga-y-aleatoria
ENVIRONMENT=development

# --- Pasarela de pago (Stripe, modo test) ---
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# --- IA: 3 proveedores gratuitos distintos, uno por función (ver sección de arriba) ---
# Gemini (CU-28, recomendaciones): clave en aistudio.google.com/apikey
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
# Groq (CU-29, chatbot): clave en console.groq.com/keys
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
# Mistral (CU-30, reportes por IA): clave en console.mistral.ai/api-keys
MISTRAL_API_KEY=
MISTRAL_MODEL=mistral-small-latest

# --- Vestidor virtual / Try-On con IA (CU-14) ---
# Token de Replicate: https://replicate.com/account/api-tokens (cada integrante debe generar el suyo)
REPLICATE_API_TOKEN=
TRYON_REPLICATE_MODEL=prunaai/p-image-try-on

# --- Notificaciones push (Firebase Cloud Messaging, solo app móvil) ---
# JSON de la cuenta de servicio, en una sola línea: Firebase Console > Configuración
# del proyecto > Cuentas de servicio > Generar nueva clave privada.
FIREBASE_CREDENTIALS_JSON=
```

`.env.example` tiene la misma plantilla sin valores reales, por si se pierde este archivo.

**`REPLICATE_API_TOKEN`, las claves de IA y `FIREBASE_CREDENTIALS_JSON` quedan vacías a propósito** — son claves personales/de facturación por uso, cada integrante (o quien despliegue el sistema) debe generar las suyas en la consola de cada proveedor. Sin ellas, el resto del sistema funciona normal; solo la función correspondiente responde "no disponible por ahora" (vestidor virtual, recomendaciones, chatbot, reportes por IA o notificaciones push, según cuál falte).

### 2. Levantar todo con Docker (recomendado)

Con el `.env` ya en la raíz:

```bash
docker compose up -d --build
```

| Servicio | URL |
|---|---|
| Backend (API + docs) | http://localhost:8000/docs |
| Frontend web | http://localhost:4200 |

El backend se conecta **directo a Supabase** (lee el `.env` vía `env_file`), no hace falta levantar ningún Postgres aparte. Para bajar todo: `docker compose down`. Para ver logs: `docker compose logs -f backend`.

### 3. Alternativa sin Docker — Backend

```bash
cd backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic current              # deberia mostrar "0001 (head)" -> confirma que ves la misma base
uvicorn app.main:app --reload
```

Prueba en `http://127.0.0.1:8000/health` → debe responder `{"status": "ok"}`.

Instrucciones completas del flujo de migraciones (cómo agregar una tabla/columna nueva sin romper la base compartida) en **[backend/README.md](backend/README.md)**.

### 4. Alternativa sin Docker — Frontend web

```bash
cd frontend-web
npm install
ng serve
```

### 5. App móvil

```bash
cd mobile-app
flutter pub get
flutter run
```

Por defecto apunta a `http://10.0.2.2:8000` (así el emulador de Android ve el backend corriendo en tu máquina). Para apuntar a otra URL (por ejemplo, un dispositivo físico con `adb reverse tcp:8000 tcp:8000`, o el backend ya desplegado en Railway): `flutter run --dart-define=API_URL=http://tu-ip:8000` o `--dart-define=API_URL=https://fashionstore-backend-production-4c32.up.railway.app`.

**Notificaciones push**: para que `mobile-app/android/app/google-services.json` (ya incluido en el repo) sirva de verdad, el backend necesita `FIREBASE_CREDENTIALS_JSON` configurado en su `.env` (ver sección 1) con la clave de cuenta de servicio del mismo proyecto de Firebase. Sin eso, la app sigue funcionando normal — solo no llegan los push.

### Credenciales de prueba

Son cuentas reales de producción (la misma Supabase compartida), válidas en la web (`https://fashionstore-uagrm.up.railway.app`), en la app móvil y en el backend (`https://fashionstore-backend-production-4c32.up.railway.app/docs`).

Cada empresa del SaaS tiene sus propias cuentas: la sesión vale solo en la empresa donde se inició. Para elegir la empresa:
- **Web:** se entra por su dirección, `/t/<dirección>/login` (FashionStore también responde en `/login`).
- **App móvil:** se escribe la dirección en el campo "Empresa" del login.
- **API (`/docs`):** `POST /api/v1/auth/login` con body `{"login": "...", "password": "..."}` y la cabecera `X-Tienda: <dirección>`. Sin cabecera se usa FashionStore.

#### Plataforma (superadmin)

| Rol | Correo | Contraseña | Dónde entra | Para probar |
|---|---|---|---|---|
| Superadmin | `superadmin@fashionstore.com` | `1234567890` | Web → `/plataforma` (API: `POST /api/v1/plataforma/login`) | Es el único usuario de la plataforma y no pertenece a ninguna empresa. Indicadores de la plataforma (ingresos por suscripciones, empresas por plan, ventas por empresa, vencimientos), administración de empresas y planes, reportes personalizables de todas las empresas (columnas, criterios, fechas y orden; también pedidos con palabras o por voz, que interpreta la IA; exportación a Excel, PDF, HTML o por correo), bitácora de toda la plataforma (cada acción de cada usuario de todas las empresas, con fecha y hora, rol e IP) y respaldo/restauración del sistema completo o de una empresa. |

#### FashionStore — dirección `fashionstore`, plan Profesional

| Rol | Correo | Contraseña | Para probar |
|---|---|---|---|
| Administrador | `admin@fashionstore.com` | `Admin123*` | Dashboard admin completo: roles/permisos, personal, sucursales, proveedores, catálogo maestro (categorías/tallas/colores/temporadas/colecciones), prendas y variantes, reportes con IA, reportes personalizados (columnas, criterios, orden, exportación; con palabras o voz en el plan Profesional), bitácora de la empresa, respaldo/restauración de los datos de la empresa, analítica ML y conflictos de sincronización (CU-14). |
| Cliente | `cliente@fashionstore.com` | `Cliente123*` | Catálogo público, filtros por talla/color/temporada, reservar prenda en sucursal, ver/cancelar "Mis Reservas", vestidor virtual con IA, recomendaciones y chatbot con IA, notificaciones push (app móvil). |
| Encargado | `encargado@fashionstore.com` | `Encargado123*` | Vinculado como personal de "Sucursal Central Equipetrol" (`id=1`). Gestiona las reservas recibidas por su sucursal en `/encargado`. |
| Cajero | `cajero@fashionstore.com` | `Cajero123*` | Vinculado a la misma sucursal. Registra ventas presenciales y procesa el cobro en caja (efectivo/tarjeta/QR) en `/caja`. |
| Proveedor | `proveedor@fashionstore.com` | `Proveedor123*` | Vinculado a "Proveedor Demo S.R.L.". Registra productos e informa disponibilidad en `/proveedor` (CU-33, CU-34); los productos quedan inactivos hasta que el Administrador los valida. |

#### Moda Andina — dirección `moda-andina`, plan Básico

El plan Básico permite hasta 2 sucursales e incluye productos, ventas, reservas, operación sin conexión, reportes, asistente con IA, vestidor virtual y pago con QR. Lo único que no incluye es la IA generativa de reportes (reportes con IA, pedir reportes personalizados con palabras o voz, y analítica ML): eso se ve bloqueado, con el aviso para mejorar el plan. El constructor de reportes personalizados, la bitácora y el respaldo sí están.

| Rol | Correo | Contraseña | Para probar |
|---|---|---|---|
| Administrador | `admin@modaandina.com` | `Admin123*` | Dashboard de su empresa, con los límites y bloqueos del plan Básico (`/admin/plan` muestra el plan y su uso). |
| Encargado | `encargado@modaandina.com` | `Encargado123*` | Reservas e inventario de su sucursal en `/encargado`. |
| Cajero | `cajero@modaandina.com` | `Cajero123*` | Ventas presenciales y cobro en `/caja`. |
| Cliente | `cliente@modaandina.com` | `Cliente123*` | Catálogo de Moda Andina. No ve productos ni datos de FashionStore (aislamiento entre empresas). |

## Guía de uso por rol

Qué hace cada rol, en qué pantalla y cómo se usa, en la web y en la app móvil. Las contraseñas están en [Credenciales de prueba](#credenciales-de-prueba) y los recorridos para comprobar cada función, en [Cómo probar](#cómo-probar).

### Cómo entrar

| | Web | App móvil |
|---|---|---|
| Dónde | https://fashionstore-uagrm.up.railway.app. En Chrome o Edge aparece el botón **Instalar app** para usarla como aplicación | APK compilada contra el backend de Railway (ver [App móvil](#5-app-móvil)) |
| Elegir la empresa | Entrar por `/t/<dirección>/login`, por ejemplo `/t/moda-andina/login`. FashionStore también responde en `/login` | Escribir la dirección (`fashionstore` o `moda-andina`) en el campo **Empresa** del login |
| Superadmin | `/plataforma` | No está en la app |
| Crear una empresa nueva | `/crear-tienda` | No está en la app |

Al iniciar sesión en la web, cada rol cae en su pantalla: el Administrador en `/admin`, el Encargado en `/encargado`, el Cajero en `/caja`, el Proveedor en `/proveedor` y el Cliente en el catálogo. En la app todos empiezan en el catálogo, y el menú (☰) muestra solo las opciones de su rol.

### Resumen

| Rol | Web | App móvil |
|---|---|---|
| Visitante (sin cuenta) | Catálogo, detalle de prendas y asistente con IA | Catálogo, sucursales y asistente con IA |
| Cliente | Catálogo, vestidor virtual, reservas, carrito y pago, mis compras, recomendaciones y asistente | Lo mismo, más notificaciones push y reservas sin conexión |
| Cajero | Caja: ventas en tienda, cobro, comprobante y cambio de prendas | Venta de contado con o sin conexión, y operaciones pendientes |
| Encargado | Reservas e inventario de su sucursal | Conflictos de sincronización, reportes con IA y operaciones pendientes |
| Administrador | Panel de la empresa (13 pestañas) y **Mi plan** | Venta de contado, conflictos, reportes con IA y analítica ML |
| Proveedor | Sus productos y la disponibilidad que informa | No está en la app |
| Superadmin | Panel de la plataforma: indicadores, empresas, planes, reportes, bitácora y respaldo | No está en la app |

### Cliente

**Web**
1. **Catálogo** (`/catalogo`): filtrar por categoría, colección, temporada, talla y color. Al tocar una prenda se abre su detalle, con las variantes (talla y color) y el stock.
2. **Vestidor virtual**: en el detalle de la prenda, botón **Vestidor Virtual**. Tiene dos modos:
   - *IA generativa*: se saca una foto con la cámara (o se sube una) y la IA devuelve una imagen de la persona con la prenda puesta. Tarda unos segundos. Usa Replicate: el backend necesita `REPLICATE_API_TOKEN` y crédito cargado en esa cuenta (sin crédito responde "Insufficient credit") y la prenda tiene que tener foto.
   - *AR en vivo*: la cámara sigue el cuerpo y dibuja la prenda encima en tiempo real.
3. **Reservar para probar en sucursal**: elegir la variante y la sucursal, donde se ve el stock real de cada una. La reserva es gratis y queda *pendiente* hasta que el encargado aparta las prendas.
4. **Mis Reservas** (`/reservas`): ver el estado de cada reserva y cancelar las que siguen pendientes. Al cancelar, el stock vuelve a la sucursal.
5. **Carrito** (`/carrito`): pagar con tarjeta (Stripe) o con QR (Libélula). Mientras se paga, las prendas quedan apartadas 15 minutos.
6. **Mis Compras** (`/mis-compras`): historial de compras y comprobante en PDF.
7. **Recomendado para ti**: prendas que sugiere la IA según lo que el cliente compró y reservó.
8. **Asistente** (botón flotante): responde sobre tallas, stock y cómo reservar. Funciona también sin cuenta.

**App móvil:** lo mismo (catálogo, vestidor con los dos modos, reservar, mis reservas, carrito, mis compras y asistente), más:
- **Notificaciones push** cuando cambia el estado de una reserva o se aprueba un pago.
- **Sin conexión:** el catálogo guardado se sigue viendo, y una reserva hecha sin Internet queda en **Operaciones pendientes** hasta que vuelve la conexión, que la envía sola.

### Cajero

**Web: caja** (`/caja`)
1. Armar la venta de una de dos formas:
   - **Cargar desde reserva atendida**: trae las prendas de una reserva que el encargado ya marcó como atendida.
   - **Agregar prenda de mostrador**: elegir la prenda, la talla y el color.
2. **Cobrar** en efectivo (calcula el cambio), con tarjeta POS o con QR (Libélula): el cliente escanea el QR desde la pantalla de la caja.
3. Se emite el **comprobante**, para imprimir o descargar en PDF.
4. **Cambio de prenda**: elegir la venta, lo que el cliente devuelve y lo que se lleva. Se acepta hasta 7 días después de la compra y solo por prendas de igual o mayor valor; la diferencia se cobra en efectivo.

Sin conexión, la caja sigue funcionando, pero solo cobra en efectivo. La venta queda en la cola de la barra superior y se envía sola cuando vuelve Internet.

**App móvil**
- **Venta de contado**: buscar la prenda por nombre o código de barras, elegir el cliente (o "cliente ocasional"), cobrar en efectivo y emitir un comprobante provisional. Funciona con o sin conexión.
- **Operaciones pendientes**: cada operación registrada en el teléfono, con su estado: *registrada* (solo en el teléfono), *enviada*, *confirmada*, *rechazada* o *conflicto*.

### Encargado

**Web** (`/encargado`)
- **Reservas** de su sucursal, filtradas por estado:
  1. **Apartar prendas**: confirma que separó las prendas (de *pendiente* a *confirmada*).
  2. **Atender cliente (vestidor)**: el cliente llegó a probarse (de *confirmada* a *atendida*). Desde ahí el cajero la puede cobrar.
  3. **No se presentó**: cierra la reserva y devuelve las prendas al stock.

  Cada paso le avisa al cliente con una notificación push.
- **Inventario de mi sucursal**: registrar ingresos, devoluciones, mermas y ajustes. No deja sacar más de lo que hay.

**App móvil**
- **Conflictos de sincronización**: decidir qué hacer con una operación sin conexión que chocó con el stock central (ver la pestaña *Resolución de Conflictos* del [Administrador](#administrador)).
- **Reportes e IA**: pedir un reporte con palabras, por ejemplo "ventas por sucursal de este mes". Requiere el plan Profesional.
- **Operaciones pendientes**.

### Administrador

**Web: panel de la empresa** (`/admin`)

| Pestaña | Qué se hace |
|---|---|
| Roles y Permisos | Crear roles y marcar qué permisos tiene cada uno |
| Personal | Dar de alta cajeros y encargados, y asignarles una sucursal |
| Sucursales | Sucursales y ciudades. El plan limita cuántas sucursales se pueden tener |
| Proveedores | Registrar proveedores y ver la disponibilidad que informan |
| Catálogo de Prendas | Prendas con foto, variantes por talla y color (con código de barras), alta y baja. Aquí se activan los productos que registra un proveedor |
| Catálogo Maestro | Categorías, tallas y colores |
| Temporadas | Temporadas y colecciones |
| Reportes | Indicadores, inventario global, reportes fijos (ventas por sucursal, prendas más vendidas, ventas por categoría y quiebres de stock) en CSV, y un análisis con IA pedido por texto o por voz (plan Profesional) |
| Reportes personalizados | 7 reportes: ventas, prendas vendidas, existencias, reservas, personal, movimientos de inventario y bitácora. Se eligen las columnas y su orden, los criterios, las fechas y el orden de las filas, y se exporta a Excel, PDF o HTML, o se envía por correo. En el plan Profesional también se piden con palabras o por voz |
| Bitácora de Auditoría | Cada acción hecha en la empresa, con fecha y hora de Bolivia, usuario, rol e IP. Se filtra por fecha, usuario y acción, y se exporta. Los intentos fallidos aparecen resaltados |
| Respaldo | Descargar un respaldo de los datos de la empresa y restaurarlo. **Verificar respaldo** muestra qué se restauraría sin cambiar nada |
| Resolución de Conflictos | Operaciones sin conexión que chocaron con el stock central. Hay tres decisiones: **aceptar con ajuste** (registra la venta y el faltante en el kardex), **reasignar** a otra sucursal con stock o **anular** |
| Analítica Machine Learning | Predicción de la demanda de las próximas semanas (regresión Ridge, con sus métricas R² y MAE) y segmentación de clientes con K-Means. Plan Profesional |

**Mi plan** (`/admin/plan`, botón arriba a la derecha del panel): plan actual, uso de los cupos, cambio de plan, renovación por 1, 3, 6 o 12 meses (el cobro es simulado) e historial de la suscripción.

**App móvil:** venta de contado, conflictos de sincronización y **Reportes e IA**, que además del reporte con palabras muestra la analítica ML.

### Proveedor

**Web** (`/proveedor`)
- **Registrar producto**: el producto queda inactivo hasta que el administrador lo revisa y lo activa en *Catálogo de Prendas*. Al activarlo, los clientes reciben un aviso push.
- **Informar disponibilidad**: cuántas unidades podrá entregar y desde cuándo. Avisa por push a los administradores. Debajo queda el historial de lo informado.

### Superadmin

**Web: panel de la plataforma** (`/plataforma`). El superadmin no pertenece a ninguna empresa: administra el servicio.

| Pestaña | Qué se hace |
|---|---|
| Indicadores | Ingresos por suscripciones de los últimos 6 meses, empresas por plan, ventas por empresa y próximos vencimientos |
| Empresas | Dar de alta una empresa con su administrador y su plan, cambiarle el plan, renovarla por 1 mes, cancelar o reactivar la suscripción, y suspender o reactivar la empresa |
| Planes | Crear planes y configurar el precio, los cupos (sucursales, prendas y personal) y las funciones incluidas |
| Reportes | Reportes personalizados de toda la plataforma (empresas, ingresos, uso de los planes, ventas, historial de suscripciones y bitácora), también pedidos con palabras o por voz |
| Bitácora | Las acciones de todas las empresas y las del propio superadmin |
| Respaldo | Respaldo y restauración del sistema completo o de una sola empresa |

### Empresa nueva (alta pública)

En `/crear-tienda` cualquiera puede contratar el servicio: completa el nombre de la empresa, la dirección (queda en `/t/<dirección>`), el correo y la contraseña del administrador, y elige el plan. Después, ese administrador entra por `/t/<dirección>/login` y arma su tienda desde cero.

### Planes

| | Básico | Profesional |
|---|---|---|
| Sucursales | Hasta 2 | Hasta 10 |
| Productos, ventas, reservas, operación sin conexión, reportes fijos y personalizados, bitácora, respaldo, asistente, vestidor virtual y pago con QR | Sí | Sí |
| Análisis con IA, reportes personalizados pedidos con palabras o voz, y analítica ML | No: se ve bloqueado, con el aviso para mejorar el plan | Sí |

Los cupos y las funciones de cada plan se cambian desde el panel del superadmin. Si la suscripción vence o se cancela, la empresa queda **en modo consulta**: se puede ver todo pero no registrar nada, y el administrador ve el aviso para renovar.

## Cómo probar

### Recorridos manuales

Se pueden hacer en la web desplegada o en local. Conviene tener dos ventanas (una normal y una de incógnito) para usar dos roles a la vez.

**1. De la reserva a la caja**
1. Cliente (web o app): reservar una prenda en *Sucursal Central Equipetrol*.
2. Encargado (`/encargado`): la reserva aparece *pendiente*. Tocar **Apartar prendas** y después **Atender cliente**.
3. Cajero (`/caja`): **Cargar desde reserva atendida**, cobrar en efectivo y emitir el comprobante.
4. Cliente: la compra aparece en **Mis Compras**, con su PDF.

Resultado esperado: al reservar, el stock pasa de disponible a reservado, y al vender se descuenta. Si el cliente tiene la app abierta y el backend tiene configurado Firebase, cada paso del encargado le llega como notificación push.

**2. Compra online**
1. Cliente: agregar prendas al carrito y elegir **QR (Libélula)**.
2. En modo de prueba aparece el botón **Simular pago (modo de prueba)**, que confirma el pago como si se hubiera escaneado el QR.
3. Se emite el comprobante y la compra queda en **Mis Compras**.

Con tarjeta, si el backend tiene configurado Stripe, se usa la tarjeta de prueba `4242 4242 4242 4242` con cualquier fecha futura y cualquier CVC.

**3. Venta sin conexión en la web**
1. Entrar como cajero en la web desplegada, con Internet, para que se descarguen los datos.
2. Cortar la conexión (apagar el WiFi, o en DevTools → Network → Offline). Aparece el aviso **Sin conexión**, pero la caja sigue funcionando.
3. Hacer una venta en efectivo: el indicador de la cola, en la barra superior, muestra una operación pendiente.
4. Recargar la página sin conexión: la venta sigue en la cola.
5. Volver a conectar: la venta se envía sola y pasa a *confirmada*.

Con `ng serve` esto no funciona, porque el service worker solo existe en la compilación de producción: hay que probarlo en la web desplegada o con `ng build`.

**4. Venta sin conexión en la app**
1. Entrar como cajero, con conexión, al menos una vez.
2. Activar el modo avión, abrir el menú → **Venta de contado** y vender en efectivo.
3. **Operaciones pendientes** muestra la venta como *registrada*. Cerrar la app y abrirla de nuevo: sigue ahí.
4. Quitar el modo avión: la venta pasa sola a *confirmada*.

**5. Conflicto de stock**
1. Encargado: en **Inventario de mi sucursal**, dejar una variante con 1 unidad.
2. Teléfono A, como cajero y sin conexión: vender esa unidad.
3. Mientras tanto, desde la web con conexión, vender la misma unidad.
4. Reconectar el teléfono A: su venta queda en *conflicto*.
5. Decidir el conflicto: el administrador desde la web (**Resolución de Conflictos**), o el encargado o el administrador desde la app (**Conflictos de sincronización**). Se puede aceptar con ajuste, reasignar o anular, y la decisión queda en la bitácora.

**6. Cambio de prenda**
1. Cajero: **Cambio de prenda** y elegir una venta reciente.
2. Devolver una prenda y llevarse otra de igual o mayor valor: se acepta y se cobra la diferencia.
3. Intentar llevarse una de menor valor: se rechaza.

**7. Reportes con IA y por voz**
1. Administrador de FashionStore (plan Profesional) → **Reportes personalizados**: escribir "prendas sin stock", o tocar el micrófono y decirlo (funciona en Chrome y Edge).
2. Se arma el reporte con sus columnas y criterios, y se exporta a Excel o PDF.
3. Un pedido que no tiene que ver con los datos (por ejemplo, "¿quién gana el mundial?") responde con ejemplos de lo que sí se puede pedir.
4. Administrador de Moda Andina (plan Básico): la misma pestaña muestra el aviso del plan en lugar del pedido con IA, pero el constructor funciona.

**8. Aislamiento entre empresas**
- `cliente@modaandina.com` solo ve el catálogo de Moda Andina.
- Las cuentas de una empresa no sirven en otra: `admin@fashionstore.com` no puede iniciar sesión en `/t/moda-andina/login`.

**9. Bitácora**
1. Intentar entrar con una contraseña equivocada.
2. Administrador → **Bitácora de Auditoría**: aparece el intento fallido, resaltado, con la hora y la IP.
3. Superadmin → **Bitácora**: aparecen las acciones de todas las empresas.

**10. Respaldo**
1. Administrador → **Respaldo** → **Descargar respaldo**.
2. Elegir ese archivo y tocar **Verificar respaldo**: muestra cuántos registros de cada tabla se restaurarían, sin cambiar nada.
3. La restauración real reemplaza los datos: hacerla solo en una empresa de prueba.

**11. Planes y suscripción**
1. Superadmin → **Empresas**: dar de alta una empresa con el plan Básico.
2. Entrar como su administrador y crear sucursales: la tercera se rechaza por el cupo del plan.
3. Superadmin: pasarla al plan Profesional. Ahora sí se puede crear.
4. Superadmin: cancelar la suscripción. La empresa queda en modo consulta: ve todo, pero no puede registrar nada. Reactivarla al terminar.

### Tests automáticos

| Parte | Comando | Qué cubre |
|---|---|---|
| Backend (pytest) | Ver abajo | Login y permisos, aislamiento entre empresas (RLS), planes y cupos, sincronización sin conexión (idempotencia, conflictos y cambios), concurrencia de stock, pago con QR, reportes, bitácora y respaldo |
| Web (Vitest) | `cd frontend-web && npm test -- --watch=false` | Servicios de la cola sin conexión y de la empresa, login, catálogo, reservas, carrito, pago con QR, panel de administración, reportes personalizados, bitácora y respaldo |
| App (flutter test) | `cd mobile-app && flutter test` | Cola sin conexión, conflictos, mis compras y robustez de la venta |

El backend se prueba contra un Postgres local desechable, **nunca con el `DATABASE_URL` del `.env`**, que apunta a la base real:

```bash
docker run -d --name fs-pg-pruebas -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=fashionstore -p 54329:5432 postgres:16-alpine
cd backend
export DATABASE_URL=postgresql://postgres:postgres@localhost:54329/fashionstore   # en PowerShell: $env:DATABASE_URL="..."
python preparar_bd_pruebas.py   # crea el esquema y los datos semilla; se niega a correr contra una base que no sea local
python -m pytest -q
```

GitHub Actions (`.github/workflows/ci.yml`) corre los tests del backend y de la web, y compila la web, en cada push a `main` o `Antonio`.

## Base de datos compartida — cosas a tener en cuenta

- **Todos trabajan contra la misma base en Supabase.** Un cambio de datos o de esquema que hagas lo ve el otro al instante.
- **Nunca modifiques el esquema corriendo SQL a mano en Supabase.** Cualquier cambio de tabla/columna va por una migración de Alembic (ver `backend/README.md`), así queda documentado y el otro solo necesita `alembic upgrade head` después de un `git pull`.
- Si necesitas romper cosas para probar (borrar datos, resetear una tabla), usa el Postgres local opcional en vez de tocar la base compartida:
  ```bash
  docker compose --profile local-db up -d postgres
  ```
  Se levanta en `localhost:5433` con usuario/clave/DB `fashionstore` / `fashionstore` / `fashionstore` (mismo valor los tres, definido en `docker-compose.yml`) y corre automáticamente `database/schema.sql` + `database/init-seeds.sql` al crearse por primera vez.
- `database/schema.sql` es la referencia histórica del diseño original — el esquema real y vivo se gestiona desde `backend/app/models/` + Alembic.

## Backend desplegado (Railway)

Además de correr local con Docker, el backend está desplegado en **Railway** para que se pueda probar la app (sobre todo la móvil) sin tener que levantar nada localmente: `https://fashionstore-backend-production-4c32.up.railway.app` (mismo `/docs` para Swagger, mismo `/health`). Se conecta a la misma Supabase compartida, así que ve los mismos datos que el entorno local.

- Se despliega automáticamente en cada push a `main` (Root Directory = `backend`, usa `backend/Dockerfile`).
- Las variables de entorno se configuran en Railway → servicio → pestaña **Variables** (mismo contenido que el `.env` local).
- **Ojo con el puerto**: Railway asigna su propio puerto dinámico vía la variable `PORT` y a veces no respeta un `PORT` fijado a mano en Variables. El `Dockerfile` ya escucha en `${PORT:-8000}`, pero si Railway devuelve **502 "Application failed to respond"**, hay que revisar en Settings → Networking en qué puerto quedó escuchando Uvicorn (mirando los Deploy Logs) y editar ahí el puerto del dominio público para que coincida — no alcanza con solo declarar la variable `PORT`.
- El APK de release para compartir con alguien fuera del equipo se compila apuntando a esta URL:
  ```bash
  cd mobile-app
  flutter build apk --release --dart-define=API_URL=https://fashionstore-backend-production-4c32.up.railway.app
  ```
  El archivo queda en `mobile-app/build/app/outputs/flutter-apk/app-release.apk`. **WhatsApp bloquea el envío de archivos `.apk` directo por chat** (los detecta por contenido, no solo por extensión) — para pasarlo hay que subirlo a Drive/Telegram/un link y compartir eso, o comprimirlo en un `.zip` antes.

## Ramas

- `main` — rama estable, con lo ya integrado de ambos.
- `Antonio` — desarrollo activo de Antonio (CU-09 en adelante).
- `jhonny` — desarrollo de Jhonny (ya mergeada a `main`, puede reabrirse para nuevo trabajo).

## Documentación del proyecto

- `docs/diseno_logico.md` — diseño lógico visual de las 25 tablas (formato tabla + PK + FKs).
- `docs/modelo_datos_logico.md` — modelo de datos en tablas markdown, con las decisiones de diseño explicadas.
- `docs/ea-scripts/diagrama_clases.js` — genera el diagrama de clases UML en Enterprise Architect (ver instrucciones dentro del archivo).
- Documento del examen (Perfil + PUDS + Casos de Uso + Paquetes de análisis) — está fuera del repo, pídelo si no lo tienes.
