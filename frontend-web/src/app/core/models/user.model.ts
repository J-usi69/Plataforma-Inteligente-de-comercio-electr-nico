export interface PersonalBrief {
  id: number;
  nombres: string;
  apellidos: string;
  cargo: string;
  sucursal_id?: number | null;
  sucursal_nombre?: string | null;
}

export interface ProveedorBrief {
  id: number;
  nombre_empresa: string;
  contacto?: string | null;
}

export interface Usuario {
  id: number;
  correo: string;
  celular?: string | null;
  estado: boolean;
  roles: string[];
  permisos: string[];
  creado_en?: string;
  personal?: PersonalBrief | null;
  proveedor?: ProveedorBrief | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

export interface Rol {
  id: number;
  nombre: string;
  descripcion?: string | null;
  estado: boolean;
  permisos: Permiso[];
}

export interface Permiso {
  id: number;
  codigo: string;
  descripcion?: string | null;
  modulo?: string | null;
  estado: boolean;
}

export interface Personal {
  id: number;
  usuario_id: number;
  sucursal_id?: number | null;
  nombres: string;
  apellidos: string;
  cargo: string;
  estado: boolean;
  correo?: string | null;
  celular?: string | null;
  sucursal_nombre?: string | null;
}

export interface Ciudad {
  id: number;
  nombre: string;
  estado: boolean;
}

export interface Sucursal {
  id: number;
  nombre: string;
  ciudad_id: number;
  direccion: string;
  telefono?: string | null;
  hora_inicio?: string | null;
  hora_fin?: string | null;
  estado: boolean;
  ciudad_nombre?: string | null;
}

export interface Proveedor {
  id: number;
  nombre_empresa: string;
  contacto?: string | null;
  estado: boolean;
  correo?: string | null;
  celular?: string | null;
}

export interface DisponibilidadProveedor {
  id: number;
  prenda_id: number;
  prenda_nombre: string;
  cantidad: number;
  fecha_estimada: string;
  fecha_registro: string;
}

export interface Prenda {
  id: number;
  nombre: string;
  descripcion?: string | null;
  categoria_id: number;
  coleccion_id?: number | null;
  proveedor_id?: number | null;
  precio_base: number;
  modelo_3d_url?: string | null;
  imagen_url?: string | null;
  estado: boolean;
  categoria_nombre?: string | null;
  coleccion_nombre?: string | null;
  proveedor_nombre?: string | null;
}

export interface Categoria {
  id: number;
  nombre: string;
  descripcion?: string | null;
  estado: boolean;
}

export interface Temporada {
  id: number;
  nombre: string;
  tipo?: string | null;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  estado: boolean;
}

export interface Coleccion {
  id: number;
  nombre: string;
  descripcion?: string | null;
  temporada_id: number;
  temporada_nombre?: string | null;
  estado: boolean;
}

export interface Bitacora {
  id: number;
  usuario_id: number;
  accion: string;
  ip?: string | null;
  fecha: string;
}

export interface Talla {
  id: number;
  nombre: string;
}

export interface Color {
  id: number;
  nombre: string;
  hex?: string | null;
}

export interface VariantePrenda {
  id: number;
  prenda_id: number;
  talla_id: number;
  color_id: number;
  codigo_barras: string;
  estado: boolean;
  talla_nombre?: string | null;
  color_nombre?: string | null;
}

export interface DisponibilidadSucursal {
  sucursal_id: number;
  sucursal_nombre: string;
  ciudad_id: number;
  ciudad_nombre: string;
  direccion: string;
  stock_disponible: number;
}

export interface DetalleReserva {
  id: number;
  variante_id: number;
  cantidad: number;
  prenda_id?: number | null;
  prenda_nombre?: string | null;
  talla_nombre?: string | null;
  color_nombre?: string | null;
  codigo_barras?: string | null;
  precio_unitario?: number | null;
  subtotal?: number | null;
}

export interface Reserva {
  id: number;
  usuario_id: number;
  cliente_correo?: string | null;
  cliente_celular?: string | null;
  sucursal_id: number;
  sucursal_nombre?: string | null;
  personal_id?: number | null;
  fecha_reserva: string;
  horario_atencion?: string | null;
  estado: 'pendiente' | 'confirmada' | 'atendida' | 'cancelada' | 'expirada';
  total_estimado?: number | null;
  detalles: DetalleReserva[];
}

export interface DetalleVenta {
  id: number;
  variante_id: number;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
  prenda_id?: number | null;
  prenda_nombre?: string | null;
  talla_nombre?: string | null;
  color_nombre?: string | null;
  codigo_barras?: string | null;
}

export interface Pago {
  id: number;
  venta_id: number;
  metodo_pago: string;
  pasarela?: string | null;
  estado: string;
  monto: number;
  transaccion_id?: string | null;
  fecha_pago: string;
}

export interface Venta {
  id: number;
  usuario_id?: number | null;
  cliente_nombre?: string | null;
  cliente_correo?: string | null;
  personal_id?: number | null;
  personal_nombre?: string | null;
  sucursal_id: number;
  sucursal_nombre?: string | null;
  reserva_id?: number | null;
  tipo_origen: 'presencial' | 'web' | 'movil';
  estado: 'pendiente' | 'pagada' | 'anulada';
  total: number;
  fecha_venta: string;
  detalles: DetalleVenta[];
  pagos: Pago[];
}

export interface ComprobanteItem {
  descripcion: string;
  talla?: string | null;
  color?: string | null;
  codigo_barras?: string | null;
  cantidad: number;
  precio_unitario: number;
  subtotal: number;
}

export interface VentaPorSucursal {
  sucursal_id: number;
  sucursal_nombre: string;
  cantidad_ventas: number;
  total_ventas: number;
}

export interface PrendaVendida {
  prenda_id?: number | null;
  prenda_nombre: string;
  cantidad_vendida: number;
  total_vendido: number;
}

export interface InventarioVariante {
  variante_id: number;
  prenda_nombre: string;
  talla_nombre?: string | null;
  color_nombre?: string | null;
  codigo_barras?: string | null;
  stock_disponible: number;
  stock_reservado: number;
}

export interface MovimientoManual {
  id: number;
  variante_id: number;
  tipo: string;
  cantidad: number;
  stock_disponible: number;
  fecha: string;
}

export interface QuiebreStock {
  variante_id: number;
  prenda_nombre: string;
  sucursal_id: number;
  sucursal_nombre: string;
  stock_disponible: number;
  stock_minimo: number;
}

export interface DashboardReporte {
  cantidad_ventas: number;
  total_ventas: number;
  ticket_promedio: number;
  reservas_pendientes: number;
  variantes_bajo_minimo: number;
  quiebres: QuiebreStock[];
}

export interface ComprobanteVenta {
  numero_comprobante: string;
  venta_id: number;
  fecha_emision: string;
  tipo_origen: string;
  sucursal_nombre: string;
  sucursal_direccion: string;
  sucursal_telefono?: string | null;
  ciudad_nombre?: string | null;
  cajero_nombre?: string | null;
  cliente_nombre: string;
  cliente_correo?: string | null;
  metodo_pago: string;
  transaccion_id?: string | null;
  estado_venta: string;
  subtotal: number;
  total: number;
  items: ComprobanteItem[];
}
