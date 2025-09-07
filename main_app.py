# main_app.py (v1.4 - Log Persistente)
import os
import subprocess
import logging
import sys
import traceback
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from threading import Lock
import time
from datetime import datetime

# --- Configuração do Logging PRIMEIRO ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("web-server")

# --- DEBUG: Verificar imports críticos ---
log.info("🚀 Iniciando main_app.py...")

try:
    log.info("📦 Importando dotenv...")
    from dotenv import dotenv_values, load_dotenv
    load_dotenv()
    log.info("✅ dotenv importado com sucesso")
except Exception as e:
    log.error(f"❌ Erro ao importar dotenv: {e}")
    sys.exit(1)

try:
    log.info("📦 Importando config...")
    from config import ADMIN_USER, ADMIN_PASSWORD, LOG_FILE
    log.info(f"✅ Config importado - Admin: {ADMIN_USER}, Log: {LOG_FILE}")
except Exception as e:
    log.error(f"❌ Erro ao importar config: {e}")
    traceback.print_exc()
    sys.exit(1)

# --- Gerenciamento de Log Persistente ---
class PersistentLogManager:
    def __init__(self, log_file_path):
        self.log_file = log_file_path
        self.ensure_log_file_exists()
    
    def ensure_log_file_exists(self):
        """Garante que o arquivo de log existe"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"# Log iniciado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.info(f"📝 Arquivo de log criado: {self.log_file}")
        else:
            log.info(f"📝 Arquivo de log existente encontrado: {self.log_file}")
    
    def get_full_log_content(self):
        """Retorna todo o conteúdo do log"""
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return content
            return ""
        except Exception as e:
            log.error(f"❌ Erro ao ler log: {e}")
            return f"Erro ao carregar log: {str(e)}"
    
    def append_session_separator(self):
        """Adiciona separador para nova sessão do bot"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"\n{'='*80}\n")
                f.write(f"🚀 NOVA SESSÃO INICIADA EM {timestamp}\n")
                f.write(f"{'='*80}\n")
        except Exception as e:
            log.error(f"❌ Erro ao adicionar separador: {e}")
    
    def rotate_log_if_needed(self):
        """Rotaciona o log se ficar muito grande (>5MB)"""
        try:
            if os.path.exists(self.log_file):
                size_mb = os.path.getsize(self.log_file) / (1024 * 1024)
                if size_mb > 5:
                    backup_name = f"{self.log_file}.backup.{int(time.time())}"
                    os.rename(self.log_file, backup_name)
                    log.info(f"📦 Log rotacionado para: {backup_name}")
                    self.ensure_log_file_exists()
        except Exception as e:
            log.error(f"❌ Erro na rotação do log: {e}")

# Inicializa o gerenciador de log
log_manager = PersistentLogManager(LOG_FILE)

# --- Inicialização da Aplicação ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key-for-development")
log.info(f"🔑 Flask secret key configurada")

try:
    socketio = SocketIO(app, async_mode='eventlet')
    log.info("✅ SocketIO inicializado com eventlet")
except Exception as e:
    log.error(f"❌ Erro ao inicializar SocketIO: {e}")
    sys.exit(1)

bot_process = None
thread = None
thread_lock = Lock()

# --- Health Check Simples ---
@app.route('/health')
def health_check():
    """Endpoint de health check simplificado"""
    return {"status": "healthy", "timestamp": time.time()}, 200

# --- Endpoint para obter logs ---
@app.route('/api/logs')
def get_logs():
    """API endpoint para obter logs completos"""
    if not session.get('logged_in'):
        return jsonify(error="Não autorizado"), 403
    
    try:
        content = log_manager.get_full_log_content()
        return jsonify({
            "logs": content,
            "timestamp": time.time(),
            "file_size": len(content)
        })
    except Exception as e:
        return jsonify(error=str(e)), 500

# --- Teste de Debug ---
@app.route('/debug')
def debug_info():
    """Endpoint para debug de informações do sistema"""
    try:
        info = {
            "python_version": sys.version,
            "working_directory": os.getcwd(),
            "environment_vars": {
                "ADMIN_USER": os.getenv("ADMIN_USER", "NOT_SET"),
                "FT_USERNAME": os.getenv("FT_USERNAME", "NOT_SET"),
                "JOGO_SLUG": os.getenv("JOGO_SLUG", "NOT_SET"),
            },
            "files_exist": {
                ".env": os.path.exists(".env"),
                "templates/login.html": os.path.exists("templates/login.html"),
                "templates/dashboard.html": os.path.exists("templates/dashboard.html"),
                "static/style.css": os.path.exists("static/style.css"),
                "log_file": os.path.exists(LOG_FILE),
            },
            "log_info": {
                "file_path": str(LOG_FILE),
                "file_exists": os.path.exists(LOG_FILE),
                "file_size": os.path.getsize(LOG_FILE) if os.path.exists(LOG_FILE) else 0,
            }
        }
        return jsonify(info)
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}, 500

# --- Autenticação Simplificada ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        log.info("🔓 Acessando rota de login...")
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            log.info(f"📝 Tentativa de login: {username}")
            
            if username == ADMIN_USER and password == ADMIN_PASSWORD:
                session['logged_in'] = True
                log.info(f"✅ Login bem-sucedido para: {username}")
                return redirect(url_for('dashboard'))
            else:
                log.warning(f"❌ Login falhou para: {username}")
                return "Credenciais inválidas", 401
        
        log.info("📄 Renderizando página de login...")
        return render_template('login.html')
    except Exception as e:
        log.error(f"❌ Erro na rota login: {e}")
        traceback.print_exc()
        return f"Erro interno: {str(e)}", 500

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    log.info("👋 Usuário deslogado")
    return redirect(url_for('login'))

