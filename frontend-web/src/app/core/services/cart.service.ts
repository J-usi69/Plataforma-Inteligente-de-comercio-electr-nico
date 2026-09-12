import { Injectable, computed, signal } from '@angular/core';

export interface CartItem {
  variante_id: number;
  prenda_id: number;
  nombre: string;
  talla: string;
  color: string;
  precio: number;
  cantidad: number;
  imagen_url?: string | null;
}

@Injectable({ providedIn: 'root' })
export class CartService {
  private readonly _items = signal<CartItem[]>([]);
  private readonly _sucursalId = signal<number>(1);

  readonly items = this._items.asReadonly();
  readonly sucursalId = this._sucursalId.asReadonly();

  readonly totalItems = computed(() =>
    this._items().reduce((acc, item) => acc + item.cantidad, 0)
  );

  readonly totalPrecio = computed(() =>
    this._items().reduce((acc, item) => acc + item.precio * item.cantidad, 0)
  );

  constructor() {
    this.cargarDesdeStorage();
  }

  private cargarDesdeStorage(): void {
    const raw = localStorage.getItem('fs_cart');
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        this._items.set(parsed.items || []);
        if (parsed.sucursalId) {
          this._sucursalId.set(parsed.sucursalId);
        }
      } catch {
        this._items.set([]);
      }
    }
  }

  private guardarEnStorage(): void {
    localStorage.setItem(
      'fs_cart',
      JSON.stringify({
        items: this._items(),
        sucursalId: this._sucursalId(),
      })
    );
  }

  setSucursal(id: number): void {
    this._sucursalId.set(id);
    this.guardarEnStorage();
  }

  agregar(item: CartItem): void {
    this._items.update((actuales) => {
      const idx = actuales.findIndex((i) => i.variante_id === item.variante_id);
      if (idx > -1) {
        const clon = [...actuales];
        clon[idx].cantidad += item.cantidad;
        return clon;
      }
      return [...actuales, item];
    });
    this.guardarEnStorage();
  }

  quitar(varianteId: number): void {
    this._items.update((actuales) => actuales.filter((i) => i.variante_id !== varianteId));
    this.guardarEnStorage();
  }

  actualizarCantidad(varianteId: number, cantidad: number): void {
    if (cantidad <= 0) {
      this.quitar(varianteId);
      return;
    }
    this._items.update((actuales) =>
      actuales.map((i) => (i.variante_id === varianteId ? { ...i, cantidad } : i))
    );
    this.guardarEnStorage();
  }

  vaciar(): void {
    this._items.set([]);
    localStorage.removeItem('fs_cart');
  }
}

