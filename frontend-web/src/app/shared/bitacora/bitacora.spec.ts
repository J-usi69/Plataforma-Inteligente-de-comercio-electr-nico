import { describe, expect, it } from 'vitest';
import { criteriosBitacora } from './bitacora';

describe('filtros de la bitácora', () => {
  it('convierte los filtros llenos en criterios «contiene» y omite los vacíos', () => {
    expect(criteriosBitacora({ usuario: ' admin@fashionstore.com ', accion: '', empresa: 'Moda' })).toEqual([
      { columna: 'Usuario', operador: 'contiene', valor: 'admin@fashionstore.com' },
      { columna: 'Empresa', operador: 'contiene', valor: 'Moda' },
    ]);
    expect(criteriosBitacora({ usuario: '', accion: '  ', empresa: '' })).toEqual([]);
  });
});
