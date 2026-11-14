"""
Script de inicialización para la base de datos de Restaurante "El Filete".
Crea las tablas, índices y siembra el catálogo completo (categorías, mesas, productos)
y los usuarios iniciales de prueba (admin, cajero1, mesero1).
"""

import os
import sys
import secrets
import hashlib
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "ElFilete.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# Hashing compatible con auth.py (PBKDF2-HMAC-SHA256 con 200,000 iteraciones)
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 200000)
    return f"200000${salt.hex()}${dk.hex()}"

CATEGORIAS = [(1, 'Entradas'), (2, 'Bebida'), (3, 'Mariscos'), (4, 'Cortes'), (5, 'Desayunos'), (6, 'Pollo'), (7, 'Cocteles'), (8, 'Postres'), (9, 'Licores'), (10, 'Cervezas'), (11, 'Sopa'), (12, 'Extras')]

MESAS = [(1, 1, 2, 'Disponible'), (2, 2, 2, 'Disponible'), (3, 3, 4, 'Disponible'), (4, 4, 4, 'Disponible'), (5, 5, 4, 'Disponible'), (6, 6, 4, 'Disponible'), (7, 7, 6, 'Disponible'), (8, 8, 6, 'Disponible'), (9, 9, 6, 'Disponible'), (10, 10, 6, 'Disponible'), (11, 11, 8, 'Disponible'), (12, 12, 8, 'Disponible'), (13, 13, 8, 'Disponible'), (14, 14, 8, 'Disponible'), (15, 15, 4, 'Disponible'), (16, 16, 4, 'Disponible'), (17, 17, 4, 'Disponible'), (18, 18, 4, 'Disponible'), (19, 19, 2, 'Disponible'), (20, 20, 2, 'Disponible'), (21, 21, 6, 'Disponible'), (22, 22, 6, 'Disponible'), (23, 23, 10, 'Disponible'), (24, 24, 10, 'Disponible'), (25, 25, 4, 'Disponible'), (26, 26, 4, 'Disponible'), (27, 27, 8, 'Disponible'), (28, 28, 8, 'Disponible'), (29, 29, 12, 'Disponible'), (30, 30, 12, 'Disponible')]

