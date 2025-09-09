# main_app.py (v1.6 - Com Botão Reiniciar e Limpeza de Logs)
import os
import subprocess
import logging
import sys
import traceback
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_socketio import SocketIO, emit
from threading import Lock, Thread
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
    
    def clear_log_file(self):
        """Limpa o arquivo de log"""
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                f.write(f"# Log limpo e reiniciado em {timestamp}\n")
                f.write(f"🧹 LOGS ANTERIORES FORAM LIMPOS\n")
                f.write(f"{'='*80}\n")
            log.info(f"🧹 Log limpo: {self.log_file}")
            return True
        except Exception as e:
            log.error(f"❌ Erro ao limpar log: {e}")
            return False
    
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
    socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")
    log.info("✅ SocketIO inicializado com eventlet")
except Exception as e:
    log.error(f"❌ Erro ao inicializar SocketIO: {e}")
    sys.exit(1)

bot_process = None
monitor_thread = None
thread_lock = Lock()

# --- Health Check ---
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

# --- Endpoint para limpar logs ---
@app.route('/clear_logs', methods=['POST'])
def clear_logs():
    """API endpoint para limpar logs"""
    if not session.get('logged_in'):
        return jsonify(error="Não autorizado"), 403
    
    try:
        if log_manager.clear_log_file():
            # Emite evento via WebSocket para atualizar o frontend
            socketio.emit('log_cleared', {'message': 'Logs limpos com sucesso'})
            return jsonify(message="Logs limpos com sucesso!")
        else:
            return jsonify(error="Erro ao limpar logs"), 500
    except Exception as e:
        return jsonify(error=str(e)), 500

# --- Debug ---
@app.route('/debug')
def debug_info():
    """Endpoint para debug"""
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
                "static/app.js": os.path.exists("static/app.js"),
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

# --- Autenticação ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if username == ADMIN_USER and password == ADMIN_PASSWORD:
                session['logged_in'] = True
                log.info(f"✅ Login bem-sucedido para: {username}")
                return redirect(url_for('dashboard'))
            else:
                log.warning(f"❌ Login falhou para: {username}")
                return "Credenciais inválidas", 401
        
        return render_template('login.html')
    except Exception as e:
        log.error(f"❌ Erro na rota login: {e}")
        return f"Erro interno: {str(e)}", 500

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# --- Dashboard ---
@app.route('/')
def dashboard():
    try:
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        config_values = dotenv_values(".env") or {}
        bot_status = "Rodando" if bot_process and bot_process.poll() is None else "Parado"
        
        return render_template('dashboard.html', config=config_values, status=bot_status)
    except Exception as e:
        log.error(f"❌ Erro no dashboard: {e}")
        return f"Erro no dashboard: {str(e)}", 500

# --- Config ---
@app.route('/save_config', methods=['POST'])
def save_config():
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        data = request.json
        current_config = dotenv_values(".env") or {}
        
        for key, value in data.items():
            if value:
                current_config[key.upper()] = value
                
        with open(".env", "w") as f:
            for key, value in current_config.items():
                f.write(f"{key}={value}\n")
                
        return jsonify(message="Configurações salvas com sucesso!")
    except Exception as e:
        return jsonify(error=str(e)), 500

# --- Bot Control ---
@app.route('/start_bot', methods=['POST'])
def start_bot():
    global bot_process
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        if bot_process and bot_process.poll() is None:
            return jsonify(message="Bot já está rodando"), 400
        
        log_manager.rotate_log_if_needed()
        log_manager.append_session_separator()
        
        bot_process = subprocess.Popen(["python", "-u", "bot_worker.py"])
        log.info(f"✅ Bot iniciado com PID: {bot_process.pid}")
        return jsonify(message="Bot iniciado!", pid=bot_process.pid)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/stop_bot', methods=['POST'])
def stop_bot():
    global bot_process
    try:
        if not session.get('logged_in'): 
            return jsonify(error="Não autorizado"), 403
        
        if bot_process and bot_process.poll() is None:
            bot_process.terminate()
            bot_process.wait(timeout=5)
            bot_process = None
            return jsonify(message="Bot parado com sucesso")
        
        return jsonify(message="Bot não estava rodando"), 400
    except Exception as e:
        return jsonify(error=str(e)), 500

# --- NOVO: Reiniciar Bot ---
@app.route('/restart_bot', methods=['POST'])
def restart_bot():
    """Reinicia o bot e limpa os logs"""
    global bot_process
    try:
        if not session.get('logged_in'):
            return jsonify(error="Não autorizado"), 403
        
        log.info("🔄 Iniciando reinicialização do bot...")
        
        # 1. Para o bot se estiver rodando
        if bot_process and bot_process.poll() is None:
            log.info("⏹️ Parando bot atual...")
            bot_process.terminate()
            bot_process.wait(timeout=10)
            bot_process = None
            log.info("✅ Bot parado")
        
        # 2. Limpa os logs
        log.info("🧹 Limpando logs...")
        if log_manager.clear_log_file():
            log.info("✅ Logs limpos")
            # Emite evento para atualizar frontend
            socketio.emit('log_cleared', {'message': 'Logs limpos - Bot reiniciando...'})
        
        # 3. Aguarda um momento
        time.sleep(2)
        
        # 4. Rotaciona se necessário e adiciona separador
        log_manager.rotate_log_if_needed()
        log_manager.append_session_separator()
        
        # 5. Inicia o bot novamente
        bot_process = subprocess.Popen(["python", "-u", "bot_worker.py"])
        log.info(f"🚀 Bot reiniciado com PID: {bot_process.pid}")
        
        return jsonify(message="Bot reiniciado e logs limpos!", pid=bot_process.pid)
        
    except Exception as e:
        log.error(f"❌ Erro ao reiniciar bot: {e}")
        return jsonify(error=str(e)), 500

# --- Thread de monitoramento de logs ---
def monitor_log_file():
    """Thread para monitorar arquivo de log"""
    log.info("🔍 Iniciando monitoramento de logs...")
    
    last_position = 0
    
    while True:
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    f.seek(last_position)
                    new_lines = f.read()
                    
                    if new_lines:
                        # Envia novas linhas via WebSocket
                        socketio.emit('new_log_line', {'line': new_lines})
                        last_position = f.tell()
            
            time.sleep(0.5)  # Check a cada 0.5 segundos
            
        except Exception as e:
            log.error(f"❌ Erro no monitoramento: {e}")
            time.sleep(2)

# --- WebSocket Events ---
@socketio.on('connect')
def handle_connect(auth=None):
    try:
        if not session.get('logged_in'):
            return False
            
        log.info("🔌 Cliente conectado ao dashboard")
        
        # Envia log completo
        full_log_content = log_manager.get_full_log_content()
        emit('historical_logs', {
            'logs': full_log_content,
            'timestamp': time.time()
        })
        
        # Inicia thread de monitoramento se necessário
        global monitor_thread
        with thread_lock:
            if monitor_thread is None or not monitor_thread.is_alive():
                monitor_thread = Thread(target=monitor_log_file, daemon=True)
                monitor_thread.start()
                log.info("🧵 Thread de monitoramento iniciada")
        
        return True
        
    except Exception as e:
        log.error(f"❌ Erro no connect: {e}")
        return False

@socketio.on('disconnect')
def handle_disconnect():
    log.info("🔌 Cliente desconectado")

# --- Error Handlers ---
@app.errorhandler(Exception)
def handle_exception(e):
    log.error(f"❌ Erro não tratado: {e}")
    return f"Erro interno: {str(e)}", 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)
