/**
 * app.js - El Filete POS System
 */

let catalogo = [];
let categorias = [];
let mesas = [];
let order = [];
let currentCategory = 'Todas';
let searchQuery = '';
let ordenAbertaActual = null;

const TAX_RATE = 0.15;

// Elementos del DOM
const productsGrid = document.getElementById('products-grid');
const categoriesContainer = document.getElementById('categories-container');
const searchInput = document.getElementById('search-input');
const orderItemsContainer = document.getElementById('order-items');
const summarySubtotal = document.getElementById('summary-subtotal');
const summaryTax = document.getElementById('summary-tax');
const summaryTotal = document.getElementById('summary-total');
const btnClearOrder = document.getElementById('btn-clear-order');
const btnProcessOrder = document.getElementById('btn-process-order');
const btnActualizarOrden = document.getElementById('btn-actualizar-orden');
const mesaSelect = document.getElementById('order-mesa-select');
const clienteInput = document.getElementById('order-cliente-input');

const categoryIcons = {
    "Entradas": "fa-cookie-bite", 
    "Bebida": "fa-bottle-water", 
    "Mariscos": "fa-fish",
    "Cortes": "fa-drumstick-bite", 
    "Desayunos": "fa-mug-saucer", 
    "Pollo": "fa-bowl-food",
    "Cocteles": "fa-martini-glass-citrus", 
    "Postres": "fa-ice-cream", 
    "Licores": "fa-wine-glass",
    "Cervezas": "fa-beer-mug-empty", 
    "Sopa": "fa-bowl-hot", 
    "Extras": "fa-plus-circle", 
    "Todas": "fa-border-all"
};

// ===========================================================================
// INICIALIZACIÓN
// ===========================================================================
async function initApp() {
    const user = await window.cargarUsuarioActual();
    if (!user) {
        return;
    }

    document.getElementById('sidebar-nombre-usuario').textContent = user.nombre_completo;
    document.getElementById('sidebar-rol').textContent = user.rol;
    document.getElementById('sidebar-rol').className = `badge badge-${user.rol}`;

    document.querySelectorAll('[data-rol-requerido]').forEach(el => {
        const roles = el.dataset.rolRequerido.split(',');
        el.style.display = roles.includes(user.rol) ? 'flex' : 'none';
    });

    _configurarRol(user.rol);

    const hoy = new Date();
    const fechaInput = document.getElementById('reporte-fecha-diario');
    if (fechaInput) {
        fechaInput.value = hoy.toISOString().split('T')[0];
    }
    
    const semanaInput = document.getElementById('reporte-fecha-semanal');
    if (semanaInput) {
        semanaInput.value = hoy.toISOString().split('T')[0];
    }
    
    const mesInput = document.getElementById('reporte-mes');
    if (mesInput) {
        mesInput.value = hoy.getMonth() + 1;
    }

    if (user.rol === 'cajero') {
        const semanal = document.getElementById('reporte-semanal-card');
        const mensual = document.getElementById('reporte-mensual-card');
        if (semanal) semanal.style.display = 'none';
        if (mensual) mensual.style.display = 'none';
    }

    setupEventListeners();
    await cargarDatosIniciales();
    await cargarFacturas();
}

function _configurarRol(rol) {
    if (rol === 'mesero') {
        const paySection = document.getElementById('payment-methods-section');
        const cashSection = document.getElementById('cash-section');
        if (paySection) paySection.style.display = 'none';
        if (cashSection) cashSection.style.display = 'none';
        if (btnProcessOrder) {
            btnProcessOrder.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Guardar Orden Abierta`;
        }
        if (btnActualizarOrden) {
            btnActualizarOrden.style.display = 'none';
        }
    }
}

// ===========================================================================
// CARGA DE DATOS
// ===========================================================================
async function cargarDatosIniciales() {
    try {
        const [resCat, resProd, resMesas] = await Promise.all([
            window.fetchAuth('/api/categorias'),
            window.fetchAuth('/api/productos'),
            window.fetchAuth('/api/mesas')
        ]);
        
        if (resCat.ok) {
            categorias = await resCat.json();
            renderCategories();
        }
        
        if (resProd.ok) {
            catalogo = await resProd.json();
            renderProducts();
        }
        
        if (resMesas.ok) {
            mesas = await resMesas.json();
            renderMesasSelect();
        }
        
        if (window.usuarioActual && window.usuarioActual.rol !== 'mesero') {
            await cargarListaOrdenesAbiertas();
        }
    } catch (err) {
        window.showToast("Error conectando con el servidor", "error");
    }
}

function renderMesasSelect() {
    if (!mesaSelect) {
        return;
    }
    
    const user = window.usuarioActual || {};
    const esMesero = user.rol === 'mesero';
    const valorPrevio = mesaSelect.value;

    mesaSelect.innerHTML = `<option value="">Para Llevar</option>` + mesas.map(m => {
        let etiqueta = `Mesa #${m.numero_mesa} (Cap: ${m.capacidad})`;
        let deshabilitada = false;
        if (m.orden_abierta_id) {
            const esMia = m.ocupada_por_id === user.id_usuario;
            if (esMesero && esMia) {
                etiqueta += ' - Tu orden abierta';
            } else {
                // Mesa en uso: solo el mesero que la atiende puede enviar ordenes
                etiqueta += ` Ocupada`;
                deshabilitada = true;
            }
        }
        return `<option value="${m.id_mesa}" ${deshabilitada ? 'disabled' : ''}>${etiqueta}</option>`;
    }).join('');

    if (valorPrevio) {
        mesaSelect.value = valorPrevio;
    }
}

async function recargarMesas() {
    try {
        const res = await window.fetchAuth('/api/mesas');
        if (res.ok) {
            mesas = await res.json();
            renderMesasSelect();
        }
    } catch (e) {
        console.error(e);
    }
}

function renderCategories() {
    if (!categoriesContainer) {
        return;
    }
    
    const listaCategorias = ['Todas', ...categorias.map(c => c.nombre)];
    
    categoriesContainer.innerHTML = listaCategorias.map(cat => `
        <div class="category-chip ${cat === currentCategory ? 'active' : ''}" data-cat="${cat}">
            <i class="fa-solid ${categoryIcons[cat] || 'fa-tag'}"></i> ${cat}
        </div>
    `).join('');

    document.querySelectorAll('.category-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            document.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
            e.currentTarget.classList.add('active');
            currentCategory = e.currentTarget.dataset.cat;
            renderProducts();
        });
    });
}

