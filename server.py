"""
Servidor Backend para Restaurante "El Filete".
Auth, roles, reportes y reservas. Compatible Flask + fallback http.server.
"""
import os
import sys
import json
import hmac
import sqlite3
import mimetypes
from datetime import date, datetime
from urllib.parse import urlparse, parse_qs

# Corregir MIME types incorrectos del registro de Windows (Python 3.15+)
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')
mimetypes.add_type('text/html', '.html')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from auth import (
    get_db, hash_password, verify_password, generar_token,
    crear_sesion, validar_sesion, renovar_sesion_si_pronto_expira,
    invalidar_sesion, invalidar_sesiones_usuario, limpiar_sesiones_expiradas,
    registrar_intento, contar_intentos_fallidos, registrar_auditoria,
)

DB_NAME = "Filete2.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
IVA = 0.15


def _orden_abierta_de_mesa(cur, id_mesa):
    """Devuelve la orden abierta (si existe) que ocupa la mesa."""
    cur.execute("""SELECT id_pedido, mesero_id, mesero_nombre
                   FROM pedido
                   WHERE id_mesa = ? AND estado = 'Abierta'
                   ORDER BY id_pedido ASC LIMIT 1""", (id_mesa,))
    return cur.fetchone()


def _migrar_mesero_ids():
    """Asigna mesero_id a pedidos antiguos que solo guardaban el nombre del mesero,
    para que el historial de cada mesero se filtre por su ID y no por nombre."""
    try:
        conn = get_db()
        conn.execute("""
            UPDATE pedido
            SET mesero_id = (
                SELECT u.id_usuario FROM usuario u
                WHERE u.nombre_completo = COALESCE(pedido.mesero_nombre,
                      (SELECT f.mesero_nombre FROM factura f WHERE f.id_pedido = pedido.id_pedido))
            )
            WHERE mesero_id IS NULL
              AND (SELECT COUNT(*) FROM usuario u
                   WHERE u.nombre_completo = COALESCE(pedido.mesero_nombre,
                         (SELECT f.mesero_nombre FROM factura f WHERE f.id_pedido = pedido.id_pedido))) = 1
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Aviso: no se pudo migrar mesero_id: {e}")


def _core_crear_venta(conn, data, mesero_id=None, mesero_nombre=None):
    items = data.get('items', [])
    if not items:
        raise ValueError("La orden no contiene productos")

    id_mesa = data.get('id_mesa')
    tipo_pedido = data.get('tipo_pedido', 'Mesa' if id_mesa else 'Para Llevar')
    cliente_nombre = data.get('cliente_nombre') or 'Consumidor Final'
    cliente_ruc = data.get('cliente_ruc_cedula')
    metodo_pago = data.get('metodo_pago', 'Efectivo')
    descuento = float(data.get('descuento', 0) or 0)
    propina = float(data.get('propina', 0) or 0)
    monto_recibido = float(data.get('monto_recibido', 0) or 0)
    # El nombre se toma del usuario autenticado, nunca del cliente
    mesero_nombre = mesero_nombre or 'Cajero'

    cur = conn.cursor()
    if id_mesa:
        abierta = _orden_abierta_de_mesa(cur, id_mesa)
        if abierta:
            raise ValueError(f"Esta mesa tiene una orden abierta del mesero {abierta['mesero_nombre']}. Cóbrala desde Órdenes Abiertas.")

    subtotal = 0.0
    procesados = []
    for it in items:
        pid = int(it.get('id_producto'))
        cant = int(it.get('cantidad', 1))
        if cant <= 0:
            continue
        cur.execute("SELECT nombre, precio FROM producto WHERE id_producto = ?", (pid,))
        p = cur.fetchone()
        if not p:
            raise ValueError(f"Producto con ID {pid} no existe")
        pu = float(p['precio'])
        st = round(pu * cant, 2)
        subtotal += st
        procesados.append((pid, cant, pu, st, it.get('observacion')))

    subtotal = round(subtotal, 2)
    impuesto = round(subtotal * IVA, 2)
    monto_total = round(subtotal + impuesto + propina - descuento, 2)
    cambio = round(max(0.0, monto_recibido - monto_total), 2) if monto_recibido > 0 else 0.0

    try:
        cur.execute("""INSERT INTO pedido (tipo_pedido, estado, id_mesa, total, mesero_id, mesero_nombre)
                       VALUES (?, 'Pagado', ?, ?, ?, ?)""",
                    (tipo_pedido, id_mesa, monto_total, mesero_id, mesero_nombre))
        id_pedido = cur.lastrowid
        for pid, cant, pu, st, obs in procesados:
            cur.execute("""INSERT INTO detalle_pedido
                           (id_pedido, id_producto, cantidad, precio_unitario, subtotal, observacion)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (id_pedido, pid, cant, pu, st, obs))
        # GUARDAR NOMBRE DEL MESERO
        cur.execute("""INSERT INTO factura
                       (id_pedido, cliente_nombre, cliente_ruc_cedula, subtotal, impuesto,
                        descuento, propina, monto_total, metodo_pago, monto_recibido, cambio_devuelto, mesero_nombre)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (id_pedido, cliente_nombre, cliente_ruc, subtotal, impuesto,
                     descuento, propina, monto_total, metodo_pago, monto_recibido, cambio, mesero_nombre))
        id_factura = cur.lastrowid
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return {
        "status": "success", "id_factura": id_factura, "id_pedido": id_pedido,
        "subtotal": subtotal, "impuesto": impuesto, "monto_total": monto_total,
        "metodo_pago": metodo_pago, "cambio_devuelto": cambio,
        "mensaje": f"Factura #{id_factura:06d} generada exitosamente",
    }


def _core_eliminar_factura(conn, id_factura, id_usuario, ip):
    cur = conn.cursor()
    cur.execute("SELECT id_pedido, monto_total FROM factura WHERE id_factura = ?", (id_factura,))
    row = cur.fetchone()
    if not row:
        raise LookupError("Factura no encontrada")
    id_pedido = row['id_pedido']
    monto = row['monto_total']
    try:
        cur.execute("DELETE FROM factura WHERE id_factura = ?", (id_factura,))
        cur.execute("DELETE FROM detalle_pedido WHERE id_pedido = ?", (id_pedido,))
        cur.execute("DELETE FROM pedido WHERE id_pedido = ?", (id_pedido,))
        registrar_auditoria(conn, id_usuario, 'eliminar_factura', 'factura', id_factura,
                            f"Monto C${monto}", ip)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"status": "deleted", "id_factura": id_factura}


def _core_reporte_diario(conn, fecha):
    cur = conn.cursor()
    cur.execute("""SELECT COUNT(*), COALESCE(SUM(monto_total),0), COALESCE(SUM(impuesto),0),
                          COALESCE(SUM(propina),0), COALESCE(SUM(descuento),0)
                   FROM factura WHERE DATE(fecha_hora) = ?""", (fecha,))
    r = cur.fetchone()
    cur.execute("""SELECT metodo_pago, COUNT(*), COALESCE(SUM(monto_total),0)
                   FROM factura WHERE DATE(fecha_hora) = ? GROUP BY metodo_pago""", (fecha,))
    metodos = [{"metodo": m[0], "cantidad": m[1], "monto": float(m[2])} for m in cur.fetchall()]
    cur.execute("""SELECT dp.id_producto, pr.nombre, SUM(dp.cantidad), SUM(dp.subtotal)
                   FROM detalle_pedido dp
                   JOIN pedido p ON dp.id_pedido = p.id_pedido
                   JOIN factura f ON f.id_pedido = p.id_pedido
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE DATE(f.fecha_hora) = ?
                   GROUP BY dp.id_producto, pr.nombre
                   ORDER BY SUM(dp.cantidad) DESC LIMIT 10""", (fecha,))
    top = [{"id_producto": t[0], "nombre": t[1], "cantidad": t[2], "monto": float(t[3])} for t in cur.fetchall()]
    return {
        "fecha": fecha, "total_facturas": r[0],
        "total_ventas": float(r[1]), "total_impuesto": float(r[2]),
        "total_propinas": float(r[3]), "total_descuentos": float(r[4]),
        "por_metodo_pago": metodos, "top_productos": top,
    }


def _core_reporte_mensual(conn, anio, mes):
    pref = f"{int(anio):04d}-{int(mes):02d}"
    cur = conn.cursor()
    cur.execute("""SELECT COUNT(*), COALESCE(SUM(monto_total),0), COALESCE(SUM(impuesto),0)
                   FROM factura WHERE strftime('%Y-%m', fecha_hora) = ?""", (pref,))
    r = cur.fetchone()
    cur.execute("""SELECT DATE(fecha_hora) AS d, COUNT(*), COALESCE(SUM(monto_total),0)
                   FROM factura WHERE strftime('%Y-%m', fecha_hora) = ?
                   GROUP BY d ORDER BY d""", (pref,))
    por_dia = [{"fecha": x[0], "cantidad_facturas": x[1], "total": float(x[2])} for x in cur.fetchall()]
    cur.execute("""SELECT metodo_pago, COUNT(*), COALESCE(SUM(monto_total),0)
                   FROM factura WHERE strftime('%Y-%m', fecha_hora) = ?
                   GROUP BY metodo_pago""", (pref,))
    metodos = [{"metodo": m[0], "cantidad": m[1], "monto": float(m[2])} for m in cur.fetchall()]
    cur.execute("""SELECT dp.id_producto, pr.nombre, SUM(dp.cantidad), SUM(dp.subtotal)
                   FROM detalle_pedido dp
                   JOIN pedido p ON dp.id_pedido = p.id_pedido
                   JOIN factura f ON f.id_pedido = p.id_pedido
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE strftime('%Y-%m', f.fecha_hora) = ?
                   GROUP BY dp.id_producto, pr.nombre
                   ORDER BY SUM(dp.cantidad) DESC LIMIT 10""", (pref,))
    top = [{"id_producto": t[0], "nombre": t[1], "cantidad": t[2], "monto": float(t[3])} for t in cur.fetchall()]
    cur.execute("""SELECT c.nombre, SUM(dp.cantidad), SUM(dp.subtotal)
                   FROM detalle_pedido dp
                   JOIN pedido p ON dp.id_pedido = p.id_pedido
                   JOIN factura f ON f.id_pedido = p.id_pedido
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   JOIN categoria c ON pr.id_categoria = c.id_categoria
                   WHERE strftime('%Y-%m', f.fecha_hora) = ?
                   GROUP BY c.nombre ORDER BY SUM(dp.subtotal) DESC""", (pref,))
    cats = [{"categoria": x[0], "cantidad": x[1], "monto": float(x[2])} for x in cur.fetchall()]
    return {
        "anio": int(anio), "mes": int(mes),
        "total_facturas": r[0], "total_ventas": float(r[1]), "total_impuesto": float(r[2]),
        "por_dia": por_dia, "por_metodo_pago": metodos,
        "top_productos": top, "ventas_por_categoria": cats,
    }


def _validar_reserva(conn, data):
    nombre = (data.get('nombre_cliente') or '').strip()
    tel = (data.get('telefono') or '').strip()
    fecha = data.get('fecha_reserva') or ''
    hora = data.get('hora_reserva') or ''
    personas = int(data.get('num_personas') or 0)
    
    if len(nombre) < 3:   return "Nombre del cliente inválido"
    if len(tel) < 8:      return "Teléfono inválido"
    if not fecha:         return "Falta fecha"
    if fecha < date.today().isoformat():
        return "La fecha debe ser hoy o en adelante"
    if not (len(hora) == 5 and hora[2] == ':'):
        return "Hora inválida (HH:MM)"
    if not ('12:00' <= hora <= '22:00'):
        return "Hora fuera de rango (12:00-22:00)"
    if personas < 1 or personas > 30:
        return "Personas entre 1 y 30"
        
    id_mesa = data.get('id_mesa')
    if id_mesa:
        cur = conn.cursor()
        cur.execute("SELECT capacidad FROM mesa WHERE id_mesa = ?", (id_mesa,))
        m = cur.fetchone()
        if not m:
            return "Mesa no encontrada"
        if m['capacidad'] < personas:
            return "La mesa no tiene capacidad suficiente"
            
        cur.execute("""
            SELECT id_reserva FROM reserva 
            WHERE id_mesa = ? AND fecha_reserva = ? AND hora_reserva = ? 
            AND estado IN ('pendiente', 'confirmada')
        """, (id_mesa, fecha, hora))
        if cur.fetchone():
            return "La mesa ya está reservada para esa fecha y hora. Por favor, elija otra mesa o cambie la hora."

    return None


# ============================================================================
# BACKEND FLASK
# ============================================================================
try:
    from flask import Flask, jsonify, request, send_from_directory, g, redirect
    from flask_cors import CORS

    app = Flask(__name__, static_folder=BASE_DIR)
    CORS(app, supports_credentials=True,
         origins=['http://localhost:5000', 'http://127.0.0.1:5000'])

    @app.before_request
    def _ensure_db():
        if 'db' not in g:
            g.db = get_db()

    @app.teardown_appcontext
    def _close_db(exc):
        db = g.pop('db', None)
        if db is not None:
            db.close()

    @app.after_request
    def _security_headers(resp):
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
        resp.headers['Referrer-Policy'] = 'same-origin'
        if request.path.startswith('/api/auth/'):
            resp.headers['Cache-Control'] = 'no-store'
        return resp

    PUBLIC_PATHS = {'/login.html', '/login.js', '/login.css', '/MenuFilete.html',
                    '/menu.css', '/favicon.ico', '/api/auth/login', '/api/auth/register'}
    # Estas rutas son públicas SOLO para GET (menú público), pero requieren auth para POST/PUT/DELETE
    PUBLIC_GET_ONLY = {'/api/productos', '/api/categorias'}

    def _check_csrf():
        cookie = request.cookies.get('csrf_token', '')
        header = request.headers.get('X-CSRF-Token', '')
        return bool(cookie and header and hmac.compare_digest(cookie, header))

    @app.before_request
    def _check_auth():
        path = request.path
        if path in PUBLIC_PATHS or path.startswith('/Imagenes/'):
            return
        if path in PUBLIC_GET_ONLY and request.method == 'GET':
            return
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if not _check_csrf():
                return jsonify({"error": "Token CSRF inválido o ausente"}), 403
        token = request.cookies.get('sesion_token')
        if not token:
            if path.startswith('/api/'):
                return jsonify({"error": "No autenticado"}), 401
            return redirect('/login.html')
        user = validar_sesion(g.db, token)
        if not user:
            if path.startswith('/api/'):
                return jsonify({"error": "Sesión inválida o expirada"}), 401
            return redirect('/login.html')
        g.usuario = user

    @app.route('/')
    def index():
        token = request.cookies.get('sesion_token')
        if token and validar_sesion(g.db, token):
            return redirect('/unificador.html')
        return redirect('/MenuFilete.html')

    @app.route('/<path:path>')
    def static_files(path):
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            return send_from_directory(BASE_DIR, path)
        
        if path.endswith(('.js', '.css', '.jpg', '.png', '.webp')) or path.startswith('Imagenes/'):
            return "Archivo no encontrado", 404
            
        return redirect('/login.html')

    @app.route('/api/auth/login', methods=['POST'])
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

    @app.route('/api/auth/register', methods=['POST'])
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

    @app.route('/api/auth/logout', methods=['POST'])
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

    @app.route('/api/auth/me', methods=['GET'])
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

    @app.route('/api/usuarios', methods=['GET'])
    def api_usuarios_list():
        if g.usuario['rol'] != 'admin':
            return jsonify({"error": "Acceso denegado"}), 403
        cur = g.db.cursor()
        cur.execute("SELECT id_usuario, username, nombre_completo, rol, activo, fecha_creacion "
                    "FROM usuario ORDER BY id_usuario")
        return jsonify([dict(r) for r in cur.fetchall()]), 200

    @app.route('/api/usuarios', methods=['POST'])
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

    @app.route('/api/usuarios/<int:uid>', methods=['DELETE'])
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

    @app.route('/api/facturas', methods=['GET'])
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

    @app.route('/api/facturas/<int:id_factura>', methods=['GET'])
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

    @app.route('/api/facturas/<int:id_factura>', methods=['DELETE'])
    def api_factura_delete(id_factura):
        if g.usuario['rol'] != 'admin':
            return jsonify({"error": "Acceso denegado"}), 403
        if request.headers.get('X-Confirm-Delete', '').lower() != 'yes':
            return jsonify({"error": "Falta header X-Confirm-Delete: yes"}), 400
        try:
            return jsonify(_core_eliminar_factura(g.db, id_factura,
                                                  g.usuario['id_usuario'],
                                                  request.remote_addr)), 200
        except LookupError:
            return jsonify({"error": "Factura no encontrada"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/ventas', methods=['POST'])
    @app.route('/api/pedidos', methods=['POST'])
    def api_crear_venta():
        data = request.get_json(silent=True) or {}
        try:
            return jsonify(_core_crear_venta(g.db, data, g.usuario['id_usuario'],
                                             g.usuario['nombre_completo'])), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route('/api/reservas', methods=['GET'])
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

    @app.route('/api/reservas', methods=['POST'])
    def api_reservas_create():
        data = request.get_json(silent=True) or {}
        err = _validar_reserva(g.db, data)
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

    @app.route('/api/reservas/<int:rid>', methods=['PUT'])
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

    @app.route('/api/reservas/<int:rid>', methods=['DELETE'])
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

    @app.route('/api/reservas/disponibilidad', methods=['GET'])
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

    @app.route('/api/categorias', methods=['GET'])
    def api_categorias():
        cur = g.db.cursor()
        cur.execute("SELECT id_categoria, nombre FROM categoria ORDER BY id_categoria")
        return jsonify([dict(r) for r in cur.fetchall()]), 200

    @app.route('/api/productos', methods=['GET'])
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

    @app.route('/api/mesas', methods=['GET'])
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

    # ========================================================================
    # ÓRDENES ABIERTAS (MESEROS)
    # ========================================================================
    @app.route('/api/pedidos/abrir', methods=['POST'])
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
            orden_existente = _orden_abierta_de_mesa(cur, id_mesa)
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

    @app.route('/api/pedidos/abiertos', methods=['GET'])
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

    @app.route('/api/pedidos/<int:id_pedido>', methods=['GET'])
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

    @app.route('/api/pedidos/<int:id_pedido>/cobrar', methods=['POST'])
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
        impuesto = round(subtotal * IVA, 2)
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

    @app.route('/api/pedidos/<int:id_pedido>/anular', methods=['POST'])
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

    @app.route('/api/pedidos/<int:id_pedido>/actualizar', methods=['POST'])
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

    # ========================================================================
    # CRUD PRODUCTOS (ADMIN)
    # ========================================================================
    @app.route('/api/productos', methods=['POST'])
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

    @app.route('/api/productos/<int:pid>', methods=['PUT'])
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

    @app.route('/api/productos/<int:pid>', methods=['DELETE'])
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

    # ========================================================================
    # REPORTES
    # ========================================================================
    @app.route('/api/reportes/diario', methods=['GET'])
    def api_reporte_diario():
        if g.usuario['rol'] not in ('admin', 'cajero'):
            return jsonify({"error": "Acceso denegado"}), 403
        fecha = request.args.get('fecha', date.today().isoformat())
        reporte = _core_reporte_diario(g.db, fecha)
        reporte['backup_guardado'] = f"reporte_diario_{fecha}.json"
        # Guardar backup
        try:
            backup_dir = os.path.join(BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
                json.dump(reporte, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return jsonify(reporte), 200

    @app.route('/api/reportes/semanal', methods=['GET'])
    def api_reporte_semanal():
        if g.usuario['rol'] != 'admin':
            return jsonify({"error": "Acceso denegado"}), 403
        fecha_inicio = request.args.get('fecha_inicio', date.today().isoformat())
        # Generar reporte de 7 días
        from datetime import timedelta
        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        dias = []
        total_ventas = 0
        total_facturas = 0
        total_impuesto = 0
        for i in range(7):
            d = (inicio + timedelta(days=i)).isoformat()
            rep = _core_reporte_diario(g.db, d)
            dias.append({"fecha": d, "cantidad_facturas": rep['total_facturas'], "total": rep['total_ventas']})
            total_ventas += rep['total_ventas']
            total_facturas += rep['total_facturas']
            total_impuesto += rep['total_impuesto']
        reporte = {
            "fecha_inicio": fecha_inicio,
            "total_ventas": total_ventas, "total_facturas": total_facturas,
            "total_impuesto": total_impuesto, "por_dia": dias,
            "backup_guardado": f"reporte_semanal_{fecha_inicio}.json"
        }
        try:
            backup_dir = os.path.join(BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
                json.dump(reporte, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return jsonify(reporte), 200

    @app.route('/api/reportes/mensual', methods=['GET'])
    def api_reporte_mensual():
        if g.usuario['rol'] != 'admin':
            return jsonify({"error": "Acceso denegado"}), 403
        mes = request.args.get('mes', date.today().month)
        anio = request.args.get('anio', date.today().year)
        reporte = _core_reporte_mensual(g.db, anio, mes)
        reporte['backup_guardado'] = f"reporte_mensual_{anio}-{int(mes):02d}.json"
        try:
            backup_dir = os.path.join(BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
                json.dump(reporte, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return jsonify(reporte), 200

    def run_server(port=5000):
        _migrar_mesero_ids()
        print("=" * 65)
        print("   RESTAURANTE 'EL FILETE' - SERVIDOR BACKEND (FLASK + AUTH)")
        print("=" * 65)
        print(f" -> Base de datos : {DB_NAME}")
        print(f" -> http://localhost:{port}")
        print("=" * 65)
        app.run(host='0.0.0.0', port=port, debug=True)


except ImportError:
    print("Error: Flask no está instalado. Ejecuta: pip install flask flask-cors")

if __name__ == '__main__':
    run_server()