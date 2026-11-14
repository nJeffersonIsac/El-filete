let reservasCache = [];
let idReservaACancelar = null;

function formatearFecha(fechaStr) {
    if (!fechaStr) {
        return '';
    }
    const [year, month, day] = fechaStr.split('-');
    return `${day}/${month}/${year}`;
}

async function cargarReservas() {
    const tbody = document.getElementById('reservas-tbody');
    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">Cargando...</td></tr>';
    
    try {
        const fecha = document.getElementById('filtro-fecha').value;
        const estado = document.getElementById('filtro-estado').value;
        const qs = new URLSearchParams({ 
            ...(fecha && { fecha }), 
            ...(estado && { estado }) 
        }).toString();
        
        const res = await window.fetchAuth(`/api/reservas${qs ? '?' + qs : ''}`);
        reservasCache = await res.json();
        
        if (!reservasCache.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;">No hay reservas registradas.</td></tr>';
            return;
        }
        
        tbody.innerHTML = reservasCache.map(r => {
            const btns = [];
            
            if (r.estado === 'pendiente') {
                btns.push(`<button class="action-btn" onclick="cambiarEstado(${r.id_reserva}, 'confirmada')" title="Confirmar"><i class="fa-solid fa-check"></i></button>`);
            }
            
            if (r.estado === 'confirmada') {
                btns.push(`<button class="action-btn" onclick="cambiarEstado(${r.id_reserva}, 'completada')" title="Completar"><i class="fa-solid fa-flag-checkered"></i></button>`);
            }
            
            if (r.estado === 'pendiente' || r.estado === 'confirmada') {
                btns.push(`<button class="action-btn delete" onclick="cambiarEstado(${r.id_reserva}, 'cancelada')" title="Cancelar"><i class="fa-solid fa-ban"></i></button>`);
            }
            
            btns.push(`<button class="action-btn" onclick="verTiquete(${r.id_reserva})" title="Ver Tiquete"><i class="fa-solid fa-print"></i></button>`);
            
            if (window.esAdmin() || r.estado === 'cancelada') {
                btns.push(`<button class="action-btn delete" onclick="eliminarReserva(${r.id_reserva})" title="Eliminar permanentemente"><i class="fa-solid fa-trash"></i></button>`);
            }
            
            return `
                <tr>
                    <td>${formatearFecha(r.fecha_reserva)}</td>
                    <td>${r.hora_reserva}</td>
                    <td>${r.nombre_cliente}</td>
                    <td>${r.num_personas}</td>
                    <td>${r.numero_mesa ? 'Mesa #' + r.numero_mesa : '—'}</td>
                    <td><span class="badge badge-${r.estado}">${r.estado}</span></td>
                    <td>${btns.join('')}</td>
                </tr>
            `;
        }).join('');
        
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="7">Error al cargar reservas</td></tr>';
    }
}

async function actualizarMesasDisponibles() {
    const fecha = document.getElementById('res-fecha').value;
    const hora = document.getElementById('res-hora').value;
    const personas = document.getElementById('res-personas').value || 1;
    const sel = document.getElementById('res-mesa');
    
    if (!fecha || !hora) {
        return;
    }
    
    sel.innerHTML = '<option value="">Cargando mesas...</option>';
    
    try {
        const res = await window.fetchAuth(`/api/reservas/disponibilidad?fecha=${fecha}&hora=${hora}&personas=${personas}`);
        const mesas = await res.json();
        
        if (mesas.length === 0) {
            sel.innerHTML = '<option value="">No hay mesas disponibles</option>';
        } else {
            sel.innerHTML = '<option value="">Sin asignar</option>' + mesas.map(m => `
                <option value="${m.id_mesa}">Mesa #${m.numero_mesa} (Cap. ${m.capacidad})</option>
            `).join('');
        }
    } catch (error) {
        sel.innerHTML = '<option value="">Error al cargar mesas</option>';
    }
}

function verTiquete(id) {
    const r = reservasCache.find(x => x.id_reserva === id);
    if (!r) {
        return;
    }

    document.getElementById('tq-numero').textContent = String(r.id_reserva).padStart(4, '0');
    document.getElementById('tq-cliente').textContent = r.nombre_cliente;
    document.getElementById('tq-telefono').textContent = r.telefono;
    document.getElementById('tq-fecha').textContent = formatearFecha(r.fecha_reserva);
    document.getElementById('tq-hora').textContent = r.hora_reserva;
    document.getElementById('tq-personas').textContent = r.num_personas;
    document.getElementById('tq-mesa').textContent = r.numero_mesa ? `Mesa #${r.numero_mesa}` : 'Sin asignar';
    document.getElementById('tq-estado').textContent = r.estado.toUpperCase();

    document.getElementById('tiquete-modal').classList.add('active');
}

function cerrarTiquete() {
    document.getElementById('tiquete-modal').classList.remove('active');
}

