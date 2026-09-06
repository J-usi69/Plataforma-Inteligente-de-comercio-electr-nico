import time
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_cu02_login_admin():
    """CU-02: Inicio de sesión de administrador"""
    response = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "Administrador" in data["usuario"]["roles"]


def test_cu01_register_and_profile():
    """CU-01: Registro de usuario cliente y consulta/actualización de perfil"""
    ts = int(time.time() * 1000)
    email = f"cliente_{ts}@test.com"
    phone = f"7{str(ts)[-7:]}"

    # Registro
    res_reg = client.post(
        "/api/v1/auth/register",
        json={"correo": email, "password": "Password123*", "celular": phone},
    )
    assert res_reg.status_code == 201
    user_data = res_reg.json()
    assert user_data["correo"] == email
    assert "Cliente" in user_data["roles"]

    # Excepción: Duplicado de correo o celular
    res_dup = client.post(
        "/api/v1/auth/register",
        json={"correo": email, "password": "OtherPassword123*", "celular": phone},
    )
    assert res_dup.status_code == 400

    # Login con celular (CU-02)
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": phone, "password": "Password123*"},
    )
    assert res_login.status_code == 200
    token = res_login.json()["access_token"]

    # Perfil /me
    headers = {"Authorization": f"Bearer {token}"}
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["celular"] == phone

    # Actualizar celular
    new_phone = f"6{str(ts)[-7:]}"
    res_update = client.put(
        "/api/v1/auth/me",
        headers=headers,
        json={"celular": new_phone},
    )
    assert res_update.status_code == 200
    assert res_update.json()["celular"] == new_phone


def test_cu03_logout():
    """CU-03: Cierre de sesión"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res_logout = client.post("/api/v1/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert "Sesión cerrada" in res_logout.json()["message"]


def test_cu04_roles_y_permisos():
    """CU-04: Gestionar roles y permisos"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Listar permisos
    res_permisos = client.get("/api/v1/permisos", headers=headers)
    assert res_permisos.status_code == 200
    permisos = res_permisos.json()
    assert len(permisos) > 0

    # Crear rol único
    ts = int(time.time() * 1000)
    rol_nombre = f"Rol_{ts}"
    res_crear_rol = client.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "nombre": rol_nombre,
            "descripcion": "Rol dinámico de prueba",
            "permiso_ids": [permisos[0]["id"], permisos[1]["id"]],
        },
    )
    assert res_crear_rol.status_code == 201
    nuevo_rol = res_crear_rol.json()
    assert nuevo_rol["nombre"] == rol_nombre
    assert len(nuevo_rol["permisos"]) == 2

    # Intentar eliminar rol Administrador con usuarios activos (Excepción CU-04)
    res_del_admin = client.delete("/api/v1/roles/1", headers=headers)
    assert res_del_admin.status_code == 400


def test_cu05_personal():
    """CU-05: Gestionar personal"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    ts = int(time.time() * 1000)
    # Crear personal (Cajero)
    res_p = client.post(
        "/api/v1/personal",
        headers=headers,
        json={
            "nombres": "Empleado",
            "apellidos": f"Test_{ts}",
            "cargo": "Cajero",
            "sucursal_id": 1,
            "correo": f"cajero_{ts}@fashionstore.com",
            "celular": f"7{str(ts)[-7:]}",
            "password": "Cajero123*",
        },
    )
    assert res_p.status_code == 201
    personal = res_p.json()
    assert personal["cargo"] == "Cajero"
    assert personal["sucursal_nombre"] == "Sucursal Central Equipetrol"

    # Listar personal
    res_list = client.get("/api/v1/personal", headers=headers)
    assert res_list.status_code == 200
    assert any(p["correo"] == f"cajero_{ts}@fashionstore.com" for p in res_list.json())


def test_cu06_sucursales():
    """CU-06: Gestionar sucursales y ciudades"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Listar ciudades
    res_ciudades = client.get("/api/v1/sucursales/ciudades")
    assert res_ciudades.status_code == 200
    ciudades = res_ciudades.json()
    assert len(ciudades) >= 3

    ts = int(time.time() * 1000)
    # Crear sucursal
    res_suc = client.post(
        "/api/v1/sucursales",
        headers=headers,
        json={
            "nombre": f"Sucursal Norte {ts}",
            "ciudad_id": ciudades[0]["id"],
            "direccion": "Av. Banzer km 8.5",
            "telefono": "33221100",
            "hora_inicio": "10:00:00",
            "hora_fin": "22:00:00",
        },
    )
    assert res_suc.status_code == 201
    suc = res_suc.json()

    # Editar sucursal
    res_edit = client.put(
        f"/api/v1/sucursales/{suc['id']}",
        headers=headers,
        json={"telefono": "33221199"},
    )
    assert res_edit.status_code == 200
    assert res_edit.json()["telefono"] == "33221199"


def test_cu07_proveedores():
    """CU-07: Gestionar proveedores"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    ts = int(time.time() * 1000)
    # Crear proveedor
    res_prov = client.post(
        "/api/v1/proveedores",
        headers=headers,
        json={
            "nombre_empresa": f"Proveedor Industrial {ts}",
            "contacto": "info@proveedor.com - 77889900",
        },
    )
    assert res_prov.status_code == 201
    prov = res_prov.json()

    # Listar proveedores
    res_list = client.get("/api/v1/proveedores", headers=headers)
    assert res_list.status_code == 200
    assert any(p["id"] == prov["id"] for p in res_list.json())


def test_cu08_catalogo_prendas():
    """CU-08: Gestionar catálogo de prendas con modelo 3D para RA"""
    res_login = client.post(
        "/api/v1/auth/login",
        json={"login": "admin@fashionstore.com", "password": "Admin123*"},
    )
    admin_token = res_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    ts = int(time.time() * 1000)
    # Crear prenda con modelo 3D
    res_prenda = client.post(
        "/api/v1/prendas",
        headers=headers,
        json={
            "nombre": f"Chaqueta Denim Modelo {ts}",
            "descripcion": "Chaqueta de mezclilla premium",
            "categoria_id": 4,  # Chaquetas
            "coleccion_id": 1,  # Urbana
            "proveedor_id": 1,  # Textil Santa Cruz
            "precio_base": 249.99,
            "modelo_3d_url": "https://storage.googleapis.com/fashionstore-3d/chaqueta_denim.glb",
        },
    )
    assert res_prenda.status_code == 201
    prenda = res_prenda.json()
    assert prenda["precio_base"] == 249.99
    assert prenda["modelo_3d_url"] is not None

    # Consultar prenda (público)
    res_get = client.get(f"/api/v1/prendas/{prenda['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["categoria_nombre"] == "Chaquetas y Abrigos"

