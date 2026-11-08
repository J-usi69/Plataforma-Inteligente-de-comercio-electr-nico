import { describe, expect, it } from 'vitest';
import { resumenDeTablas } from './respaldo';

describe('resumen de una restauración', () => {
  it('muestra las tablas principales con nombres legibles y en orden fijo', () => {
    expect(resumenDeTablas({ venta: 12, usuario: 3, rol_permiso: 40, bitacora: 90 })).toEqual([
      { nombre: 'Cuentas de usuario', filas: 3 },
      { nombre: 'Ventas', filas: 12 },
      { nombre: 'Registros de bitácora', filas: 90 },
    ]);
  });
});
