// Marca de la empresa: sus dos colores reemplazan a los tokens de styles.scss (--primary,
// --accent y sus variantes), así toda la web se viste con la marca sin tocar los componentes.

type Rgb = [number, number, number];

function aRgb(hex: string): Rgb {
  const limpio = hex.replace('#', '');
  return [0, 2, 4].map((i) => parseInt(limpio.slice(i, i + 2), 16)) as Rgb;
}

function aHex([r, g, b]: Rgb): string {
  return '#' + [r, g, b].map((c) => Math.round(c).toString(16).padStart(2, '0')).join('');
}

/** Mezcla `color` con `con` en la proporción indicada (0 = color, 1 = con). */
function mezclar(color: string, con: string, proporcion: number): string {
  const a = aRgb(color);
  const b = aRgb(con);
  return aHex(a.map((c, i) => c + (b[i] - c) * proporcion) as Rgb);
}

export function aplicarMarca(primario: string, acento: string, raiz: HTMLElement = document.documentElement): void {
  const [r, g, b] = aRgb(primario);
  const tokens: Record<string, string> = {
    '--primary': primario,
    '--primary-hover': mezclar(primario, '#000000', 0.15),
    '--primary-light': mezclar(primario, '#ffffff', 0.92),
    '--primary-glow': `rgba(${r}, ${g}, ${b}, 0.25)`,
    '--border-focus': mezclar(primario, '#ffffff', 0.4),
    '--accent': acento,
    '--accent-light': mezclar(acento, '#ffffff', 0.92),
  };
  for (const [token, valor] of Object.entries(tokens)) {
    raiz.style.setProperty(token, valor);
  }
}