function renderProducts() {
    if (!productsGrid) {
        return;
    }
    
    let filtered = catalogo;
    
    if (currentCategory !== 'Todas') {
        filtered = filtered.filter(p => p.categoria === currentCategory);
    }
    
    if (searchQuery.trim() !== '') {
        const query = searchQuery.toLowerCase().trim();
        filtered = filtered.filter(p =>
            p.nombre.toLowerCase().includes(query) || 
            p.categoria.toLowerCase().includes(query)
        );
    }

    if (filtered.length === 0) {
        productsGrid.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 3rem;">
                No se encontraron productos.
            </div>
        `;
        return;
    }

    productsGrid.innerHTML = filtered.map(p => {
        const cssVarCat = `var(--cat-${p.categoria.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")})`;
        
        const imagenHtml = p.imagen_url
            ? `<img src="${p.imagen_url}" alt="${p.nombre}" class="product-card-img" onerror="this.onerror=null; this.src='Imagenes/Logo.jpg';">`
            : `<i class="fa-solid ${categoryIcons[p.categoria] || 'fa-utensils'}"></i>`;
            
        return `
            <div class="product-card" onclick="addToOrder(${p.id_producto})">
                <span class="product-cat-badge" style="color: ${cssVarCat}; border: 1px solid ${cssVarCat}">${p.categoria}</span>
                <div class="product-img-box">${imagenHtml}</div>
                <div class="product-info">
                    <h3 class="product-name">${p.nombre}</h3>
                    <span class="product-price">C$ ${p.precio.toFixed(2)}</span>
                </div>
            </div>
        `;
    }).join('');
}

// ===========================================================================
// GESTIÓN DE ORDEN
// ===========================================================================
window.addToOrder = function(id) {
    const product = catalogo.find(p => p.id_producto === id);
    if (!product) {
        return;
    }
    
    const existingItem = order.find(item => item.id_producto === id);
    if (existingItem) {
        existingItem.cantidad++;
    } else {
        order.push({ ...product, cantidad: 1 });
    }
    renderOrder();
};

window.updateQty = function(id, delta) {
    const item = order.find(i => i.id_producto === id);
    if (item) {
        item.cantidad += delta;
        if (item.cantidad <= 0) {
            order = order.filter(i => i.id_producto !== id);
        }
        renderOrder();
    }
};

function renderOrder() {
    if (!orderItemsContainer) {
        return;
    }
    
    if (order.length === 0) {
        orderItemsContainer.innerHTML = `<div class="empty-order-msg"><i class="fa-solid fa-cart-arrow-down"></i><p>No hay productos</p></div>`;
        if (btnProcessOrder) {
            btnProcessOrder.disabled = true;
        }
        if (btnActualizarOrden) {
            btnActualizarOrden.disabled = true;
        }
    } else {
        if (btnProcessOrder) {
            btnProcessOrder.disabled = false;
        }
        if (btnActualizarOrden && ordenAbertaActual) {
            btnActualizarOrden.disabled = false;
        }
        
        orderItemsContainer.innerHTML = order.map(item => `
            <div class="order-item">
                <div class="item-top">
                    <span class="item-name">${item.nombre}</span>
                    <button class="item-delete" onclick="updateQty(${item.id_producto}, -999)"><i class="fa-solid fa-xmark"></i></button>
                </div>
                <div class="item-bottom">
                    <div class="qty-controls">
                        <button class="qty-btn" onclick="updateQty(${item.id_producto}, -1)">-</button>
                        <input type="number" class="qty-input" value="${item.cantidad}" readonly>
                        <button class="qty-btn" onclick="updateQty(${item.id_producto}, 1)">+</button>
                    </div>
                    <span class="item-total">C$ ${(item.precio * item.cantidad).toFixed(2)}</span>
                </div>
            </div>
        `).join('');
    }
    updateOrderSummary();
}

function updateOrderSummary() {
    if (!summarySubtotal) {
        return;
    }
    
    const subtotal = order.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
    const tax = subtotal * TAX_RATE;
    const total = subtotal + tax;

    summarySubtotal.textContent = `C$ ${subtotal.toFixed(2)}`;
    summaryTax.textContent = `C$ ${tax.toFixed(2)}`;
    summaryTotal.textContent = `C$ ${total.toFixed(2)}`;
    
    const btnTotalEl = document.getElementById('btn-total');
    if (btnTotalEl) {
        btnTotalEl.textContent = `C$ ${total.toFixed(2)}`;
    }

    const montoInput = document.getElementById('monto-recibido');
    if (montoInput) {
        calcularCambio();
    }
}

function calcularCambio() {
    const totalStr = document.getElementById('summary-total').textContent.replace('C$ ', '');
    const total = parseFloat(totalStr) || 0;
    const recibido = parseFloat(document.getElementById('monto-recibido').value) || 0;
    const cambio = Math.max(0, recibido - total);
    
    document.getElementById('cambio-vuelto').textContent = `C$ ${cambio.toFixed(2)}`;
}

// ===========================================================================
// PROCESAR ORDEN
// ===========================================================================
async function processOrder() {
    if (order.length === 0) {
        return;
    }

    // Si hay una orden abierta cargada desde el selector, se cobra esa orden (no se crea una venta nueva)
    if (_ordenParaCobrarId && window.usuarioActual && window.usuarioActual.rol !== 'mesero') {
        return cobrarOrdenCargada();
    }
    
    btnProcessOrder.disabled = true;
    btnProcessOrder.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Procesando...`;

    const user = window.usuarioActual;
    const esMesero = user.rol === 'mesero';
    const mesaIdVal = mesaSelect ? mesaSelect.value : "";
    const clienteNombreVal = clienteInput && clienteInput.value.trim() ? clienteInput.value.trim() : "Consumidor Final";

    const payload = {
        id_mesa: mesaIdVal ? parseInt(mesaIdVal) : null,
        cliente_nombre: clienteNombreVal,
        mesero_nombre: user.nombre_completo,
        items: order.map(it => ({ 
            id_producto: it.id_producto, 
            cantidad: it.cantidad 
        }))
    };

    let endpoint = '/api/ventas';

    if (esMesero) {
        endpoint = '/api/pedidos/abrir';
    } else {
        const paymentEl = document.querySelector('input[name="payment"]:checked');
        payload.metodo_pago = paymentEl ? paymentEl.value : 'Efectivo';
        
        if (payload.metodo_pago === 'Efectivo') {
            payload.monto_recibido = parseFloat(document.getElementById('monto-recibido').value) || 0;
            const totalVenta = parseFloat(document.getElementById('summary-total').textContent.replace('C$ ', '')) || 0;
            
            if (payload.monto_recibido < totalVenta) {
                window.showToast("El monto recibido es menor al total", "error");
                btnProcessOrder.disabled = false;
                _resetBtnProcess(esMesero, totalVenta);
                return;
            }
        }
    }

    try {
        const response = await window.fetchAuth(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || "Error al procesar");
        }

        if (esMesero) {
            const msg = result.agregado_a_existente
                ? `✅ Productos agregados a tu Orden #${result.id_pedido} de esta mesa.`
                : `✅ Orden #${result.id_pedido} guardada. Mesa puede seguir pidiendo.`;
            window.showToast(msg, 'success');
        } else {
            const mesaOption = mesaSelect ? mesaSelect.options[mesaSelect.selectedIndex] : null;
            const mesaTexto = mesaOption && mesaOption.value ? mesaOption.text : 'Para Llevar';

            mostrarComprobanteModal({
                id_factura: result.id_factura,
                fecha_hora: new Date().toLocaleString('es-NI'),
                cliente_nombre: clienteNombreVal,
                mesa_texto: mesaTexto,
                mesero_nombre: user.nombre_completo,
                subtotal: result.subtotal,
                impuesto: result.impuesto,
                monto_total: result.monto_total,
                metodo_pago: result.metodo_pago,
                monto_recibido: payload.monto_recibido || 0,
                cambio_devuelto: result.cambio_devuelto,
                items: [...order]
            }, true);
        }

        order = [];
        renderOrder();
        if (clienteInput) clienteInput.value = '';
        if (mesaSelect) mesaSelect.value = '';
        
        const montoEl = document.getElementById('monto-recibido');
        if (montoEl) {
            montoEl.value = '';
        }

    } catch (error) {
        window.showToast(error.message || "Error de conexión", 'error');
    } finally {
        recargarMesas();
        const totalFinal = parseFloat(document.getElementById('summary-total').textContent.replace('C$ ', '')) || 0;
        _resetBtnProcess(esMesero, totalFinal);
        btnProcessOrder.disabled = order.length === 0;
        updateOrderSummary();
    }
}

