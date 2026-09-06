export interface Usuario {
  id: number;
  correo: string;
  celular?: string | null;
  estado: boolean;
  roles: string[];
  permisos: string[];
  creado_en?: string;
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

export interface Coleccion {
  id: number;
  nombre: string;
  descripcion?: string | null;
  temporada_id: number;
  estado: boolean;
}

export interface Bitacora {
  id: number;
  usuario_id: number;
  accion: string;
  ip?: string | null;
  fecha: string;
}

