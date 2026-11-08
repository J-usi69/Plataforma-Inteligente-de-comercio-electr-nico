import { HttpParams } from '@angular/common/http';
import { describe, expect, it } from 'vitest';
import { parametrosDe } from '../../core/services/fuentes';
import { alturaBarra } from '../../features/plataforma/indicadores-plataforma/indicadores-plataforma';
import { mover } from './reportes-personalizados';

describe('constructor de reportes personalizables', () => {
  it('reordena columnas sin salirse de la lista', () => {
    expect(mover(['A', 'B', 'C'], 2, -1)).toEqual(['A', 'C', 'B']);
    expect(mover(['A', 'B', 'C'], 0, -1)).toEqual(['A', 'B', 'C']);
    expect(mover(['A', 'B', 'C'], 2, 1)).toEqual(['A', 'B', 'C']);
  });

  it('manda columnas y criterios repetidos y omite criterios sin valor', () => {
    const params: HttpParams = parametrosDe({
      desde: '2026-10-01',
      columnas: ['Empresa', 'Plan'],
      criterios: [
        { columna: 'Plan', operador: 'igual', valor: ' Básico ' },
        { columna: 'Empresa', operador: 'contiene', valor: '  ' },
      ],
      orden: 'Empresa',
      descendente: false,
    });
    expect(params.getAll('columnas')).toEqual(['Empresa', 'Plan']);
    expect(params.getAll('criterio')).toEqual(['Plan|igual|Básico']);
    expect(params.get('desde')).toBe('2026-10-01');
    expect(params.get('hasta')).toBeNull();
    expect(params.get('descendente')).toBe('false');
  });

  it('escala las barras respecto del mayor y deja visibles los valores chicos', () => {
    expect(alturaBarra(50, 100)).toBe(50);
    expect(alturaBarra(1, 1000)).toBe(4);
    expect(alturaBarra(0, 100)).toBe(0);
    expect(alturaBarra(10, 0)).toBe(0);
  });
});
