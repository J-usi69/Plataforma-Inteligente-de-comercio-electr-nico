"""Motor de los reportes personalizables (característica 5), compartido por el superadmin (todas las
empresas) y por el administrador de cada empresa (solo la suya).

Cada catálogo es un diccionario tipo -> Definicion. El usuario elige qué columnas ver y en qué
orden, filtra por fechas, agrega criterios de selección (columna, operador y valor) y ordena por
cualquier columna; después lo exporta a Excel, PDF o HTML o lo envía por correo. También se puede
pedir con palabras (escrito o dictado): la IA traduce el pedido a esas mismas opciones, nunca arma
consultas.
"""
import json
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html import escape as escape_html
from typing import Any, Callable, List, Optional
from xml.sax.saxutils import escape as escape_xml

from fastapi import HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.services import correo_service, ia_service, reportes_service
from app.services.reportes_service import _fin_dia, _inicio_dia

OPERADORES = {
    "contiene": "contiene",
    "igual": "es igual a",
    "distinto": "es distinto de",
    "mayor": "es mayor que",
    "menor": "es menor que",
}
FORMATOS = {
    "excel": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": ("pdf", "application/pdf"),
    "html": ("html", "text/html; charset=utf-8"),
}
# Bolivia no tiene horario de verano: la hora local es siempre UTC-4
HORA_BOLIVIA = timezone(timedelta(hours=-4))

Fila = dict[str, Any]


@dataclass
class Criterio:
    """Criterio de selección: «Plan es igual a Básico», «Ventas es mayor que 10»."""

    columna: str
    operador: str
    valor: str

    @classmethod
    def desde_texto(cls, texto: str) -> "Criterio":
        partes = texto.split("|", 2)
        if len(partes) != 3:
            raise HTTPException(status_code=422, detail=f"Criterio inválido '{texto}': se espera columna|operador|valor")
        return cls(*partes)


@dataclass
class Definicion:
    titulo: str
    descripcion: str  # qué muestra y a qué se aplican las fechas
    columnas: list[str]
    obtener: Callable[[Session, Optional[date], Optional[date]], list[Fila]]
    resumir: Callable[[list[Fila], str], str]  # filas ya filtradas + período -> conclusión
    orden: tuple[str, bool]  # columna por defecto y si es descendente
    sumables: list[str] = field(default_factory=list)  # columnas que se totalizan
    columnas_monto: list[str] = field(default_factory=list)
    etiqueta_total: str = "TOTAL"
    # Valores posibles de las columnas con valores fijos (estado, canal...): la IA los usa tal cual
    valores: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Reporte:
    titulo: str
    columnas: list[str]
    filas: list[list[Any]]
    totales: Optional[dict[str, Any]]
    narrativa: str
    columnas_monto: list[str]
    filtros: str  # descripción legible de los filtros aplicados


Catalogo = dict[str, Definicion]


# --------------------------------------------------------------------------- utilidades para las definiciones

def hoy() -> date:
    return datetime.now(timezone.utc).date()


def fecha_texto(valor: Optional[datetime]) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "-"


def fecha_hora_local(valor: Optional[datetime]) -> str:
    """Fecha y hora de Bolivia (en la base se guardan en UTC)."""
    if not valor:
        return "-"
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(HORA_BOLIVIA).strftime("%d/%m/%Y %H:%M:%S")


def monto(valor) -> float:
    return round(float(valor or 0), 2)


def en_rango(columna, desde: Optional[date], hasta: Optional[date]) -> list:
    condiciones = []
    if desde:
        condiciones.append(columna >= _inicio_dia(desde))
    if hasta:
        condiciones.append(columna <= _fin_dia(hasta))
    return condiciones


def periodo(desde: Optional[date], hasta: Optional[date]) -> str:
    if desde and hasta:
        return f"del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    if desde:
        return f"desde el {desde:%d/%m/%Y}"
    if hasta:
        return f"hasta el {hasta:%d/%m/%Y}"
    return "de todo el historial"


def contar_por(filas: list[Fila], columna: str) -> str:
    """«3 pagada, 1 anulada»: cuántas filas hay de cada valor, de más a menos."""
    cuenta: dict[str, int] = defaultdict(int)
    for f in filas:
        cuenta[str(f[columna])] += 1
    return ", ".join(f"{n} {valor.lower()}" for valor, n in sorted(cuenta.items(), key=lambda x: -x[1]))