PRODUCTOS = [(1, 1, 'Tostones con queso', 'Tostones acompañdos de queso y ensalada', 300.0, 'Imagenes/TostonQ.jpg', 1), (2, 1, 'Tostones con carne', 'Toston', 370.0, 'Imagenes/TostonC.jpg', 1), (3, 1, 'Tostones mixtos', '', 370.0, 'Imagenes/TostonMx.jpg', 1), (4, 1, 'Consome de camarones', '', 400.0, 'Imagenes/ConsomeCamarón.jpg', 1), (5, 1, 'Canasta de camarones', '', 555.0, 'Imagenes/CanastaC.jpg', 0), (6, 2, 'Agua Purificada', '', 65.0, 'Imagenes/Agua.jpg', 1), (7, 2, 'Gaseosa/Soda', '', 65.0, 'Imagenes/Gaseosa.jpg', 1), (8, 2, 'Refresco de temporada', '', 115.0, 'Imagenes/Refrescos.jpg', 1), (9, 2, 'Fruit Punch', '', 150.0, 'Imagenes/Fruit.jpg', 1), (10, 2, 'Frozen Fruit', '', 185.0, 'Imagenes/frozenfruit.jpg', 1), (11, 2, 'Gatorade', '', 70.0, 'Imagenes/Gatorade.jpg', 1), (12, 3, 'Camarones al Ajillo', '', 690.0, 'Imagenes/CamaronesA.jpg', 1), (13, 3, 'Camarones Empanizados', '', 615.0, 'Imagenes/CamaronesE.jpg', 1), (14, 3, 'Arroz con Camaron', '', 615.0, 'Imagenes/ArrozCC.jpg', 1), (15, 3, 'Salmon a la plancha', '', 725.0, 'Imagenes/Salmon.jpg', 1), (16, 3, 'Langosta Triton', '', 1465.0, 'Imagenes/LangostaT.jpg', 1), (17, 3, 'Langosta a la Termidor', '', 1280.0, 'Imagenes/LangostaTe.jpg', 1), (18, 3, 'Mar y Tierra', '', 2205.0, 'Imagenes/MyT.jpg', 1), (19, 3, 'Paella Mixta', '', 1095.0, 'Imagenes/paella-mixta.jpg', 1), (20, 3, 'Ceviche de Pescado', '', 200.0, 'Imagenes/CevicheP.jpg', 1), (21, 3, 'Ceviche de Camaron', '', 220.0, 'Imagenes/CevicheC.jpg', 1), (22, 3, 'Ceviche Mixto', '', 250.0, 'Imagenes/CevicheMx.jpg', 1), (23, 4, 'Filete de Res', '', 380.0, 'Imagenes/Filete.jpg', 1), (24, 4, 'Rib Eye', '', 380.0, 'Imagenes/RibEye.jpg', 1), (25, 4, 'Churrasco Criollo', '', 300.0, 'Imagenes/Churrasco.jpg', 1), (26, 4, 'Lomo de Entrana', '', 300.0, 'Imagenes/LomoE.jpg', 1), (27, 4, 'Puyazo', '', 300.0, 'Imagenes/puyaso.jpg', 1), (28, 4, 'Lomo de Costilla', '', 570.0, 'Imagenes/LomoC.jpg', 1), (29, 4, 'Filete de res con camarones', '', 450.0, 'Imagenes/FileteCC.jpg', 1), (30, 4, 'Arrachera', '', 350.0, 'Imagenes/Arrachera.jpg', 1), (31, 4, 'Filete Jalapeno', '', 380.0, 'Imagenes/622_02.webp', 1), (32, 4, 'Tomahawk', '', 580.0, 'Imagenes/Tomahawk.jpg', 1), (33, 4, 'New York Steak', '', 350.0, 'Imagenes/NewYorkSteak.jpg', 1), (34, 4, 'Poterhouse', '', 450.0, 'Imagenes/Porterhouse.jpg', 1), (35, 4, 'T-Bone', '', 390.0, 'Imagenes/T-Bone.jpg', 1), (36, 4, 'Brocheta', '', 350.0, 'Imagenes/Brocheta.jpg', 1), (37, 4, 'Carne de Asada', '', 250.0, 'Imagenes/CarneDeAsada.jpg', 1), (38, 4, 'Carne Desmenuzada', '', 220.0, 'Imagenes/CarneDesmenuzada.jpg', 1), (39, 4, 'Fajitas de Res', '', 220.0, 'Imagenes/FajitasDeRes.jpg', 1), (40, 5, 'Tipico', '', 250.0, 'Imagenes/Tipico.jpg', 1), (41, 5, 'Americano', '', 300.0, 'Imagenes/Americano.jpg', 1), (42, 5, 'Panqueques', '', 200.0, 'Imagenes/Panqueques.jpg', 1), (43, 5, 'Tropical', '', 200.0, 'Imagenes/Tropical.jpg', 1), (44, 6, 'Pollo Asado', '', 200.0, 'Imagenes/PolloAsado.jpg', 1), (45, 6, 'Pollo Rostizado', '', 210.0, 'Imagenes/PolloRostizado.jpg', 1), (46, 6, 'Fajitas de Pollo', '', 220.0, 'Imagenes/FajitasDePollo.jpg', 1), (47, 6, 'Filete de Pollo', '', 230.0, 'Imagenes/FileteDePollo.jpg', 1), (48, 6, 'Deditos de pollo', '', 170.0, 'Imagenes/DeditosDePollo.jpg', 1), (49, 6, 'Alitas 12u', '', 275.0, 'Imagenes/Alitas12u.jpg', 1), (50, 6, 'Chunk Daiquiri', '', 290.0, 'Imagenes/ChunkDaiquiri.jpg', 1), (51, 6, 'Alitas 18u', '', 380.0, 'Imagenes/Alitas18u.jpg', 1), (52, 6, 'Toston Familiar', '', 310.0, 'Imagenes/TostonFamiliar.jpg', 1), (53, 7, 'Margarita', '', 150.0, 'Imagenes/Margarita.jpg', 1), (54, 7, 'Piña Colada', '', 180.0, 'Imagenes/PiñaColada.jpg', 1), (55, 7, 'Martini', '', 180.0, 'Imagenes/Martini.jpg', 1), (56, 7, 'Bloody Mary', '', 200.0, 'Imagenes/BloodyMary.jpg', 1), (57, 7, 'Cuba Libre', '', 130.0, 'Imagenes/CubaLibre.jpg', 1), (58, 7, 'Mojito Cubano', '', 180.0, 'Imagenes/MojitoCubano.jpg', 1), (59, 7, 'Long Island Ice Tea', '', 200.0, 'Imagenes/LongIslandIceTea.jpg', 1), (60, 7, 'Mango Daiquiri', '', 180.0, 'Imagenes/MangoDaiquiri.jpg', 1), (61, 7, 'Flor Ginger', '', 200.0, 'Imagenes/FlorGinger.jpg', 1), (62, 7, 'Tom Colins', '', 180.0, 'Imagenes/TomColins.jpg', 1), (63, 8, 'Tres Leche', '', 130.0, 'Imagenes/TresLeche.jpg', 1), (64, 8, 'Pio X', '', 130.0, 'Imagenes/piox.jpg', 1), (65, 8, 'Toronjas en Miel', '', 130.0, 'Imagenes/ToronjasEnMiel.jpg', 1), (66, 8, 'Torta de Chocolate', '', 170.0, 'Imagenes/TortaDeChocolate.jpg', 1), (67, 8, 'Selva Negra', '', 170.0, 'Imagenes/SelvaNegra.jpg', 1), (68, 8, 'Cafe', '', 60.0, 'Imagenes/Cafe.jpg', 1), (69, 8, 'Capuchino', '', 110.0, 'Imagenes/Capuchino.jpg', 1), (70, 9, 'Flor de caña Gran Reserva', '', 60.0, 'Imagenes/FlorDeCañaGranReserva.jpg', 1), (71, 9, 'Flor de caña Extra Lite', '', 55.0, 'Imagenes/FlorDeCañaExtraLite.jpg', 1), (72, 9, 'Flor de caña Centenario', '', 100.0, 'Imagenes/FlorDeCañaCentenario.jpg', 1), (73, 9, 'Tequila Jose Cuervo', '', 90.0, 'Imagenes/TequilaJoseCuervo.jpg', 1), (74, 9, 'Jaggermeister', '', 120.0, 'Imagenes/Jaggermeister.jpg', 1), (75, 9, 'Baileys', '', 100.0, 'Imagenes/Baileys.jpg', 1), (76, 10, 'Toña', '', 60.0, 'Imagenes/Toña.jpg', 1), (77, 10, 'Toña Lite', '', 60.0, 'Imagenes/ToñaLite.jpg', 1), (78, 10, 'Toña Lata', '', 60.0, 'Imagenes/ToñaLata.jpg', 1), (79, 10, 'Victoria Clasica', '', 60.0, 'Imagenes/VictoriaClasica.jpg', 1), (80, 10, 'Victoria Frost', '', 50.0, 'Imagenes/VictoriaFrost.jpg', 1), (81, 10, 'Sol', '', 100.0, 'Imagenes/Sol.jpg', 1), (82, 10, 'Bliss', '', 110.0, 'Imagenes/Bliss.jpg', 1), (83, 10, 'Smirnoff', '', 110.0, 'Imagenes/Smirnoff.jpg', 1), (84, 10, 'Miller Lite', '', 70.0, 'Imagenes/MillerLite.jpg', 1), (85, 10, 'Heineken', '', 100.0, 'Imagenes/Heineken.jpg', 1), (86, 10, 'Bamboo', '', 70.0, 'Imagenes/Bamboo.jpg', 1), (87, 10, 'Adan y Eva', '', 80.0, 'Imagenes/AdanYEva.jpg', 1), (88, 10, 'Hard Seltzer', '', 65.0, 'Imagenes/HardSeltzer.jpg', 1), (89, 11, 'Sopa de Pollo', '', 210.0, 'Imagenes/SopaDePollo.jpg', 1), (90, 11, 'Sopa Marinera', '', 700.0, 'Imagenes/SopaMarinera.jpg', 1), (91, 11, 'Sopa Junior Daiquiri', '', 300.0, 'Imagenes/SopaDeRes.jpg', 1), (92, 11, 'Sopa de Res', '', 250.0, 'Imagenes/SopaDeRes.jpg', 1), (93, 12, 'Arroz', '', 50.0, 'Imagenes/Arroz.jpg', 1), (94, 12, 'Frijoles Molidos', '', 50.0, 'Imagenes/FrijolesMolidos.jpg', 1), (95, 12, 'Papas Fritas', '', 60.0, 'Imagenes/PapasFritas.jpg', 1), (96, 12, 'Mayonesa', '', 40.0, 'Imagenes/Mayonesa.jpg', 1), (97, 12, 'Salsa de Tomate', '', 40.0, 'Imagenes/SalsaDeTomate.jpg', 1), (98, 12, 'Tostones 5u', '', 50.0, 'Imagenes/Tostones.jpg', 1), (99, 12, 'Papa Asada 2u', '', 50.0, 'Imagenes/PapaAsada.jpg', 1), (100, 12, 'Galleta', '', 20.0, 'Imagenes/Galleta.jpg', 1), (101, 12, 'Vegetales', '', 70.0, 'Imagenes/Vegetales.jpg', 1), (102, 10, 'Bamboo', 'Bebida alcoholica', 45.0, 'https://walmartni.vtexassets.com/arquivos/ids/759029/bebida-bamboo-sandia-10-5-alcohol-473-ml-0764009045188.webp?v=639149946081400000', 1)]

