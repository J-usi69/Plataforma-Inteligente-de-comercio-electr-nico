// SaaS: la empresa (tenant) de la URL, sus planes y su suscripción. Mismos contratos que
// backend/app/schemas/tienda.py.

export interface FuncionesPlan {
  operacion_offline: boolean;
  reportes: boolean;
  reportes_ia: boolean;
  asistente_ia: boolean;
  vestidor_ar: boolean;
  pago_qr: boolean;
}

export interface TiendaPublica {
  slug: string;
  nombre: string;
  logo_url: string | null;
  color_primario: string;
  color_acento: string;
  plan: string;
  plan_nombre: string;
  funciones: FuncionesPlan;
  suscripcion_vigente: boolean;
}

export interface Plan extends FuncionesPlan {
  codigo: string;
  nombre: string;
  descripcion: string | null;
  precio_mensual: number;
  moneda: string;
  // null = sin límite
  max_sucursales: number | null;
  max_prendas: number | null;
  max_personal: number | null;
}

export interface Suscripcion {
  estado: 'activa' | 'vencida' | 'cancelada';
  fecha_inicio: string;
  fecha_vencimiento: string | null;
  dias_restantes: number | null;
  cobro: 'simulado' | 'stripe';
}

export interface MovimientoSuscripcion {
  fecha: string;
  tipo: string;
  plan: string;
  monto: number;
  origen: string;
  detalle: string | null;
}

export interface UsoPlan {
  plan: Plan;
  suscripcion: Suscripcion;
  uso: Record<'sucursales' | 'prendas' | 'personal', number>;
  planes_disponibles: Plan[];
  movimientos: MovimientoSuscripcion[];
}

export interface CambioPlan {
  url: string | null; // Stripe Checkout; null si el cambio ya se aplicó (cobro simulado)
  estado: UsoPlan | null;
}

export interface TiendaAdmin {
  id: number;
  slug: string;
  nombre: string;
  estado: 'activa' | 'suspendida';
  plan: string;
  plan_codigo: string;
  estado_suscripcion: string;
  fecha_inicio: string | null;
  fecha_vencimiento: string | null;
  creado_en: string;
  sucursales: number;
  usuarios: number;
  prendas: number;
  ventas: number;
}

export interface RegistroTienda {
  slug: string;
  nombre: string;
  access_token: string;
  token_type: string;
}

export const FUNCIONES_PLAN: { clave: keyof FuncionesPlan; nombre: string }[] = [
  { clave: 'operacion_offline', nombre: 'Operación sin conexión' },
  { clave: 'reportes', nombre: 'Reportes convencionales' },
  { clave: 'reportes_ia', nombre: 'Reportes generados con IA' },
  { clave: 'asistente_ia', nombre: 'Asistente con IA' },
  { clave: 'vestidor_ar', nombre: 'Vestidor virtual' },
  { clave: 'pago_qr', nombre: 'Pago con QR' },
];
