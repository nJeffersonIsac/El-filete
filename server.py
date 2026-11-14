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


def _core_anular_factura(conn, id_factura, id_usuario, ip):
    """Anulación lógica de factura: marca factura como 'Anulada' y pedido como 'Anulado'.
    No elimina registros, preservando el historial para auditoría."""
    cur = conn.cursor()
    cur.execute("SELECT id_pedido, monto_total, estado FROM factura WHERE id_factura = ?", (id_factura,))
    row = cur.fetchone()
    if not row:
        raise LookupError("Factura no encontrada")
    # Verificar que la factura no esté ya anulada
    if row['estado'] == 'Anulada':
        raise ValueError("La factura ya se encuentra anulada")
    id_pedido = row['id_pedido']
    monto = row['monto_total']
    try:
        # Anulación lógica: actualizar estados en lugar de eliminar registros
        cur.execute("UPDATE factura SET estado = 'Anulada' WHERE id_factura = ?", (id_factura,))
        cur.execute("UPDATE pedido SET estado = 'Anulado' WHERE id_pedido = ?", (id_pedido,))
        registrar_auditoria(conn, id_usuario, 'anular_factura', 'factura', id_factura,
                            f"Monto C${monto} - Anulación lógica", ip)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"status": "anulada", "id_factura": id_factura}


def _core_reporte_diario(conn, fecha):
    cur = conn.cursor()
    # Excluir facturas anuladas de los cálculos de ventas
    cur.execute("""SELECT COUNT(*), COALESCE(SUM(monto_total),0), COALESCE(SUM(impuesto),0),
                          COALESCE(SUM(propina),0), COALESCE(SUM(descuento),0)
                   FROM factura WHERE DATE(fecha_hora) = ?
                   AND COALESCE(estado, 'Emitida') != 'Anulada'""", (fecha,))
    r = cur.fetchone()
    cur.execute("""SELECT metodo_pago, COUNT(*), COALESCE(SUM(monto_total),0)
                   FROM factura WHERE DATE(fecha_hora) = ?
                   AND COALESCE(estado, 'Emitida') != 'Anulada'
                   GROUP BY metodo_pago""", (fecha,))
    metodos = [{"metodo": m[0], "cantidad": m[1], "monto": float(m[2])} for m in cur.fetchall()]
    cur.execute("""SELECT dp.id_producto, pr.nombre, SUM(dp.cantidad), SUM(dp.subtotal)
                   FROM detalle_pedido dp
                   JOIN pedido p ON dp.id_pedido = p.id_pedido
                   JOIN factura f ON f.id_pedido = p.id_pedido
                   JOIN producto pr ON dp.id_producto = pr.id_producto
                   WHERE DATE(f.fecha_hora) = ?
                   AND COALESCE(f.estado, 'Emitida') != 'Anulada'
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
    # Excluir facturas anuladas de los cálculos de ventas
    cur.execute("""SELECT COUNT(*), COALESCE(SUM(monto_total),0), COALESCE(SUM(impuesto),0)
                   FROM factura WHERE strftime('%Y-%m', fecha_hora) = ?
                   AND COALESCE(estado, 'Emitida') != 'Anulada'""", (pref,))
    r = cur.fetchone()
    cur.execute("""SELECT DATE(fecha_hora) AS d, COUNT(*), COALESCE(SUM(monto_total),0)
                   FROM factura WHERE strftime('%Y-%m', fecha_hora) = ?
                   AND COALESCE(estado, 'Emitida') != 'Anulada'
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

    # ========================================================================
    # REGISTRO DE BLUEPRINTS
    # ========================================================================
    from routes.auth_routes import auth_bp
    from routes.usuarios_routes import usuarios_bp
    from routes.productos_routes import productos_bp
    from routes.mesas_routes import mesas_bp
    from routes.pedidos_routes import pedidos_bp
    from routes.facturas_routes import facturas_bp
    from routes.reservas_routes import reservas_bp
    from routes.reportes_routes import reportes_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(mesas_bp)
    app.register_blueprint(pedidos_bp)
    app.register_blueprint(facturas_bp)
    app.register_blueprint(reservas_bp)
    app.register_blueprint(reportes_bp)

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