USUARIOS_INICIALES = [
    ("admin", "admin123", "Administrador Principal", "admin"),
    ("cajero1", "cajero123", "Cajero de Turno", "cajero"),
    ("mesero1", "mesero123", "Mesero de Turno", "mesero"),
]

DDL_TABLAS = """
CREATE TABLE categoria (
    id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE producto (
    id_producto  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_categoria INTEGER NOT NULL,
    nombre       TEXT NOT NULL,
    descripcion  TEXT DEFAULT '',
    precio       REAL NOT NULL CHECK (precio >= 0),
    imagen_url   TEXT DEFAULT '',
    disponible   INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE mesa (
    id_mesa     INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_mesa INTEGER NOT NULL UNIQUE,
    capacidad   INTEGER NOT NULL DEFAULT 4,
    estado      TEXT NOT NULL DEFAULT 'Disponible'
);

CREATE TABLE usuario (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    nombre_completo TEXT NOT NULL,
    rol             TEXT NOT NULL CHECK (rol IN ('admin','cajero','mesero')),
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_por      INTEGER,
    fecha_creacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (creado_por) REFERENCES usuario(id_usuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE UNIQUE INDEX idx_unico_admin
    ON usuario(rol) WHERE rol = 'admin' AND activo = 1;

CREATE TABLE sesion (
    id_sesion        INTEGER PRIMARY KEY AUTOINCREMENT,
    token            TEXT NOT NULL UNIQUE,
    id_usuario       INTEGER NOT NULL,
    ip               TEXT,
    user_agent       TEXT,
    fecha_creacion   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_expiracion DATETIME NOT NULL,
    activa           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX idx_sesion_token        ON sesion(token);
CREATE INDEX idx_sesion_usuario      ON sesion(id_usuario);

CREATE TABLE intento_login (
    id_intento INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL,
    ip         TEXT NOT NULL,
    exitoso    INTEGER NOT NULL,
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_intento_ip_user     ON intento_login(ip, username, fecha_hora);

CREATE TABLE pedido (
    id_pedido     INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_pedido   TEXT NOT NULL DEFAULT 'Para Llevar',
    estado        TEXT NOT NULL DEFAULT 'Pagado'
                  CHECK (estado IN ('Abierta', 'Pagado', 'Anulado')),
    id_mesa       INTEGER,
    total         REAL NOT NULL DEFAULT 0,
    mesero_id     INTEGER,
    mesero_nombre TEXT,
    fecha_hora    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_mesa) REFERENCES mesa(id_mesa)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (mesero_id) REFERENCES usuario(id_usuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX idx_pedido_mesa         ON pedido(id_mesa);
CREATE INDEX idx_pedido_estado       ON pedido(estado);

CREATE TABLE detalle_pedido (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_pedido       INTEGER NOT NULL,
    id_producto     INTEGER NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL,
    subtotal        REAL NOT NULL,
    observacion     TEXT,
    FOREIGN KEY (id_pedido) REFERENCES pedido(id_pedido)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (id_producto) REFERENCES producto(id_producto)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX idx_detalle_ped_pedido  ON detalle_pedido(id_pedido);
CREATE INDEX idx_detalle_ped_prod    ON detalle_pedido(id_producto);

CREATE TABLE factura (
    id_factura         INTEGER PRIMARY KEY AUTOINCREMENT,
    id_pedido          INTEGER NOT NULL UNIQUE,
    fecha_hora         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cliente_nombre     TEXT NOT NULL DEFAULT 'Consumidor Final',
    cliente_ruc_cedula TEXT,
    subtotal           REAL NOT NULL DEFAULT 0,
    impuesto           REAL NOT NULL DEFAULT 0,
    descuento          REAL NOT NULL DEFAULT 0,
    propina            REAL NOT NULL DEFAULT 0,
    monto_total        REAL NOT NULL DEFAULT 0,
    metodo_pago        TEXT NOT NULL DEFAULT 'Efectivo',
    monto_recibido     REAL NOT NULL DEFAULT 0,
    cambio_devuelto    REAL NOT NULL DEFAULT 0,
    mesero_nombre      TEXT NOT NULL DEFAULT 'Sistema',
    FOREIGN KEY (id_pedido) REFERENCES pedido(id_pedido)
        ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX idx_factura_fecha       ON factura(fecha_hora);

CREATE TABLE reserva (
    id_reserva     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_cliente TEXT NOT NULL,
    telefono       TEXT NOT NULL,
    email          TEXT,
    fecha_reserva  DATE NOT NULL,
    hora_reserva   TEXT NOT NULL,
    num_personas   INTEGER NOT NULL CHECK (num_personas > 0),
    id_mesa        INTEGER,
    notas          TEXT,
    estado         TEXT NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente','confirmada','cancelada','completada')),
    creado_por     INTEGER,
    fecha_creacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_mesa) REFERENCES mesa(id_mesa)
        ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (creado_por) REFERENCES usuario(id_usuario)
        ON UPDATE CASCADE ON DELETE SET NULL
);

CREATE INDEX idx_reserva_fecha       ON reserva(fecha_reserva, hora_reserva);

CREATE TABLE auditoria (
    id_evento  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario INTEGER,
    accion     TEXT NOT NULL,
    entidad    TEXT,
    entidad_id INTEGER,
    detalle    TEXT,
    ip         TEXT,
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auditoria_usuario   ON auditoria(id_usuario, fecha_hora);
CREATE INDEX idx_auditoria_entidad   ON auditoria(entidad, entidad_id);
CREATE INDEX idx_producto_categoria  ON producto(id_categoria);
"""

