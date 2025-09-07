# main_app.py (v1.2 - Correção de Imports)
import os
import subprocess
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from threading import Lock
import time
from dotenv import dotenv_values

# --- Configuração Inicial ---
# Carrega as configurações de admin e o caminho do arquivo de log
from config import ADMIN_USER, ADMIN_PASSWORD, LOG_FILE

# --- Configuração do Logging para o Servidor Web ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | WEB-SERVER | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()] # Em produção, os logs vão para o console do Docker/EasyPanel
)
log = logging.getLogger("web-server")

# --- Inicialização da Aplicação ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24)) # Usa uma chave do ambiente ou gera uma nova
socketio = SocketIO(app, async_mode='eventlet') # 'eventlet' é recomendado para Gunicorn

bot_process = None
thread = None
thread_lock = Lock()

# --- Autenticação do Dashboard ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USER and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            log.info(f"Login bem-sucedido para o usuário '{ADMIN_USER}'")
            return redirect(url_for('dashboard'))
        else:
            log.warning("Tentativa de login falhou.")
            return "Credenciais inválidas", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    log.info("Usuário deslogado.")
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
    if not session.get('logged_in'): 
        return jsonify(error="Não autorizado"), 403
    
    data = request.json
    # Lê o .env existente para preservar variáveis não enviadas pelo formulário
    current_config = dotenv_values(".env")
    
    # Atualiza com os novos dados, ignorando valores vazios
    for key, value in data.items():
        if value:
            current_config[key.upper()] = value
            
    with open(".env", "w") as f:
        for key, value in current_config.items():
            f.write(f"{key}={value}\n")
            
    log.info("Configurações salvas no arquivo .env")
    return jsonify(message="Configurações salvas. Reinicie o bot para aplicá-las.")

@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_process
    if not session.get('logged_in'): 
        return jsonify(error="Não autorizado"), 403
    
    if bot_process and bot_process.poll() is None:
        log.warning("Tentativa de iniciar um bot que já está rodando.")
        return jsonify(message="Bot já está rodando"), 400
    
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    
    log.info("Iniciando o processo do bot_worker.py...")
    bot_process = subprocess.Popen(["python", "-u", "bot_worker.py"])
    log.info(f"Bot iniciado com PID: {bot_process.pid}")
    return jsonify(message="Bot iniciado com sucesso!", pid=bot_process.pid)

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_process
    if not session.get('logged_in'): 
        return jsonify(error="Não autorizado"), 403
    
    if bot_process and bot_process.poll() is None:
        log.info(f"Parando o processo do bot (PID: {bot_process.pid})...")
        bot_process.terminate()
        bot_process.wait(timeout=5) # Espera o processo terminar
        bot_process = None
        log.info("Bot parado com sucesso.")
        return jsonify(message="Bot parado com sucesso.")
    
    log.warning("Tentativa de parar um bot que não estava rodando.")
    return jsonify(message="Bot não estava rodando."), 400

# --- Lógica de Streaming de Logs com WebSocket ---
def tail_log_file():
    """Lê as novas linhas do arquivo de log e as envia para o cliente."""
    log.info("Iniciando a thread de monitoramento de logs...")
    # Espera o arquivo de log ser criado pelo worker
    while not os.path.exists(LOG_FILE):
        time.sleep(1)
        
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        f.seek(0, 2)
        while True:
            # Verifica se o processo do bot ainda está vivo
            if bot_process is None or bot_process.poll() is not None:
                log.info("Processo do bot não está mais rodando. Encerrando a thread de logs.")
                break
            
            line = f.readline()
            if not line:
                socketio.sleep(0.1) # Usa o sleep do socketio para cooperar com eventlet
                continue
            socketio.emit('new_log_line', {'line': line})
    
@socketio.on('connect')
def handle_connect():
    if not session.get('logged_in'):
        return False # Recusa a conexão WebSocket se não estiver logado
        
    log.info("Cliente do dashboard conectado para streaming de logs.")
    # Envia o conteúdo do log existente
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            emit('historical_logs', {'logs': f.read()})
    
    # Garante que apenas uma thread de monitoramento seja iniciada
    global thread
    with thread_lock:
        if thread is None or not thread.is_alive():
            thread = socketio.start_background_task(target=tail_log_file)

# --- Health Check Endpoint ---
@app.route('/health')
def health_check():
    """Endpoint de health check para o Easypanel"""
    return {"status": "healthy", "timestamp": time.time()}, 200

if __name__ == '__main__':
    # Esta seção é apenas para desenvolvimento local. Em produção, o Gunicorn será usado.
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)
