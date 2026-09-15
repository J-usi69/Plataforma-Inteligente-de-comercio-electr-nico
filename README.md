# FashionStore

Plataforma inteligente de comercio electrónico para una cadena de tiendas de ropa: catálogo con vestidor virtual (RA), reserva de prendas para prueba física, compra presencial o digital, inventario centralizado por sucursal e inteligencia artificial (recomendación, chatbot y reportes).

Trabajo del **Primer Examen Parcial — Sistemas de Información 2** (Grupo 13, UAGRM). El enunciado completo, los casos de uso (CU-01 a CU-34) y el análisis de paquetes están en `docs/` — léelo antes de tocar código, ahí está el detalle de cada flujo.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI + SQLAlchemy + Alembic |
| Web | Angular (standalone) |
| Móvil | Flutter/Dart |
| Base de datos | PostgreSQL, alojada en **Supabase** (compartida por todo el equipo) |
| Infraestructura local | Docker (backend + frontend, conectados directo a Supabase) |
| Despliegue final | Google Cloud Platform (Cloud Run, Cloud SQL, Cloud Storage) |

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

También implementado (CU-17 a CU-27, a cargo de Jhonny): roles y permisos, personal, proveedores, temporadas/colecciones, gestión de reservas recibidas por sucursal (Encargado), ventas presenciales y digitales con pago electrónico (Stripe, modo test), comprobante oficial e historial de compras del cliente.

- **CU-28**: recomendaciones de prendas por IA (Gemini) para el Cliente, a partir de su historial de compras/reservas y el catálogo activo; si Gemini no responde a tiempo, cae en un fallback con las prendas más vendidas.
- **CU-29**: asistente conversacional (chatbot) con IA (Groq), disponible **incluso sin sesión iniciada** — funciona igual para un visitante que para un Cliente logueado (a un logueado además se le guarda el historial de interacción). Mantiene memoria de la conversación (se manda el historial de turnos en cada mensaje) y su prompt está anclado a datos reales del negocio (moneda en Bolivianos, reserva sin costo) para no inventar precios ni políticas.
- **CU-30**: generación de reportes en lenguaje natural por IA (Mistral) para el Administrador, reusando los mismos endpoints de reportes predefinidos.
- **CU-31/CU-32**: reportes predefinidos (ventas por sucursal, prendas más vendidas, quiebres de stock) y dashboard de indicadores con datos reales agregados en el backend.
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

### Flujo actual por rol de usuario

El sistema diferencia el rol en el login y cada uno tiene su propia pantalla.

- **Administrador** (`admin@fashionstore.com`): al loguearse entra directo al **Dashboard admin** (`/admin`) — ahí gestiona roles y permisos, personal, sucursales, proveedores, todo el catálogo maestro (categorías, tallas, colores, temporadas, colecciones, prendas y variantes), el dashboard de indicadores y reportes (predefinidos o generados con IA en lenguaje natural).
- **Cliente** (`cliente@fashionstore.com`): al loguearse cae en el **catálogo público** (`/catalogo`, misma pantalla que ve un visitante sin cuenta) y desde ahí puede filtrar prendas, tocar cualquier tarjeta de producto para ver su detalle completo, reservar una variante en la sucursal con stock disponible, ver/cancelar sus reservas (`/reservas`), comprar desde el carrito con pago por pasarela digital (Stripe, modo test), consultar su historial de compras (`/mis-compras`), ver un carrusel de "Recomendado para ti" (IA), chatear con el asistente virtual y usar el vestidor virtual con IA (**solo disponible en la app móvil por ahora**, no en la web). En la app móvil además recibe notificaciones push sobre sus reservas y compras.
- **Encargado** (`encargado@fashionstore.com`, vinculado como personal de la Sucursal Central Equipetrol): tiene su propia pantalla (`/encargado`) para ver las reservas entrantes de su sucursal, confirmar que apartó las prendas ("Apartar Prendas"), confirmar la recepción del cliente ("Atender Cliente") o marcarla como no presentada ("No se presentó") — cada una de estas tres acciones le manda un push al celular del Cliente.
- **Cajero** (`cajero@fashionstore.com`, misma sucursal): tiene su propia pantalla de caja (`/caja`) para cargar una reserva ya atendida o agregar prendas de mostrador, cobrar la venta y emitir el comprobante.
- **Proveedor** (`proveedor@fashionstore.com`, vinculado a "Proveedor Demo S.R.L."): tiene su propia pantalla (`/proveedor`) para registrar sus propios productos (quedan inactivos hasta que el Administrador los valida y reactiva — eso dispara un push a todos los Clientes) e informar disponibilidad futura de stock (dispara un push a los Administradores).

