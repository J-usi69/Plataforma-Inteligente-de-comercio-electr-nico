from datetime import time
from typing import Optional, Union
from pydantic import BaseModel


class CiudadCreate(BaseModel):
    nombre: str


class CiudadOut(BaseModel):
    id: int
    nombre: str
    estado: bool

    class Config:
        from_attributes = True


class SucursalCreate(BaseModel):
    nombre: str
    ciudad_id: int
    direccion: str
    telefono: Optional[str] = None
    hora_inicio: Optional[Union[time, str]] = None
    hora_fin: Optional[Union[time, str]] = None


class SucursalUpdate(BaseModel):
    nombre: Optional[str] = None
    ciudad_id: Optional[int] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    hora_inicio: Optional[Union[time, str]] = None
    hora_fin: Optional[Union[time, str]] = None
    estado: Optional[bool] = None


class SucursalOut(BaseModel):
    id: int
    nombre: str
    ciudad_id: int
    direccion: str
    telefono: Optional[str] = None
    hora_inicio: Optional[Union[time, str]] = None
    hora_fin: Optional[Union[time, str]] = None
    estado: bool
    ciudad_nombre: Optional[str] = None

    class Config:
        from_attributes = True