def _normalizar(texto: Any) -> str:
    sin_tildes = unicodedata.normalize("NFD", str(texto)).encode("ascii", "ignore").decode()
    return sin_tildes.strip().lower()


def _como_numero(valor: Any) -> Optional[float]:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return None


# --------------------------------------------------------------------------- motor

def catalogo(reportes: Catalogo) -> list[dict]:
    """Los reportes disponibles con sus columnas, para armar el constructor en la web."""
    return [
        {
            "tipo": tipo, "titulo": d.titulo, "descripcion": d.descripcion, "columnas": d.columnas,
            "orden": d.orden[0], "descendente": d.orden[1], "columnas_monto": d.columnas_monto,
        }
        for tipo, d in reportes.items()
    ]


def definicion(reportes: Catalogo, tipo: str) -> Definicion:
    if tipo not in reportes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el reporte '{tipo}'. Disponibles: {', '.join(reportes)}",
        )
    return reportes[tipo]


def _cumple(fila: Fila, criterio: Criterio) -> bool:
    celda = fila.get(criterio.columna)
    if criterio.operador in ("mayor", "menor"):
        a, b = _como_numero(celda), _como_numero(criterio.valor)
        if a is None or b is None:
            return False
        return a > b if criterio.operador == "mayor" else a < b
    texto, buscado = _normalizar(celda), _normalizar(criterio.valor)
    if criterio.operador == "contiene":
        return buscado in texto
    a, b = _como_numero(celda), _como_numero(criterio.valor)
    iguales = (a == b) if a is not None and b is not None else texto == buscado
    return iguales if criterio.operador == "igual" else not iguales


def _cumple_todos(fila: Fila, criterios: list[Criterio]) -> bool:
    """Criterios sobre la misma columna se combinan con O («Plan es Básico» o «Plan es Profesional»);
    sobre columnas distintas, con Y. «Es distinto de» se exige siempre (todos deben cumplirse)."""
    por_columna: dict[str, list[Criterio]] = defaultdict(list)
    for c in criterios:
        por_columna[c.columna].append(c)
    for grupo in por_columna.values():
        positivos = [c for c in grupo if c.operador != "distinto"]
        if positivos and not any(_cumple(fila, c) for c in positivos):
            return False
        if not all(_cumple(fila, c) for c in grupo if c.operador == "distinto"):
            return False
    return True


def _clave_orden(columna: str):
    def clave(fila: Fila):
        if columna == "Fecha" and "_orden_fecha" in fila:
            return (0, fila["_orden_fecha"].timestamp(), "")
        valor = fila.get(columna)
        numero = _como_numero(valor)
        if numero is not None:
            return (0, numero, "")
        # Los textos van después de los números (p. ej. "Sin vencimiento" al final)
        return (1, 0, _normalizar(valor))
    return clave


def _total(filas: list[Fila], columna: str) -> int | float:
    """Suma de una columna: entera si todos sus valores son enteros (cantidades), si no con 2 decimales."""
    valores = [f[columna] for f in filas]
    if all(isinstance(v, int) and not isinstance(v, bool) for v in valores):
        return sum(valores)
    return round(sum(_como_numero(v) or 0 for v in valores), 2)


