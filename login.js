/**
 * login.js
 * Utilidades globales para autenticación, peticiones HTTP y notificaciones.
 */

(function () {
    function getCookie(name) {
        const raw = document.cookie || '';
        for (const part of raw.split(';')) {
            const [k, ...rest] = part.trim().split('=');
            if (k === name) {
                return rest.join('=');
            }
        }
        return null;
    }

    window.getCsrfToken = () => getCookie('csrf_token') || '';
    window.usuarioActual = null;

    // Notificaciones (Toasts) globales
    window.showToast = function (message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) {
            return;
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' 
            ? 'fa-check-circle' 
            : type === 'error' 
                ? 'fa-circle-exclamation' 
                : 'fa-circle-info';
                
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
        container.appendChild(toast);
        
        setTimeout(() => { 
            toast.classList.add('fade-out'); 
            setTimeout(() => {
                toast.remove();
            }, 300); 
        }, 4000);
    };

    // Wrapper para peticiones autenticadas
    window.fetchAuth = async function (url, opts = {}) {
        const method = (opts.method || 'GET').toUpperCase();
        const headers = new Headers(opts.headers || {});
        
        if (opts.body && !headers.has('Content-Type')) {
            headers.set('Content-Type', 'application/json');
        }
        
        if (['POST', 'PUT', 'DELETE'].includes(method)) {
            headers.set('X-CSRF-Token', window.getCsrfToken());
        }

        const res = await fetch(url, { 
            ...opts, 
            method, 
            headers, 
            credentials: 'same-origin' 
        });
        
        if (res.status === 401) {
            window.location.href = 'login.html';
            throw new Error('Sesión expirada. Vuelve a iniciar sesión.');
        }
        
        return res;
    };

    window.cargarUsuarioActual = async function () {
        try {
            const res = await window.fetchAuth('/api/auth/me');
            if (res.ok) {
                window.usuarioActual = await res.json();
            }
            return window.usuarioActual;
        } catch (err) { 
            return null; 
        }
    };

    window.cerrarSesion = async function () {
        try { 
            await window.fetchAuth('/api/auth/logout', { method: 'POST' }); 
        } catch (e) {
            console.error(e);
        }
        window.location.href = 'login.html';
    };

    // Helpers de roles
    window.esAdmin = () => window.usuarioActual && window.usuarioActual.rol === 'admin';
    window.esCajero = () => window.usuarioActual && window.usuarioActual.rol === 'cajero';
    window.esMesero = () => window.usuarioActual && window.usuarioActual.rol === 'mesero';
})();