function _resetBtnProcess(esMesero, total = 0) {
    if (esMesero) {
        btnProcessOrder.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Guardar Orden Abierta`;
    } else {
        btnProcessOrder.innerHTML = `Cobrar <span id="btn-total">C$ ${total.toFixed(2)}</span>`;
    }
}

// ===========================================================================
// ACTUALIZAR ORDEN ABIERTA
// ===========================================================================
window.limpiarOrdenCargada = function() {
    ordenAbertaActual = null;
    document.getElementById('orden-abierta-info').style.display = 'none';
    if (btnActualizarOrden) {
        btnActualizarOrden.style.display = 'none';
    }
    document.getElementById('orden-titulo').textContent = 'Orden Actual';
};

async function actualizarOrdenAbierta() {
    if (!ordenAbertaActual || order.length === 0) {
        return;
    }
    
    btnActualizarOrden.disabled = true;
    btnActualizarOrden.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Guardando...`;

    const payload = {
        items: order.map(it => ({ 
            id_producto: it.id_producto, 
            cantidad: it.cantidad 
        }))
    };

    try {
        const res = await window.fetchAuth(`/api/pedidos/${ordenAbertaActual.id_pedido}/actualizar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await res.json();
        
        if (!res.ok) {
            throw new Error(result.error || 'Error al actualizar');
        }

        window.showToast(`✅ Orden #${ordenAbertaActual.id_pedido} actualizada. Nuevo total: C$ ${result.nuevo_total.toFixed(2)}`, 'success');
        order = [];
        renderOrder();
    } catch (e) {
        window.showToast(e.message, 'error');
    } finally {
        btnActualizarOrden.disabled = false;
        btnActualizarOrden.innerHTML = `<i class="fa-solid fa-plus"></i> Agregar a Orden #<span id="btn-orden-id">${ordenAbertaActual ? ordenAbertaActual.id_pedido : '-'}</span>`;
    }
}

// ===========================================================================
// COMPROBANTE MODAL
// ===========================================================================
function mostrarComprobanteModal(datos, esNuevaVenta = false) {
    const modal = document.getElementById('invoice-modal');
    if (!modal) {
        return;
    }

    let fechaStr = '', horaStr = '';
    if (datos.fecha_hora) {
        const partes = datos.fecha_hora.split(' ');
        fechaStr = partes[0] || '';
        horaStr = partes[1] || '';
    }
    
    document.getElementById('inv-date').textContent = fechaStr;
    document.getElementById('inv-time').textContent = horaStr;
    document.getElementById('inv-number').textContent = String(datos.id_factura).padStart(6, '0');
    document.getElementById('inv-cliente').textContent = datos.cliente_nombre || 'Consumidor Final';
    document.getElementById('inv-mesa').textContent = datos.mesa_texto || (datos.numero_mesa ? `Mesa #${datos.numero_mesa}` : 'Para Llevar');
    document.getElementById('inv-mesero').textContent = datos.mesero_nombre || '-';

    document.getElementById('inv-items').innerHTML = (datos.items || []).map(item => `
        <tr>
            <td>${item.cantidad}</td>
            <td>${item.nombre}</td>
            <td>C$ ${parseFloat(item.precio_unitario || item.precio || 0).toFixed(2)}</td>
            <td>C$ ${(parseFloat(item.precio_unitario || item.precio || 0) * item.cantidad).toFixed(2)}</td>
        </tr>
    `).join('');

    document.getElementById('inv-subtotal').textContent = `C$ ${parseFloat(datos.subtotal || 0).toFixed(2)}`;
    document.getElementById('inv-tax').textContent = `C$ ${parseFloat(datos.impuesto || 0).toFixed(2)}`;
    document.getElementById('inv-total').textContent = `C$ ${parseFloat(datos.monto_total || 0).toFixed(2)}`;

    const cashRow = document.getElementById('inv-cash-row');
    const changeRow = document.getElementById('inv-change-row');
    
    if (datos.metodo_pago === 'Efectivo' && datos.monto_recibido > 0) {
        cashRow.style.display = 'flex';
        changeRow.style.display = 'flex';
        document.getElementById('inv-recibido').textContent = `C$ ${parseFloat(datos.monto_recibido).toFixed(2)}`;
        document.getElementById('inv-cambio').textContent = `C$ ${parseFloat(datos.cambio_devuelto).toFixed(2)}`;
    } else {
        cashRow.style.display = 'none';
        changeRow.style.display = 'none';
    }

    const btnDone = document.getElementById('btn-done');
    if (btnDone) {
        btnDone.style.display = esNuevaVenta ? 'flex' : 'none';
    }
    
    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('invoice-modal').classList.remove('active');
}

function finishOrder() {
    closeModal();
    cargarFacturas();
}

// ===========================================================================
// HISTORIAL DE FACTURAS
// ===========================================================================
async function cargarFacturas() {
    const tbody = document.getElementById('facturas-table-body');
    if (!tbody) {
        return;
    }
    
    try {
        const response = await window.fetchAuth('/api/facturas');
        const facturas = await response.json();
        
        if (!response.ok) {
            throw new Error(facturas.error || 'Error');
        }
        
        if (facturas.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted);">No hay facturas registradas.</td></tr>';
            return;
        }

        tbody.innerHTML = facturas.map(f => `
            <tr>
                <td><strong>#${String(f.id_factura).padStart(6, '0')}</strong></td>
                <td style="font-size:0.8rem;">${f.fecha_hora || '-'}</td>
                <td>${f.numero_mesa ? `Mesa #${f.numero_mesa}` : (f.tipo_pedido || '-')}</td>
                <td>${f.cliente_nombre || '-'}</td>
                <td>${f.mesero_nombre || '-'}</td>
                <td><span style="background:rgba(59,130,246,0.1); color:var(--primary); padding:2px 8px; border-radius:6px; font-size:0.8rem;">${f.metodo_pago}</span></td>
                <td><strong>C$ ${parseFloat(f.monto_total).toFixed(2)}</strong></td>
                <td>
                    <button class="action-btn" onclick="verFactura(${f.id_factura})" title="Ver/Imprimir"><i class="fa-solid fa-print"></i></button>
                    ${window.esAdmin() || window.esCajero() ? `<button class="action-btn delete" onclick="eliminarFactura(${f.id_factura})" title="Eliminar"><i class="fa-solid fa-trash-can"></i></button>` : ''}
                    ${window.esAdmin() || window.esCajero() ? `<button class="action-btn" onclick="anularPorFactura(${f.id_pedido})" title="Anular" style="color:var(--danger);"><i class="fa-solid fa-ban"></i></button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="8" style="color:var(--danger);">Error al cargar facturas.</td></tr>';
    }
}

window.verFactura = async function(id_factura) {
    try {
        const response = await window.fetchAuth('/api/facturas/' + id_factura);
        const factura = await response.json();
        if (!response.ok) {
            throw new Error(factura.error || 'Error');
        }
        factura.mesa_texto = factura.numero_mesa ? `Mesa #${factura.numero_mesa}` : (factura.tipo_pedido || 'Para Llevar');
        mostrarComprobanteModal(factura, false);
    } catch (error) {
        window.showToast("Error al abrir la factura: " + error.message, "error");
    }
};

window.eliminarFactura = async function(id_factura) {
    if (!confirm('¿Eliminar factura permanentemente? Esta acción no se puede deshacer.')) {
        return;
    }
    
    try {
        const res = await window.fetchAuth('/api/facturas/' + id_factura, {
            method: 'DELETE',
            headers: { 'X-Confirm-Delete': 'yes' }
        });
        
        if (res.ok) {
            window.showToast('Factura eliminada', 'success');
            cargarFacturas();
        } else {
            const data = await res.json();
            window.showToast(data.error || 'Error al eliminar', 'error');
        }
    } catch (err) {
        window.showToast('Error de conexión', 'error');
    }
};

window.anularPorFactura = async function(id_pedido) {
    if (!id_pedido) {
        window.showToast('ID de pedido no disponible', 'error');
        return;
    }
    
    if (!confirm(`¿Anular el pedido #${id_pedido}? Se eliminará la factura asociada.`)) {
        return;
    }
    
    try {
        const res = await window.fetchAuth(`/api/pedidos/${id_pedido}/anular`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await res.json();
        
        if (res.ok) {
            window.showToast('Pedido anulado correctamente', 'success');
            cargarFacturas();
        } else {
            window.showToast(data.error || 'Error al anular', 'error');
        }
    } catch (e) {
        window.showToast('Error de conexión', 'error');
    }
};

// ===========================================================================
// ÓRDENES ABIERTAS
// ===========================================================================
async function cargarListaOrdenesAbiertas() {
    recargarMesas();
    const select = document.getElementById('select-ordenes-abiertas');
    if (!select) {
        return;
    }
    
    try {
        const res = await window.fetchAuth('/api/pedidos/abiertos');
        const pedidos = await res.json();
        
        if (pedidos.length === 0) {
            select.innerHTML = '<option value="">No hay órdenes pendientes</option>';
            return;
        }
        
        select.innerHTML = '<option value="">-- Seleccionar mesa/orden --</option>' + pedidos.map(p => `
            <option value="${p.id_pedido}">
                ${p.numero_mesa ? 'Mesa #' + p.numero_mesa : 'Para Llevar'} - ${p.mesero_nombre} (C$ ${p.total.toFixed(2)})
            </option>
        `).join('');
    } catch (e) {
        console.error(e);
    }
}

// Orden abierta cargada en el POS para ser cobrada por el cajero.
// Se usa una variable en lugar de reemplazar btn.onclick, porque el botón ya tiene
// processOrder como listener y ambos se ejecutaban a la vez en un solo clic.
let _ordenParaCobrarId = null;

async function cargarOrdenAbierta(id_pedido) {
    if (!id_pedido) {
        _ordenParaCobrarId = null;
        return;
    }
    
    try {
        const res = await window.fetchAuth(`/api/pedidos/${id_pedido}`);
        const orden = await res.json();
        
        if (!res.ok) {
            throw new Error(orden.error);
        }
        
        order = [];
        orden.items.forEach(item => {
            order.push({
                id_producto: item.id_producto,
                nombre: item.nombre,
                precio: item.precio_unitario,
                cantidad: item.cantidad
            });
        });
        
        if (orden.id_mesa) {
            document.getElementById('order-mesa-select').value = orden.id_mesa;
        }
        
        document.getElementById('order-cliente-input').value = "Cliente de Mesa";
        _ordenParaCobrarId = id_pedido;
        renderOrder();
        window.showToast(`Orden de ${orden.mesero_nombre} cargada.`, 'info');
    } catch (e) {
        _ordenParaCobrarId = null;
        window.showToast("Error al cargar la orden", "error");
    }
}

async function cobrarOrdenCargada() {
    const id_pedido = _ordenParaCobrarId;
    btnProcessOrder.disabled = true;
    btnProcessOrder.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Cobrando...`;
    
    const paymentEl = document.querySelector('input[name="payment"]:checked');
    const montoRecibido = document.getElementById('monto-recibido').value ? parseFloat(document.getElementById('monto-recibido').value) : 0;
    
    try {
        const cobroRes = await window.fetchAuth(`/api/pedidos/${id_pedido}/cobrar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cliente_nombre: document.getElementById('order-cliente-input').value.trim() || "Consumidor Final",
                metodo_pago: paymentEl ? paymentEl.value : 'Efectivo',
                monto_recibido: montoRecibido
            })
        });
        
        const result = await cobroRes.json();
        
        if (!cobroRes.ok || !result.id_factura) {
            throw new Error(result.error || 'No se pudo generar la factura');
        }
        
        window.showToast(`Factura #${String(result.id_factura).padStart(6,'0')} generada`, 'success');
        
        const factura = result.factura;
        factura.mesa_texto = factura.numero_mesa ? `Mesa #${factura.numero_mesa}` : (factura.tipo_pedido || 'Para Llevar');
        mostrarComprobanteModal(factura, true);
        
        _ordenParaCobrarId = null;
        document.getElementById('select-ordenes-abiertas').value = '';
        order = [];
        renderOrder();
        cargarListaOrdenesAbiertas();
        cargarFacturas();
        
    } catch(err) {
        window.showToast(err.message, 'error');
    } finally {
        const totalFinal = parseFloat(document.getElementById('summary-total').textContent.replace('C$ ', '')) || 0;
        _resetBtnProcess(false, totalFinal);
        btnProcessOrder.disabled = order.length === 0;
    }
}

