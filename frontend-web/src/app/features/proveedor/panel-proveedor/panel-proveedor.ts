import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Categoria, DisponibilidadProveedor, Prenda } from '../../../core/models/user.model';
import { AuthService } from '../../../core/services/auth.service';
import { BusinessService } from '../../../core/services/business.service';

@Component({
  selector: 'app-panel-proveedor',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './panel-proveedor.html',
  styles: [`
    .proveedor-hero {
      background: linear-gradient(135deg, #78350f 0%, #92400e 100%);
      border-radius: 16px;
      padding: 2rem 2.5rem;
      color: #ffffff;
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 10px 25px -5px rgba(120, 53, 15, 0.2);

      h2 { color: #ffffff; font-size: 1.75rem; margin-bottom: 0.35rem; }
      p { color: #fde68a; font-size: 0.9rem; }
    }
  `],
})
export class PanelProveedor implements OnInit {
  private readonly business = inject(BusinessService);
  readonly authService = inject(AuthService);

  isLoading = signal(false);
  alertMessage = signal<{ type: 'success' | 'danger'; text: string } | null>(null);
  showModal = signal<'producto' | 'disponibilidad' | null>(null);

  productos = signal<Prenda[]>([]);
  categorias = signal<Categoria[]>([]);
  disponibilidad = signal<DisponibilidadProveedor[]>([]);

  productoSeleccionado = signal<Prenda | null>(null);

  productoForm = { nombre: '', descripcion: '', categoria_id: null as number | null, precio_base: 150.0, modelo_3d_url: '' };
  disponibilidadForm = { cantidad: 10, fecha_estimada: '' };
  private ultimoIntentoDuplicado: typeof this.productoForm | null = null;

  ngOnInit(): void {
    this.cargarDatos();
  }

  cargarDatos(): void {
    this.isLoading.set(true);
    this.business.getCategorias().subscribe((data) => {
      this.categorias.set(data);
      if (data.length && this.productoForm.categoria_id === null) this.productoForm.categoria_id = data[0].id;
    });
    this.business.getMisProductosProveedor().subscribe({
      next: (data) => { this.productos.set(data); this.isLoading.set(false); },
      error: () => this.isLoading.set(false),
    });
    this.business.getMiDisponibilidad().subscribe({ next: (data) => this.disponibilidad.set(data) });
  }

  mostrarAlerta(type: 'success' | 'danger', text: string): void {
    this.alertMessage.set({ type, text });
    setTimeout(() => {
      if (this.alertMessage()?.text === text) this.alertMessage.set(null);
    }, 6000);
  }

  cerrarModal(): void {
    this.showModal.set(null);
    this.ultimoIntentoDuplicado = null;
  }

  abrirModalProducto(): void {
    this.productoForm = {
      nombre: '',
      descripcion: '',
      categoria_id: this.categorias().length ? this.categorias()[0].id : null,
      precio_base: 150.0,
      modelo_3d_url: '',
    };
    this.showModal.set('producto');
  }

  registrarProducto(forzar = false): void {
    if (!this.productoForm.categoria_id) return;
    this.business.registrarProductoProveedor({
      nombre: this.productoForm.nombre,
      descripcion: this.productoForm.descripcion,
      categoria_id: this.productoForm.categoria_id,
      precio_base: this.productoForm.precio_base,
      modelo_3d_url: this.productoForm.modelo_3d_url,
      forzar,
    }).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Producto registrado. Quedará pendiente de validación del administrador.');
        this.cerrarModal();
        this.cargarDatos();
      },
      error: (err) => {
        if (err.status === 409) {
          this.ultimoIntentoDuplicado = { ...this.productoForm };
          this.mostrarAlerta('danger', err.error?.detail || 'Ya existe un producto con ese nombre. Pulsa nuevamente "Guardar" para confirmar de todas formas.');
        } else {
          this.mostrarAlerta('danger', err.error?.detail || 'Error al registrar el producto');
        }
      },
    });
  }

  confirmarGuardarProducto(): void {
    const esReintentoDuplicado = this.ultimoIntentoDuplicado !== null
      && this.ultimoIntentoDuplicado.nombre === this.productoForm.nombre;
    this.registrarProducto(esReintentoDuplicado);
  }

  abrirModalDisponibilidad(prenda: Prenda): void {
    this.productoSeleccionado.set(prenda);
    const manana = new Date();
    manana.setDate(manana.getDate() + 7);
    this.disponibilidadForm = { cantidad: 10, fecha_estimada: manana.toISOString().slice(0, 10) };
    this.showModal.set('disponibilidad');
  }

  guardarDisponibilidad(): void {
    const prenda = this.productoSeleccionado();
    if (!prenda) return;
    this.business.informarDisponibilidad(prenda.id, this.disponibilidadForm).subscribe({
      next: () => {
        this.mostrarAlerta('success', 'Disponibilidad informada correctamente');
        this.cerrarModal();
        this.cargarDatos();
      },
      error: (err) => this.mostrarAlerta('danger', err.error?.detail || 'Error al informar la disponibilidad'),
    });
  }
}
