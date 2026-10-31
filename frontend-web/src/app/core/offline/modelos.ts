// Operación sin conexión: mismos contratos que backend/app/schemas/sincronizacion.py (la app
// móvil usa los mismos con SQLite).

export interface SucursalLocal {
  id: number;
  nombre: string;
  direccion: string;
  ciudad: string | null;
}

export interface ItemNombre {
  id: number;
  nombre: string;
}

export interface ColorLocal extends ItemNombre {
  hex: string | null;
}

export interface PrendaLocal {
  id: number;
  nombre: string;
  descripcion: string | null;
  categoria_id: number;
  precio_base: number;
  imagen_url: string | null;
}

export interface VarianteLocal {
  id: number;
  prenda_id: number;
  talla_id: number;
  color_id: number;
  codigo_barras: string;
  imagen_url: string | null;
}

export interface InventarioLocal {
  variante_id: number;
  sucursal_id: number;
  stock_disponible: number;
}

export interface ClienteLocal {
  id: number;
  correo: string;
}

export interface DetalleVentaLocal {
  variante_id: number;
  cantidad: number;
  precio_unitario: number;
  devuelto: number;
}

/** Venta pagada que todavía está dentro del plazo de cambio. */
export interface VentaCambiable {
  id: number;
  sucursal_id: number;
  cliente_id: number | null;
  fecha_venta: string;
  total: number;
  detalles: DetalleVentaLocal[];
}

export interface Paquete {
  generado_en: string;
  vigencia_horas: number;
  tienda: string;
  dias_para_cambio: number;
  sucursales: SucursalLocal[];
  categorias: ItemNombre[];
  tallas: ItemNombre[];
  colores: ColorLocal[];
  prendas: PrendaLocal[];
  variantes: VarianteLocal[];
  inventario: InventarioLocal[];
  clientes: ClienteLocal[];
  ventas: VentaCambiable[];
}

/** Lo que se sabe del paquete guardado, sin las tablas. */
export interface InfoPaquete {
  generado_en: string;
  vigencia_horas: number;
  tienda: string;
  dias_para_cambio: number;
  usuario_id: number;
}

export type TipoOperacion = 'venta' | 'reserva' | 'cambio';

export interface Linea {
  variante_id: number;
  cantidad: number;
}

export interface LineaConPrecio extends Linea {
  precio_unitario: number;
}

export interface DatosVenta {
  cliente_id: number | null;
  detalles: LineaConPrecio[];
  total: number;
  metodo_pago: 'efectivo';
  monto_recibido: number | null;
}

export interface DatosReserva {
  cliente_id: number | null;
  detalles: Linea[];
  horario_atencion?: string | null;
}

export interface DatosCambio {
  venta_id: number | null;
  venta_operacion_id: string | null;
  devuelve: Linea[];
  entrega: LineaConPrecio[];
  diferencia: number;
  motivo: string | null;
  metodo_pago: 'efectivo';
}

/** registrada: solo en este dispositivo. enviada: salió hacia el servidor y todavía no hay respuesta
 * definitiva (se reintenta). confirmada / rechazada: respuesta final. conflicto: el servidor la
 * recibió y espera la decisión de un encargado. */
export type EstadoLocal = 'registrada' | 'enviada' | 'confirmada' | 'rechazada' | 'conflicto';

export interface ResultadoServidor {
  codigo: string | null;
  mensaje: string | null;
  referencia_tipo: string | null;
  referencia_id: number | null;
}

export interface OperacionLocal {
  id: string; // UUID generado en el dispositivo: el mismo en todos los reintentos
  orden: number; // se envían en el orden en que se registraron
  tipo: TipoOperacion;
  tienda: string;
  sucursal_id: number;
  registrada_en: string;
  dispositivo: string;
  datos: DatosVenta | DatosReserva | DatosCambio;
  usuario_id: number; // solo la sesión de quien la registró la envía
  estado: EstadoLocal;
  intentos: number;
  ultimo_intento: string | null;
  resultado: ResultadoServidor | null;
  resumen: string;
}

export type EstadoServidor = 'confirmada' | 'rechazada' | 'conflicto' | 'error';

export interface ResultadoOperacion extends ResultadoServidor {
  id: string;
  tipo: string;
  estado: EstadoServidor;
  duplicada: boolean;
  procesada_en: string | null;
}

export interface LoteOut {
  recibido_en: string;
  resultados: ResultadoOperacion[];
}

export interface EstadoOperacionesOut {
  resultados: ResultadoOperacion[];
  desconocidas: string[];
}
