/** Guarda un archivo recibido de la API (Blob) con el nombre indicado. */
export function descargar(archivo: Blob, nombre: string): void {
  const url = URL.createObjectURL(archivo);
  const enlace = document.createElement('a');
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** El mensaje de error de la API, también cuando la respuesta era un archivo (Blob con el JSON adentro). */
export async function detalleDelError(err: { status?: number; error?: unknown } | null | undefined, porDefecto: string): Promise<string> {
  let cuerpo = err?.error;
  if (cuerpo instanceof Blob) {
    try {
      cuerpo = JSON.parse(await cuerpo.text());
    } catch {
      return porDefecto;
    }
  }
  const detalle = (cuerpo as { detail?: unknown } | null | undefined)?.detail;
  return typeof detalle === 'string' ? detalle : porDefecto;
}

/** La fecha de hoy como AAAA-MM-DD (para nombres de archivo). */
export function hoyISO(): string {
  return new Date().toISOString().slice(0, 10);
}
