"""
Rutas de autenticación: login, registro, logout, sesión actual.
"""
import sqlite3
from flask import Blueprint, jsonify, request, g

from auth import (
    hash_password, verify_password, generar_token,
    crear_sesion, validar_sesion, renovar_sesion_si_pronto_expira,
    invalidar_sesion, limpiar_sesiones_expiradas,
    registrar_intento, contar_intentos_fallidos, registrar_auditoria,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    ip = request.remote_addr or ''
    ua = request.headers.get('User-Agent', '')

    if contar_intentos_fallidos(g.db, username, ip, 15) >= 5:
        return jsonify({"error": "Demasiados intentos. Espera 15 minutos."}), 429

    cur = g.db.cursor()
    cur.execute("SELECT id_usuario, password_hash, nombre_completo, rol, activo "
                "FROM usuario WHERE username = ?", (username,))
    row = cur.fetchone()
    ok = bool(row) and row['activo'] and verify_password(password, row['password_hash'])

    if not ok:
        registrar_intento(g.db, username, ip, False)
        return jsonify({"error": "Credenciales inválidas"}), 401

    registrar_intento(g.db, username, ip, True)
    limpiar_sesiones_expiradas(g.db)
    token = crear_sesion(g.db, row['id_usuario'], ip, ua)
    csrf = generar_token()
    registrar_auditoria(g.db, row['id_usuario'], 'login',
                        entidad='usuario', entidad_id=row['id_usuario'], ip=ip)

    resp = jsonify({
        "id_usuario": row['id_usuario'], "username": username,
        "rol": row['rol'], "nombre_completo": row['nombre_completo'],
    })
    resp.set_cookie('sesion_token', token, max_age=8*3600, httponly=True,
                    samesite='Lax', secure=request.is_secure)
    resp.set_cookie('csrf_token', csrf, max_age=8*3600, httponly=False,
                    samesite='Lax', secure=request.is_secure)
    return resp, 200


@auth_bp.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    nombre = (data.get('nombre_completo') or '').strip() or username

    if len(username) < 3 or not all(c.isalnum() or c == '_' for c in username):
        return jsonify({"error": "Usuario inválido (mín. 3, alfanumérico/_)"}), 400
    if len(password) < 8:
        return jsonify({"error": "Contraseña de al menos 8 caracteres"}), 400

    cur = g.db.cursor()
    cur.execute("SELECT 1 FROM usuario WHERE username = ?", (username,))
    if cur.fetchone():
        return jsonify({"error": "El nombre de usuario ya está en uso"}), 409

    try:
        cur.execute("""INSERT INTO usuario
                       (username, password_hash, nombre_completo, rol, activo)
                       VALUES (?, ?, ?, 'mesero', 1)""",
                    (username, hash_password(password), nombre))
        nuevo_id = cur.lastrowid
        registrar_auditoria(g.db, nuevo_id, 'registro_publico',
                            'usuario', nuevo_id, "Auto-registro web", request.remote_addr)
        g.db.commit()
    except sqlite3.IntegrityError as e:
        g.db.rollback()
        return jsonify({"error": str(e)}), 409

    return jsonify({"status": "success", "mensaje": "Usuario registrado correctamente. Ya puedes iniciar sesión."}), 201


@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    token = request.cookies.get('sesion_token')
    if token:
        invalidar_sesion(g.db, token)
        registrar_auditoria(g.db, g.usuario['id_usuario'], 'logout',
                            ip=request.remote_addr)
    resp = jsonify({"status": "ok"})
    resp.set_cookie('sesion_token', '', max_age=0)
    resp.set_cookie('csrf_token', '', max_age=0)
    return resp, 200


@auth_bp.route('/api/auth/me', methods=['GET'])
def api_me():
    u = g.usuario
    token = request.cookies.get('sesion_token')
    renovada = renovar_sesion_si_pronto_expira(g.db, token)
    resp = jsonify({
        "id_usuario": u['id_usuario'], "username": u['username'],
        "rol": u['rol'], "nombre_completo": u['nombre_completo'],
    })
    if renovada:
        resp.set_cookie('sesion_token', token, max_age=8*3600, httponly=True,
                        samesite='Lax', secure=request.is_secure)
    return resp, 200
