from flask import Flask, render_template, request, redirect, session, flash
import os

app = Flask(__name__)
app.secret_key = 'clave-secreta-temporal-123456'

# ========== RUTAS SIMPLIFICADAS ==========
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Login simple SIN base de datos
        if username == 'admin' and password == 'password123':
            session['user_id'] = 1
            session['user_rol'] = 'admin'
            session['user_nombre'] = 'Administrador'
            flash('¡Bienvenido, Administrador!', 'success')
            return redirect('/dashboard')  # Usar ruta directa, no url_for
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('dashboard.html')

@app.route('/miembros')
def miembros():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('miembros.html')

@app.route('/pagos')
def pagos():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('pagos.html')

@app.route('/clases')
def clases():
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('clases.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada exitosamente', 'success')
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
