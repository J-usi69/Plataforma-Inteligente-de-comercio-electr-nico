from pydantic import BaseModel


class DisponibilidadSucursalOut(BaseModel):
    sucursal_id: int
    sucursal_nombre: str
    ciudad_id: int
    ciudad_nombre: str
    direccion: str
    stock_disponible: int
