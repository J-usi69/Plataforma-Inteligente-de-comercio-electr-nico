# FashionStore

Plataforma inteligente de comercio electrónico para una cadena de tiendas de ropa: catálogo con vestidor virtual (RA), reserva de prendas para prueba física, compra presencial o digital, inventario centralizado por sucursal e inteligencia artificial (recomendación, chatbot y reportes).

Trabajo del **Primer Examen Parcial — Sistemas de Información 2** (Grupo 13). El enunciado completo, los casos de uso (CU-01 a CU-34) y el análisis de paquetes están en `docs/` — léelo antes de tocar código, ahí está el detalle de cada flujo.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python + FastAPI + SQLAlchemy + Alembic |
| Web | Angular (standalone) |
| Móvil | Flutter/Dart |
| Base de datos | PostgreSQL, alojada en **Supabase** (compartida por todo el equipo) |
| Despliegue final | Google Cloud Platform (Cloud Run, Cloud SQL, Cloud Storage) |

## Estado actual del proyecto

Ya está armado y commiteado:

- **Modelo de datos completo** (23 tablas): usuarios/personal separados, RBAC (rol/permiso), bitácora de auditoría, catálogo (prenda/variante/talla/color/categoría/temporada/colección), inventario por sucursal + histórico de movimientos, reservas (funcionan como "carrito" del cliente, no hay tabla `carrito` separada), ventas/pagos, e interacción con IA.
- **Base de datos ya creada en Supabase** con ese esquema aplicado — no hace falta crearla, solo conectarse (ver sección de configuración abajo).
- **Backend FastAPI**: estructura base con modelos SQLAlchemy (1:1 con la base real, verificado sin diffs vía `alembic --autogenerate`) y flujo de migraciones con Alembic ya andando.
- **Frontend web (Angular)**: esqueleto con rutas y páginas placeholder por módulo (`login`, `catalogo`, `reservas`, `carrito`, `admin`).
- **App móvil (Flutter)**: esqueleto con `go_router` y pantallas placeholder, incluyendo la pantalla del vestidor virtual AR (`/vestidor-ar`).
- **Diagrama de clases UML**: script para generar en Enterprise Architect en `docs/ea-scripts/diagrama_clases.js`.

Lo que falta: implementar la lógica real de cada caso de uso (endpoints del backend, pantallas funcionales en web/móvil), integrar pasarela de pago, IA y vestidor AR.

## Estructura del repositorio

```
database/
  schema.sql                 # DDL de referencia (documenta el diseño original)
docs/
  modelo_datos_logico.md     # Modelo lógico en tablas
  ea-scripts/
    diagrama_clases.js        # Script para regenerar el diagrama de clases en EA
backend/
  app/
    core/config.py            # Settings (lee el .env de la raíz)
    db/session.py              # Engine, SessionLocal, Base declarativa
    models/                     # Modelos SQLAlchemy (fuente de verdad del esquema)
    main.py                      # App FastAPI
  alembic/                        # Migraciones (ver backend/README.md para el flujo)
  requirements.txt
frontend-web/                      # Angular
  src/app/core/                     # Servicios compartidos (ApiService, guards, models)
  src/app/features/                  # Un folder por módulo: auth, catalogo, reservas, ventas, admin
mobile-app/                          # Flutter
  lib/core/                           # Config (Env) y servicios (ApiService)
  lib/features/                        # auth, catalogo, reservas, ventas, vestidor_ar
docker-compose.yml                     # Postgres local opcional (para pruebas destructivas sin tocar Supabase)
```

## Configuración inicial (para cada integrante del equipo)

### 1. Variables de entorno

Pide el archivo `.env` real por WhatsApp/Drive (no está en el repo por seguridad — el repo es público y contiene la contraseña de la base de datos compartida). Colócalo en la **raíz del repositorio**, al lado de `docker-compose.yml`. `/.env.example` muestra qué variables lleva.

### 2. Backend

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

### 3. Frontend web

```bash
cd frontend-web
npm install
ng serve
```

### 4. App móvil

```bash
cd mobile-app
flutter pub get
flutter run
```

Por defecto apunta a `http://10.0.2.2:8000` (así el emulador de Android ve el backend corriendo en tu máquina). Para apuntar a otra URL: `flutter run --dart-define=API_URL=http://tu-ip:8000`.

## Base de datos compartida — cosas a tener en cuenta

- **Todos trabajan contra la misma base en Supabase.** Un cambio de datos o de esquema que hagas lo ve el otro al instante.
- **Nunca modifiques el esquema corriendo SQL a mano en Supabase.** Cualquier cambio de tabla/columna va por una migración de Alembic (ver `backend/README.md`), así queda documentado y el otro solo necesita `alembic upgrade head` después de un `git pull`.
- Si necesitas romper cosas para probar (borrar datos, resetear una tabla), mejor usa el Postgres local de `docker-compose.yml` en vez de tocar la base compartida.
- `database/schema.sql` es la referencia histórica del diseño original — el esquema real y vivo se gestiona desde `backend/app/models/` + Alembic.

## Documentación del proyecto

- `docs/modelo_datos_logico.md` — modelo de datos en tablas, con las decisiones de diseño explicadas.
- `docs/ea-scripts/diagrama_clases.js` — genera el diagrama de clases UML en Enterprise Architect (ver instrucciones dentro del archivo).
- Documento del examen (Perfil + PUDS + Casos de Uso + Paquetes de análisis) — está fuera del repo, pídelo si no lo tienes.