function imprimirTiquete() {
    const elem = document.getElementById('tiquete-modal');
    if (!elem) {
        return;
    }
    
    const iframe = document.createElement('iframe');
    iframe.style.position = 'fixed';
    iframe.style.width = '0';
    iframe.style.height = '0';
    iframe.style.border = 'none';
    document.body.appendChild(iframe);
    
    const doc = iframe.contentWindow.document;
    doc.open();
    doc.write(`
        <html>
            <head>
                <title>Comprobante de Reserva</title>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
                <style>
                    body { font-family: 'Inter', sans-serif; padding: 20px; color: #000; background: #fff; }
                    .modal-actions, .close-modal { display: none !important; }
                    .invoice-header { text-align: center; margin-bottom: 2rem; }
                    .invoice-header h2 { font-size: 1.5rem; margin-bottom: 5px; }
                    .invoice-header img { width: 80px; height: 80px; object-fit: contain; margin-bottom: 10px; }
                    .tiquete-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px dashed #ccc; font-size: 0.95rem; }
                    .tiquete-row:last-child { border-bottom: none; }
                    .highlight { font-weight: bold; font-family: monospace; font-size: 1.1rem; }
                </style>
            </head>
            <body>
                ${elem.querySelector('.modal-content').innerHTML}
            </body>
        </html>
    `);
    doc.close();
    
    setTimeout(() => {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
        setTimeout(() => document.body.removeChild(iframe), 1000);
    }, 500);
}

async function abrirModalReserva() {
    document.getElementById('reserva-form').reset();
    
    const hoy = new Date().toISOString().split('T')[0];
    document.getElementById('res-fecha').value = hoy;
    document.getElementById('res-fecha').min = hoy;
    document.getElementById('reserva-error').style.display = 'none';
    
    actualizarMesasDisponibles();
    document.getElementById('reserva-modal').classList.add('active');
}

function cerrarModalReserva() {
    document.getElementById('reserva-modal').classList.remove('active');
}

window.cambiarEstado = (id, estado) => {
    if (estado === 'cancelada') {
        idReservaACancelar = id;
        document.getElementById('modal-confirmar-cancelacion').classList.add('active');
        return;
    }
    ejecutarCambioEstado(id, estado);
};

async function ejecutarCambioEstado(id, estado) {
    try {
        const res = await window.fetchAuth('/api/reservas/' + id, {
            method: 'PUT',
            body: JSON.stringify({ estado })
        });
        
        if (res.ok) {
            cargarReservas();
        } else {
            const data = await res.json();
            showToast(data.error || 'Error al cambiar el estado.', 'error');
        }
    } catch (error) {
        showToast('Error de conexión.', 'error');
    }
}

window.eliminarReserva = async (id) => {
    if (!confirm('¿Eliminar esta reserva permanentemente?')) {
        return;
    }
    
    try {
        const res = await window.fetchAuth('/api/reservas/' + id, { method: 'DELETE' });
        if (res.ok) {
            cargarReservas();
        } else {
            showToast('Error al eliminar', 'error');
        }
    } catch (e) {
        showToast('Error de conexión', 'error');
    }
};

function cerrarModalCancelacion() {
    document.getElementById('modal-confirmar-cancelacion').classList.remove('active');
    idReservaACancelar = null;
}

async function confirmarCancelacion() {
    if (!idReservaACancelar) {
        return;
    }
    
    const idParaCancelar = idReservaACancelar;
    cerrarModalCancelacion();
    await ejecutarCambioEstado(idParaCancelar, 'cancelada');
}

document.getElementById('reserva-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const btnSubmit = e.target.querySelector('button[type="submit"]');
    const errBox = document.getElementById('reserva-error');
    
    btnSubmit.disabled = true;
    btnSubmit.textContent = 'Guardando...';
    errBox.style.display = 'none';

    const payload = {
        nombre_cliente: document.getElementById('res-nombre').value,
        telefono: document.getElementById('res-telefono').value,
        fecha_reserva: document.getElementById('res-fecha').value,
        hora_reserva: document.getElementById('res-hora').value,
        num_personas: parseInt(document.getElementById('res-personas').value),
        id_mesa: document.getElementById('res-mesa').value ? parseInt(document.getElementById('res-mesa').value) : null,
        notas: document.getElementById('res-notas').value
    };
    
    try {
        const res = await window.fetchAuth('/api/reservas', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        
        const data = await res.json();
        
        if (res.ok) {
            cerrarModalReserva();
            cargarReservas();
            showToast('Reserva creada exitosamente', 'success');
        } else {
            errBox.textContent = data.error;
            errBox.style.display = 'block';
        }
    } catch (e) {
        errBox.textContent = 'Error de conexión';
        errBox.style.display = 'block';
    } finally {
        btnSubmit.disabled = false;
        btnSubmit.textContent = 'Guardar';
    }
});

document.addEventListener('DOMContentLoaded', async () => {
    await window.cargarUsuarioActual();
    
    if (window.esAdmin()) {
        const btn = document.getElementById('btn-nueva-reserva');
        if (btn) {
            btn.style.display = 'none';
        }
    }
    
    cargarReservas();
});