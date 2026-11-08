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

/** El plan visto por el superadmin: también los desactivados y cuántas empresas lo tienen. */
export interface PlanAdmin extends Plan {
  estado: boolean;
  empresas: number;
}

/** Plan nuevo creado por el superadmin (CU-02). */
export type NuevoPlan = Omit<Plan, 'moneda'>;

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

// --- Reportes e indicadores de la plataforma (superadmin) --------------------------------------

export interface IndicadoresPlataforma {
  empresas: number;
  vigentes: number;
  suspendidas: number;
  sin_suscripcion_vigente: number;
  ingreso_mensual: number;
  ingresos_mes_actual: number;
  ingresos_por_mes: { mes: string; etiqueta: string; monto: number }[];
  empresas_por_plan: { plan: string; cantidad: number; ingreso_mensual: number }[];
  ventas_por_empresa: { empresa: string; ventas: number; total: number }[];
  proximos_vencimientos: { empresa: string; slug: string; vence: string; dias: number }[];
}

/** Un reporte del constructor: sus columnas y el orden por defecto. */
export interface CatalogoReporte {
  tipo: string;
  titulo: string;
  descripcion: string;
  columnas: string[];
  orden: string;
  descendente: boolean;
  columnas_monto: string[];
}

export type Celda = string | number | null;

export interface ReportePlataforma {
  tipo: string;
  titulo: string;
  columnas: string[];
  filas: Celda[][];
  totales: Record<string, Celda> | null;
  narrativa: string;
  columnas_monto: string[];
  filtros: string;
}

export type OperadorCriterio = 'contiene' | 'igual' | 'distinto' | 'mayor' | 'menor';

export const OPERADORES_CRITERIO: { clave: OperadorCriterio; nombre: string }[] = [
  { clave: 'contiene', nombre: 'contiene' },
  { clave: 'igual', nombre: 'es igual a' },
  { clave: 'distinto', nombre: 'es distinto de' },
  { clave: 'mayor', nombre: 'es mayor que' },
  { clave: 'menor', nombre: 'es menor que' },
];

export interface CriterioReporte {
  columna: string;
  operador: OperadorCriterio;
  valor: string;
}

/** Lo que el usuario arma en el constructor; se usa igual para ver, exportar y enviar. */
export interface OpcionesReporte {
  desde?: string;
  hasta?: string;
  columnas: string[];
  criterios: CriterioReporte[];
  orden?: string;
  descendente?: boolean;
}

export type FormatoReporte = 'excel' | 'pdf' | 'html';

/** Cómo interpretó la IA un pedido de reporte (texto o voz): se carga en el constructor. */
export interface ReporteIAPlataforma {
  pedido: string;
  opciones: {
    tipo: string;
    columnas: string[] | null;
    criterios: CriterioReporte[];
    desde: string | null;
    hasta: string | null;
    orden: string | null;
    descendente: boolean | null;
  };
  reporte: ReportePlataforma;
}

/** Qué se restauró (o se restauraría, si simulado) desde un respaldo. */
export interface Restauracion {
  simulado: boolean;
  alcance: 'empresa' | 'sistema';
  empresa: string | null;
  respaldo_del: string | null;
  tablas: Record<string, number>;
  filas: number;
  usuarios_desactivados: number;
  empresas_suspendidas: number;
}