def generar(
    reportes: Catalogo,
    db: Session,
    tipo: str,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    columnas: Optional[list[str]] = None,
    criterios: Optional[list[Criterio]] = None,
    orden: Optional[str] = None,
    descendente: Optional[bool] = None,
) -> Reporte:
    d = definicion(reportes, tipo)
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La fecha 'desde' es posterior a 'hasta'")

    elegidas = [c for c in (columnas or d.columnas)]
    desconocidas = [c for c in elegidas if c not in d.columnas]
    criterios = criterios or []
    desconocidas += [c.columna for c in criterios if c.columna not in d.columnas]
    if orden and orden not in d.columnas:
        desconocidas.append(orden)
    if desconocidas:
        raise HTTPException(status_code=422, detail=f"Columnas que no tiene el reporte: {', '.join(dict.fromkeys(desconocidas))}")
    if invalidos := [c.operador for c in criterios if c.operador not in OPERADORES]:
        raise HTTPException(status_code=422, detail=f"Operadores no soportados: {', '.join(invalidos)}. Usá: {', '.join(OPERADORES)}")
    if not elegidas:
        raise HTTPException(status_code=422, detail="Elegí al menos una columna")

    filas = [f for f in d.obtener(db, desde, hasta) if _cumple_todos(f, criterios)]
    texto_periodo = periodo(desde, hasta)
    columna_orden = orden or d.orden[0]
    al_reves = d.orden[1] if descendente is None else descendente
    filas.sort(key=_clave_orden(columna_orden), reverse=al_reves)

    totales = None
    sumables = [c for c in d.sumables if c in elegidas]
    if filas:
        totales = {c: _total(filas, c) for c in sumables}
        etiqueta = f"{d.etiqueta_total} ({len(filas)} filas)"
        primera_libre = next((c for c in elegidas if c not in sumables), None)
        if primera_libre:
            totales[primera_libre] = etiqueta

    descripcion_filtros = [f"Período: {texto_periodo}"]
    descripcion_filtros += [f"{c.columna} {OPERADORES[c.operador]} «{c.valor}»" for c in criterios]
    descripcion_filtros.append(f"Orden: {columna_orden} ({'descendente' if al_reves else 'ascendente'})")

    return Reporte(
        titulo=d.titulo,
        columnas=elegidas,
        filas=[[f[c] for c in elegidas] for f in filas],
        totales=totales,
        narrativa=d.resumir(filas, texto_periodo),
        columnas_monto=[c for c in d.columnas_monto if c in elegidas],
        filtros=" · ".join(descripcion_filtros),
    )


# --------------------------------------------------------------------------- pedido en lenguaje natural

def prompt_interpretacion(reportes: Catalogo, fecha_hoy: date, quien: str) -> str:
    """Instrucciones para que la IA traduzca un pedido (escrito o dictado) a las opciones del
    constructor. La IA solo elige entre reportes, columnas y operadores conocidos: nunca escribe
    consultas; lo que devuelva se valida antes de usarlo. quien: de quién son los pedidos."""
    lista = [
        {"tipo": t, "titulo": d.titulo, "descripcion": d.descripcion, "columnas": d.columnas, **({"valores": d.valores} if d.valores else {})}
        for t, d in reportes.items()
    ]
    return (
        f"Hoy es {fecha_hoy.isoformat()}. Resolvé los períodos relativos (hoy, este mes, el mes pasado, los últimos N días, "
        "este año) a fechas concretas a partir de esa fecha. "
        f"Traducís pedidos de reportes {quien} a un JSON estricto. "
        f"Reportes disponibles (JSON): {json.dumps(lista, ensure_ascii=False)}. "
        f"Operadores de criterio: {', '.join(OPERADORES)}. "
        "Varios criterios sobre la misma columna se combinan con O (p. ej. dos estados distintos); "
        "sobre columnas distintas, con Y. "
        'Respondé ÚNICAMENTE con un objeto JSON de la forma {"tipo": string|null, "columnas": [string]|null, '
        '"criterios": [{"columna": string, "operador": string, "valor": string}], "desde": "YYYY-MM-DD"|null, '
        '"hasta": "YYYY-MM-DD"|null, "orden": string|null, "descendente": true|false|null}. '
        "Usá solo tipos y columnas de la lista, escritos exactamente igual. columnas null significa todas. "
        "Si una columna tiene «valores», el criterio sobre ella usa uno de esos valores, escrito igual. "
        "Para filtrar por un valor concreto (un plan, una empresa, una sucursal, un usuario, un estado) usá un criterio. "
        "Si el pedido no corresponde a ninguno de los reportes, devolvé tipo null. Sin texto adicional."
    )


def _valor_conocido(valor: str, conocidos: list[str]) -> Optional[str]:
    """El valor de la lista que corresponde al que eligió la IA (sin tildes ni mayúsculas, o el único
    que contiene al otro); None si no corresponde a ninguno."""
    buscado = _normalizar(valor)
    for conocido in conocidos:
        if _normalizar(conocido) == buscado:
            return conocido
    parecidos = [c for c in conocidos if buscado in _normalizar(c) or _normalizar(c) in buscado]
    return parecidos[0] if len(parecidos) == 1 else None


