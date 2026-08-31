# FashionStore — Backend (FastAPI + PostgreSQL/Supabase)

## Configuración inicial (una sola vez por persona)

1. Copia el `.env` compartido a la raíz del repositorio (al lado de `docker-compose.yml`, un nivel arriba de `backend/`). Nunca lo subas a git.
2. Crea el entorno virtual e instala dependencias:

```bash
cd backend
py -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

3. Verifica la conexión:

```bash
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000/health` — debe responder `{"status": "ok"}`.

## Estructura

```
backend/
  app/
    core/config.py      # Settings (lee el .env de la raíz del repo)
    db/session.py        # Engine, SessionLocal, Base declarativa
    models/               # Modelos SQLAlchemy, uno por módulo (seguridad, catalogo, venta, etc.)
    main.py                # App FastAPI
  alembic/
    env.py                 # Configuración de Alembic (usa Settings, no hardcodea la URL)
    versions/               # Historial de migraciones
  alembic.ini
  requirements.txt
```

## Flujo de migraciones (Alembic)

La base de datos ya existe en Supabase con el esquema de `database/schema.sql`. Esa creación inicial quedó documentada como la migración `0001_baseline`, pero **su `upgrade()` no se ejecuta en Supabase** (las tablas ya existen) — en su lugar, la base se marcó como si ya estuviera en esa revisión:

```bash
alembic stamp 0001
```

Esto solo escribe en la tabla `alembic_version`, no toca ninguna tabla de datos.

### A partir de ahora, cualquier cambio de esquema sigue este flujo:

1. **Modifica los modelos SQLAlchemy** en `app/models/` (agregar columna, tabla nueva, etc.) — esta es la fuente de verdad del esquema, no `database/schema.sql` (ese archivo queda como referencia histórica del diseño original).
2. **Genera la migración automáticamente**, comparando los modelos contra la base real:

```bash
alembic revision --autogenerate -m "descripcion corta del cambio"
```

3. **Revisa el archivo generado** en `alembic/versions/` — Alembic no es infalible, a veces hay que ajustar a mano (por ejemplo, tipos ENUM nuevos, o si detecta un rename como un drop+create).
4. **Aplica la migración a Supabase** (afecta a todo el equipo, la base es compartida):

```bash
alembic upgrade head
```

5. **Commitea el archivo de migración** junto con el cambio de modelo, para que el otro desarrollador solo necesite correr `alembic upgrade head` la próxima vez que haga `git pull` (no necesita tocar la base manualmente).

### Comandos útiles

```bash
alembic current          # Ver en qué revisión está la base conectada
alembic history           # Ver el historial completo de migraciones
alembic downgrade -1       # Revertir la última migración (con cuidado, es una BD compartida)
```

### Importante

- **Nunca edites una migración ya aplicada en Supabase** (ya la corrió alguien más) — crea una nueva migración para corregir.
- **Avisa al equipo antes de correr `alembic upgrade head`** con cambios grandes, porque afecta la base compartida en tiempo real.
- Si en algún momento quieren una base local aparte para probar algo destructivo sin afectar al otro, pueden levantar el `docker-compose.yml` de la raíz y apuntar su `.env` local a `postgresql://fashionstore:fashionstore@localhost:5432/fashionstore`, corriendo ahí `alembic upgrade head` desde cero (sí ejecuta el baseline completo porque parte de una base vacía).
