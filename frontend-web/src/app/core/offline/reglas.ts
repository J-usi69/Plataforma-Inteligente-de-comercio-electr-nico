// Reglas de negocio de la operación sin conexión, sin Angular ni almacenamiento: qué le hace cada
// operación al stock local, montos, plazos y cómo queda una operación según la respuesta del
// servidor. Las mismas que valida el backend (app/services/sincronizacion_service.py): acá sirven
// para avisar antes, la decisión final es siempre del servidor.
import {
  DatosCambio,
  DatosReserva,
  DatosVenta,
  EstadoLocal,
  Linea,
  LineaConPrecio,
  OperacionLocal,
  ResultadoOperacion,
  TipoOperacion,
} from './modelos';

export const redondear = (monto: number): number => Math.round(monto * 100) / 100;

export function totalDe(lineas: LineaConPrecio[]): number {
  return redondear(lineas.reduce((suma, l) => suma + redondear(l.precio_unitario * l.cantidad), 0));
}

/** Lo que paga el cliente en un cambio: lo que se lleva menos lo que devuelve (al precio que pagó). */
export function diferenciaDeCambio(devuelve: LineaConPrecio[], entrega: LineaConPrecio[]): number {
  return redondear(totalDe(entrega) - totalDe(devuelve));
}

export function vencimientoDelCambio(fechaVenta: string, diasParaCambio: number): Date {
  return new Date(new Date(fechaVenta).getTime() + diasParaCambio * 86_400_000);
}

export function dentroDelPlazo(fechaVenta: string, diasParaCambio: number, ahora: Date = new Date()): boolean {
  return ahora.getTime() <= vencimientoDelCambio(fechaVenta, diasParaCambio).getTime();
}

/** Cuánto saca (negativo) o devuelve (positivo) cada operación al stock de su sucursal, por
 * variante. Así lo que se ve sin conexión ya descuenta lo vendido y reservado en este dispositivo. */
export function efectoEnStock(tipo: TipoOperacion, datos: OperacionLocal['datos']): Map<number, number> {
  const efecto = new Map<number, number>();
  const sumar = (lineas: Linea[], signo: number) =>
    lineas.forEach((l) => efecto.set(l.variante_id, (efecto.get(l.variante_id) ?? 0) + signo * l.cantidad));
  if (tipo === 'cambio') {
    sumar((datos as DatosCambio).devuelve, 1);
    sumar((datos as DatosCambio).entrega, -1);
  } else {
    sumar((datos as DatosVenta | DatosReserva).detalles, -1);
  }
  return efecto;
}

/** Sigue pendiente de envío: todavía no hay una respuesta definitiva del servidor. */
export function pendienteDeEnvio(op: Pick<OperacionLocal, 'estado'>): boolean {
  return op.estado === 'registrada' || op.estado === 'enviada';
}

/** "error" no es una respuesta definitiva (falla momentánea del servidor): se vuelve a enviar. */
export function estadoTrasResultado(resultado: Pick<ResultadoOperacion, 'estado'>): EstadoLocal {
  return resultado.estado === 'error' ? 'enviada' : resultado.estado;
}

export function paqueteDesactualizado(generadoEn: string, vigenciaHoras: number, ahora: number = Date.now()): boolean {
  return ahora - new Date(generadoEn).getTime() > vigenciaHoras * 3_600_000;
}

/** Lo que viaja al servidor (sin los datos que solo usa el dispositivo). */
export function sobreParaEnviar(op: OperacionLocal) {
  const { id, tipo, tienda, sucursal_id, registrada_en, dispositivo, datos } = op;
  return { id, tipo, tienda, sucursal_id, registrada_en, dispositivo, datos };
}

const bs = new Intl.NumberFormat('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const formatoBs = (monto: number): string => `Bs. ${bs.format(monto)}`;

const prendas = (lineas: Linea[]): string => {
  const unidades = lineas.reduce((suma, l) => suma + l.cantidad, 0);
  return `${unidades} ${unidades === 1 ? 'prenda' : 'prendas'}`;
};

export function resumenDe(tipo: TipoOperacion, datos: OperacionLocal['datos']): string {
  if (tipo === 'venta') {
    const venta = datos as DatosVenta;
    return `Venta de contado · ${prendas(venta.detalles)} · ${formatoBs(venta.total)}`;
  }
  if (tipo === 'reserva') {
    return `Reserva · ${prendas((datos as DatosReserva).detalles)}`;
  }
  const cambio = datos as DatosCambio;
  return `Cambio · devuelve ${prendas(cambio.devuelve)}, se lleva ${prendas(cambio.entrega)} · paga ${formatoBs(cambio.diferencia)}`;
}

/** UUID v4 para identificar la operación (crypto.randomUUID solo existe en contextos seguros). */
export function nuevoId(): string {
  if (typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