# --- Dashboard ---
@app.route('/')
def dashboard():
    try:
        log.info("🏠 Acessando dashboard...")
        if not session.get('logged_in'):
            log.info("🔒 Usuário não logado, redirecionando...")
            return redirect(url_for('login'))
        
        config_values = dotenv_values(".env") or {}
        bot_status = "Rodando" if bot_process and bot_process.poll() is None else "Parado"
        
        log.info("📄 Renderizando dashboard...")
        return render_template('dashboard.html', config=config_values, status=bot_status)
    except Exception as e:
        log.error(f"❌ Erro no dashboard: {e}")
        traceback.print_exc()
        return f"Erro no dashboard: {str(e)}", 500

# --- Configurações ---
@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        data = request.json
        log.info(f"💾 Salvando configurações: {list(data.keys())}")
        
        # Lê o .env existente
        current_config = dotenv_values(".env") or {}
        
        # Atualiza com os novos dados
        for key, value in data.items():
            if value:
                current_config[key.upper()] = value
                
        # Salva no arquivo
        with open(".env", "w") as f:
            for key, value in current_config.items():
                f.write(f"{key}={value}\n")
                
        log.info("✅ Configurações salvas")
        return jsonify(message="Configurações salvas com sucesso!")
    except Exception as e:
        log.error(f"❌ Erro ao salvar config: {e}")
        return jsonify(error=str(e)), 500

# --- Controle do Bot ---
@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_process
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        if bot_process and bot_process.poll() is None:
            return jsonify(message="Bot já está rodando"), 400
        
        # IMPORTANTE: NÃO remove o arquivo de log
        log_manager.rotate_log_if_needed()
        log_manager.append_session_separator()
        
        log.info("🤖 Iniciando bot...")
        bot_process = subprocess.Popen(["python", "-u", "bot_worker.py"])
        log.info(f"✅ Bot iniciado com PID: {bot_process.pid}")
        return jsonify(message="Bot iniciado!", pid=bot_process.pid)
    except Exception as e:
        log.error(f"❌ Erro ao iniciar bot: {e}")
        return jsonify(error=str(e)), 500

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_process
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        if bot_process and bot_process.poll() is None:
            log.info(f"⏹️ Parando bot PID: {bot_process.pid}")
            bot_process.terminate()
            bot_process.wait(timeout=5)
            bot_process = None
            return jsonify(message="Bot parado com sucesso")
        
        return jsonify(message="Bot não estava rodando"), 400
    except Exception as e:
        log.error(f"❌ Erro ao parar bot: {e}")
        return jsonify(error=str(e)), 500

# --- Lógica de Streaming de Logs com WebSocket MELHORADA ---
def tail_log_file():
    """Lê as novas linhas do arquivo de log e as envia para o cliente."""
    log.info("🔍 Iniciando thread de monitoramento de logs...")
    
    # Garante que o arquivo existe
    log_manager.ensure_log_file_exists()
    
    last_position = 0
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            # Vai para o final do arquivo
            f.seek(0, 2)
            last_position = f.tell()
            
            while True:
                # Verifica se o processo do bot ainda está vivo
                if bot_process is None or bot_process.poll() is not None:
                    log.info("🔍 Bot não está mais rodando, mas mantendo monitoramento...")
                    socketio.sleep(2)  # Verifica menos frequentemente
                    continue
                
                # Verifica se há novos dados
                current_position = f.tell()
                if current_position < last_position:
                    # Arquivo foi rotacionado ou truncado
                    f.seek(0)
                    last_position = 0
                
                line = f.readline()
                if line:
                    socketio.emit('new_log_line', {'line': line})
                    last_position = f.tell()
                else:
                    socketio.sleep(0.1)
                    
    except Exception as e:
        log.error(f"❌ Erro na thread de logs: {e}")

@socketio.on('connect')
def handle_connect():
    if not session.get('logged_in'):
        return False
        
    log.info("🔌 Cliente conectado ao dashboard")
    
    # SEMPRE envia o log completo para qualquer cliente que se conecta
    try:
        full_log_content = log_manager.get_full_log_content()
        emit('historical_logs', {
            'logs': full_log_content,
            'timestamp': time.time()
        })
        log.info(f"📜 Enviado log completo ({len(full_log_content)} chars) para cliente")
    except Exception as e:
        log.error(f"❌ Erro ao enviar log histórico: {e}")
        emit('historical_logs', {'logs': f"Erro ao carregar log: {str(e)}"})
    
    # Inicia thread de monitoramento se necessário
    global thread
    with thread_lock:
        if thread is None or not thread.is_alive():
            thread = socketio.start_background_task(target=tail_log_file)
            log.info("🧵 Thread de monitoramento de logs iniciada")

@socketio.on('disconnect')
def handle_disconnect():
    log.info("🔌 Cliente desconectado do dashboard")

# --- Error Handlers ---
@app.errorhandler(Exception)
def handle_exception(e):
    log.error(f"❌ Erro não tratado: {e}")
    traceback.print_exc()
    return f"Erro interno: {str(e)}", 500

if __name__ == '__main__':
    log.info("🚀 Iniciando aplicação em modo debug...")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)
