/*
 * FashionStore - Generador de Diagrama de Clases (UML) - v2
 * -----------------------------------------------------------
 * Refleja el modelo final acordado con el equipo (ver database/schema.sql
 * y docs/modelo_datos_logico.md): usuario/personal separados, RBAC
 * (rol/permiso), bitacora, catalogos de talla/color/temporada/coleccion
 * normalizados, movimiento_inventario, y reserva funcionando como
 * "carrito" (sin tabla carrito independiente).
 *
 * Uso en Enterprise Architect:
 *   1. Extensions > Scripting > Script Groups (o Ctrl+Alt+F9)
 *   2. Boton derecho sobre "Local Scripts" > Add Script > JScript
 *   3. Pegar todo este contenido y guardar
 *   4. Boton derecho sobre el script > Run (o F5)
 *
 * Si ya corriste una version anterior, borra primero el paquete
 * "FashionStore - Dominio" del Project Browser para evitar clases
 * duplicadas.
 */

function ObtenerOCrearPaquete(nombre) {
    var models = Repository.Models;
    var i;
    for (i = 0; i < models.Count; i++) {
        if (models.GetAt(i).Name == nombre) {
            return models.GetAt(i);
        }
    }
    var pkg = models.AddNew(nombre, "Package");
    pkg.Update();
    models.Refresh();
    return pkg;
}

function CrearClase(pkg, nombre, atributos) {
    var el = pkg.Elements.AddNew(nombre, "Class");
    el.Update();
    pkg.Elements.Refresh();
    var i;
    for (i = 0; i < atributos.length; i++) {
        var a = el.Attributes.AddNew(atributos[i][0], atributos[i][1]);
        a.Update();
    }
    el.Attributes.Refresh();
    return el;
}

function CrearAsociacion(origen, destino, cardOrigen, cardDestino, tipo, rolDestino) {
    var conn = origen.Connectors.AddNew("", tipo);
    conn.SupplierID = destino.ElementID;
    conn.ClientEnd.Cardinality = cardOrigen;
    conn.SupplierEnd.Cardinality = cardDestino;
    if (rolDestino) {
        conn.SupplierEnd.Role = rolDestino;
    }
    conn.Update();
    origen.Connectors.Refresh();
    return conn;
}