### Frontend web (Angular)
Login/registro funcionales contra la API real, interceptor de autenticación JWT, dashboard administrativo con listados (roles, personal, sucursales, proveedores, catálogo, reportes/dashboard), panel propio de Proveedor, asistente conversacional flotante (disponible sin sesión iniciada), catálogo con tarjetas de producto clickeables, servicios `AuthService`/`ApiService`/`BusinessService`.

### App móvil (Flutter)
Login/registro/perfil funcionales contra la API real, listado de sucursales, catálogo de prendas con filtros por talla/color y tarjetas de producto clickeables (abren el detalle completo: categoría, descripción, variantes, accesos directos a 3D RA/Reservar/Comprar), reserva de variante en sucursal (`/reservar`) y gestión de "Mis Reservas" (`/reservas`), vestidor virtual con IA (`/vestidor-ar` — cámara + Replicate, único lugar donde el CU-14 está integrado por ahora), carrusel de recomendaciones y pantalla de chat con el asistente (`/asistente`, funciona sin sesión iniciada), y notificaciones push nativas vía Firebase Cloud Messaging (se registra el token del dispositivo al iniciar sesión).

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

Válidas contra la Supabase compartida. Úsalas contra `POST /api/v1/auth/login` (body `{"login": "...", "password": "..."}`) para obtener un token y probar los endpoints protegidos desde `/docs`, o directamente desde el login de la web/app móvil:

| Rol | Correo | Contraseña | Para probar |
|---|---|---|---|
| Administrador | `admin@fashionstore.com` | `Admin123*` | Dashboard admin completo: roles/permisos, personal, sucursales, proveedores, catálogo maestro (categorías/tallas/colores/temporadas/colecciones), prendas y variantes. |
| Cliente | `cliente@fashionstore.com` | `Cliente123*` | Catálogo público, filtros por talla/color/temporada, reservar prenda en sucursal, ver/cancelar "Mis Reservas", vestidor virtual con IA, recomendaciones y chatbot con IA, notificaciones push (app móvil). |
| Encargado | `encargado@fashionstore.com` | `Encargado123*` | Vinculado como personal de "Sucursal Central Equipetrol" (`id=1`). Gestiona las reservas recibidas por su sucursal en `/encargado`. |
| Cajero | `cajero@fashionstore.com` | `Cajero123*` | Vinculado a la misma sucursal. Registra ventas presenciales y procesa el cobro en caja (efectivo/tarjeta/QR) en `/caja`. |
| Proveedor | `proveedor@fashionstore.com` | `Proveedor123*` | Vinculado a "Proveedor Demo S.R.L.". Registra productos e informa disponibilidad en `/proveedor` (CU-33, CU-34); los productos quedan inactivos hasta que el Administrador los valida. |

### Cómo probar el flujo completo (guía rápida para Jhonny)

1. `git pull` sobre `main`, luego `docker compose up -d --build` (ver sección 2 más arriba). Backend en `http://localhost:8000`, web en `http://localhost:4200`, ambos contra la Supabase compartida — no necesitas tocar nada de datos, ya está todo sembrado.
2. **Como Cliente** (`cliente@fashionstore.com` / `Cliente123*`):
   - En la web, entra al catálogo (ya hay 5 prendas de ejemplo con imagen, una por categoría) y prueba los filtros de categoría/talla/color.
   - Abre una prenda → botón **"Reservar para probar en sucursal"** → elige variante (talla/color) → elige sucursal (te muestra el stock disponible real) → confirma. Luego revisa **"Mis Reservas"** y prueba cancelarla.
   - El mismo flujo de catálogo + reserva funciona igual en la app móvil (Flutter), con el botón **"Reservar"** en cada tarjeta.
3. **Vestidor virtual con IA (CU-14) — solo disponible en la app móvil por ahora**, no en la web (la web solo muestra un aviso). Desde el catálogo en Flutter, botón **"Probar con RA"** → toma una foto con la cámara → el backend llama a Replicate (modelo `prunaai/p-image-try-on`) y devuelve la imagen generada. **Importante:** cada integrante necesita su propio `REPLICATE_API_TOKEN` en su `.env` local (ver sección 1) y crédito cargado en su cuenta de Replicate (https://replicate.com/account/billing) — sin crédito, el job falla con "Insufficient credit" (no es un bug, es facturación).
4. **Como Administrador**, revisa el módulo de Roles y Permisos (`admin@fashionstore.com`) — el modal de edición de rol ahora se ve bien alineado (checkboxes + descripción de cada permiso).
5. Si necesitas resetear o agregar más datos de catálogo para tus propias pruebas, hazlo con `INSERT`/`UPDATE` normales sobre `prenda`, `variante_prenda` e `inventario_sucursal` (o pídeme que te pase el script) — evita usar el Postgres local para esto porque entonces no lo ves reflejado en la web/app que sí apunta a Supabase.

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
