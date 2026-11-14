"""
Rutas de productos y categorías (lectura pública + CRUD admin).
"""
from flask import Blueprint, jsonify, request, g

productos_bp = Blueprint('productos', __name__)


@productos_bp.route('/api/categorias', methods=['GET'])
def api_categorias():
    cur = g.db.cursor()
    cur.execute("SELECT id_categoria, nombre FROM categoria ORDER BY id_categoria")
    return jsonify([dict(r) for r in cur.fetchall()]), 200


@productos_bp.route('/api/productos', methods=['GET'])
def api_productos():
    cur = g.db.cursor()
    cur.execute("""SELECT p.id_producto, p.nombre, p.descripcion, p.precio, p.imagen_url,
                          p.disponible, c.id_categoria, c.nombre AS categoria
                   FROM producto p
                   JOIN categoria c ON p.id_categoria = c.id_categoria
                   WHERE p.disponible = 1
                   ORDER BY c.id_categoria, p.id_producto""")
    data = [{"id_producto": r['id_producto'], "nombre": r['nombre'],
             "descripcion": r['descripcion'] or "", "precio": float(r['precio']),
             "imagen_url": r['imagen_url'] or "", "disponible": r['disponible'],
             "id_categoria": r['id_categoria'], "categoria": r['categoria']}
            for r in cur.fetchall()]
    return jsonify(data), 200


# ========================================================================
# CRUD PRODUCTOS (ADMIN)
# ========================================================================
@productos_bp.route('/api/productos', methods=['POST'])
def api_producto_crear():
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    data = request.get_json(silent=True) or {}
    nombre = (data.get('nombre') or '').strip()
    precio = float(data.get('precio', 0))
    id_cat = int(data.get('id_categoria', 0))
    if not nombre or precio <= 0 or id_cat <= 0:
        return jsonify({"error": "Datos incompletos"}), 400
    cur = g.db.cursor()
    cur.execute("""INSERT INTO producto (nombre, descripcion, precio, imagen_url, id_categoria, disponible)
                   VALUES (?, ?, ?, ?, ?, 1)""",
                (nombre, data.get('descripcion', ''), precio,
                 data.get('imagen_url', ''), id_cat))
    g.db.commit()
    return jsonify({"status": "created", "id_producto": cur.lastrowid}), 201


@productos_bp.route('/api/productos/<int:pid>', methods=['PUT'])
def api_producto_editar(pid):
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    data = request.get_json(silent=True) or {}
    sets, vals = [], []
    for campo in ('nombre', 'descripcion', 'precio', 'imagen_url', 'id_categoria'):
        if campo in data:
            sets.append(f"{campo} = ?"); vals.append(data[campo])
    if 'disponible' in data:
        sets.append("disponible = ?"); vals.append(1 if data['disponible'] else 0)
    if not sets:
        return jsonify({"status": "noop"}), 200
    vals.append(pid)
    g.db.execute(f"UPDATE producto SET {', '.join(sets)} WHERE id_producto = ?", vals)
    g.db.commit()
    return jsonify({"status": "updated", "id_producto": pid}), 200


@productos_bp.route('/api/productos/<int:pid>', methods=['DELETE'])
def api_producto_eliminar(pid):
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    cur = g.db.cursor()
    cur.execute("SELECT COUNT(*) FROM detalle_pedido WHERE id_producto = ?", (pid,))
    if cur.fetchone()[0] > 0:
        g.db.execute("UPDATE producto SET disponible = 0 WHERE id_producto = ?", (pid,))
        accion = "deshabilitado"
    else:
        g.db.execute("DELETE FROM producto WHERE id_producto = ?", (pid,))
        accion = "eliminado"
    g.db.commit()
    return jsonify({"status": "ok", "accion": accion}), 200
