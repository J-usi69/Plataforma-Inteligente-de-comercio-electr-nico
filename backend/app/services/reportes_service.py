"""Consultas de agregación reutilizadas por los reportes predefinidos (CU-31, CU-32),
por el reporte generado mediante IA (CU-16) y por el módulo de exportación (CU-17)."""
from datetime import date, datetime, time, timezone
import io
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalogo import Categoria, Color, Prenda, Talla, VariantePrenda
from app.models.enums import EstadoReserva, EstadoVenta
from app.models.inventario import InventarioSucursal
from app.models.reserva import Reserva
from app.models.sucursal import Ciudad, Sucursal
from app.models.venta import DetalleVenta, Venta


def _inicio_dia(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, time.min, tzinfo=timezone.utc) if d else None


def _fin_dia(d: Optional[date]) -> Optional[datetime]:
    return datetime.combine(d, time.max, tzinfo=timezone.utc) if d else None


def ventas_por_sucursal(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> list[dict]:
    stmt = select(
        Venta.sucursal_id,
        func.count(Venta.id),
        func.coalesce(func.sum(Venta.total), 0),
    ).where(Venta.estado == EstadoVenta.pagada)
    if desde:
        stmt = stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        stmt = stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    stmt = stmt.group_by(Venta.sucursal_id).order_by(func.sum(Venta.total).desc())

    resultado = []
    for sucursal_id, cantidad, total in db.execute(stmt).all():
        sucursal = db.get(Sucursal, sucursal_id)
        resultado.append({
            "sucursal_id": sucursal_id,
            "sucursal_nombre": sucursal.nombre if sucursal else "Sucursal eliminada",
            "cantidad_ventas": cantidad,
            "total_ventas": float(total),
        })
    return resultado


def prendas_mas_vendidas(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None, limit: int = 10) -> list[dict]:
    stmt = (
        select(
            DetalleVenta.variante_id,
            func.sum(DetalleVenta.cantidad),
            func.sum(DetalleVenta.subtotal),
        )
        .join(Venta, Venta.id == DetalleVenta.venta_id)
        .where(Venta.estado == EstadoVenta.pagada)
    )
    if desde:
        stmt = stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        stmt = stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    stmt = stmt.group_by(DetalleVenta.variante_id).order_by(func.sum(DetalleVenta.cantidad).desc()).limit(limit)

    resultado = []
    for variante_id, cantidad, total in db.execute(stmt).all():
        variante = db.get(VariantePrenda, variante_id)
        prenda = db.get(Prenda, variante.prenda_id) if variante else None
        resultado.append({
            "prenda_id": prenda.id if prenda else None,
            "prenda_nombre": prenda.nombre if prenda else "Prenda eliminada",
            "cantidad_vendida": int(cantidad),
            "total_vendido": float(total),
        })
    return resultado


def quiebres_stock(db: Session, sucursal_id: Optional[int] = None) -> list[dict]:
    stmt = select(InventarioSucursal).where(InventarioSucursal.stock_disponible < InventarioSucursal.stock_minimo)
    if sucursal_id:
        stmt = stmt.where(InventarioSucursal.sucursal_id == sucursal_id)

    resultado = []
    for inv in db.scalars(stmt).all():
        variante = db.get(VariantePrenda, inv.variante_id)
        prenda = db.get(Prenda, variante.prenda_id) if variante else None
        sucursal = db.get(Sucursal, inv.sucursal_id)
        resultado.append({
            "variante_id": inv.variante_id,
            "prenda_nombre": prenda.nombre if prenda else "Prenda eliminada",
            "sucursal_id": inv.sucursal_id,
            "sucursal_nombre": sucursal.nombre if sucursal else "Sucursal eliminada",
            "stock_disponible": inv.stock_disponible,
            "stock_minimo": inv.stock_minimo,
        })
    return resultado


def inventario_global(db: Session, ciudad_id: Optional[int] = None, categoria_id: Optional[int] = None) -> list[dict]:
    """CU-27: existencias de todas las sucursales activas, consolidadas, con filtros
    opcionales por ciudad y categoría."""
    stmt = (
        select(InventarioSucursal, VariantePrenda, Prenda, Talla, Color, Sucursal, Ciudad, Categoria)
        .join(VariantePrenda, VariantePrenda.id == InventarioSucursal.variante_id)
        .join(Prenda, Prenda.id == VariantePrenda.prenda_id)
        .outerjoin(Talla, Talla.id == VariantePrenda.talla_id)
        .outerjoin(Color, Color.id == VariantePrenda.color_id)
        .join(Sucursal, Sucursal.id == InventarioSucursal.sucursal_id)
        .join(Ciudad, Ciudad.id == Sucursal.ciudad_id)
        .outerjoin(Categoria, Categoria.id == Prenda.categoria_id)
        .where(Sucursal.estado.is_(True), Sucursal.fecha_eliminacion.is_(None))
    )
    if ciudad_id:
        stmt = stmt.where(Ciudad.id == ciudad_id)
    if categoria_id:
        stmt = stmt.where(Prenda.categoria_id == categoria_id)
    stmt = stmt.order_by(Ciudad.nombre, Sucursal.nombre, Prenda.nombre)

    resultado = []
    for inv, variante, prenda, talla, color, sucursal, ciudad, categoria in db.execute(stmt).all():
        resultado.append({
            "variante_id": variante.id,
            "prenda_nombre": prenda.nombre,
            "categoria_id": categoria.id if categoria else None,
            "categoria_nombre": categoria.nombre if categoria else None,
            "talla_nombre": talla.nombre if talla else None,
            "color_nombre": color.nombre if color else None,
            "sucursal_id": sucursal.id,
            "sucursal_nombre": sucursal.nombre,
            "ciudad_id": ciudad.id,
            "ciudad_nombre": ciudad.nombre,
            "stock_disponible": inv.stock_disponible,
            "stock_minimo": inv.stock_minimo,
            "es_quiebre": inv.stock_disponible < inv.stock_minimo,
        })
    return resultado


def rendimiento_categorias(db: Session, desde: Optional[date] = None, hasta: Optional[date] = None) -> list[dict]:
    """CU-16: cuarto tipo de reporte (RF21) que consolida ingresos y volumen por categoría."""
    stmt = (
        select(
            Categoria.id,
            Categoria.nombre,
            func.coalesce(func.sum(DetalleVenta.cantidad), 0),
            func.coalesce(func.sum(DetalleVenta.subtotal), 0),
        )
        .join(Prenda, Prenda.categoria_id == Categoria.id)
        .join(VariantePrenda, VariantePrenda.prenda_id == Prenda.id)
        .join(DetalleVenta, DetalleVenta.variante_id == VariantePrenda.id)
        .join(Venta, Venta.id == DetalleVenta.venta_id)
        .where(Venta.estado == EstadoVenta.pagada)
    )
    if desde:
        stmt = stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        stmt = stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    stmt = stmt.group_by(Categoria.id, Categoria.nombre).order_by(func.sum(DetalleVenta.subtotal).desc())

    filas = db.execute(stmt).all()
    total_general = sum(float(r[3]) for r in filas) or 1.0

    resultado = []
    for cat_id, cat_nom, cant, subtotal in filas:
        subtotal_f = float(subtotal)
        resultado.append({
            "categoria_id": cat_id,
            "categoria_nombre": cat_nom,
            "cantidad_prendas_vendidas": int(cant),
            "total_ingresos": subtotal_f,
            "porcentaje_ventas": round((subtotal_f / total_general) * 100.0, 1),
        })
    return resultado


def resumen_dashboard(
    db: Session,
    sucursal_id: Optional[int] = None,
    ciudad_id: Optional[int] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> dict:
    ventas_stmt = select(func.count(Venta.id), func.coalesce(func.sum(Venta.total), 0)).where(Venta.estado == EstadoVenta.pagada)
    if sucursal_id:
        ventas_stmt = ventas_stmt.where(Venta.sucursal_id == sucursal_id)
    if ciudad_id:
        ventas_stmt = ventas_stmt.join(Sucursal, Sucursal.id == Venta.sucursal_id).where(Sucursal.ciudad_id == ciudad_id)
    if desde:
        ventas_stmt = ventas_stmt.where(Venta.fecha_venta >= _inicio_dia(desde))
    if hasta:
        ventas_stmt = ventas_stmt.where(Venta.fecha_venta <= _fin_dia(hasta))
    cantidad_ventas, total_ventas = db.execute(ventas_stmt).one()
    total_ventas = float(total_ventas)
    ticket_promedio = total_ventas / cantidad_ventas if cantidad_ventas else 0.0

    reservas_stmt = select(func.count(Reserva.id)).where(Reserva.estado == EstadoReserva.pendiente)
    if sucursal_id:
        reservas_stmt = reservas_stmt.where(Reserva.sucursal_id == sucursal_id)
    reservas_pendientes = db.execute(reservas_stmt).scalar() or 0

    quiebres = quiebres_stock(db, sucursal_id)

    return {
        "cantidad_ventas": cantidad_ventas,
        "total_ventas": total_ventas,
        "ticket_promedio": round(ticket_promedio, 2),
        "reservas_pendientes": reservas_pendientes,
        "variantes_bajo_minimo": len(quiebres),
        "quiebres": quiebres[:10],
    }


# =====================================================================
# CU-17: EXPORTACIÓN DINÁMICA DE REPORTES (EXCEL XLSX Y PDF)
# =====================================================================

def generar_excel_reporte(
    tienda_nombre: str,
    titulo: str,
    columnas: List[str],
    filas: List[List[Any]],
    resumen_totales: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Construye dinámicamente un archivo XLSX con formato corporativo."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.views.sheetView[0].showGridLines = True

    # Estilos
    fuente_titulo = Font(name="Segoe UI", size=15, bold=True, color="1E293B")
    fuente_sub = Font(name="Segoe UI", size=10, italic=True, color="64748B")
    fuente_header = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    fuente_cuerpo = Font(name="Segoe UI", size=10, color="0F172A")
    fuente_total = Font(name="Segoe UI", size=11, bold=True, color="1E293B")

    fill_header = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    fill_alt = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_total = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")

    borde_fino = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )
    borde_total = Border(
        top=Side(style="thin", color="94A3B8"),
        bottom=Side(style="double", color="1E293B"),
    )

    # Encabezado institucional
    ws["A1"] = f"FASHIONSTORE - {tienda_nombre.upper()}"
    ws["A1"].font = fuente_titulo
    ws["A2"] = f"{titulo} | Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws["A2"].font = fuente_sub

    # Fila de columnas
    header_row = 4
    for col_idx, col_name in enumerate(columnas, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=col_name)
        cell.font = fuente_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = borde_fino
    ws.row_dimensions[header_row].height = 26

    # Datos
    current_row = header_row + 1
    for r_idx, fila in enumerate(filas):
        for c_idx, val in enumerate(fila, start=1):
            cell = ws.cell(row=current_row, column=c_idx, value=val)
            cell.font = fuente_cuerpo
            cell.border = borde_fino
            if r_idx % 2 == 1:
                cell.fill = fill_alt
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[current_row].height = 20
        current_row += 1

    # Fila de totales si corresponde
    if resumen_totales:
        for c_idx, col_name in enumerate(columnas, start=1):
            val_total = resumen_totales.get(col_name, "")
            cell = ws.cell(row=current_row, column=c_idx, value=val_total)
            cell.font = fuente_total
            cell.fill = fill_total
            cell.border = borde_total
            if isinstance(val_total, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[current_row].height = 24

    # Autoajuste de columnas
    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generar_pdf_reporte(
    tienda_nombre: str,
    titulo: str,
    columnas: List[str],
    filas: List[List[Any]],
    narrativa_ia: Optional[str] = None,
) -> bytes:
    """Construye dinámicamente un documento PDF profesional con membrete corporativo."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    style_titulo = ParagraphStyle(
        "TituloFS",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e293b"),
    )
    style_sub = ParagraphStyle(
        "SubtituloFS",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#64748b"),
    )
    style_narrativa = ParagraphStyle(
        "NarrativaIA",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
    )
    style_th = ParagraphStyle(
        "TableHead",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1,
    )
    style_td = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
    )

    story = []
    story.append(Paragraph(f"FashionStore — {tienda_nombre.upper()}", style_titulo))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"{titulo} • Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}", style_sub))
    story.append(Spacer(1, 14))

    # Narrativa ejecutiva IA si está presente
    if narrativa_ia:
        bloque_ia = [
            [Paragraph(f"<b>Análisis Ejecutivo (IA):</b> {narrativa_ia}", style_narrativa)]
        ]
        t_ia = Table(bloque_ia, colWidths=[540])
        t_ia.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#bfdbfe")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(t_ia)
        story.append(Spacer(1, 14))

    # Tabla de datos
    datos_tabla = [[Paragraph(c, style_th) for c in columnas]]
    for fila in filas:
        fila_cells = []
        for val in fila:
            texto = f"Bs. {val:.2f}" if isinstance(val, float) and "total" in str(columnas).lower() else str(val)
            fila_cells.append(Paragraph(texto, style_td))
        datos_tabla.append(fila_cells)

    ancho_disponible = 540
    ancho_col = ancho_disponible / max(len(columnas), 1)
    t = Table(datos_tabla, colWidths=[ancho_col] * len(columnas))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(t)

    doc.build(story)
    return buf.getvalue()
