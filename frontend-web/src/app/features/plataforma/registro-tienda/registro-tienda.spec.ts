import { aDireccion } from './registro-tienda';

describe('aDireccion (dirección de la empresa en la URL)', () => {
  it('arma la dirección desde el nombre: sin tildes, en minúsculas y con guiones', () => {
    expect(aDireccion('Moda Sureña  Ñandú')).toBe('moda-surena-nandu');
  });

  it('al enviar no deja guiones en los extremos', () => {
    expect(aDireccion('-moda-andina-')).toBe('moda-andina');
  });

  it('mientras se escribe a mano conserva el guion del final para poder seguir escribiendo', () => {
    // Tecla por tecla: "m", "mo", ..., "moda-", "moda-a", ... como hace el campo en cada cambio
    let campo = '';
    for (const letra of 'moda-andina') {
      campo = aDireccion(campo + letra, true);
    }
    expect(campo).toBe('moda-andina');
  });
});
