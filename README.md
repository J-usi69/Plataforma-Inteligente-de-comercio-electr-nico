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

También implementado: gestión de reservas recibidas por sucursal (Encargado), ventas presenciales y digitales con pagos, comprobante oficial e historial de compras del cliente — a cargo de Jhonny.

### Flujo actual por rol de usuario

El sistema diferencia el rol en el login y cada uno tiene su propia pantalla.

- **Administrador** (`admin@fashionstore.com`): al loguearse entra directo al **Dashboard admin** (`/admin`) — ahí gestiona roles y permisos, personal, sucursales, proveedores y todo el catálogo maestro (categorías, tallas, colores, temporadas, colecciones, prendas y variantes).
- **Cliente** (`cliente@fashionstore.com`): al loguearse cae en el **catálogo público** (`/catalogo`, misma pantalla que ve un visitante sin cuenta) y desde ahí puede filtrar prendas, reservar una variante en la sucursal con stock disponible, ver/cancelar sus reservas (`/reservas`), comprar desde el carrito con pago por pasarela digital simulada (`/carrito`), consultar su historial de compras (`/mis-compras`) y usar el vestidor virtual con IA (**solo disponible en la app móvil por ahora**, no en la web).
- **Encargado** (`encargado@fashionstore.com`, vinculado como personal de la Sucursal Central Equipetrol): tiene su propia pantalla (`/encargado`) para ver las reservas entrantes de su sucursal, confirmar que apartó las prendas, confirmar la recepción del cliente o marcarla como no presentada.
- **Cajero** (`cajero@fashionstore.com`, misma sucursal): tiene su propia pantalla de caja (`/caja`) para cargar una reserva ya atendida o agregar prendas de mostrador, cobrar la venta y emitir el comprobante.

### Frontend web (Angular)
Login/registro funcionales contra la API real, interceptor de autenticación JWT, dashboard administrativo con listados (roles, personal, sucursales, proveedores, catálogo), servicios `AuthService`/`ApiService`/`BusinessService`.

### App móvil (Flutter)
Login/registro/perfil funcionales contra la API real, listado de sucursales, catálogo de prendas con filtros por talla/color, reserva de variante en sucursal (`/reservar`) y gestión de "Mis Reservas" (`/reservas`), y vestidor virtual con IA funcional (`/vestidor-ar` — cámara + Replicate, único lugar donde el CU-14 está integrado por ahora).

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
    api/v1/endpoints/                 # Un archivo por caso de uso/módulo (auth, prendas, roles, etc.)
    main.py                            # App FastAPI (CORS + router /api/v1)
  alembic/                              # Migraciones (ver backend/README.md para el flujo)
  tests/                                 # Tests de CU-01 a CU-08
  requirements.txt
frontend-web/                            # Angular
  Dockerfile
  nginx.conf
  src/app/core/                           # AuthService, ApiService, BusinessService, interceptor JWT
  src/app/features/                        # Un folder por módulo: auth, catalogo, reservas, ventas, admin
mobile-app/                                # Flutter
  lib/core/                                 # Config (Env) y ApiService (singleton con token/currentUser)
  lib/features/                              # auth, catalogo, reservas, sucursales, ventas, vestidor_ar
docker-compose.yml                           # backend + frontend (conectados a Supabase vía .env)
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

# --- Pasarela de pago (completar cuando se integre) ---
PAYMENT_GATEWAY_API_KEY=

# --- IA (completar cuando se integre) ---
AI_API_KEY=

# --- Vestidor virtual / Try-On con IA (CU-14) ---
# Token de Replicate: https://replicate.com/account/api-tokens (cada integrante debe generar el suyo)
REPLICATE_API_TOKEN=
TRYON_REPLICATE_MODEL=prunaai/p-image-try-on
```

`.env.example` tiene la misma plantilla sin valores reales, por si se pierde este archivo.

**`REPLICATE_API_TOKEN` queda vacío a propósito** — es una clave personal de facturación por uso, cada integrante debe crear su propia cuenta gratuita en [replicate.com](https://replicate.com) y generar su token. Sin ese token, todo el resto del sistema funciona normal; solo el vestidor virtual (CU-14) responde "no configurado".

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

Por defecto apunta a `http://10.0.2.2:8000` (así el emulador de Android ve el backend corriendo en tu máquina). Para apuntar a otra URL: `flutter run --dart-define=API_URL=http://tu-ip:8000`.

### Credenciales de prueba

Válidas contra la Supabase compartida. Úsalas contra `POST /api/v1/auth/login` (body `{"login": "...", "password": "..."}`) para obtener un token y probar los endpoints protegidos desde `/docs`, o directamente desde el login de la web/app móvil:

| Rol | Correo | Contraseña | Para probar |
|---|---|---|---|
| Administrador | `admin@fashionstore.com` | `Admin123*` | Dashboard admin completo: roles/permisos, personal, sucursales, proveedores, catálogo maestro (categorías/tallas/colores/temporadas/colecciones), prendas y variantes. |
| Cliente | `cliente@fashionstore.com` | `Cliente123*` | Catálogo público, filtros por talla/color/temporada, reservar prenda en sucursal, ver/cancelar "Mis Reservas", vestidor virtual con IA. |
| Encargado | `encargado@fashionstore.com` | `Encargado123*` | Vinculado como personal de "Sucursal Central Equipetrol" (`id=1`). Gestiona las reservas recibidas por su sucursal en `/encargado`. |
| Cajero | `cajero@fashionstore.com` | `Cajero123*` | Vinculado a la misma sucursal. Pensado para el módulo de ventas/POS (todavía no implementado). |

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

## Ramas

- `main` — rama estable, con lo ya integrado de ambos.
- `Antonio` — desarrollo activo de Antonio (CU-09 en adelante).
- `jhonny` — desarrollo de Jhonny (ya mergeada a `main`, puede reabrirse para nuevo trabajo).

## Documentación del proyecto

- `docs/diseno_logico.md` — diseño lógico visual de las 25 tablas (formato tabla + PK + FKs).
- `docs/modelo_datos_logico.md` — modelo de datos en tablas markdown, con las decisiones de diseño explicadas.
- `docs/ea-scripts/diagrama_clases.js` — genera el diagrama de clases UML en Enterprise Architect (ver instrucciones dentro del archivo).
- Documento del examen (Perfil + PUDS + Casos de Uso + Paquetes de análisis) — está fuera del repo, pídelo si no lo tienes.
