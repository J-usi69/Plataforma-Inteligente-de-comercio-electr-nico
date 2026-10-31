import { DatosCambio, DatosVenta } from './modelos';
import {
  dentroDelPlazo,
  diferenciaDeCambio,
  efectoEnStock,
  estadoTrasResultado,
  nuevoId,
  paqueteDesactualizado,
  pendienteDeEnvio,
  resumenDe,
  totalDe,
} from './reglas';

describe('Reglas de la operación sin conexión', () => {
  it('los montos se redondean a centavos como en el backend', () => {
    expect(totalDe([{ variante_id: 1, cantidad: 3, precio_unitario: 33.335 }])).toBe(100.01);
    const devuelve = [{ variante_id: 1, cantidad: 1, precio_unitario: 100 }];
    expect(diferenciaDeCambio(devuelve, [{ variante_id: 2, cantidad: 1, precio_unitario: 150 }])).toBe(50);
    expect(diferenciaDeCambio(devuelve, [{ variante_id: 2, cantidad: 1, precio_unitario: 80 }])).toBe(-20);
  });

  it('una venta saca stock y un cambio devuelve lo que vuelve y saca lo que se lleva', () => {
    const venta: DatosVenta = {
      cliente_id: null,
      detalles: [
        { variante_id: 1, cantidad: 2, precio_unitario: 10 },
        { variante_id: 1, cantidad: 1, precio_unitario: 10 },
      ],
      total: 30,
      metodo_pago: 'efectivo',
      monto_recibido: null,
    };
    expect([...efectoEnStock('venta', venta)]).toEqual([[1, -3]]);

    const cambio: DatosCambio = {
      venta_id: 9,
      venta_operacion_id: null,
      devuelve: [{ variante_id: 1, cantidad: 1 }],
      entrega: [{ variante_id: 2, cantidad: 1, precio_unitario: 10 }],
      diferencia: 0,
      motivo: null,
      metodo_pago: 'efectivo',
    };
    expect(Object.fromEntries(efectoEnStock('cambio', cambio))).toEqual({ 1: 1, 2: -1 });
    expect(resumenDe('cambio', cambio)).toContain('devuelve 1 prenda');
  });

  it('el plazo de cambio se cuenta en días desde la venta', () => {
    const venta = '2026-10-01T12:00:00Z';
    expect(dentroDelPlazo(venta, 7, new Date('2026-10-08T11:59:00Z'))).toBe(true);
    expect(dentroDelPlazo(venta, 7, new Date('2026-10-08T12:01:00Z'))).toBe(false);
  });

  it('solo la respuesta "error" del servidor deja la operación para reenviar', () => {
    expect(estadoTrasResultado({ estado: 'error' })).toBe('enviada');
    expect(estadoTrasResultado({ estado: 'conflicto' })).toBe('conflicto');
    expect(pendienteDeEnvio({ estado: 'enviada' })).toBe(true);
    expect(pendienteDeEnvio({ estado: 'rechazada' })).toBe(false);
  });

  it('avisa cuando el paquete superó su vigencia y genera ids únicos', () => {
    const ahora = Date.parse('2026-10-24T12:00:00Z');
    expect(paqueteDesactualizado('2026-10-24T01:00:00Z', 12, ahora)).toBe(false);
    expect(paqueteDesactualizado('2026-10-23T23:00:00Z', 12, ahora)).toBe(true);
    const ids = new Set(Array.from({ length: 50 }, nuevoId));
    expect(ids.size).toBe(50);
    expect([...ids][0]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  });
});
