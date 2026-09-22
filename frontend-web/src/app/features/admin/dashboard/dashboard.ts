import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  Bitacora,
  Categoria,
  Ciudad,
  Coleccion,
  Color,
  DashboardReporte,
  InventarioGlobalItem,
  Permiso,
  Personal,
  Prenda,
  PrendaVendida,
  Proveedor,
  QuiebreStock,
  Rol,
  Sucursal,
  Talla,
  Temporada,
  VariantePrenda,
  VentaPorSucursal,
} from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';
import { Paginador } from '../../../shared/paginador/paginador';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, Paginador],
  templateUrl: './dashboard.html',
  styles: [`
    .admin-hero {
      background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
      border-radius: 16px;
      padding: 2.25rem;
      color: #ffffff;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15);

      h2 { color: #ffffff; font-size: 1.85rem; margin-bottom: 0.35rem; }
      p { color: #94a3b8; font-size: 0.9rem; }
    }

    .admin-nav-bar {
      display: flex;
      gap: 0.5rem;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 6px;
      margin-bottom: 2rem;
      overflow-x: auto;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
    }

    .nav-pill-btn {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      padding: 0.65rem 1.15rem;
      background: none;
      border: none;
      font-weight: 600;
      font-size: 0.85rem;
      color: #64748b;
      border-radius: 8px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;

      svg {
        transition: transform 0.2s;
      }

      &:hover {
        color: #0f172a;
        background: #f1f5f9;
      }

      &.active {
        background: #4f46e5;
        color: #ffffff;
        box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);

        svg {
          transform: scale(1.1);
        }
      }
    }

    .action-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;

      .header-title-box {
        display: flex;
        flex-direction: column;
      }
    }

    .search-filter-box {
      position: relative;
      min-width: 260px;

      input {
        width: 100%;
        padding: 0.55rem 0.85rem 0.55rem 2.25rem;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        font-size: 0.85rem;
        outline: none;
        transition: all 0.2s;

        &:focus {
          border-color: #4f46e5;
          box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
        }
      }

      svg {
        position: absolute;
        left: 0.75rem;
        top: 50%;
        transform: translateY(-50%);
        color: #94a3b8;
      }
    }

    .avatar-badge {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
      color: #3730a3;
      font-weight: 700;
      font-size: 0.78rem;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-right: 0.75rem;
    }
  `],
})
export class Dashboard implements OnInit {
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);

  activeTab = signal<'roles' | 'personal' | 'sucursales' | 'proveedores' | 'temporadas' | 'prendas' | 'catalogo-maestro' | 'reportes' | 'bitacora'>('roles');
  isLoading = signal(false);
  filtroTexto = signal('');
  alertMessage = signal<{ type: 'success' | 'danger'; text: string } | null>(null);

  // Datos
  roles = signal<Rol[]>([]);
  permisos = signal<Permiso[]>([]);
  personal = signal<Personal[]>([]);
  sucursales = signal<Sucursal[]>([]);
  ciudades = signal<Ciudad[]>([]);
  proveedores = signal<Proveedor[]>([]);
  temporadas = signal<Temporada[]>([]);
  coleccionesAdmin = signal<Coleccion[]>([]);
  prendas = signal<Prenda[]>([]);
  prendasPendientes = signal<Prenda[]>([]);
  categorias = signal<Categoria[]>([]);
  colecciones = signal<Coleccion[]>([]);
  tallas = signal<Talla[]>([]);
  colores = signal<Color[]>([]);
  variantesPrendaActual = signal<VariantePrenda[]>([]);
  prendaSeleccionadaVariantes = signal<Prenda | null>(null);
  bitacora = signal<Bitacora[]>([]);
  dashboardReporte = signal<DashboardReporte | null>(null);
  reporteVentas = signal<VentaPorSucursal[]>([]);
  reportePrendas = signal<PrendaVendida[]>([]);
  reporteFiltros = { desde: '', hasta: '' };
  reporteIAPrompt = '';
  reporteIACargando = signal(false);
  reporteIAResultado = signal<{ tipo: string; datos: any } | null>(null);
  reporteIAError = signal<string | null>(null);

  // CU-27: inventario global (todas las sucursales, filtrable por ciudad/categoría)
  inventarioGlobal = signal<InventarioGlobalItem[]>([]);
  inventarioGlobalFiltros = { ciudad_id: null as number | null, categoria_id: null as number | null };
  inventarioGlobalCargando = signal(false);
  inventarioGlobalBuscado = signal(false);

  // Computed KPIs
  totalSucursales = computed(() => this.sucursales().length);
  totalPrendas = computed(() => this.prendas().length);
  totalPersonal = computed(() => this.personal().length);
  totalRoles = computed(() => this.roles().length);
  totalProveedores = computed(() => this.proveedores().length);

  // Modales
  showModal = signal<string | null>(null);

  // Form states
  rolForm = { id: 0, nombre: '', descripcion: '', permiso_ids: [] as number[] };
  personalForm = {
    id: 0,
    nombres: '',
    apellidos: '',
    cargo: 'Encargado',
    sucursal_id: null as number | null,
    correo: '',
    celular: '',
    password: '',
  };
  sucursalForm = {
    id: 0,
    nombre: '',
    ciudad_id: 1,
    direccion: '',
    telefono: '',
    hora_inicio: '09:00',
    hora_fin: '21:00',
  };
  nuevaCiudadNombre = '';
  nuevaCategoriaForm = { nombre: '', descripcion: '' };
  nuevaTallaNombre = '';
  nuevoColorForm = { nombre: '', hex: '#4f46e5' };
  nuevaVarianteForm = { talla_id: null as number | null, color_id: null as number | null };
  proveedorForm = { id: 0, nombre_empresa: '', contacto: '', correo: '', password: '' };
  temporadaForm = { id: 0, nombre: '', tipo: '', fecha_inicio: '', fecha_fin: '' };
  coleccionForm = { id: 0, nombre: '', descripcion: '', temporada_id: null as number | null };
  prendaForm = {
    id: 0,
    nombre: '',
    descripcion: '',
    categoria_id: 1,
    coleccion_id: null as number | null,
    proveedor_id: null as number | null,
    precio_base: 150.0,
    modelo_3d_url: '',
    imagen_url: '',
  };

  // Filtrados reactivos
  rolesFiltrados = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.roles();
    return this.roles().filter((r) => r.nombre.toLowerCase().includes(q) || (r.descripcion && r.descripcion.toLowerCase().includes(q)));
  });

  personalFiltrado = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.personal();
    return this.personal().filter((p) =>
      p.nombres.toLowerCase().includes(q) ||
      p.apellidos.toLowerCase().includes(q) ||
      (p.correo && p.correo.toLowerCase().includes(q)) ||
      p.cargo.toLowerCase().includes(q)
    );
  });

  sucursalesFiltradas = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.sucursales();
    return this.sucursales().filter((s) => s.nombre.toLowerCase().includes(q) || (s.ciudad_nombre && s.ciudad_nombre.toLowerCase().includes(q)));
  });

  proveedoresFiltrados = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.proveedores();
    return this.proveedores().filter((pr) => pr.nombre_empresa.toLowerCase().includes(q));
  });

  prendasFiltradas = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.prendas();
    return this.prendas().filter((p) => p.nombre.toLowerCase().includes(q) || (p.categoria_nombre && p.categoria_nombre.toLowerCase().includes(q)));
  });

  temporadasFiltradas = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.temporadas();
    return this.temporadas().filter((t) => t.nombre.toLowerCase().includes(q) || (t.tipo && t.tipo.toLowerCase().includes(q)));
  });

  coleccionesAdminFiltradas = computed(() => {
    const q = this.filtroTexto().toLowerCase().trim();
    if (!q) return this.coleccionesAdmin();
    return this.coleccionesAdmin().filter((c) => c.nombre.toLowerCase().includes(q) || (c.temporada_nombre && c.temporada_nombre.toLowerCase().includes(q)));
  });

  maxTotalVentaSucursal = computed(() => Math.max(1, ...this.reporteVentas().map((v) => v.total_ventas)));
  maxCantidadPrendaVendida = computed(() => Math.max(1, ...this.reportePrendas().map((p) => p.cantidad_vendida)));

  // --- Paginación de las listas largas del panel admin ---
  private readonly PAGINA_TAM = 10;

  paginaRoles = signal(1);
  paginaPersonal = signal(1);
  paginaSucursales = signal(1);
  paginaProveedores = signal(1);
  paginaPrendas = signal(1);
  paginaTemporadas = signal(1);
  paginaColecciones = signal(1);
  paginaBitacora = signal(1);
  paginaInventarioGlobal = signal(1);
  paginaReporteVentas = signal(1);
  paginaReportePrendas = signal(1);

  private paginar<T>(lista: T[], pagina: number): { items: T[]; actual: number; total: number } {
    const total = Math.max(1, Math.ceil(lista.length / this.PAGINA_TAM));
    const actual = Math.min(Math.max(1, pagina), total);
    const inicio = (actual - 1) * this.PAGINA_TAM;
    return { items: lista.slice(inicio, inicio + this.PAGINA_TAM), actual, total };
  }

  rolesPagina = computed(() => this.paginar(this.rolesFiltrados(), this.paginaRoles()));
  personalPagina = computed(() => this.paginar(this.personalFiltrado(), this.paginaPersonal()));
  sucursalesPagina = computed(() => this.paginar(this.sucursalesFiltradas(), this.paginaSucursales()));
  proveedoresPagina = computed(() => this.paginar(this.proveedoresFiltrados(), this.paginaProveedores()));
  prendasPagina = computed(() => this.paginar(this.prendasFiltradas(), this.paginaPrendas()));
  temporadasPagina = computed(() => this.paginar(this.temporadasFiltradas(), this.paginaTemporadas()));
  coleccionesAdminPagina = computed(() => this.paginar(this.coleccionesAdminFiltradas(), this.paginaColecciones()));
  bitacoraPagina = computed(() => this.paginar(this.bitacora(), this.paginaBitacora()));
  inventarioGlobalPagina = computed(() => this.paginar(this.inventarioGlobal(), this.paginaInventarioGlobal()));
  reporteVentasPagina = computed(() => this.paginar(this.reporteVentas(), this.paginaReporteVentas()));
  reportePrendasPagina = computed(() => this.paginar(this.reportePrendas(), this.paginaReportePrendas()));

  ngOnInit(): void {
    this.cargarDatosIniciales();
  }

  cargarDatosIniciales(): void {
    this.isLoading.set(true);
    // Carga paralela de KPIs para el resumen superior
    this.business.getPermisos().subscribe((data) => this.permisos.set(data));
    this.business.getCiudades().subscribe((data) => this.ciudades.set(data));
    this.business.getCategorias().subscribe((data) => this.categorias.set(data));
    this.business.getColecciones().subscribe((data) => this.colecciones.set(data));
    this.business.getSucursales().subscribe((data) => this.sucursales.set(data));
    this.business.getPersonal().subscribe((data) => this.personal.set(data));
    this.business.getProveedores().subscribe((data) => this.proveedores.set(data));
    this.business.getPrendas().subscribe((data) => this.prendas.set(data));
    this.cambiarTab(this.activeTab());
  }

  cambiarTab(tab: 'roles' | 'personal' | 'sucursales' | 'proveedores' | 'temporadas' | 'prendas' | 'catalogo-maestro' | 'reportes' | 'bitacora'): void {
    this.activeTab.set(tab);
    this.alertMessage.set(null);
    this.filtroTexto.set('');
    this.isLoading.set(true);
    this.paginaRoles.set(1);
    this.paginaPersonal.set(1);
    this.paginaSucursales.set(1);
    this.paginaProveedores.set(1);
    this.paginaPrendas.set(1);
    this.paginaTemporadas.set(1);
    this.paginaColecciones.set(1);
    this.paginaBitacora.set(1);

    if (tab === 'roles') {
      this.business.getRoles().subscribe({
        next: (data) => { this.roles.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'personal') {
      this.business.getPersonal().subscribe({
        next: (data) => { this.personal.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'sucursales') {
      this.business.getSucursales().subscribe({
        next: (data) => { this.sucursales.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'proveedores') {
      this.business.getProveedores().subscribe({
        next: (data) => { this.proveedores.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'temporadas') {
      this.business.listarTemporadas().subscribe({ next: (data) => this.temporadas.set(data) });
      this.business.listarColeccionesAdmin().subscribe({
        next: (data) => { this.coleccionesAdmin.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'prendas') {
      this.business.getPrendas().subscribe({
        next: (data) => { this.prendas.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
      this.business.getPrendasPendientesValidacion().subscribe({
        next: (data) => this.prendasPendientes.set(data),
      });
    } else if (tab === 'catalogo-maestro') {
      this.business.getCategorias().subscribe({ next: (data) => this.categorias.set(data) });
      this.business.getTallas().subscribe({ next: (data) => this.tallas.set(data) });
      this.business.getColores().subscribe({
        next: (data) => { this.colores.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    } else if (tab === 'reportes') {
      this.cargarReportes();
    } else if (tab === 'bitacora') {
      this.business.getBitacora().subscribe({
        next: (data) => { this.bitacora.set(data); this.isLoading.set(false); },
        error: () => this.isLoading.set(false),
      });
    }
  }

  // --- CU-31 / CU-32: Reportes e Indicadores ---
  cargarReportes(): void {
    this.isLoading.set(true);
    this.paginaReporteVentas.set(1);
    this.paginaReportePrendas.set(1);
    const filtros = {
      desde: this.reporteFiltros.desde || undefined,
      hasta: this.reporteFiltros.hasta || undefined,
    };
    this.business.getDashboard(filtros).subscribe({
      next: (data) => this.dashboardReporte.set(data),
      error: () => this.mostrarAlerta('danger', 'No se pudo cargar el dashboard de indicadores'),
    });
    this.business.getReporteVentas(filtros).subscribe({ next: (data) => this.reporteVentas.set(data) });
    this.business.getPrendasMasVendidas({ ...filtros, limit: 10 }).subscribe({
      next: (data) => { this.reportePrendas.set(data); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
    if (!this.categorias().length) {
      this.business.getCategorias().subscribe({ next: (data) => this.categorias.set(data) });
    }
    this.cargarInventarioGlobal();
  }

  aplicarFiltrosReporte(): void {
    this.cargarReportes();
  }

  // --- CU-27: Consulta de inventario global ---
  cargarInventarioGlobal(): void {
    this.inventarioGlobalCargando.set(true);
    this.paginaInventarioGlobal.set(1);
    this.business.getInventarioGlobal({
      ciudadId: this.inventarioGlobalFiltros.ciudad_id,
      categoriaId: this.inventarioGlobalFiltros.categoria_id,
    }).subscribe({
      next: (data) => {
        this.inventarioGlobal.set(data);
        this.inventarioGlobalCargando.set(false);
        this.inventarioGlobalBuscado.set(true);
      },
      error: () => {
        this.inventarioGlobalCargando.set(false);
        this.inventarioGlobalBuscado.set(true);
      },
    });
  }

  // --- CU-31: Descargar el reporte generado como CSV ---
  private descargarCsv(nombreArchivo: string, encabezados: string[], filas: (string | number)[][]): void {
    const escapar = (valor: string | number) => `"${String(valor).replace(/"/g, '""')}"`;
    const lineas = [encabezados.map(escapar).join(','), ...filas.map((fila) => fila.map(escapar).join(','))];
    const contenido = '﻿' + lineas.join('\r\n'); // BOM para que Excel respete los acentos
    const blob = new Blob([contenido], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = nombreArchivo;
    link.click();
    URL.revokeObjectURL(url);
  }

  descargarReporteVentas(): void {
    this.descargarCsv(
      'ventas_por_sucursal.csv',
      ['Sucursal', 'Cantidad de ventas', 'Total (Bs.)'],
      this.reporteVentas().map((v) => [v.sucursal_nombre, v.cantidad_ventas, v.total_ventas]),
    );
  }

  descargarReportePrendas(): void {
    this.descargarCsv(
      'prendas_mas_vendidas.csv',
      ['Prenda', 'Cantidad vendida', 'Total (Bs.)'],
      this.reportePrendas().map((p) => [p.prenda_nombre, p.cantidad_vendida, p.total_vendido]),
    );
  }

  descargarQuiebresStock(): void {
    this.descargarCsv(
      'quiebres_de_stock.csv',
      ['Prenda', 'Sucursal', 'Stock disponible', 'Stock mínimo'],
      (this.dashboardReporte()?.quiebres ?? []).map((q) => [q.prenda_nombre, q.sucursal_nombre, q.stock_disponible, q.stock_minimo]),
    );
  }

  descargarInventarioGlobal(): void {
    this.descargarCsv(
      'inventario_global.csv',
      ['Prenda', 'Categoría', 'Talla', 'Color', 'Sucursal', 'Ciudad', 'Disponible', 'Mínimo', 'Quiebre'],
      this.inventarioGlobal().map((i) => [
        i.prenda_nombre, i.categoria_nombre || '', i.talla_nombre || '', i.color_nombre || '',
        i.sucursal_nombre, i.ciudad_nombre, i.stock_disponible, i.stock_minimo, i.es_quiebre ? 'Sí' : 'No',
      ]),
    );
  }

  // --- CU-30: Generar reporte mediante IA (prompt) ---
  generarReporteConIA(): void {
    if (!this.reporteIAPrompt.trim()) return;
    this.reporteIACargando.set(true);
    this.reporteIAError.set(null);
    this.reporteIAResultado.set(null);
    this.business.generarReporteIA(this.reporteIAPrompt).subscribe({
      next: (res) => {
        this.reporteIAResultado.set(res);
        this.reporteIACargando.set(false);
      },
      error: (err) => {
        this.reporteIAError.set(err.error?.detail || 'No se pudo generar el reporte con IA');
        this.reporteIACargando.set(false);
      },
    });
  }

  mostrarAlerta(type: 'success' | 'danger', text: string): void {
    this.alertMessage.set({ type, text });
    setTimeout(() => {
      if (this.alertMessage()?.text === text) this.alertMessage.set(null);
    }, 6000);
  }

  cerrarModal(): void {
    this.showModal.set(null);
  }

  // --- CU-04 Roles ---
  abrirModalRol(rol?: Rol): void {
    if (rol) {
      this.rolForm = {
        id: rol.id,
        nombre: rol.nombre,
        descripcion: rol.descripcion || '',
        permiso_ids: rol.permisos.map((p) => p.id),
      };
    } else {
      this.rolForm = { id: 0, nombre: '', descripcion: '', permiso_ids: [] };
    }
    this.showModal.set('rol');
  }

  togglePermiso(id: number): void {
    const idx = this.rolForm.permiso_ids.indexOf(id);
    if (idx > -1) {
      this.rolForm.permiso_ids.splice(idx, 1);
    } else {
      this.rolForm.permiso_ids.push(id);
    }
  }

  guardarRol(): void {
    if (!this.rolForm.nombre) return;
    if (this.rolForm.id === 0) {
      this.business.createRol(this.rolForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Rol creado exitosamente');
          this.cerrarModal();
          this.cambiarTab('roles');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al crear rol'),
      });
    } else {
      this.business.updateRol(this.rolForm.id, this.rolForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Rol actualizado exitosamente');
          this.cerrarModal();
          this.cambiarTab('roles');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar rol'),
      });
    }
  }

  eliminarRol(id: number): void {
    if (!confirm('¿Está seguro de desactivar este rol?')) return;
    this.business.deleteRol(id).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Rol desactivado');
        this.cambiarTab('roles');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar rol'),
    });
  }

  // --- CU-05 Personal ---
  abrirModalPersonal(p?: Personal): void {
    if (p) {
      this.personalForm = {
        id: p.id,
        nombres: p.nombres,
        apellidos: p.apellidos,
        cargo: p.cargo,
        sucursal_id: p.sucursal_id || null,
        correo: p.correo || '',
        celular: p.celular || '',
        password: '',
      };
    } else {
      this.personalForm = {
        id: 0,
        nombres: '',
        apellidos: '',
        cargo: 'Encargado',
        sucursal_id: this.sucursales().length ? this.sucursales()[0].id : null,
        correo: '',
        celular: '',
        password: '',
      };
    }
    this.showModal.set('personal');
  }

  guardarPersonal(): void {
    if (this.personalForm.id === 0) {
      this.business.createPersonal(this.personalForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Personal registrado correctamente');
          this.cerrarModal();
          this.cambiarTab('personal');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar personal'),
      });
    } else {
      this.business.updatePersonal(this.personalForm.id, this.personalForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Datos del personal actualizados');
          this.cerrarModal();
          this.cambiarTab('personal');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar personal'),
      });
    }
  }

  eliminarPersonal(id: number): void {
    if (!confirm('¿Está seguro de desactivar a este empleado?')) return;
    this.business.deletePersonal(id).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Personal desactivado');
        this.cambiarTab('personal');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar personal'),
    });
  }

  // --- CU-06 Sucursales ---
  abrirModalSucursal(s?: Sucursal): void {
    if (s) {
      this.sucursalForm = {
        id: s.id,
        nombre: s.nombre,
        ciudad_id: s.ciudad_id,
        direccion: s.direccion,
        telefono: s.telefono || '',
        hora_inicio: (s.hora_inicio as string) || '09:00',
        hora_fin: (s.hora_fin as string) || '21:00',
      };
    } else {
      this.sucursalForm = {
        id: 0,
        nombre: '',
        ciudad_id: this.ciudades().length ? this.ciudades()[0].id : 1,
        direccion: '',
        telefono: '',
        hora_inicio: '09:00',
        hora_fin: '21:00',
      };
    }
    this.showModal.set('sucursal');
  }

  guardarSucursal(): void {
    if (this.sucursalForm.id === 0) {
      this.business.createSucursal(this.sucursalForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Sucursal creada exitosamente');
          this.cerrarModal();
          this.cambiarTab('sucursales');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al crear sucursal'),
      });
    } else {
      this.business.updateSucursal(this.sucursalForm.id, this.sucursalForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Sucursal actualizada');
          this.cerrarModal();
          this.cambiarTab('sucursales');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar sucursal'),
      });
    }
  }

  eliminarSucursal(id: number): void {
    if (!confirm('¿Está seguro de desactivar esta sucursal?')) return;
    this.business.deleteSucursal(id).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Sucursal desactivada');
        this.cambiarTab('sucursales');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al desactivar sucursal'),
    });
  }

  agregarCiudad(): void {
    if (!this.nuevaCiudadNombre) return;
    this.business.createCiudad(this.nuevaCiudadNombre).subscribe({
      next: (nueva) => {
        this.ciudades.update((prev) => [...prev, nueva]);
        this.nuevaCiudadNombre = '';
        this.mostrarAlerta('success', 'Ciudad añadida');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al crear ciudad'),
    });
  }

  // --- CU-07 Proveedores ---
  abrirModalProveedor(p?: Proveedor): void {
    if (p) {
      this.proveedorForm = { id: p.id, nombre_empresa: p.nombre_empresa, contacto: p.contacto || '', correo: p.correo || '', password: '' };
    } else {
      this.proveedorForm = { id: 0, nombre_empresa: '', contacto: '', correo: '', password: '' };
    }
    this.showModal.set('proveedor');
  }

  guardarProveedor(): void {
    if (this.proveedorForm.id === 0) {
      this.business.createProveedor(this.proveedorForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Proveedor registrado correctamente');
          this.cerrarModal();
          this.cambiarTab('proveedores');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar proveedor'),
      });
    } else {
      this.business.updateProveedor(this.proveedorForm.id, this.proveedorForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Proveedor actualizado');
          this.cerrarModal();
          this.cambiarTab('proveedores');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar proveedor'),
      });
    }
  }

  eliminarProveedor(id: number): void {
    if (!confirm('¿Está seguro de desactivar este proveedor?')) return;
    this.business.deleteProveedor(id).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Proveedor desactivado');
        this.cambiarTab('proveedores');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar proveedor'),
    });
  }

  // --- CU-10 Temporadas ---
  abrirModalTemporada(t?: Temporada): void {
    if (t) {
      this.temporadaForm = {
        id: t.id,
        nombre: t.nombre,
        tipo: t.tipo || '',
        fecha_inicio: t.fecha_inicio || '',
        fecha_fin: t.fecha_fin || '',
      };
    } else {
      this.temporadaForm = { id: 0, nombre: '', tipo: '', fecha_inicio: '', fecha_fin: '' };
    }
    this.showModal.set('temporada');
  }

  guardarTemporada(): void {
    if (this.temporadaForm.id === 0) {
      this.business.crearTemporada(this.temporadaForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Temporada creada exitosamente');
          this.cerrarModal();
          this.cambiarTab('temporadas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al crear la temporada'),
      });
    } else {
      this.business.actualizarTemporada(this.temporadaForm.id, this.temporadaForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Temporada actualizada');
          this.cerrarModal();
          this.cambiarTab('temporadas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar la temporada'),
      });
    }
  }

  toggleTemporadaEstado(t: Temporada): void {
    this.business.actualizarTemporada(t.id, { estado: !t.estado }).subscribe({
      next: (actualizada) => {
        this.temporadas.update((prev) => prev.map((x) => (x.id === actualizada.id ? actualizada : x)));
        this.mostrarAlerta('success', actualizada.estado ? 'Temporada activada' : 'Temporada desactivada');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar la temporada'),
    });
  }

  // --- CU-10 Colecciones ---
  abrirModalColeccion(c?: Coleccion): void {
    if (c) {
      this.coleccionForm = { id: c.id, nombre: c.nombre, descripcion: c.descripcion || '', temporada_id: c.temporada_id };
    } else {
      this.coleccionForm = {
        id: 0,
        nombre: '',
        descripcion: '',
        temporada_id: this.temporadas().length ? this.temporadas()[0].id : null,
      };
    }
    this.showModal.set('coleccion');
  }

  guardarColeccion(): void {
    if (!this.coleccionForm.temporada_id) return;
    if (this.coleccionForm.id === 0) {
      this.business.crearColeccionAdmin({
        nombre: this.coleccionForm.nombre,
        descripcion: this.coleccionForm.descripcion,
        temporada_id: this.coleccionForm.temporada_id,
      }).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Colección creada exitosamente');
          this.cerrarModal();
          this.cambiarTab('temporadas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al crear la colección'),
      });
    } else {
      this.business.actualizarColeccionAdmin(this.coleccionForm.id, {
        nombre: this.coleccionForm.nombre,
        descripcion: this.coleccionForm.descripcion,
        temporada_id: this.coleccionForm.temporada_id ?? undefined,
      }).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Colección actualizada');
          this.cerrarModal();
          this.cambiarTab('temporadas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar la colección'),
      });
    }
  }

  toggleColeccionEstado(c: Coleccion): void {
    this.business.actualizarColeccionAdmin(c.id, { estado: !c.estado }).subscribe({
      next: (actualizada) => {
        this.coleccionesAdmin.update((prev) => prev.map((x) => (x.id === actualizada.id ? actualizada : x)));
        this.mostrarAlerta('success', actualizada.estado ? 'Colección activada' : 'Colección desactivada');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar la colección'),
    });
  }

  // --- CU-08 Catálogo de Prendas ---
  abrirModalPrenda(p?: Prenda): void {
    if (p) {
      this.prendaForm = {
        id: p.id,
        nombre: p.nombre,
        descripcion: p.descripcion || '',
        categoria_id: p.categoria_id,
        coleccion_id: p.coleccion_id || null,
        proveedor_id: p.proveedor_id || null,
        precio_base: p.precio_base,
        modelo_3d_url: p.modelo_3d_url || '',
        imagen_url: p.imagen_url || '',
      };
    } else {
      this.prendaForm = {
        id: 0,
        nombre: '',
        descripcion: '',
        categoria_id: this.categorias().length ? this.categorias()[0].id : 1,
        coleccion_id: this.colecciones().length ? this.colecciones()[0].id : null,
        proveedor_id: this.proveedores().length ? this.proveedores()[0].id : null,
        precio_base: 150.0,
        modelo_3d_url: '',
        imagen_url: '',
      };
    }
    this.showModal.set('prenda');
  }

  guardarPrenda(): void {
    if (this.prendaForm.id === 0) {
      this.business.createPrenda(this.prendaForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Prenda agregada al catálogo');
          this.cerrarModal();
          this.cambiarTab('prendas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al guardar prenda'),
      });
    } else {
      this.business.updatePrenda(this.prendaForm.id, this.prendaForm).subscribe({
        next: () => {
          this.mostrarAlerta('success', 'Prenda actualizada');
          this.cerrarModal();
          this.cambiarTab('prendas');
        },
        error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar prenda'),
      });
    }
  }

  eliminarPrenda(id: number): void {
    if (!confirm('¿Está seguro de desactivar esta prenda del catálogo?')) return;
    this.business.deletePrenda(id).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Prenda desactivada');
        this.cambiarTab('prendas');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar prenda'),
    });
  }

  // CU-33: el Admin valida y publica un producto que registró un Proveedor
  activarPrendaProveedor(p: Prenda): void {
    if (!confirm(`¿Publicar "${p.nombre}" en el catálogo?`)) return;
    this.business.updatePrenda(p.id, { estado: true }).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Producto validado y publicado en el catálogo');
        this.cambiarTab('prendas');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al activar el producto'),
    });
  }

  // --- CU-09: Catálogo Maestro (Categorías, Tallas y Colores) ---
  agregarCategoria(): void {
    if (!this.nuevaCategoriaForm.nombre.trim()) return;
    this.business.createCategoria(this.nuevaCategoriaForm).subscribe({
      next: (nueva) => {
        this.categorias.update((prev) => [...prev, nueva]);
        this.nuevaCategoriaForm = { nombre: '', descripcion: '' };
        this.mostrarAlerta('success', 'Categoría registrada correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar la categoría'),
    });
  }

  toggleCategoriaEstado(cat: Categoria): void {
    this.business.updateCategoria(cat.id, { estado: !cat.estado }).subscribe({
      next: (actualizada) => {
        this.categorias.update((prev) => prev.map((c) => (c.id === actualizada.id ? actualizada : c)));
        this.mostrarAlerta('success', actualizada.estado ? 'Categoría activada' : 'Categoría desactivada');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al actualizar la categoría'),
    });
  }

  agregarTalla(): void {
    if (!this.nuevaTallaNombre.trim()) return;
    this.business.createTalla(this.nuevaTallaNombre.trim()).subscribe({
      next: (nueva) => {
        this.tallas.update((prev) => [...prev, nueva]);
        this.nuevaTallaNombre = '';
        this.mostrarAlerta('success', 'Talla registrada correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar la talla'),
    });
  }

  eliminarTalla(id: number): void {
    if (!confirm('¿Está seguro de eliminar esta talla?')) return;
    this.business.deleteTalla(id).subscribe({
      next: () => {
        this.tallas.update((prev) => prev.filter((t) => t.id !== id));
        this.mostrarAlerta('success', 'Talla eliminada correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar la talla'),
    });
  }

  agregarColor(): void {
    if (!this.nuevoColorForm.nombre.trim()) return;
    this.business.createColor(this.nuevoColorForm).subscribe({
      next: (nuevo) => {
        this.colores.update((prev) => [...prev, nuevo]);
        this.nuevoColorForm = { nombre: '', hex: '#4f46e5' };
        this.mostrarAlerta('success', 'Color registrado correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar el color'),
    });
  }

  eliminarColor(id: number): void {
    if (!confirm('¿Está seguro de eliminar este color?')) return;
    this.business.deleteColor(id).subscribe({
      next: () => {
        this.colores.update((prev) => prev.filter((c) => c.id !== id));
        this.mostrarAlerta('success', 'Color eliminado correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al eliminar el color'),
    });
  }

  // --- CU-11: Variantes de prenda (talla + color) ---
  abrirModalVariantes(prenda: Prenda): void {
    this.prendaSeleccionadaVariantes.set(prenda);
    this.nuevaVarianteForm = { talla_id: null, color_id: null };
    this.business.getTallas().subscribe((data) => {
      this.tallas.set(data);
      if (data.length) this.nuevaVarianteForm.talla_id = data[0].id;
    });
    this.business.getColores().subscribe((data) => {
      this.colores.set(data);
      if (data.length) this.nuevaVarianteForm.color_id = data[0].id;
    });
    this.cargarVariantesDePrenda(prenda.id);
    this.showModal.set('variantes');
  }

  cargarVariantesDePrenda(prendaId: number): void {
    this.business.getVariantes(prendaId).subscribe((data) => this.variantesPrendaActual.set(data));
  }

  agregarVariante(): void {
    const prenda = this.prendaSeleccionadaVariantes();
    if (!prenda || !this.nuevaVarianteForm.talla_id || !this.nuevaVarianteForm.color_id) return;

    this.business.createVariante(prenda.id, {
      talla_id: this.nuevaVarianteForm.talla_id,
      color_id: this.nuevaVarianteForm.color_id,
    }).subscribe({
      next: (nueva) => {
        this.variantesPrendaActual.update((prev) => [...prev, nueva]);
        this.mostrarAlerta('success', 'Variante agregada correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al agregar la variante'),
    });
  }

  eliminarVariante(varianteId: number): void {
    const prenda = this.prendaSeleccionadaVariantes();
    if (!prenda) return;
    if (!confirm('¿Está seguro de desactivar esta variante?')) return;

    this.business.deleteVariante(prenda.id, varianteId).subscribe({
      next: () => {
        this.cargarVariantesDePrenda(prenda.id);
        this.mostrarAlerta('success', 'Variante desactivada correctamente');
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al desactivar la variante'),
    });
  }
}
