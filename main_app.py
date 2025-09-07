# main_app.py
import os
import subprocess
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO
from threading import Thread
import time
from dotenv import dotenv_values

# Carrega as configurações de admin
from config import ADMIN_USER, ADMIN_PASSWORD, LOG_FILE

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, async_mode='threading')

bot_process = None

# --- Autenticação do Dashboard ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return "Credenciais inválidas", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- Rotas do Dashboard ---
@app.route('/')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    config_values = dotenv_values(".env")
    bot_status = "Rodando" if bot_process and bot_process.poll() is None else "Parado"
    return render_template('dashboard.html', config=config_values, status=bot_status)

@app.route('/save_config', methods=['POST'])
def save_config():
    if not session.get('logged_in'): return jsonify(error="Não autorizado"), 403
    
    data = request.json
    with open(".env", "w") as f:
        for key, value in data.items():
            f.write(f"{key.upper()}={value}\n")
    return jsonify(message="Configurações salvas. Reinicie o bot para aplicá-las.")

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_process
    if not session.get('logged_in'): return jsonify(error="Não autorizado"), 403
    
    if bot_process and bot_process.poll() is None:
        return jsonify(message="Bot já está rodando"), 400
    
    # Limpa o log antigo antes de iniciar
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    bot_process = subprocess.Popen(["python", "-u", "bot_worker.py"]) # -u para unbuffered output
    return jsonify(message="Bot iniciado com sucesso!", pid=bot_process.pid)

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_process
    if not session.get('logged_in'): return jsonify(error="Não autorizado"), 403
    
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process = None
        return jsonify(message="Bot parado com sucesso.")
    return jsonify(message="Bot não estava rodando."), 400

# --- Lógica de Streaming de Logs com WebSocket ---
def tail_log_file():
    if not os.path.exists(LOG_FILE):
        time.sleep(1)
        
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            socketio.emit('new_log_line', {'line': line})

@socketio.on('connect')
def handle_connect():
    if session.get('logged_in'):
        log.info("Cliente do dashboard conectado para streaming de logs.")
        # Envia o conteúdo do log existente
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                socketio.emit('historical_logs', {'logs': f.read()})
        
        socketio.start_background_task(target=tail_log_file)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001)
