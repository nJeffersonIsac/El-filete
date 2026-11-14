"""
Rutas de pedidos: crear venta directa, abrir orden, listar abiertas,
detalle, cobrar, anular, actualizar.
"""
from flask import Blueprint, jsonify, request, g

from auth import registrar_auditoria

# Importar funciones compartidas desde server
import server as _srv

pedidos_bp = Blueprint('pedidos', __name__)


@pedidos_bp.route('/api/ventas', methods=['POST'])
@pedidos_bp.route('/api/pedidos', methods=['POST'])
def api_crear_venta():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(_srv._core_crear_venta(g.db, data, g.usuario['id_usuario'],
                                              g.usuario['nombre_completo'])), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ========================================================================
# ÓRDENES ABIERTAS (MESEROS)
# ========================================================================
@pedidos_bp.route('/api/pedidos/abrir', methods=['POST'])
def api_pedidos_abrir():
    """Mesero crea una orden abierta (sin cobrar)."""
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    if not items:
        return jsonify({"error": "La orden no contiene productos"}), 400

    id_mesa = data.get('id_mesa')
    tipo_pedido = data.get('tipo_pedido', 'Mesa' if id_mesa else 'Para Llevar')
    # El mesero se identifica siempre por la sesión, nunca por datos del cliente
    mesero_nombre = g.usuario.get('nombre_completo') or g.usuario.get('username') or 'Mesero'
    mesero_id = g.usuario['id_usuario']

    cur = g.db.cursor()

    # Una mesa en uso solo puede recibir órdenes del mesero que la atiende
    orden_existente = None
    if id_mesa:
        orden_existente = _srv._orden_abierta_de_mesa(cur, id_mesa)
        if orden_existente and orden_existente['mesero_id'] != mesero_id:
            return jsonify({
                "error": f"Esta mesa está siendo atendida por "
                         f"{orden_existente['mesero_nombre'] or 'otro mesero'}. "
                         f"No puedes enviar órdenes a esta mesa."
            }), 409

    total = 0.0
    procesados = []
    for it in items:
        pid = int(it.get('id_producto'))
        cant = int(it.get('cantidad', 1))
        if cant <= 0:
            continue
        cur.execute("SELECT nombre, precio FROM producto WHERE id_producto = ?", (pid,))
        p = cur.fetchone()
        if not p:
            return jsonify({"error": f"Producto con ID {pid} no existe"}), 400
        pu = float(p['precio'])
        st = round(pu * cant, 2)
        total += st
        procesados.append((pid, cant, pu, st, it.get('observacion')))

    total = round(total, 2)

    try:
        if orden_existente:
            # La mesa ya tiene una orden de este mismo mesero: se agregan los productos a ella
            id_pedido = orden_existente['id_pedido']
            for pid, cant, pu, st, obs in procesados:
                cur.execute("""SELECT id_detalle, cantidad FROM detalle_pedido
                               WHERE id_pedido = ? AND id_producto = ?""", (id_pedido, pid))
                ex = cur.fetchone()
                if ex:
                    nueva = ex['cantidad'] + cant
                    cur.execute("UPDATE detalle_pedido SET cantidad = ?, subtotal = ? WHERE id_detalle = ?",
                                (nueva, round(pu * nueva, 2), ex['id_detalle']))
                else:
                    cur.execute("""INSERT INTO detalle_pedido
                                   (id_pedido, id_producto, cantidad, precio_unitario, subtotal, observacion)
                                   VALUES (?, ?, ?, ?, ?, ?)""",
                                (id_pedido, pid, cant, pu, st, obs))
            cur.execute("SELECT COALESCE(SUM(subtotal), 0) FROM detalle_pedido WHERE id_pedido = ?",
                        (id_pedido,))
            total = round(float(cur.fetchone()[0]), 2)
            cur.execute("UPDATE pedido SET total = ? WHERE id_pedido = ?", (total, id_pedido))
            g.db.commit()
            return jsonify({"status": "updated", "id_pedido": id_pedido, "total": total,
                            "agregado_a_existente": True}), 200

        cur.execute("""INSERT INTO pedido (tipo_pedido, estado, id_mesa, total, mesero_id, mesero_nombre)
                       VALUES (?, 'Abierta', ?, ?, ?, ?)""",
                    (tipo_pedido, id_mesa, total, mesero_id, mesero_nombre))
        id_pedido = cur.lastrowid
        for pid, cant, pu, st, obs in procesados:
            cur.execute("""INSERT INTO detalle_pedido
                           (id_pedido, id_producto, cantidad, precio_unitario, subtotal, observacion)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (id_pedido, pid, cant, pu, st, obs))
        g.db.commit()
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "success", "id_pedido": id_pedido, "total": total}), 201


@pedidos_bp.route('/api/pedidos/abiertos', methods=['GET'])
def api_pedidos_abiertos():
    """Lista todas las órdenes con estado 'Abierto'."""
    cur = g.db.cursor()
    cur.execute("""SELECT p.id_pedido, p.tipo_pedido, p.id_mesa, p.total, p.mesero_nombre,
                          p.mesero_id, p.fecha_hora, m.numero_mesa
                   FROM pedido p
                   LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                   WHERE p.estado = 'Abierta'
                   ORDER BY p.id_pedido DESC""")
    pedidos = []
    for row in cur.fetchall():
        ped = dict(row)
        cur2 = g.db.cursor()
        cur2.execute("""SELECT dp.id_producto, pr.nombre, dp.cantidad, dp.precio_unitario, dp.subtotal
                        FROM detalle_pedido dp
                        JOIN producto pr ON dp.id_producto = pr.id_producto
                        WHERE dp.id_pedido = ?""", (ped['id_pedido'],))
        ped['items'] = [dict(r) for r in cur2.fetchall()]
        pedidos.append(ped)
    return jsonify(pedidos), 200


@pedidos_bp.route('/api/pedidos/<int:id_pedido>', methods=['GET'])
def api_pedido_detalle(id_pedido):
    cur = g.db.cursor()
    cur.execute("""SELECT p.*, m.numero_mesa
                   FROM pedido p
                   LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                   WHERE p.id_pedido = ?""", (id_pedido,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Pedido no encontrado"}), 404
    ped = dict(row)
    cur.execute("""SELECT dp.id_producto, pr.nombre, dp.cantidad, dp.precio_unitario, dp.subtotal
                   FROM detalle_pedido dp
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE dp.id_pedido = ?""", (id_pedido,))
    ped['items'] = [dict(r) for r in cur.fetchall()]
    return jsonify(ped), 200


@pedidos_bp.route('/api/pedidos/<int:id_pedido>/cobrar', methods=['POST'])
def api_pedido_cobrar(id_pedido):
    """Cobrar una orden abierta: genera factura y cambia estado a 'Pagado'."""
    if g.usuario['rol'] not in ('admin', 'cajero'):
        return jsonify({"error": f"Solo un cajero o administrador puede cobrar. "
                                 f"La sesión activa es de '{g.usuario['username']}' "
                                 f"({g.usuario['rol']}); recarga la página e inicia sesión como cajero."}), 403
    cur = g.db.cursor()
    cur.execute("SELECT * FROM pedido WHERE id_pedido = ? AND estado = 'Abierta'", (id_pedido,))
    pedido = cur.fetchone()
    if not pedido:
        return jsonify({"error": "Pedido no encontrado o ya cobrado"}), 404

    data = request.get_json(silent=True) or {}
    cliente_nombre = data.get('cliente_nombre') or 'Consumidor Final'
    metodo_pago = data.get('metodo_pago', 'Efectivo')
    monto_recibido = float(data.get('monto_recibido', 0) or 0)

    cur.execute("""SELECT dp.id_producto, dp.cantidad, dp.precio_unitario, dp.subtotal
                   FROM detalle_pedido dp WHERE dp.id_pedido = ?""", (id_pedido,))
    items = cur.fetchall()
    if not items:
        return jsonify({"error": "La orden no tiene productos. No se puede generar una factura vacía."}), 400
    subtotal = round(sum(float(it['subtotal']) for it in items), 2)
    impuesto = round(subtotal * _srv.IVA, 2)
    monto_total = round(subtotal + impuesto, 2)

    # Validar que el monto recibido no sea menor al total cuando se paga en efectivo
    if metodo_pago == 'Efectivo' and monto_recibido < monto_total:
        return jsonify({
            "error": f"El monto recibido es menor al total C$ {monto_total:.2f}. No es posible cobrar."
        }), 400

    cambio = round(max(0.0, monto_recibido - monto_total), 2) if monto_recibido > 0 else 0.0

    mesero_nombre = pedido['mesero_nombre'] if 'mesero_nombre' in pedido.keys() else 'Mesero'

    try:
        cur.execute("UPDATE pedido SET estado = 'Pagado', total = ? WHERE id_pedido = ?",
                    (monto_total, id_pedido))
        cur.execute("""INSERT INTO factura
                       (id_pedido, cliente_nombre, subtotal, impuesto,
                        descuento, propina, monto_total, metodo_pago, monto_recibido, cambio_devuelto, mesero_nombre)
                       VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)""",
                    (id_pedido, cliente_nombre, subtotal, impuesto,
                     monto_total, metodo_pago, monto_recibido, cambio, mesero_nombre))
        id_factura = cur.lastrowid
        g.db.commit()
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500

    # Devolver la factura completa para que el comprobante no dependa de otra consulta
    cur.execute("""SELECT f.*, p.tipo_pedido, p.id_mesa, p.mesero_id, m.numero_mesa
                   FROM factura f
                   JOIN pedido p ON f.id_pedido = p.id_pedido
                   LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                   WHERE f.id_factura = ?""", (id_factura,))
    factura = dict(cur.fetchone())
    cur.execute("""SELECT dp.id_detalle, dp.id_producto, pr.nombre, dp.cantidad,
                          dp.precio_unitario, dp.subtotal, dp.observacion
                   FROM detalle_pedido dp
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE dp.id_pedido = ?
                   ORDER BY dp.id_detalle ASC""", (id_pedido,))
    factura['items'] = [dict(r) for r in cur.fetchall()]

    return jsonify({
        "status": "success", "id_factura": id_factura, "id_pedido": id_pedido,
        "subtotal": subtotal, "impuesto": impuesto, "monto_total": monto_total,
        "cambio_devuelto": cambio, "factura": factura,
    }), 200


@pedidos_bp.route('/api/pedidos/<int:id_pedido>/anular', methods=['POST'])
def api_pedido_anular(id_pedido):
    """Anular un pedido (abierto o pagado). Si tiene factura, la elimina."""
    if g.usuario['rol'] not in ('admin', 'cajero'):
        return jsonify({"error": "Acceso denegado"}), 403
    cur = g.db.cursor()
    cur.execute("SELECT * FROM pedido WHERE id_pedido = ?", (id_pedido,))
    if not cur.fetchone():
        return jsonify({"error": "Pedido no encontrado"}), 404
    try:
        cur.execute("DELETE FROM factura WHERE id_pedido = ?", (id_pedido,))
        cur.execute("DELETE FROM detalle_pedido WHERE id_pedido = ?", (id_pedido,))
        cur.execute("DELETE FROM pedido WHERE id_pedido = ?", (id_pedido,))
        registrar_auditoria(g.db, g.usuario['id_usuario'], 'anular_pedido',
                            'pedido', id_pedido, None, request.remote_addr)
        g.db.commit()
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500
    return jsonify({"status": "anulado", "id_pedido": id_pedido}), 200


@pedidos_bp.route('/api/pedidos/<int:id_pedido>/actualizar', methods=['POST'])
def api_pedido_actualizar(id_pedido):
    """Agregar items a una orden abierta existente."""
    cur = g.db.cursor()
    cur.execute("SELECT * FROM pedido WHERE id_pedido = ? AND estado = 'Abierta'", (id_pedido,))
    pedido_actual = cur.fetchone()
    if not pedido_actual:
        return jsonify({"error": "Pedido no encontrado o ya cerrado"}), 404
    if g.usuario['rol'] == 'mesero' and pedido_actual['mesero_id'] != g.usuario['id_usuario']:
        return jsonify({"error": f"Esta orden pertenece a "
                                 f"{pedido_actual['mesero_nombre'] or 'otro mesero'}. "
                                 f"Solo el mesero que atiende la mesa puede agregar productos."}), 403

    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    if not items:
        return jsonify({"error": "No hay items para agregar"}), 400

    try:
        for it in items:
            pid = int(it.get('id_producto'))
            cant = int(it.get('cantidad', 1))
            if cant <= 0:
                continue
            cur.execute("SELECT precio FROM producto WHERE id_producto = ?", (pid,))
            p = cur.fetchone()
            if not p:
                continue
            pu = float(p['precio'])
            st = round(pu * cant, 2)
            # Verificar si el producto ya existe en la orden
            cur.execute("""SELECT id_detalle, cantidad, subtotal FROM detalle_pedido
                           WHERE id_pedido = ? AND id_producto = ?""", (id_pedido, pid))
            existing = cur.fetchone()
            if existing:
                nueva_cant = existing['cantidad'] + cant
                nuevo_st = round(pu * nueva_cant, 2)
                cur.execute("""UPDATE detalle_pedido SET cantidad = ?, subtotal = ?
                               WHERE id_detalle = ?""", (nueva_cant, nuevo_st, existing['id_detalle']))
            else:
                cur.execute("""INSERT INTO detalle_pedido
                               (id_pedido, id_producto, cantidad, precio_unitario, subtotal)
                               VALUES (?, ?, ?, ?, ?)""", (id_pedido, pid, cant, pu, st))

        # Recalcular total
        cur.execute("SELECT COALESCE(SUM(subtotal), 0) FROM detalle_pedido WHERE id_pedido = ?",
                    (id_pedido,))
        nuevo_total = round(float(cur.fetchone()[0]), 2)
        cur.execute("UPDATE pedido SET total = ? WHERE id_pedido = ?", (nuevo_total, id_pedido))
        g.db.commit()
    except Exception as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "updated", "id_pedido": id_pedido, "nuevo_total": nuevo_total}), 200
