import enum


class CanalVenta(str, enum.Enum):
    web = "web"
    movil = "movil"
    presencial = "presencial"


class EstadoReserva(str, enum.Enum):
    pendiente = "pendiente"
    confirmada = "confirmada"
    atendida = "atendida"
    cancelada = "cancelada"
    expirada = "expirada"


class EstadoVenta(str, enum.Enum):
    pendiente = "pendiente"
    pagada = "pagada"
    anulada = "anulada"


class EstadoPago(str, enum.Enum):
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class TipoMovimiento(str, enum.Enum):
    entrada = "entrada"
    venta = "venta"
    reserva = "reserva"
    devolucion = "devolucion"
    ajuste = "ajuste"
