"""
Rutas de mesas.
"""
from flask import Blueprint, jsonify, g

mesas_bp = Blueprint('mesas', __name__)


@mesas_bp.route('/api/mesas', methods=['GET'])
def api_mesas():
    cur = g.db.cursor()
    cur.execute("""SELECT m.id_mesa, m.numero_mesa, m.capacidad, m.estado,
                          (SELECT p.id_pedido FROM pedido p
                           WHERE p.id_mesa = m.id_mesa AND p.estado = 'Abierta'
                           ORDER BY p.id_pedido LIMIT 1) AS orden_abierta_id,
                          (SELECT p.mesero_id FROM pedido p
                           WHERE p.id_mesa = m.id_mesa AND p.estado = 'Abierta'
                           ORDER BY p.id_pedido LIMIT 1) AS ocupada_por_id,
                          (SELECT p.mesero_nombre FROM pedido p
                           WHERE p.id_mesa = m.id_mesa AND p.estado = 'Abierta'
                           ORDER BY p.id_pedido LIMIT 1) AS ocupada_por_nombre
                   FROM mesa m ORDER BY m.numero_mesa""")
    return jsonify([dict(r) for r in cur.fetchall()]), 200