def opciones_desde_ia(reportes: Catalogo, datos: Any) -> dict:
    """Valida la interpretación de la IA y la convierte en las opciones de generar(). Descarta columnas,
    criterios u orden que no existan; si no hay un reporte válido lanza ValueError."""
    if not isinstance(datos, dict) or datos.get("tipo") not in reportes:
        raise ValueError("El pedido no corresponde a ningún reporte")
    d = reportes[datos["tipo"]]

    def fecha(valor) -> Optional[date]:
        try:
            return date.fromisoformat(valor) if valor else None
        except (TypeError, ValueError):
            return None

    columnas = [c for c in (datos.get("columnas") or []) if c in d.columnas]
    criterios = []
    for c in datos.get("criterios") or []:
        if not (isinstance(c, dict) and c.get("columna") in d.columnas and c.get("operador") in OPERADORES):
            continue
        valor = str(c.get("valor", "")).strip()
        if valor and c["columna"] in d.valores:
            # Un valor inventado («Agotado») dejaría el reporte vacío: se usa el real o se descarta
            valor = _valor_conocido(valor, d.valores[c["columna"]]) or ""
        if valor:
            criterios.append(Criterio(str(c["columna"]), str(c["operador"]), valor))
    desde, hasta = fecha(datos.get("desde")), fecha(datos.get("hasta"))
    if desde and hasta and desde > hasta:
        desde, hasta = hasta, desde
    orden = datos.get("orden") if datos.get("orden") in d.columnas else None
    descendente = datos.get("descendente") if isinstance(datos.get("descendente"), bool) else None
    return {
        "tipo": datos["tipo"], "columnas": columnas or None, "criterios": criterios,
        "desde": desde, "hasta": hasta, "orden": orden, "descendente": descendente,
    }


def interpretar(reportes: Catalogo, pedido: str, quien: str, ejemplos: str) -> dict:
    """Pedido con palabras -> opciones del constructor (o 503 si no hay IA, 422 si no se entiende)."""
    try:
        respuesta = ia_service.interpretar_con_respaldo(
            prompt_interpretacion(reportes, date.today(), quien), pedido, max_tokens=500,
        )
    except ia_service.IAServiceError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La IA no está disponible en este momento. Armá el reporte con el constructor de abajo.",
        )
    try:
        return opciones_desde_ia(reportes, ia_service.extraer_json(respuesta))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"No pude relacionar el pedido con un reporte. Probá, por ejemplo: {ejemplos}.",
        )


# --------------------------------------------------------------------------- salida: HTML, archivos y correo

def celda_texto(valor: Any, es_monto: bool) -> str:
    """Cómo se muestra una celda en el HTML y en el PDF."""
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and es_monto:
        return f"{valor:,.2f}"
    return "" if valor is None else str(valor)