def inicializar_bd(forzar: bool = False):
    if os.path.exists(DB_PATH):
        if not forzar:
            print(f"[!] La base de datos ya existe en: {DB_PATH}")
            respuesta = input("¿Deseas sobreescribirla y reiniciar todos los datos? (s/N): ").strip().lower()
            if respuesta not in ('s', 'si', 'y', 'yes'):
                print("Operación cancelada. No se modificó la base de datos.")
                return False
        # Eliminar archivo existente para inicialización limpia
        try:
            os.remove(DB_PATH)
            print(f"[-] Base de datos anterior eliminada.")
        except Exception as e:
            print(f"[ERROR] No se pudo eliminar la base de datos existente: {e}")
            return False

    print(f"[+] Creando base de datos en: {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        cur = conn.cursor()

        # 1. Crear tablas e índices
        print(" -> Creando tablas e índices...")
        cur.executescript(DDL_TABLAS)

        # 2. Sembrar categorías
        print(f" -> Sembrando {len(CATEGORIAS)} categorías...")
        cur.executemany("INSERT INTO categoria (id_categoria, nombre) VALUES (?, ?);", CATEGORIAS)

        # 3. Sembrar mesas
        print(f" -> Sembrando {len(MESAS)} mesas...")
        cur.executemany("INSERT INTO mesa (id_mesa, numero_mesa, capacidad, estado) VALUES (?, ?, ?, ?);", MESAS)

        # 4. Sembrar productos
        print(f" -> Sembrando {len(PRODUCTOS)} productos...")
        cur.executemany(
            "INSERT INTO producto (id_producto, id_categoria, nombre, descripcion, precio, imagen_url, disponible) "
            "VALUES (?, ?, ?, ?, ?, ?, ?);",
            PRODUCTOS
        )

        # 5. Sembrar usuarios iniciales
        print(f" -> Creando usuarios iniciales...")
        for username, password, nombre, rol in USUARIOS_INICIALES:
            p_hash = hash_password(password)
            cur.execute(
                "INSERT INTO usuario (username, password_hash, nombre_completo, rol, activo) "
                "VALUES (?, ?, ?, ?, 1);",
                (username, p_hash, nombre, rol)
            )

        # Registrar auditoría de inicialización
        cur.execute(
            "INSERT INTO auditoria (id_usuario, accion, entidad, detalle, ip) "
            "VALUES (1, 'inicializacion_sistema', 'sistema', 'Creación y siembra inicial de catálogo y usuarios', '127.0.0.1');"
        )

        conn.commit()
        print("\n[OK] Base de datos inicializada exitosamente.")
        print("=" * 60)
        print("  Resumen de siembra:")
        print(f"    - Categorías : {len(CATEGORIAS)}")
        print(f"    - Mesas      : {len(MESAS)}")
        print(f"    - Productos  : {len(PRODUCTOS)}")
        print(f"    - Usuarios   : {len(USUARIOS_INICIALES)}")
        print("-" * 60)
        print("  Credenciales disponibles:")
        for username, password, nombre, rol in USUARIOS_INICIALES:
            print(f"    - [{rol.upper():<7}] {username:<8} / {password} ({nombre})")
        print("=" * 60)
        return True

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error durante la inicialización: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    forzar = '--force' in sys.argv or '-f' in sys.argv
    inicializar_bd(forzar=forzar)
