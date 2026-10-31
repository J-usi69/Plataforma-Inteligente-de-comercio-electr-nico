// Persistencia local de la operación sin conexión (IndexedDB): el paquete descargado en tablas
// normalizadas, como las devuelve el backend, y la cola de operaciones. Sobrevive a cerrar la
// pestaña o reiniciar el equipo. Cada empresa tiene su propia base en el navegador.
import { DBSchema, IDBPDatabase, IDBPTransaction, StoreNames, openDB } from 'idb';
import {
  ClienteLocal,
  ColorLocal,
  InfoPaquete,
  InventarioLocal,
  ItemNombre,
  OperacionLocal,
  Paquete,
  PrendaLocal,
  SucursalLocal,
  VarianteLocal,
  VentaCambiable,
} from './modelos';

interface EsquemaOffline extends DBSchema {
  meta: { key: string; value: { clave: string; valor: unknown } };
  sucursales: { key: number; value: SucursalLocal };
  categorias: { key: number; value: ItemNombre };
  tallas: { key: number; value: ItemNombre };
  colores: { key: number; value: ColorLocal };
  prendas: { key: number; value: PrendaLocal };
  variantes: { key: number; value: VarianteLocal; indexes: { prenda_id: number } };
  inventario: { key: [number, number]; value: InventarioLocal };
  clientes: { key: number; value: ClienteLocal };
  ventas: { key: number; value: VentaCambiable };
  operaciones: { key: string; value: OperacionLocal; indexes: { orden: number } };
}

const TABLAS = ['sucursales', 'categorias', 'tallas', 'colores', 'prendas', 'variantes', 'inventario', 'clientes', 'ventas'] as const;
type Tabla = (typeof TABLAS)[number];
type Escritura = IDBPTransaction<EsquemaOffline, StoreNames<EsquemaOffline>[], 'readwrite'>;

/** El paquete tal como quedó guardado, listo para mostrar. */
export type DatosLocales = { info: InfoPaquete } & Pick<Paquete, Tabla>;

export class AlmacenLocal {
  private db?: Promise<IDBPDatabase<EsquemaOffline>>;

  constructor(private readonly nombre: string) {}

  private abrir(): Promise<IDBPDatabase<EsquemaOffline>> {
    return (this.db ??= openDB<EsquemaOffline>(this.nombre, 1, {
      upgrade(db) {
        db.createObjectStore('meta', { keyPath: 'clave' });
        for (const tabla of ['sucursales', 'categorias', 'tallas', 'colores', 'prendas', 'clientes', 'ventas'] as const) {
          db.createObjectStore(tabla, { keyPath: 'id' });
        }
        db.createObjectStore('variantes', { keyPath: 'id' }).createIndex('prenda_id', 'prenda_id');
        db.createObjectStore('inventario', { keyPath: ['variante_id', 'sucursal_id'] });
        db.createObjectStore('operaciones', { keyPath: 'id' }).createIndex('orden', 'orden');
      },
    }));
  }

  /** Reemplaza el paquete entero en una sola transacción (o queda el anterior completo). Lo
   * vendido o reservado en este dispositivo que el servidor todavía no conoce se vuelve a
   * descontar del stock recién descargado. */
  async guardarPaquete(
    paquete: Paquete,
    usuarioId: number,
    sinEnviar: OperacionLocal[],
    efecto: (op: OperacionLocal) => Map<number, number>,
  ): Promise<void> {
    const db = await this.abrir();
    const tx = db.transaction(['meta', ...TABLAS], 'readwrite');
    for (const tabla of TABLAS) {
      const almacen = tx.objectStore(tabla) as unknown as { clear(): Promise<void>; put(fila: unknown): Promise<unknown> };
      await almacen.clear();
      for (const fila of paquete[tabla]) {
        await almacen.put(fila);
      }
    }
    for (const op of sinEnviar) {
      await this.aplicarEfecto(tx, op.sucursal_id, efecto(op));
    }
    const info: InfoPaquete = {
      generado_en: paquete.generado_en,
      vigencia_horas: paquete.vigencia_horas,
      tienda: paquete.tienda,
      dias_para_cambio: paquete.dias_para_cambio,
      usuario_id: usuarioId,
    };
    await tx.objectStore('meta').put({ clave: 'paquete', valor: info });
    await tx.done;
  }

  async leerPaquete(): Promise<DatosLocales | null> {
    const db = await this.abrir();
    const info = (await db.get('meta', 'paquete'))?.valor as InfoPaquete | undefined;
    if (!info) {
      return null;
    }
    const tx = db.transaction([...TABLAS], 'readonly');
    const filas = await Promise.all(TABLAS.map((tabla) => tx.objectStore(tabla).getAll()));
    const datos = Object.fromEntries(TABLAS.map((tabla, i) => [tabla, filas[i]]));
    return { info, ...datos } as DatosLocales;
  }

  /** Al cerrar sesión: el paquete tiene datos de clientes. Las operaciones no se tocan. */
  async borrarPaquete(): Promise<void> {
    const db = await this.abrir();
    const tx = db.transaction(['meta', ...TABLAS], 'readwrite');
    await Promise.all([...TABLAS.map((tabla) => tx.objectStore(tabla).clear()), tx.objectStore('meta').delete('paquete')]);
    await tx.done;
  }

  async operaciones(): Promise<OperacionLocal[]> {
    const db = await this.abrir();
    return db.getAllFromIndex('operaciones', 'orden');
  }

  /** Guarda la operación y descuenta su efecto del stock local, juntos: o quedan las dos cosas o
   * ninguna. Le asigna su lugar en la cola. */
  async registrar(op: OperacionLocal, efecto: Map<number, number>): Promise<OperacionLocal> {
    const db = await this.abrir();
    const tx = db.transaction(['meta', 'inventario', 'operaciones'], 'readwrite');
    const ultimo = ((await tx.objectStore('meta').get('ultimo_orden'))?.valor as number | undefined) ?? 0;
    const registrada = { ...op, orden: ultimo + 1 };
    await tx.objectStore('meta').put({ clave: 'ultimo_orden', valor: registrada.orden });
    await tx.objectStore('operaciones').add(registrada);
    await this.aplicarEfecto(tx as unknown as Escritura, op.sucursal_id, efecto);
    await tx.done;
    return registrada;
  }

  async actualizar(ops: OperacionLocal[]): Promise<void> {
    const db = await this.abrir();
    const tx = db.transaction('operaciones', 'readwrite');
    await Promise.all(ops.map((op) => tx.store.put(op)));
    await tx.done;
  }

  private async aplicarEfecto(tx: Escritura, sucursalId: number, efecto: Map<number, number>): Promise<void> {
    const inventario = tx.objectStore('inventario');
    for (const [varianteId, cambio] of efecto) {
      const fila = (await inventario.get([varianteId, sucursalId])) ?? { variante_id: varianteId, sucursal_id: sucursalId, stock_disponible: 0 };
      await inventario.put({ ...fila, stock_disponible: Math.max(0, fila.stock_disponible + cambio) });
    }
  }
}
