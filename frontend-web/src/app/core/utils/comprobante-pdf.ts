import { jsPDF } from 'jspdf';
import { ComprobanteVenta } from '../models/user.model';

// CU-23: genera un comprobante en PDF descargable (formato ticket angosto),
// reusado por la vista de "Mis Compras" del Cliente y por la Caja del Cajero.
export function descargarComprobantePdf(comp: ComprobanteVenta): void {
  const doc = new jsPDF({ unit: 'mm', format: [80, 150 + comp.items.length * 6] });
  const centro = 40;
  let y = 10;

  doc.setFontSize(12).setFont('helvetica', 'bold');
  doc.text('FashionStore', centro, y, { align: 'center' });
  y += 6;
  doc.setFontSize(8).setFont('helvetica', 'normal');
  doc.text(comp.sucursal_nombre, centro, y, { align: 'center' });
  y += 4;
  doc.text(comp.sucursal_direccion, centro, y, { align: 'center' });
  y += 6;

  doc.setFont('helvetica', 'bold');
  doc.text(`Comprobante ${comp.numero_comprobante}`, centro, y, { align: 'center' });
  y += 5;
  doc.setFont('helvetica', 'normal');
  doc.text(`Fecha: ${new Date(comp.fecha_emision).toLocaleString('es-BO')}`, 4, y);
  y += 4;
  doc.text(`Cliente: ${comp.cliente_nombre}`, 4, y);
  y += 4;
  if (comp.cajero_nombre) {
    doc.text(`Cajero: ${comp.cajero_nombre}`, 4, y);
    y += 4;
  }
  doc.text(`Pago: ${comp.metodo_pago} — Estado: ${comp.estado_venta}`, 4, y);
  y += 6;

  doc.line(4, y, 76, y);
  y += 4;
  comp.items.forEach((item) => {
    doc.setFont('helvetica', 'bold');
    doc.text(item.descripcion, 4, y);
    y += 4;
    doc.setFont('helvetica', 'normal');
    const detalle = [item.talla, item.color].filter(Boolean).join(' / ');
    doc.text(`${detalle ? detalle + ' — ' : ''}${item.cantidad} x Bs. ${item.precio_unitario.toFixed(2)}`, 4, y);
    doc.text(`Bs. ${item.subtotal.toFixed(2)}`, 76, y, { align: 'right' });
    y += 5;
  });

  doc.line(4, y, 76, y);
  y += 5;
  doc.setFont('helvetica', 'bold').setFontSize(9);
  doc.text('TOTAL', 4, y);
  doc.text(`Bs. ${comp.total.toFixed(2)}`, 76, y, { align: 'right' });
  y += 8;
  doc.setFontSize(7).setFont('helvetica', 'normal');
  doc.text('¡Gracias por tu compra!', centro, y, { align: 'center' });

  doc.save(`comprobante_${comp.numero_comprobante}.pdf`);
}
