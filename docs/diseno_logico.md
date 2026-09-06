# Diseño lógico

<table>
<tr><th colspan="5">rol</th></tr>
<tr><td>id</td><td>nombre</td><td>descripcion</td><td>estado</td><td>fecha_eliminacion</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="5">permiso</th></tr>
<tr><td>id</td><td>codigo</td><td>descripcion</td><td>modulo</td><td>estado</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="2">rol_permiso</th></tr>
<tr><td>rol_id</td><td>permiso_id</td></tr>
</table>

**Primary key**: rol_id, permiso_id
*FK rol_id a rol*
*FK permiso_id a permiso*

<table>
<tr><th colspan="8">usuario</th></tr>
<tr><td>id</td><td>correo</td><td>password_hash</td><td>celular</td><td>estado</td><td>verificado</td><td>fecha_eliminacion</td><td>creado_en</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="2">usuario_rol</th></tr>
<tr><td>usuario_id</td><td>rol_id</td></tr>
</table>

**Primary key**: usuario_id, rol_id
*FK usuario_id a usuario*
*FK rol_id a rol*

<table>
<tr><th colspan="5">bitacora</th></tr>
<tr><td>id</td><td>usuario_id</td><td>accion</td><td>ip</td><td>fecha</td></tr>
</table>

**Primary key**: id
*FK usuario_id a usuario*

<table>
<tr><th colspan="4">ciudad</th></tr>
<tr><td>id</td><td>nombre</td><td>estado</td><td>fecha_eliminacion</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="9">sucursal</th></tr>
<tr><td>id</td><td>nombre</td><td>ciudad_id</td><td>direccion</td><td>telefono</td><td>hora_inicio</td><td>hora_fin</td><td>estado</td><td>fecha_eliminacion</td></tr>
</table>

**Primary key**: id
*FK ciudad_id a ciudad*

<table>
<tr><th colspan="8">personal</th></tr>
<tr><td>id</td><td>usuario_id</td><td>sucursal_id</td><td>nombres</td><td>apellidos</td><td>cargo</td><td>estado</td><td>fecha_eliminacion</td></tr>
</table>

**Primary key**: id
*FK usuario_id a usuario*
*FK sucursal_id a sucursal*

<table>
<tr><th colspan="4">categoria</th></tr>
<tr><td>id</td><td>nombre</td><td>descripcion</td><td>estado</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="2">talla</th></tr>
<tr><td>id</td><td>nombre</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="3">color</th></tr>
<tr><td>id</td><td>nombre</td><td>hex</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="6">temporada</th></tr>
<tr><td>id</td><td>nombre</td><td>tipo</td><td>fecha_inicio</td><td>fecha_fin</td><td>estado</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="5">coleccion</th></tr>
<tr><td>id</td><td>nombre</td><td>descripcion</td><td>temporada_id</td><td>estado</td></tr>
</table>

**Primary key**: id
*FK temporada_id a temporada*

<table>
<tr><th colspan="4">proveedor</th></tr>
<tr><td>id</td><td>nombre_empresa</td><td>contacto</td><td>estado</td></tr>
</table>

**Primary key**: id

<table>
<tr><th colspan="9">prenda</th></tr>
<tr><td>id</td><td>nombre</td><td>descripcion</td><td>categoria_id</td><td>coleccion_id</td><td>proveedor_id</td><td>precio_base</td><td>modelo_3d_url</td><td>estado</td></tr>
</table>

**Primary key**: id
*FK categoria_id a categoria*
*FK coleccion_id a coleccion*
*FK proveedor_id a proveedor*

<table>
<tr><th colspan="6">variante_prenda</th></tr>
<tr><td>id</td><td>prenda_id</td><td>talla_id</td><td>color_id</td><td>codigo_barras</td><td>estado</td></tr>
</table>

**Primary key**: id
*FK prenda_id a prenda*
*FK talla_id a talla*
*FK color_id a color*

<table>
<tr><th colspan="7">inventario_sucursal</th></tr>
<tr><td>id</td><td>variante_id</td><td>sucursal_id</td><td>stock_disponible</td><td>stock_reservado</td><td>stock_minimo</td><td>stock_maximo</td></tr>
</table>

**Primary key**: id
*FK variante_id a variante_prenda*
*FK sucursal_id a sucursal*

<table>
<tr><th colspan="9">movimiento_inventario</th></tr>
<tr><td>id</td><td>variante_id</td><td>sucursal_id</td><td>tipo_movimiento</td><td>cantidad</td><td>referencia_id</td><td>referencia_tipo</td><td>usuario_id</td><td>fecha</td></tr>
</table>

**Primary key**: id
*FK variante_id a variante_prenda*
*FK sucursal_id a sucursal*
*FK usuario_id a usuario*

<table>
<tr><th colspan="7">reserva</th></tr>
<tr><td>id</td><td>usuario_id</td><td>sucursal_id</td><td>personal_id</td><td>fecha_reserva</td><td>horario_atencion</td><td>estado</td></tr>
</table>

**Primary key**: id
*FK usuario_id a usuario*
*FK sucursal_id a sucursal*
*FK personal_id a personal*

<table>
<tr><th colspan="4">detalle_reserva</th></tr>
<tr><td>id</td><td>reserva_id</td><td>variante_id</td><td>cantidad</td></tr>
</table>

**Primary key**: id
*FK reserva_id a reserva*
*FK variante_id a variante_prenda*

<table>
<tr><th colspan="9">venta</th></tr>
<tr><td>id</td><td>usuario_id</td><td>personal_id</td><td>sucursal_id</td><td>reserva_id</td><td>tipo_origen</td><td>estado</td><td>total</td><td>fecha_venta</td></tr>
</table>

**Primary key**: id
*FK usuario_id a usuario*
*FK personal_id a personal*
*FK sucursal_id a sucursal*
*FK reserva_id a reserva*

<table>
<tr><th colspan="6">detalle_venta</th></tr>
<tr><td>id</td><td>venta_id</td><td>variante_id</td><td>cantidad</td><td>precio_unitario</td><td>subtotal</td></tr>
</table>

**Primary key**: id
*FK venta_id a venta*
*FK variante_id a variante_prenda*

<table>
<tr><th colspan="8">pago</th></tr>
<tr><td>id</td><td>venta_id</td><td>metodo_pago</td><td>pasarela</td><td>estado</td><td>monto</td><td>transaccion_id</td><td>fecha_pago</td></tr>
</table>

**Primary key**: id
*FK venta_id a venta*

<table>
<tr><th colspan="6">interaccion_ia</th></tr>
<tr><td>id</td><td>usuario_id</td><td>tipo_consulta</td><td>prompt_consulta</td><td>prendas_sugeridas_ids</td><td>fecha</td></tr>
</table>

**Primary key**: id
*FK usuario_id a usuario*
