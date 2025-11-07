from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
import bcrypt
import datetime
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'clave-secreta-gimnasio-123456')

# Configuración para PostgreSQL en Render
app.config['DB_HOST'] = os.getenv('MYSQL_HOST', 'localhost')
app.config['DB_USER'] = os.getenv('MYSQL_USER', 'root')
app.config['DB_PASSWORD'] = os.getenv('MYSQL_PASSWORD', '')
app.config['DB_NAME'] = os.getenv('MYSQL_DB', 'gimnasio_db')
app.config['DB_PORT'] = int(os.getenv('MYSQL_PORT', '5432'))

# Función para conexión a PostgreSQL
def get_db_connection():
    try:
        conn = psycopg.connect(
            host=app.config['DB_HOST'],
            dbname=app.config['DB_NAME'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            port=app.config['DB_PORT']
        )
        return conn
    except Exception as e:
        print(f"Error de conexión a la base de datos: {e}")
        return None

# ========== CREAR TABLAS SI NO EXISTEN ==========
def crear_tablas_si_no_existen():
    try:
        conn = get_db_connection()
        if conn is None:
            print("No se pudo conectar a la base de datos")
            return
        
        cur = conn.cursor(row_factory=dict_row)
        
        # Crear tabla de usuarios si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                rol VARCHAR(20) NOT NULL,
                activo BOOLEAN DEFAULT TRUE,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Crear tabla de miembros si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS miembros (
                id SERIAL PRIMARY KEY,
                codigo_miembro VARCHAR(20) UNIQUE NOT NULL,
                nombre VARCHAR(100) NOT NULL,
                apellido VARCHAR(100) NOT NULL,
                email VARCHAR(100),
                telefono VARCHAR(20),
                fecha_nacimiento DATE,
                direccion TEXT,
                activo BOOLEAN DEFAULT TRUE,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Crear tabla de membresías si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS membresias (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT,
                precio DECIMAL(10,2) NOT NULL,
                duracion_dias INTEGER NOT NULL,
                activa BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Crear tabla de pagos si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pagos (
                id SERIAL PRIMARY KEY,
                miembro_id INTEGER REFERENCES miembros(id),
                membresia_id INTEGER REFERENCES membresias(id),
                monto DECIMAL(10,2) NOT NULL,
                fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_inicio DATE NOT NULL,
                fecha_fin DATE NOT NULL,
                metodo_pago VARCHAR(50)
            )
        """)
        
        # Crear tabla de clases si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS clases (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT,
                instructor VARCHAR(100),
                horario TIME,
                duracion_minutos INTEGER,
                capacidad_maxima INTEGER,
                dias_semana VARCHAR(50),
                activa BOOLEAN DEFAULT TRUE
            )
        """)
        
        # Crear tabla de logs si no existe
        cur.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                usuario_id INTEGER,
                accion VARCHAR(100) NOT NULL,
                tabla_afectada VARCHAR(100),
                registro_id INTEGER,
                detalles TEXT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insertar usuario admin si no existe
        cur.execute("SELECT COUNT(*) as count FROM usuarios WHERE username = 'admin'")
        result = cur.fetchone()
        if result['count'] == 0:
            # Contraseña: password123
            hashed_password = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt())
            cur.execute("""
                INSERT INTO usuarios (username, password, nombre, rol) 
                VALUES (%s, %s, %s, %s)
            """, ('admin', hashed_password.decode('utf-8'), 'Administrador', 'admin'))
        
        # Insertar membresía básica si no existe
        cur.execute("SELECT COUNT(*) as count FROM membresias WHERE nombre = 'Mensual'")
        result = cur.fetchone()
        if result['count'] == 0:
            cur.execute("""
                INSERT INTO membresias (nombre, descripcion, precio, duracion_dias) 
                VALUES (%s, %s, %s, %s)
            """, ('Mensual', 'Membresía mensual estándar', 300.00, 30))
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Tablas creadas correctamente")
    except Exception as e:
        print(f"⚠️ Error creando tablas: {e}")

# Llamar la función cuando la app inicie
with app.app_context():
    crear_tablas_si_no_existen()
    
# ========== DECORADORES ==========
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if session.get('user_rol') not in roles:
                flash('No tienes permisos para acceder a esta página', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ========== FUNCIONES AUXILIARES ==========
def registrar_log(accion, tabla_afectada, registro_id=None, detalles=None):
    try:
        conn = get_db_connection()
        if conn is None:
            return
            
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""
            INSERT INTO logs (usuario_id, accion, tabla_afectada, registro_id, detalles)
            VALUES (%s, %s, %s, %s, %s)
        """, (session.get('user_id'), accion, tabla_afectada, registro_id, detalles))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error al registrar log: {e}")

# ========== RUTAS DE AUTENTICACIÓN ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            conn = get_db_connection()
            if conn is None:
                flash('Error de conexión a la base de datos', 'error')
                return render_template('login.html')
                
            cur = conn.cursor(row_factory=dict_row)
            cur.execute("SELECT * FROM usuarios WHERE username = %s AND activo = TRUE", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                session['user_id'] = user['id']
                session['user_rol'] = user['rol']
                session['user_nombre'] = user['nombre']
                registrar_log('LOGIN', 'usuarios', user['id'], 'Inicio de sesión exitoso')
                flash(f'¡Bienvenido, {user["nombre"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario o contraseña incorrectos', 'error')
        except Exception as e:
            flash(f'Error de conexión: {str(e)}', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    if 'user_id' in session:
        registrar_log('LOGOUT', 'usuarios', session['user_id'], 'Cierre de sesión')
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect(url_for('index'))

# ========== DASHBOARD ==========
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('dashboard.html')
        
    cur = conn.cursor(row_factory=dict_row)
    
    # Estadísticas
    cur.execute("SELECT COUNT(*) as total FROM miembros WHERE activo = TRUE")
    total_miembros = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM pagos WHERE DATE(fecha_pago) = CURRENT_DATE")
    pagos_result = cur.fetchone()
    pagos_hoy = pagos_result['total'] if pagos_result else 0
    
    cur.execute("SELECT COUNT(*) as total FROM clases WHERE activa = TRUE")
    clases_activas = cur.fetchone()['total']
    
    # Últimos logs
    cur.execute("""
        SELECT l.*, u.username 
        FROM logs l 
        JOIN usuarios u ON l.usuario_id = u.id 
        ORDER BY l.fecha DESC 
        LIMIT 5
    """)
    ultimos_logs = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template('dashboard.html', 
                         total_miembros=total_miembros,
                         pagos_hoy=pagos_hoy,
                         asistencias_hoy=0,
                         clases_activas=clases_activas,
                         ultimos_logs=ultimos_logs)

# ========== GESTIÓN DE MIEMBROS ==========
@app.route('/miembros')
@login_required
@role_required(['admin', 'responsable'])
def miembros():
    search = request.args.get('search', '')
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('miembros.html', miembros=[], search=search)
        
    cur = conn.cursor(row_factory=dict_row)
    
    if search:
        cur.execute("""
            SELECT m.*
            FROM miembros m 
            WHERE m.activo = TRUE AND (m.nombre LIKE %s OR m.apellido LIKE %s OR m.codigo_miembro LIKE %s)
            ORDER BY m.nombre
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""
            SELECT m.*
            FROM miembros m 
            WHERE m.activo = TRUE 
            ORDER BY m.nombre
        """)
    
    miembros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('miembros.html', miembros=miembros, search=search)

@app.route('/miembros/agregar', methods=['GET', 'POST'])
@login_required
@role_required(['admin', 'responsable'])
def agregar_miembro():
    if request.method == 'POST':
        codigo_miembro = request.form['codigo_miembro']
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        email = request.form['email']
        telefono = request.form['telefono']
        fecha_nacimiento = request.form['fecha_nacimiento']
        direccion = request.form['direccion']
        
        conn = get_db_connection()
        if conn is None:
            flash('Error de conexión a la base de datos', 'error')
            return render_template('agregar_miembro.html')
            
        cur = conn.cursor(row_factory=dict_row)
        try:
            cur.execute("""
                INSERT INTO miembros (codigo_miembro, nombre, apellido, email, telefono, fecha_nacimiento, direccion)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (codigo_miembro, nombre, apellido, email, telefono, fecha_nacimiento, direccion))
            conn.commit()
            
            registrar_log('INSERT', 'miembros', None, f'Nuevo miembro: {nombre} {apellido} - Código: {codigo_miembro}')
            flash('Miembro agregado exitosamente', 'success')
            return redirect(url_for('miembros'))
        except Exception as e:
            conn.rollback()
            flash(f'Error al agregar miembro: {str(e)}', 'error')
        finally:
            cur.close()
            conn.close()
    
    return render_template('agregar_miembro.html')

# ========== SISTEMA DE PAGOS ==========
@app.route('/pagos')
@login_required
@role_required(['admin', 'responsable'])
def pagos():
    search = request.args.get('search', '')
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('pagos.html', pagos=[], search=search, hoy=datetime.datetime.now().date())
        
    cur = conn.cursor(row_factory=dict_row)
    
    if search:
        cur.execute("""
            SELECT p.*, m.nombre, m.apellido, m.codigo_miembro
            FROM pagos p
            JOIN miembros m ON p.miembro_id = m.id
            WHERE m.nombre LIKE %s OR m.apellido LIKE %s OR m.codigo_miembro LIKE %s
            ORDER BY p.fecha_pago DESC
        """, (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("""
            SELECT p.*, m.nombre, m.apellido, m.codigo_miembro
            FROM pagos p
            JOIN miembros m ON p.miembro_id = m.id
            ORDER BY p.fecha_pago DESC
        """)
    
    pagos = cur.fetchall()
    cur.close()
    conn.close()
    
    hoy = datetime.datetime.now().date()
    return render_template('pagos.html', pagos=pagos, search=search, hoy=hoy)

# ========== GESTIÓN DE CLASES ==========
@app.route('/clases')
@login_required
@role_required(['admin', 'responsable'])
def clases():
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('clases.html', clases=[])
        
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM clases ORDER BY nombre")
    clases = cur.fetchall()
    cur.close()
    conn.close()
    
    for clase in clases:
        if clase['horario']:
            clase['horario_str'] = str(clase['horario'])[:5]
        else:
            clase['horario_str'] = ''
    return render_template('clases.html', clases=clases)

# ========== CONSULTAS PARA USUARIOS REGULARES ==========
@app.route('/consultas/miembros')
@login_required
def consultas_miembros():
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('consultas_miembros.html', miembros=[])
        
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("""
        SELECT codigo_miembro, nombre, apellido, email, telefono, fecha_registro 
        FROM miembros 
        WHERE activo = TRUE 
        ORDER BY nombre
    """)
    miembros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('consultas_miembros.html', miembros=miembros, datetime=datetime)

@app.route('/consultas/clases')
@login_required
def consultas_clases():
    conn = get_db_connection()
    if conn is None:
        flash('Error de conexión a la base de datos', 'error')
        return render_template('consultas_clases.html', clases=[])
        
    cur = conn.cursor(row_factory=dict_row)
    cur.execute("SELECT * FROM clases WHERE activa = TRUE ORDER BY nombre")
    clases = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('consultas_clases.html', clases=clases)

# ========== EJECUCIÓN ==========
if __name__ == '__main__':
    if 'RENDER' in os.environ:
        port = int(os.environ.get('PORT', 5000))
        print(f"🚀 Iniciando servidor en modo producción - Puerto: {port}")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        print("=" * 60)
        print("🚀 Sistema de Gimnasio - VERSIÓN COMPLETA")
        print("=" * 60)
        print("📊 Usuario de prueba: admin / password123")
        print("🌐 Abre: http://localhost:5000")
        print("=" * 60)
        app.run(debug=True, host='0.0.0.0', port=5000)