async function cargarOrdenesAbiertas() {
    recargarMesas();
    const tbody = document.getElementById('ordenes-abiertas-tbody');
    if (!tbody) {
        return;
    }
    
    try {
        const res = await window.fetchAuth('/api/pedidos/abiertos');
        const pedidos = await res.json();
        
        if (!res.ok) {
            throw new Error(pedidos.error || 'Error');
        }
        
        if (pedidos.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No hay órdenes abiertas en este momento.</td></tr>';
            return;
        }
        
        tbody.innerHTML = pedidos.map(p => `
            <tr>
                <td><strong>#${p.id_pedido}</strong></td>
                <td>${p.numero_mesa ? `Mesa #${p.numero_mesa}` : (p.tipo_pedido || '-')}</td>
                <td>${p.mesero_nombre || '-'}</td>
                <td style="font-size:0.8rem;">${(p.items || []).map(i => `${i.cantidad}x ${i.nombre}`).join(', ') || '-'}</td>
                <td><strong>C$ ${parseFloat(p.total).toFixed(2)}</strong></td>
                <td style="font-size:0.8rem;">${p.fecha_hora || '-'}</td>
                <td>
                    ${window.esAdmin() || window.esCajero() ? `
                        <button class="action-btn" onclick="abrirCobrarModal(${p.id_pedido}, ${parseFloat(p.total).toFixed(2)})" title="Cobrar" style="color:var(--secondary);">
                            <i class="fa-solid fa-dollar-sign"></i>
                        </button>
                        <button class="action-btn delete" onclick="anularOrden(${p.id_pedido})" title="Anular">
                            <i class="fa-solid fa-ban"></i>
                        </button>
                    ` : ''}
                    ${window.usuarioActual && window.usuarioActual.rol === 'mesero' ? (
                        p.mesero_id === window.usuarioActual.id_usuario ? `
                        <button class="action-btn" onclick="cargarOrdenEnPOS(${p.id_pedido}, ${p.id_mesa || 'null'})" title="Cargar en POS" style="color:var(--primary);">
                            <i class="fa-solid fa-cart-plus"></i> Agregar
                        </button>
                    ` : `<span style="font-size:0.8rem; color:var(--text-muted);"><i class="fa-solid fa-lock"></i> Atendida por otro mesero</span>`
                    ) : ''}
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="color:var(--danger);">${e.message}</td></tr>`;
    }
}

window.cargarOrdenEnPOS = function(id_pedido, id_mesa) {
    ordenAbertaActual = { id_pedido, id_mesa };
    order = [];
    renderOrder();

    const infoEl = document.getElementById('orden-abierta-info');
    const textoEl = document.getElementById('orden-abierta-texto');
    
    if (infoEl && textoEl) {
        textoEl.textContent = `Orden abierta #${id_pedido} cargada. Agrega productos y presiona "Agregar a Orden".`;
        infoEl.style.display = 'block';
    }

    if (btnActualizarOrden) {
        btnActualizarOrden.style.display = 'flex';
        btnActualizarOrden.disabled = true;
        document.getElementById('btn-orden-id').textContent = id_pedido;
    }

    document.getElementById('orden-titulo').textContent = `Agregar a Orden #${id_pedido}`;
    _navegar('pos');
    window.showToast(`Orden #${id_pedido} cargada. Selecciona productos para agregar.`, 'info');
};

// ===========================================================================
// MODAL COBRAR ORDEN ABIERTA
// ===========================================================================
let _cobrarOrdenId = null;
let _cobrarOrdenTotal = 0;

window.abrirCobrarModal = function(id_pedido, total) {
    _cobrarOrdenId = id_pedido;
    const subtotal = parseFloat(total);
    _cobrarOrdenTotal = Math.round((subtotal + Math.round(subtotal * 0.15 * 100) / 100) * 100) / 100; // subtotal + IVA
    document.getElementById('cobrar-orden-id').textContent = id_pedido;
    document.getElementById('cobrar-orden-detalle').innerHTML = `<strong>Total estimado: C$ ${subtotal.toFixed(2)} + IVA = C$ ${_cobrarOrdenTotal.toFixed(2)}</strong>`;
    document.getElementById('cobrar-modal').classList.add('active');
    // Limpiar campo de monto recibido
    const montoInput = document.getElementById('cobrar-monto');
    if (montoInput) montoInput.value = '';
};

window.cerrarCobrarModal = function() {
    document.getElementById('cobrar-modal').classList.remove('active');
    _cobrarOrdenId = null;
    _cobrarOrdenTotal = 0;
};

window.anularOrden = async function(id_pedido) {
    if (!confirm(`¿Anular la orden #${id_pedido}?`)) {
        return;
    }
    
    try {
        const res = await window.fetchAuth(`/api/pedidos/${id_pedido}/anular`, { 
            method: 'POST', 
            headers: {'Content-Type':'application/json'} 
        });
        
        const data = await res.json();
        
        if (res.ok) {
            window.showToast('Orden anulada', 'success');
            cargarOrdenesAbiertas();
        } else {
            window.showToast(data.error || 'Error al anular', 'error');
        }
    } catch (e) {
        window.showToast('Error de conexión', 'error');
    }
};

// ===========================================================================
// REPORTES
// ===========================================================================
async function generarReporte(tipo) {
    const cont = document.getElementById('reporte-resultado');
    cont.innerHTML = '<p><i class="fa-solid fa-spinner fa-spin"></i> Generando reporte y guardando copia de seguridad...</p>';

    let url = `/api/reportes/${tipo}`;
    
    if (tipo === 'diario') {
        const f = document.getElementById('reporte-fecha-diario')?.value;
        if (f) {
            url += `?fecha=${f}`;
        }
    } else if (tipo === 'semanal') {
        const f = document.getElementById('reporte-fecha-semanal')?.value;
        if (f) {
            url += `?fecha_inicio=${f}`;
        }
    } else if (tipo === 'mensual') {
        const mes = document.getElementById('reporte-mes')?.value;
        const anio = document.getElementById('reporte-anio')?.value;
        if (mes && anio) {
            url += `?mes=${mes}&anio=${anio}`;
        }
    }

    try {
        const res = await window.fetchAuth(url);
        const data = await res.json();
        
        if (!res.ok) {
            throw new Error(data.error || 'Error al generar reporte');
        }

        window._ultimoReporte = { tipo, datos: data };

        let html = `
            <div style="display:flex; flex-direction:column; gap:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h3 style="color:var(--secondary);"><i class="fa-solid fa-check-circle"></i> Reporte ${tipo.toUpperCase()} generado</h3>
                    <div style="display:flex; gap:10px;">
                        <button class="btn-secondary" onclick="descargarCSV()"><i class="fa-solid fa-file-csv"></i> Descargar Excel</button>
                        <button class="btn-secondary" onclick="imprimirReporte()"><i class="fa-solid fa-print"></i> Imprimir / PDF</button>
                    </div>
                </div>
                <div style="background:rgba(16,185,129,0.1); border:1px solid var(--secondary); border-radius:8px; padding:12px; font-size:0.85rem;">
                    <i class="fa-solid fa-floppy-disk"></i> Backup guardado: <strong>${data.backup_guardado}</strong>
                </div>
                <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap:12px; margin-top:8px;">
                    <div style="background:var(--glass-bg); border-radius:10px; padding:12px; text-align:center;">
                        <div style="font-size:1.5rem; font-weight:700; color:var(--primary);">C$ ${parseFloat(data.total_ventas || 0).toFixed(2)}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted);">Total Ventas</div>
                    </div>
                    <div style="background:var(--glass-bg); border-radius:10px; padding:12px; text-align:center;">
                        <div style="font-size:1.5rem; font-weight:700; color:var(--secondary);">${data.total_facturas || 0}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted);">Facturas Emitidas</div>
                    </div>
                    <div style="background:var(--glass-bg); border-radius:10px; padding:12px; text-align:center;">
                        <div style="font-size:1.5rem; font-weight:700; color:var(--danger);">C$ ${parseFloat(data.total_impuesto || 0).toFixed(2)}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted);">IVA Recaudado</div>
                    </div>
                </div>`;

        if (data.por_metodo_pago && data.por_metodo_pago.length > 0) {
            html += `<div><h4 style="margin-bottom:8px; color:var(--text-muted);">Por Método de Pago</h4><div style="display:flex; gap:8px; flex-wrap:wrap;">`;
            data.por_metodo_pago.forEach(m => {
                html += `
                    <span style="background:rgba(59,130,246,0.1); border:1px solid rgba(59,130,246,0.3); padding:6px 12px; border-radius:20px; font-size:0.85rem;">
                        <i class="fa-solid fa-credit-card"></i> ${m.metodo}: <strong>C$ ${parseFloat(m.monto).toFixed(2)}</strong> (${m.cantidad} facturas)
                    </span>
                `;
            });
            html += `</div></div>`;
        }

        if (data.top_productos && data.top_productos.length > 0) {
            html += `<div><h4 style="margin-bottom:8px; color:var(--text-muted);">Top Productos</h4><div style="display:flex; flex-direction:column; gap:4px;">`;
            data.top_productos.slice(0, 5).forEach((p, i) => {
                html += `
                    <div style="display:flex; justify-content:space-between; padding:6px 10px; background:var(--glass-bg); border-radius:6px; font-size:0.85rem;">
                        <span><strong>#${i+1}</strong> ${p.nombre}</span>
                        <span style="color:var(--secondary);">${p.cantidad} und. · C$ ${parseFloat(p.monto).toFixed(2)}</span>
                    </div>
                `;
            });
            html += `</div></div>`;
        }

        html += `</div>`;
        cont.innerHTML = html;
        
    } catch (e) {
        cont.innerHTML = `<div style="color:var(--danger);"><i class="fa-solid fa-circle-exclamation"></i> ${e.message}</div>`;
    }
}

function descargarCSV() {
    if (!window._ultimoReporte) {
        return;
    }
    
    const { tipo, datos } = window._ultimoReporte;
    let filas = datos.facturas || datos.por_dia || [];
    
    if (filas.length === 0) {
        window.showToast("El reporte no tiene datos para exportar", "info");
        return;
    }

    const cabeceras = Object.keys(filas[0]).join(';');
    const contenido = filas.map(f => Object.values(f).join(';')).join('\n');
    const csv = `\uFEFF${cabeceras}\n${contenido}`;

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `reporte_${tipo}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    window.showToast("Archivo Excel descargado", "success");
}

function imprimirReporte() {
    const contenido = document.getElementById('reporte-resultado').innerHTML;
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
                <title>Reporte de Ventas - El Filete</title>
                <style>
                    body { font-family: sans-serif; padding: 20px; color: #000; }
                    h3 { color: #333; border-bottom: 2px solid #000; padding-bottom: 10px; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                    th, td { border: 1px solid #ccc; padding: 8px; text-align: left; font-size: 12px; }
                    .no-print { display: none; }
                </style>
            </head>
            <body>
                <h1>El Filete - Reporte de Ventas</h1>
                ${contenido}
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

// ===========================================================================
// MENÚ ADMIN CRUD
// ===========================================================================
async function cargarMenuAdmin() {
    const tbody = document.getElementById('tabla-menu-admin');
    if (!tbody) {
        return;
    }
    
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">Cargando...</td></tr>';
    
    try {
        const res = await window.fetchAuth('/api/productos?todos=1');
        const productos = await res.json();
        
        if (!res.ok) {
            throw new Error(productos.error);
        }
        
        tbody.innerHTML = productos.map(p => `
            <tr style="${!p.disponible ? 'opacity:0.5;' : ''}">
                <td>${p.id_producto}</td>
                <td><strong>${p.nombre}</strong></td>
                <td>C$ ${parseFloat(p.precio).toFixed(2)}</td>
                <td>${p.categoria}</td>
                <td>${p.disponible ? '✅ Activo' : '❌ Inactivo'}</td>
                <td>
                    <button class="action-btn" onclick="abrirModalProducto(${p.id_producto})" title="Editar"><i class="fa-solid fa-pen-to-square"></i></button>
                    <button class="action-btn delete" onclick="eliminarProducto(${p.id_producto})" title="Eliminar/Deshabilitar"><i class="fa-solid fa-trash"></i></button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="color:var(--danger);">Error: ${e.message}</td></tr>`;
    }
}

window.abrirModalProducto = async function(id_producto = null) {
    const catSelect = document.getElementById('prod-categoria');
    catSelect.innerHTML = categorias.map(c =>
        `<option value="${c.id_categoria}">${c.nombre}</option>`
    ).join('');

    document.getElementById('prod-id').value = '';
    document.getElementById('prod-nombre').value = '';
    document.getElementById('prod-precio').value = '';
    document.getElementById('prod-descripcion').value = '';
    document.getElementById('prod-imagen').value = '';
    document.getElementById('prod-disponible').checked = true;
    document.getElementById('prod-disponible-group').style.display = 'none';
    document.getElementById('producto-modal-titulo').textContent = 'Nuevo Producto';

    if (id_producto) {
        try {
            const res = await window.fetchAuth('/api/productos?todos=1');
            const prods = await res.json();
            const prod = prods.find(p => p.id_producto === id_producto);
            
            if (prod) {
                document.getElementById('prod-id').value = prod.id_producto;
                document.getElementById('prod-nombre').value = prod.nombre;
                document.getElementById('prod-precio').value = prod.precio;
                document.getElementById('prod-descripcion').value = prod.descripcion || '';
                document.getElementById('prod-imagen').value = prod.imagen_url || '';
                document.getElementById('prod-disponible').checked = !!prod.disponible;
                catSelect.value = prod.id_categoria;
                document.getElementById('prod-disponible-group').style.display = 'flex';
                document.getElementById('producto-modal-titulo').textContent = `Editar Producto #${id_producto}`;
            }
        } catch (e) {
            window.showToast('Error cargando datos', 'error');
        }
    }
    document.getElementById('producto-modal').classList.add('active');
};