def a_html(reporte: Reporte, emisor: str) -> str:
    """El reporte como página HTML autocontenida (para descargar o como cuerpo de un correo)."""
    montos = [c in reporte.columnas_monto for c in reporte.columnas]
    alineado = lambda v: ' class="num"' if isinstance(v, (int, float)) and not isinstance(v, bool) else ""  # noqa: E731
    cabecera = "".join(f"<th>{escape_html(c)}</th>" for c in reporte.columnas)
    cuerpo = "".join(
        "<tr>" + "".join(f"<td{alineado(v)}>{escape_html(celda_texto(v, m))}</td>" for v, m in zip(fila, montos)) + "</tr>"
        for fila in reporte.filas
    ) or f'<tr><td colspan="{len(reporte.columnas)}">Ningún registro cumple los filtros.</td></tr>'
    pie = ""
    if reporte.totales:
        pie = "<tfoot><tr>" + "".join(
            f"<td{alineado(reporte.totales.get(c))}>{escape_html(celda_texto(reporte.totales.get(c, ''), m))}</td>"
            for c, m in zip(reporte.columnas, montos)
        ) + "</tr></tfoot>"
    generado = datetime.now(HORA_BOLIVIA).strftime("%d/%m/%Y %H:%M")
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape_html(reporte.titulo)}</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;color:#0f172a;margin:24px;background:#fff}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#64748b;font-size:13px;margin:0 0 16px}}
.nota{{background:#eef2ff;border-left:4px solid #4f46e5;padding:10px 14px;font-size:14px;margin:0 0 16px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th{{background:#1e293b;color:#fff;text-align:left}}
th,td{{border:1px solid #cbd5e1;padding:6px 8px}} tbody tr:nth-child(even){{background:#f8fafc}}
tfoot td{{background:#e2e8f0;font-weight:700}} .num{{text-align:right}}
</style></head><body>
<h1>FashionStore · {escape_html(emisor)} — {escape_html(reporte.titulo)}</h1>
<p class="sub">Generado el {generado} (hora de Bolivia) · {escape_html(reporte.filtros)}</p>
<p class="nota">{escape_html(reporte.narrativa)}</p>
<table><thead><tr>{cabecera}</tr></thead><tbody>{cuerpo}</tbody>{pie}</table>
</body></html>"""


def archivo(reporte: Reporte, formato: str, emisor: str) -> bytes:
    """El reporte en Excel, PDF o HTML."""
    if formato == "excel":
        return reportes_service.generar_excel_reporte(
            tienda_nombre=emisor, titulo=reporte.titulo, columnas=reporte.columnas,
            filas=reporte.filas, resumen_totales=reporte.totales,
        )
    if formato == "html":
        return a_html(reporte, emisor).encode("utf-8")
    # El PDF interpreta etiquetas en el texto: todo lo que viene de los datos va escapado
    montos = [c in reporte.columnas_monto for c in reporte.columnas]
    filas = [[escape_xml(celda_texto(v, m)) for v, m in zip(fila, montos)] for fila in reporte.filas]
    if reporte.totales:
        filas.append([escape_xml(celda_texto(reporte.totales.get(c, ""), m)) for c, m in zip(reporte.columnas, montos)])
    return reportes_service.generar_pdf_reporte(
        tienda_nombre=emisor, titulo=reporte.titulo, columnas=reporte.columnas,
        filas=filas, narrativa_ia=escape_xml(f"{reporte.narrativa} ({reporte.filtros})"), etiqueta_narrativa="Conclusión",
    )


def nombre_archivo(prefijo: str, tipo: str, formato: str) -> str:
    return f"{prefijo}_{tipo}_{date.today():%Y-%m-%d}.{FORMATOS[formato][0]}"


def opciones_de_consulta(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    columnas: Optional[List[str]] = Query(None, description="Columnas a mostrar, en orden"),
    criterio: Optional[List[str]] = Query(None, description="Criterios de selección: columna|operador|valor"),
    orden: Optional[str] = None,
    descendente: Optional[bool] = None,
) -> dict:
    """Dependencia de FastAPI: las opciones del constructor que llegan en la URL."""
    return {
        "desde": desde, "hasta": hasta, "columnas": columnas, "orden": orden, "descendente": descendente,
        "criterios": [Criterio.desde_texto(c) for c in criterio or []],
    }


def opciones_de_envio(datos) -> dict:
    """Las opciones del constructor que llegan en el cuerpo de un envío por correo (EnviarReporteIn)."""
    return {
        "desde": datos.desde, "hasta": datos.hasta, "columnas": datos.columnas or None, "orden": datos.orden,
        "descendente": datos.descendente, "criterios": [Criterio.desde_texto(c) for c in datos.criterios],
    }


def descarga(reporte: Reporte, formato: str, emisor: str, prefijo: str, tipo: str) -> Response:
    """Respuesta HTTP con el archivo del reporte para descargar."""
    return Response(
        content=archivo(reporte, formato, emisor), media_type=FORMATOS[formato][1],
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo(prefijo, tipo, formato)}"'},
    )


def enviar_por_correo(reporte: Reporte, destinatario: str, formato: str, emisor: str, prefijo: str, tipo: str) -> None:
    """El HTML en el cuerpo y el archivo elegido adjunto (503 si el servidor no tiene correo)."""
    correo_service.enviar(
        destinatario,
        asunto=f"FashionStore · {emisor} · {reporte.titulo}",
        texto="\n".join([reporte.titulo, reporte.narrativa, reporte.filtros, "", "El reporte completo va adjunto."]),
        html=a_html(reporte, emisor),
        adjunto=correo_service.Adjunto(
            nombre_archivo(prefijo, tipo, formato), archivo(reporte, formato, emisor), FORMATOS[formato][1].split(";")[0],
        ),
    )