function main() {
    var raiz = ObtenerOCrearPaquete("FashionStore - Dominio");
    var dia = raiz.Diagrams.AddNew("Diagrama de Clases - FashionStore", "Logical");
    dia.Update();
    raiz.Diagrams.Refresh();

    var definiciones = [
        ["Rol", [
            ["id", "int"], ["nombre", "string"], ["descripcion", "string"], ["estado", "boolean"]
        ]],
        ["Permiso", [
            ["id", "int"], ["codigo", "string"], ["descripcion", "string"],
            ["modulo", "string"], ["estado", "boolean"]
        ]],
        ["Usuario", [
            ["id", "int"], ["correo", "string"], ["passwordHash", "string"],
            ["celular", "string"], ["estado", "boolean"], ["verificado", "datetime"],
            ["creadoEn", "datetime"]
        ]],
        ["Bitacora", [
            ["id", "int"], ["accion", "string"], ["ip", "string"], ["fecha", "datetime"]
        ]],
        ["Ciudad", [
            ["id", "int"], ["nombre", "string"], ["estado", "boolean"]
        ]],
        ["Sucursal", [
            ["id", "int"], ["nombre", "string"], ["direccion", "string"], ["telefono", "string"],
            ["horaInicio", "time"], ["horaFin", "time"], ["estado", "boolean"]
        ]],
        ["Personal", [
            ["id", "int"], ["nombres", "string"], ["apellidos", "string"],
            ["cargo", "string"], ["estado", "boolean"]
        ]],
        ["Categoria", [
            ["id", "int"], ["nombre", "string"], ["descripcion", "string"], ["estado", "boolean"]
        ]],
        ["Talla", [
            ["id", "int"], ["nombre", "string"]
        ]],
        ["Color", [
            ["id", "int"], ["nombre", "string"], ["hex", "string"]
        ]],
        ["Temporada", [
            ["id", "int"], ["nombre", "string"], ["tipo", "string"],
            ["fechaInicio", "date"], ["fechaFin", "date"], ["estado", "boolean"]
        ]],
        ["Coleccion", [
            ["id", "int"], ["nombre", "string"], ["descripcion", "string"], ["estado", "boolean"]
        ]],
        ["Proveedor", [
            ["id", "int"], ["nombreEmpresa", "string"], ["contacto", "string"], ["estado", "boolean"]
        ]],
        ["Prenda", [
            ["id", "int"], ["nombre", "string"], ["descripcion", "string"],
            ["precioBase", "decimal"], ["modelo3dUrl", "string"], ["estado", "boolean"]
        ]],
        ["VariantePrenda", [
            ["id", "int"], ["codigoBarras", "string"], ["estado", "boolean"]
        ]],
        ["InventarioSucursal", [
            ["id", "int"], ["stockDisponible", "int"], ["stockReservado", "int"],
            ["stockMinimo", "int"], ["stockMaximo", "int"]
        ]],
        ["MovimientoInventario", [
            ["id", "int"], ["tipoMovimiento", "string"], ["cantidad", "int"],
            ["referenciaId", "int"], ["referenciaTipo", "string"], ["fecha", "datetime"]
        ]],
        ["Reserva", [
            ["id", "int"], ["fechaReserva", "datetime"], ["horarioAtencion", "time"], ["estado", "string"]
        ]],
        ["DetalleReserva", [
            ["id", "int"], ["cantidad", "int"]
        ]],
        ["Venta", [
            ["id", "int"], ["tipoOrigen", "string"], ["estado", "string"],
            ["total", "decimal"], ["fechaVenta", "datetime"]
        ]],
        ["DetalleVenta", [
            ["id", "int"], ["cantidad", "int"], ["precioUnitario", "decimal"], ["subtotal", "decimal"]
        ]],
        ["Pago", [
            ["id", "int"], ["metodoPago", "string"], ["pasarela", "string"], ["estado", "string"],
            ["monto", "decimal"], ["transaccionId", "string"], ["fechaPago", "datetime"]
        ]],
        ["InteraccionIA", [
            ["id", "int"], ["tipoConsulta", "string"], ["promptConsulta", "string"],
            ["prendasSugeridasIds", "string"], ["fecha", "datetime"]
        ]]
    ];

    var clases = {};
    var i;
    var nombre;
    try {
        for (i = 0; i < definiciones.length; i++) {
            nombre = definiciones[i][0];
            var atributos = definiciones[i][1];
            clases[nombre] = { el: CrearClase(raiz, nombre, atributos), numAtributos: atributos.length };
        }
    } catch (eClases) {
        Session.Output("ETAPA 1 (crear clases) fallo en '" + nombre + "': " + (eClases.number ? eClases.number : "") + " " + (eClases.description ? eClases.description : eClases.message));
        return;
    }

    try {
        // Seguridad
        CrearAsociacion(clases["Usuario"].el, clases["Rol"].el, "0..*", "0..*", "Association", "roles");
        CrearAsociacion(clases["Rol"].el, clases["Permiso"].el, "0..*", "0..*", "Association", "permisos");
        CrearAsociacion(clases["Bitacora"].el, clases["Usuario"].el, "0..*", "1", "Association", "usuario");

        // Sucursales y personal
        CrearAsociacion(clases["Sucursal"].el, clases["Ciudad"].el, "0..*", "1", "Association", "ciudad");
        CrearAsociacion(clases["Personal"].el, clases["Usuario"].el, "1", "1", "Aggregation", "cuenta");
        CrearAsociacion(clases["Personal"].el, clases["Sucursal"].el, "0..*", "0..1", "Association", "sucursal");

        // Catalogo
        CrearAsociacion(clases["Coleccion"].el, clases["Temporada"].el, "0..*", "1", "Association", "temporada");
        CrearAsociacion(clases["Prenda"].el, clases["Categoria"].el, "0..*", "1", "Association", "categoria");
        CrearAsociacion(clases["Prenda"].el, clases["Coleccion"].el, "0..*", "0..1", "Association", "coleccion");
        CrearAsociacion(clases["Prenda"].el, clases["Proveedor"].el, "0..*", "0..1", "Association", "proveedor");
        CrearAsociacion(clases["VariantePrenda"].el, clases["Prenda"].el, "0..*", "1", "Aggregation", "prenda");
        CrearAsociacion(clases["VariantePrenda"].el, clases["Talla"].el, "0..*", "1", "Association", "talla");
        CrearAsociacion(clases["VariantePrenda"].el, clases["Color"].el, "0..*", "1", "Association", "color");

        // Inventario
        CrearAsociacion(clases["InventarioSucursal"].el, clases["VariantePrenda"].el, "0..*", "1", "Association", "variante");
        CrearAsociacion(clases["InventarioSucursal"].el, clases["Sucursal"].el, "0..*", "1", "Association", "sucursal");
        CrearAsociacion(clases["MovimientoInventario"].el, clases["VariantePrenda"].el, "0..*", "1", "Association", "variante");
        CrearAsociacion(clases["MovimientoInventario"].el, clases["Sucursal"].el, "0..*", "1", "Association", "sucursal");
        CrearAsociacion(clases["MovimientoInventario"].el, clases["Usuario"].el, "0..*", "0..1", "Association", "responsable");

        // Reserva (funciona como "carrito")
        CrearAsociacion(clases["Reserva"].el, clases["Usuario"].el, "0..*", "1", "Association", "cliente");
        CrearAsociacion(clases["Reserva"].el, clases["Sucursal"].el, "0..*", "1", "Association", "sucursal");
        CrearAsociacion(clases["Reserva"].el, clases["Personal"].el, "0..*", "0..1", "Association", "atiende");
        CrearAsociacion(clases["DetalleReserva"].el, clases["Reserva"].el, "0..*", "1", "Aggregation", "reserva");
        CrearAsociacion(clases["DetalleReserva"].el, clases["VariantePrenda"].el, "0..*", "1", "Association", "variante");

        // Venta
        CrearAsociacion(clases["Venta"].el, clases["Usuario"].el, "0..*", "0..1", "Association", "cliente");
        CrearAsociacion(clases["Venta"].el, clases["Personal"].el, "0..*", "0..1", "Association", "cajero");
        CrearAsociacion(clases["Venta"].el, clases["Sucursal"].el, "0..*", "1", "Association", "sucursal");
        CrearAsociacion(clases["Venta"].el, clases["Reserva"].el, "0..*", "0..1", "Association", "reservaOrigen");
        CrearAsociacion(clases["DetalleVenta"].el, clases["Venta"].el, "0..*", "1", "Aggregation", "venta");
        CrearAsociacion(clases["DetalleVenta"].el, clases["VariantePrenda"].el, "0..*", "1", "Association", "variante");
        CrearAsociacion(clases["Pago"].el, clases["Venta"].el, "0..*", "1", "Aggregation", "venta");

        // IA
        CrearAsociacion(clases["InteraccionIA"].el, clases["Usuario"].el, "0..*", "1", "Association", "usuario");
    } catch (eRel) {
        Session.Output("ETAPA 2 (crear relaciones) fallo: " + (eRel.number ? eRel.number : "") + " " + (eRel.description ? eRel.description : eRel.message));
        return;
    }

    // Ubicacion manual por "slots" de 300x300, agrupada por modulo para
    // minimizar cruces de lineas.
    var posiciones = {
        "Rol":                  [0, 0],
        "Permiso":              [1, 0],
        "Usuario":              [2, 0],
        "Bitacora":             [3, 0],
        "InteraccionIA":        [0, 1],
        "Ciudad":               [2, 1],
        "Sucursal":             [2, 2],
        "Personal":             [3, 2],
        "Categoria":            [5, 0],
        "Talla":                [6, 0],
        "Color":                [6, 1],
        "Temporada":            [5, 1],
        "Coleccion":            [5, 2],
        "Proveedor":            [6, 2],
        "Prenda":               [5, 3],
        "VariantePrenda":       [5, 4],
        "InventarioSucursal":   [4, 4],
        "MovimientoInventario": [4, 5],
        "Reserva":              [2, 3],
        "DetalleReserva":       [2, 4],
        "Venta":                [1, 3],
        "DetalleVenta":         [1, 4],
        "Pago":                 [0, 4]
    };

    var slot = 300;
    var anchoCaja = 220;
    var margen = 40;
    var alturaCabecera = 50;
    var alturaPorAtributo = 18;

    try {
        for (i = 0; i < definiciones.length; i++) {
            var nombreClase = definiciones[i][0];
            var info = clases[nombreClase];
            var pos = posiciones[nombreClase];

            var x1 = margen + pos[0] * slot;
            var x2 = x1 + anchoCaja;
            var y1 = margen + pos[1] * slot;
            var altura = alturaCabecera + info.numAtributos * alturaPorAtributo;
            var y2 = y1 + altura;

            // La posicion se define en el propio AddNew como string "l=;r=;t=;b=;",
            // no asignando dobj.left/right/top/bottom despues de creado.
            var posStr = "l=" + x1 + ";r=" + x2 + ";t=" + y1 + ";b=" + y2 + ";";
            var dobj = dia.DiagramObjects.AddNew(posStr, "");
            dobj.ElementID = info.el.ElementID;
            dobj.Update();
            dia.DiagramObjects.Refresh();
        }
    } catch (ePos) {
        Session.Output("ETAPA 3 (posicionar en diagrama) fallo en '" + nombreClase + "': " + (ePos.number ? ePos.number : "") + " " + (ePos.description ? ePos.description : ePos.message));
        return;
    }

    Repository.ReloadDiagram(dia.DiagramID);
    Session.Output("Diagrama de clases FashionStore generado: " + definiciones.length + " clases en el paquete 'FashionStore - Dominio'.");
}

try {
    main();
} catch (e) {
    Session.Output("ERROR al generar el diagrama de clases: " + (e.description ? e.description : e.message));
}
