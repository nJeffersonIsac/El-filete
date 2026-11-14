"""
Rutas de facturas: listar, detalle, eliminar (anulación lógica).
"""
from flask import Blueprint, jsonify, request, g

import server as _srv

facturas_bp = Blueprint('facturas', __name__)


@facturas_bp.route('/api/facturas', methods=['GET'])
def api_facturas_list():
    cur = g.db.cursor()
    u = g.usuario
    if u['rol'] == 'mesero':
        cur.execute("""SELECT f.*, p.tipo_pedido, p.id_mesa, m.numero_mesa
                       FROM factura f
                       JOIN pedido p ON f.id_pedido = p.id_pedido
                       LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                       WHERE p.mesero_id = ?
                       ORDER BY f.id_factura DESC""",
                    (u['id_usuario'],))
    else:
        cur.execute("""SELECT f.*, p.tipo_pedido, p.id_mesa, m.numero_mesa
                       FROM factura f
                       JOIN pedido p ON f.id_pedido = p.id_pedido
                       LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                       ORDER BY f.id_factura DESC""")
    return jsonify([dict(r) for r in cur.fetchall()]), 200


@facturas_bp.route('/api/facturas/<int:id_factura>', methods=['GET'])
def api_factura_detalle(id_factura):
    cur = g.db.cursor()
    cur.execute("""SELECT f.*, p.tipo_pedido, p.id_mesa, p.mesero_id, m.numero_mesa
                   FROM factura f
                   JOIN pedido p ON f.id_pedido = p.id_pedido
                   LEFT JOIN mesa m ON p.id_mesa = m.id_mesa
                   WHERE f.id_factura = ?""", (id_factura,))
    row = cur.fetchone()
    if not row:
        return jsonify({"error": "Factura no encontrada"}), 404
    u = g.usuario
    if u['rol'] == 'mesero':
        if row['mesero_id'] != u['id_usuario']:
            return jsonify({"error": "Acceso denegado a esta factura"}), 403
    f = dict(row)
    cur.execute("""SELECT dp.id_detalle, dp.id_producto, pr.nombre, dp.cantidad,
                          dp.precio_unitario, dp.subtotal, dp.observacion
                   FROM detalle_pedido dp
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE dp.id_pedido = ?
                   ORDER BY dp.id_detalle ASC""", (f['id_pedido'],))
    f['items'] = [dict(r) for r in cur.fetchall()]
    return jsonify(f), 200


@facturas_bp.route('/api/facturas/<int:id_factura>', methods=['DELETE'])
def api_factura_delete(id_factura):
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    if request.headers.get('X-Confirm-Delete', '').lower() != 'yes':
        return jsonify({"error": "Falta header X-Confirm-Delete: yes"}), 400
    try:
        return jsonify(_srv._core_eliminar_factura(g.db, id_factura,
                                                  g.usuario['id_usuario'],
                                                  request.remote_addr)), 200
    except LookupError:
        return jsonify({"error": "Factura no encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
