"""
Rutas de gestión de usuarios (CRUD admin).
"""
import sqlite3
from flask import Blueprint, jsonify, request, g

from auth import hash_password, registrar_auditoria

usuarios_bp = Blueprint('usuarios', __name__)


@usuarios_bp.route('/api/usuarios', methods=['GET'])
def api_usuarios_list():
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    cur = g.db.cursor()
    cur.execute("SELECT id_usuario, username, nombre_completo, rol, activo, fecha_creacion "
                "FROM usuario ORDER BY id_usuario")
    return jsonify([dict(r) for r in cur.fetchall()]), 200


@usuarios_bp.route('/api/usuarios', methods=['POST'])
def api_usuarios_create():
    creador = g.usuario
    if creador['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado. Solo el administrador puede crear usuarios."}), 403
        
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    nombre = (data.get('nombre_completo') or '').strip() or username
    rol = data.get('rol') or 'mesero'

    if len(username) < 3 or not all(c.isalnum() or c == '_' for c in username):
        return jsonify({"error": "Username inválido"}), 400
    if len(password) < 8:
        return jsonify({"error": "Contraseña de al menos 8 caracteres"}), 400
    if rol not in ('admin', 'cajero', 'mesero'):
        return jsonify({"error": "Rol inválido"}), 400

    cur = g.db.cursor()
    cur.execute("SELECT 1 FROM usuario WHERE username = ?", (username,))
    if cur.fetchone():
        return jsonify({"error": "El username ya existe"}), 409
    if rol == 'admin':
        cur.execute("SELECT 1 FROM usuario WHERE rol='admin' AND activo=1")
        if cur.fetchone():
            return jsonify({"error": "Ya existe un administrador"}), 409

    try:
        cur.execute("""INSERT INTO usuario
                       (username, password_hash, nombre_completo, rol, activo, creado_por)
                       VALUES (?, ?, ?, ?, 1, ?)""",
                    (username, hash_password(password), nombre, rol, creador['id_usuario']))
        nuevo_id = cur.lastrowid
        registrar_auditoria(g.db, creador['id_usuario'], 'crear_usuario',
                            'usuario', nuevo_id, f"rol={rol}", request.remote_addr)
        g.db.commit()
    except sqlite3.IntegrityError as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 409
    return jsonify({"status": "created", "id_usuario": nuevo_id, "rol": rol}), 201


@usuarios_bp.route('/api/usuarios/<int:uid>', methods=['DELETE'])
def api_usuarios_delete(uid):
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    if uid == g.usuario['id_usuario']:
        return jsonify({"error": "No puedes eliminarte a ti mismo"}), 409
    cur = g.db.cursor()
    cur.execute("SELECT * FROM usuario WHERE id_usuario = ?", (uid,))
    if not cur.fetchone():
        return jsonify({"error": "Usuario no encontrado"}), 404
    cur.execute("SELECT COUNT(*) FROM reserva WHERE creado_por = ?", (uid,))
    n_res = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM auditoria WHERE id_usuario = ?", (uid,))
    n_aud = cur.fetchone()[0]
    if n_res > 0 or n_aud > 0:
        g.db.execute("UPDATE usuario SET activo = 0 WHERE id_usuario = ?", (uid,))
        action = "desactivado (tenía historial)"
    else:
        g.db.execute("DELETE FROM usuario WHERE id_usuario = ?", (uid,))
        action = "eliminado"
    registrar_auditoria(g.db, g.usuario['id_usuario'], 'eliminar_usuario',
                        'usuario', uid, action, request.remote_addr)
    g.db.commit()
    return jsonify({"status": "ok", "accion": action}), 200
