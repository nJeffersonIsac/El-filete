"""
Rutas de reservas: CRUD + disponibilidad.
"""
from flask import Blueprint, jsonify, request, g

from auth import registrar_auditoria
import server as _srv

reservas_bp = Blueprint('reservas', __name__)


@reservas_bp.route('/api/reservas', methods=['GET'])
def api_reservas_list():
    cur = g.db.cursor()
    conds, vals = [], []
    if request.args.get('fecha'):
        conds.append("r.fecha_reserva = ?"); vals.append(request.args['fecha'])
    if request.args.get('estado'):
        conds.append("r.estado = ?"); vals.append(request.args['estado'])
    where = "WHERE " + " AND ".join(conds) if conds else ""
    cur.execute(f"""SELECT r.*, m.numero_mesa, u.username AS creador_username
                    FROM reserva r
                    LEFT JOIN mesa m ON r.id_mesa = m.id_mesa
                    LEFT JOIN usuario u ON r.creado_por = u.id_usuario
                    {where}
                    ORDER BY r.fecha_reserva ASC, r.hora_reserva ASC""", vals)
    return jsonify([dict(r) for r in cur.fetchall()]), 200


@reservas_bp.route('/api/reservas', methods=['POST'])
def api_reservas_create():
    data = request.get_json(silent=True) or {}
    err = _srv._validar_reserva(g.db, data)
    if err:
        return jsonify({"error": err}), 400
    cur = g.db.cursor()
    cur.execute("""INSERT INTO reserva
                   (nombre_cliente, telefono, email, fecha_reserva, hora_reserva,
                    num_personas, id_mesa, notas, estado, creado_por)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)""",
                (data['nombre_cliente'].strip(), data['telefono'].strip(),
                 (data.get('email') or '').strip() or None,
                 data['fecha_reserva'], data['hora_reserva'],
                 int(data['num_personas']), data.get('id_mesa') or None,
                 (data.get('notas') or '').strip() or None,
                 g.usuario['id_usuario']))
    rid = cur.lastrowid
    registrar_auditoria(g.db, g.usuario['id_usuario'], 'crear_reserva',
                        'reserva', rid, None, request.remote_addr)
    g.db.commit()
    return jsonify({"status": "created", "id_reserva": rid}), 201


@reservas_bp.route('/api/reservas/<int:rid>', methods=['PUT'])
def api_reservas_update(rid):
    cur = g.db.cursor()
    cur.execute("SELECT * FROM reserva WHERE id_reserva = ?", (rid,))
    r = cur.fetchone()
    if not r:
        return jsonify({"error": "Reserva no encontrada"}), 404
    u = g.usuario
    if u['rol'] == 'mesero' and r['creado_por'] != u['id_usuario']:
        return jsonify({"error": "Acceso denegado"}), 403
        
    data = request.get_json(silent=True) or {}
    sets, vals = [], []
    
    nueva_mesa = data.get('id_mesa', r['id_mesa'])
    nueva_fecha = data.get('fecha_reserva', r['fecha_reserva'])
    nueva_hora = data.get('hora_reserva', r['hora_reserva'])
    
    if nueva_mesa and 'estado' not in data:
        cur.execute("""
            SELECT id_reserva FROM reserva 
            WHERE id_mesa = ? AND fecha_reserva = ? AND hora_reserva = ? 
            AND estado IN ('pendiente', 'confirmada') AND id_reserva != ?
        """, (nueva_mesa, nueva_fecha, nueva_hora, rid))
        if cur.fetchone():
            return jsonify({"error": "La mesa ya está reservada para esa fecha y hora."}), 400

    for campo in ('nombre_cliente', 'telefono', 'email', 'fecha_reserva',
                  'hora_reserva', 'num_personas', 'id_mesa', 'notas'):
        if campo in data:
            sets.append(f"{campo} = ?"); vals.append(data[campo])
            
    if 'estado' in data:
        trans = {'pendiente': ('confirmada', 'cancelada'),
                 'confirmada': ('completada', 'cancelada'),
                 'completada': (), 'cancelada': ()}
        nuevo = data['estado']
        if nuevo != r['estado'] and nuevo not in trans.get(r['estado'], ()):
            return jsonify({"error": f"Transición {r['estado']} → {nuevo} no permitida"}), 400
        sets.append("estado = ?"); vals.append(nuevo)
        
    if not sets:
        return jsonify({"status": "noop"}), 200
        
    vals.append(rid)
    g.db.execute(f"UPDATE reserva SET {', '.join(sets)} WHERE id_reserva = ?", vals)
    registrar_auditoria(g.db, u['id_usuario'], 'editar_reserva', 'reserva', rid, None, request.remote_addr)
    g.db.commit()
    return jsonify({"status": "updated", "id_reserva": rid}), 200


@reservas_bp.route('/api/reservas/<int:rid>', methods=['DELETE'])
def api_reservas_delete(rid):
    cur = g.db.cursor()
    cur.execute("SELECT creado_por FROM reserva WHERE id_reserva = ?", (rid,))
    r = cur.fetchone()
    if not r:
        return jsonify({"error": "Reserva no encontrada"}), 404
    u = g.usuario
    if u['rol'] != 'admin' and r['creado_por'] != u['id_usuario']:
        return jsonify({"error": "Acceso denegado"}), 403
    g.db.execute("DELETE FROM reserva WHERE id_reserva = ?", (rid,))
    registrar_auditoria(g.db, u['id_usuario'], 'eliminar_reserva',
                        'reserva', rid, None, request.remote_addr)
    g.db.commit()
    return jsonify({"status": "deleted", "id_reserva": rid}), 200


@reservas_bp.route('/api/reservas/disponibilidad', methods=['GET'])
def api_reservas_disponibilidad():
    fecha = request.args.get('fecha')
    hora = request.args.get('hora')
    personas = int(request.args.get('personas') or 1)
    cur = g.db.cursor()
    if fecha and hora:
        cur.execute("""SELECT id_mesa, numero_mesa, capacidad FROM mesa
                       WHERE capacidad >= ?
                         AND id_mesa NOT IN (
                            SELECT id_mesa FROM reserva
                            WHERE fecha_reserva = ? AND hora_reserva = ?
                              AND estado IN ('pendiente','confirmada')
                              AND id_mesa IS NOT NULL)
                       ORDER BY numero_mesa""", (personas, fecha, hora))
    else:
        cur.execute("SELECT id_mesa, numero_mesa, capacidad FROM mesa "
                    "WHERE capacidad >= ? ORDER BY numero_mesa", (personas,))
    return jsonify([dict(r) for r in cur.fetchall()]), 200
