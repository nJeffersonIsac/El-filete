"""
Rutas de reportes: diario, semanal, mensual.
"""
import os
import json
from datetime import date, datetime
from flask import Blueprint, jsonify, request, g

import server as _srv

reportes_bp = Blueprint('reportes', __name__)


# ========================================================================
# REPORTES
# ========================================================================
@reportes_bp.route('/api/reportes/diario', methods=['GET'])
def api_reporte_diario():
    if g.usuario['rol'] not in ('admin', 'cajero'):
        return jsonify({"error": "Acceso denegado"}), 403
    fecha = request.args.get('fecha', date.today().isoformat())
    reporte = _srv._core_reporte_diario(g.db, fecha)
    reporte['backup_guardado'] = f"reporte_diario_{fecha}.json"
    # Guardar backup
    try:
        backup_dir = os.path.join(_srv.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
            json.dump(reporte, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return jsonify(reporte), 200


@reportes_bp.route('/api/reportes/semanal', methods=['GET'])
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
        rep = _srv._core_reporte_diario(g.db, d)
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
        backup_dir = os.path.join(_srv.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
            json.dump(reporte, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return jsonify(reporte), 200


@reportes_bp.route('/api/reportes/mensual', methods=['GET'])
def api_reporte_mensual():
    if g.usuario['rol'] != 'admin':
        return jsonify({"error": "Acceso denegado"}), 403
    mes = request.args.get('mes', date.today().month)
    anio = request.args.get('anio', date.today().year)
    reporte = _srv._core_reporte_mensual(g.db, anio, mes)
    reporte['backup_guardado'] = f"reporte_mensual_{anio}-{int(mes):02d}.json"
    try:
        backup_dir = os.path.join(_srv.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        with open(os.path.join(backup_dir, reporte['backup_guardado']), 'w', encoding='utf-8') as f:
            json.dump(reporte, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return jsonify(reporte), 200