window.cerrarModalProducto = function() {
    document.getElementById('producto-modal').classList.remove('active');
};

async function eliminarProducto(id) {
    if (!confirm('¿Eliminar o deshabilitar este producto del menú?')) {
        return;
    }
    
    try {
        const res = await window.fetchAuth(`/api/productos/${id}`, { method: 'DELETE' });
        const data = await res.json();
        
        if (res.ok) {
            window.showToast(`Producto ${data.accion}`, 'success');
            cargarMenuAdmin();
            
            const r = await window.fetchAuth('/api/productos');
            if (r.ok) {
                catalogo = await r.json();
                renderProducts();
            }
        } else {
            window.showToast(data.error || 'Error', 'error');
        }
    } catch (e) {
        window.showToast('Error de conexión', 'error');
    }
}

// ===========================================================================
// GESTIÓN DE USUARIOS
// ===========================================================================
async function cargarUsuarios() {
    const tbody = document.getElementById('usuarios-tbody');
    if (!tbody) {
        return;
    }
    
    try {
        const res = await window.fetchAuth('/api/usuarios');
        const users = await res.json();
        
        tbody.innerHTML = users.map(u => `
            <tr style="${!u.activo ? 'opacity:0.4;' : ''}">
                <td>${u.id_usuario}</td>
                <td><strong>${u.username}</strong></td>
                <td>${u.nombre_completo}</td>
                <td><span class="badge badge-${u.rol}">${u.rol}</span></td>
                <td>${u.activo ? '✅' : '❌'}</td>
                <td>
                    ${u.activo ? `<button class="action-btn delete" onclick="desactivarUsuario(${u.id_usuario})" title="Desactivar"><i class="fa-solid fa-user-slash"></i></button>` : ''}
                </td>
            </tr>
        `).join('');
    } catch (e) {
        window.showToast('Error cargando usuarios', 'error');
    }
}

