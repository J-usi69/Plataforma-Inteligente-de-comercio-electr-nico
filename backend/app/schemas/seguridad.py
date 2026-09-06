from typing import List, Optional
from pydantic import BaseModel


class PermisoOut(BaseModel):
    id: int
    codigo: str
    descripcion: Optional[str] = None
    modulo: Optional[str] = None
    estado: bool

    class Config:
        from_attributes = True


class RolCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    permiso_ids: Optional[List[int]] = []


class RolUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    estado: Optional[bool] = None
    permiso_ids: Optional[List[int]] = None


class RolOut(BaseModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    estado: bool
    permisos: List[PermisoOut] = []

    class Config:
        from_attributes = True


class AsignarRolesUsuario(BaseModel):
    rol_ids: List[int]