window.abrirModalUsuario = function() {
    document.getElementById('usuario-modal').classList.add('active');
};

window.cerrarModalUsuario = function() {
    document.getElementById('usuario-modal').classList.remove('active');
};

window.desactivarUsuario = async function(uid) {
    if (!confirm('¿Desactivar este usuario?')) {
        return;
    }
    
    try {
        const res = await window.fetchAuth(`/api/usuarios/${uid}`, { method: 'DELETE' });
        const data = await res.json();
        
        if (res.ok) {
            window.showToast('Usuario desactivado', 'success');
            cargarUsuarios();
        } else {
            window.showToast(data.error || 'Error', 'error');
        }
    } catch (e) {
        window.showToast('Error de conexión', 'error');
    }
};

// ===========================================================================
// EVENT LISTENERS
// ===========================================================================
function setupEventListeners() {
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            searchQuery = e.target.value;
            renderProducts();
        });
    }

    if (btnClearOrder) {
        btnClearOrder.addEventListener('click', () => {
            order = [];
            renderOrder();
            limpiarOrdenCargada();
        });
    }

    document.querySelectorAll('.payment-method').forEach(method => {
        method.addEventListener('click', (e) => {
            document.querySelectorAll('.payment-method').forEach(m => m.classList.remove('selected'));
            e.currentTarget.classList.add('selected');
            const radio = e.currentTarget.querySelector('input');
            if (radio) {
                radio.checked = true;
            }
            
            const cashSection = document.getElementById('cash-section');
            if (cashSection) {
                if (radio && radio.value === 'Efectivo') {
                    cashSection.classList.remove('hidden');
                } else {
                    cashSection.classList.add('hidden');
                }
            }
        });
    });

    const montoInput = document.getElementById('monto-recibido');
    if (montoInput) {
        montoInput.addEventListener('input', calcularCambio);
    }

    if (btnProcessOrder) {
        btnProcessOrder.addEventListener('click', processOrder);
    }
    
    if (btnActualizarOrden) {
        btnActualizarOrden.addEventListener('click', actualizarOrdenAbierta);
    }

    const closeInvoice = document.getElementById('close-invoice');
    if (closeInvoice) {
        closeInvoice.addEventListener('click', closeModal);
    }
    
    const btnDone = document.getElementById('btn-done');
    if (btnDone) {
        btnDone.addEventListener('click', finishOrder);
    }

    const btnPrint = document.getElementById('btn-print');
    if (btnPrint) {
        btnPrint.addEventListener('click', () => {
            window.print();
        });
    }

    const formProducto = document.getElementById('producto-form');
    if (formProducto) {
        formProducto.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('prod-id').value;
            
            const payload = {
                nombre: document.getElementById('prod-nombre').value.trim(),
                precio: parseFloat(document.getElementById('prod-precio').value),
                id_categoria: parseInt(document.getElementById('prod-categoria').value),
                descripcion: document.getElementById('prod-descripcion').value.trim(),
                imagen_url: document.getElementById('prod-imagen').value.trim(),
            };
            
            if (id) {
                payload.disponible = document.getElementById('prod-disponible').checked;
            }

            try {
                const url = id ? `/api/productos/${id}` : '/api/productos';
                const method = id ? 'PUT' : 'POST';
                
                const res = await window.fetchAuth(url, {
                    method, 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    window.showToast(id ? 'Producto actualizado' : 'Producto creado', 'success');
                    cerrarModalProducto();
                    cargarMenuAdmin();
                    
                    const r = await window.fetchAuth('/api/productos');
                    if (r.ok) {
                        catalogo = await r.json();
                        renderProducts();
                    }
                } else {
                    window.showToast(data.error || 'Error', 'error');
                }
            } catch (err) {
                window.showToast('Error de conexión', 'error');
            }
        });
    }

    const formUsuario = document.getElementById('usuario-form');
    if (formUsuario) {
        formUsuario.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const payload = {
                username: document.getElementById('usr-username').value.trim(),
                nombre_completo: document.getElementById('usr-nombre').value.trim(),
                password: document.getElementById('usr-password').value,
                rol: document.getElementById('usr-rol').value,
            };
            
            try {
                const res = await window.fetchAuth('/api/usuarios', {
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    window.showToast('Usuario creado exitosamente', 'success');
                    cerrarModalUsuario();
                    cargarUsuarios();
                } else {
                    window.showToast(data.error || 'Error', 'error');
                }
            } catch (err) {
                window.showToast('Error de conexión', 'error');
            }
        });
    }

    const formCobrar = document.getElementById('cobrar-form');
    if (formCobrar) {
        const metodoSelect = document.getElementById('cobrar-metodo');
        const efectivoGroup = document.getElementById('cobrar-efectivo-group');
        
        if (metodoSelect) {
            metodoSelect.addEventListener('change', () => {
                if (efectivoGroup) {
                    efectivoGroup.style.display = metodoSelect.value === 'Efectivo' ? 'flex' : 'none';
                }
            });
        }

        formCobrar.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            if (!_cobrarOrdenId) {
                return;
            }

            const metodo = document.getElementById('cobrar-metodo').value;
            const montoRecibido = parseFloat(document.getElementById('cobrar-monto').value) || 0;

            // Validar que el monto recibido no sea menor al total cuando es efectivo
            if (metodo === 'Efectivo' && montoRecibido < _cobrarOrdenTotal) {
                window.showToast(`El monto recibido es menor al total C$ ${_cobrarOrdenTotal.toFixed(2)}. No es posible cobrar.`, 'error');
                return;
            }
            
            const payload = {
                cliente_nombre: document.getElementById('cobrar-cliente').value.trim() || 'Consumidor Final',
                metodo_pago: metodo,
                monto_recibido: montoRecibido,
            };
            
            try {
                const res = await window.fetchAuth(`/api/pedidos/${_cobrarOrdenId}/cobrar`, {
                    method: 'POST', 
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await res.json();
                
                if (res.ok && data.id_factura) {
                    window.showToast(`Factura #${String(data.id_factura).padStart(6,'0')} generada`, 'success');
                    cerrarCobrarModal();
                    cargarOrdenesAbiertas();
                    cargarFacturas();
                    
                    const factura = data.factura;
                    factura.mesa_texto = factura.numero_mesa ? `Mesa #${factura.numero_mesa}` : (factura.tipo_pedido || 'Para Llevar');
                    mostrarComprobanteModal(factura, false);
                } else {
                    window.showToast(data.error || 'Error al cobrar', 'error');
                }
            } catch (err) {
                window.showToast('Error de conexión', 'error');
            }
        });
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            const tab = e.currentTarget.dataset.tab;
            _navegar(tab);
        });
    });
}

function _navegar(tab) {
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItem = document.querySelector(`[data-tab="${tab}"]`);
    if (navItem) {
        navItem.classList.add('active');
    }

    document.querySelectorAll('.view-section').forEach(v => v.classList.remove('active-view'));
    const targetView = document.getElementById(`${tab}-view`);
    if (targetView) {
        targetView.classList.add('active-view');
    }

    if (tab === 'inventory') {
        cargarFacturas();
    }
    
    if (tab === 'usuarios') {
        cargarUsuarios();
    }
    
    if (tab === 'menu-admin') {
        cargarMenuAdmin();
    }
    
    if (tab === 'ordenes-abiertas') {
        cargarOrdenesAbiertas();
    }

    if (tab === 'pos') {
        recargarMesas();
    }
    
    if (tab === 'reportes') {
        const cont = document.getElementById('reporte-resultado');
        if (cont && !cont.innerHTML.trim()) {
            cont.innerHTML = '';
        }
    }
}

// ===========================================================================
// INICIAR APP
// ===========================================================================
document.addEventListener('DOMContentLoaded', initApp);