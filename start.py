#!/usr/bin/env python3
# start.py - Script de inicialização e diagnóstico atualizado

import os
import sys
import subprocess
import logging
from pathlib import Path

def setup_logging():
    """Configura o logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | STARTUP | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler()]
    )
    return logging.getLogger("startup")

def check_environment():
    """Verifica o ambiente e dependências"""
    log = logging.getLogger("startup")
    log.info("🔍 Verificando ambiente...")
    
    # Verifica se o arquivo .env existe
    if not Path(".env").exists():
        log.warning("⚠️ Arquivo .env não encontrado!")
        return False
    
    # Verifica variáveis críticas
    from dotenv import load_dotenv
    load_dotenv()
    
    # ATUALIZADO: Removido DEPENDENTE_ID da lista de variáveis críticas
    critical_vars = [
        "ADMIN_USER", "ADMIN_PASSWORD", 
        "FT_USERNAME", "FT_PASSWORD",
        "JOGO_SLUG", "TARGET_SECTOR_SLUG"
    ]
    
    missing_vars = []
    for var in critical_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        log.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing_vars)}")
        return False
    
    log.info("✅ Variáveis de ambiente OK")
    
    # Informa sobre a nova funcionalidade de dependentes
    log.info("🆕 IDs de dependentes: EXTRAÇÃO AUTOMÁTICA habilitada")
    log.info("   💡 Não é mais necessário configurar DEPENDENTE_ID manualmente")
    
    return True

def check_dependencies():
    """Verifica se as dependências estão instaladas"""
    log = logging.getLogger("startup")
    log.info("📦 Verificando dependências...")
    
    try:
        import flask
        import flask_socketio
        import playwright
        import httpx
        import bs4
        import requests
        log.info("✅ Todas as dependências estão instaladas")
        return True
    except ImportError as e:
        log.error(f"❌ Dependência faltando: {e}")
        log.info("💡 Execute: pip install -r requirements.txt")
        return False

def check_ports():
    """Verifica se a porta está disponível"""
    log = logging.getLogger("startup")
    import socket
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 5001))
        log.info("✅ Porta 5001 disponível")
        return True
    except OSError:
        log.warning("⚠️ Porta 5001 já está em uso")
        log.info("💡 Tente parar outros processos ou use outra porta")
        return False

def check_project_integrity():
    """Verifica integridade do projeto"""
    log = logging.getLogger("startup")
    log.info("🔧 Verificando integridade do projeto...")
    
    required_files = [
        "main_app.py",
        "bot_worker.py", 
        "session_manager.py",
        "captcha_solvers.py",
        "config.py",
        "templates/dashboard.html",
        "templates/login.html",
        "static/app.js",
        "static/style.css"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        log.error(f"❌ Arquivos faltando: {', '.join(missing_files)}")
        return False
    
    log.info("✅ Todos os arquivos do projeto encontrados")
    return True

def run_diagnostics():
    """Executa diagnósticos completos"""
    log = setup_logging()
    log.info("🚀 Iniciando diagnósticos do projeto...")
    log.info("=" * 60)
    
    checks = [
        ("Ambiente", check_environment),
        ("Dependências", check_dependencies),
        ("Integridade do Projeto", check_project_integrity),
        ("Porta", check_ports)
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            log.info(f"📋 Verificando: {name}")
            if not check_func():
                all_passed = False
                log.error(f"❌ Check {name} FALHOU")
            else:
                log.info(f"✅ Check {name} OK")
        except Exception as e:
            log.error(f"❌ Erro no check {name}: {e}")
            all_passed = False
        
        log.info("-" * 40)
    
    if all_passed:
        log.info("🎉 Todos os checks passaram! Iniciando aplicação...")
        log.info("🔥 Funcionalidades ativas:")
        log.info("   ✅ Dashboard web em http://localhost:5001")
        log.info("   ✅ Logs em tempo real via WebSocket")
        log.info("   ✅ Extração automática de IDs de dependentes")
        log.info("   ✅ Resolução automática de CAPTCHA")
        log.info("   ✅ Vigilância contínua de setores")
        log.info("=" * 60)
        return True
    else:
        log.error("❌ Alguns checks falharam. Verifique os logs acima.")
        return False

def start_application():
    """Inicia a aplicação"""
    log = logging.getLogger("startup")
    
    if not run_diagnostics():
        log.error("💥 Falha nos diagnósticos. Não é possível iniciar.")
        sys.exit(1)
    
    try:
        # Tenta importar a aplicação para verificar se não há erros de sintaxe
        log.info("🔍 Verificando sintaxe da aplicação...")
        import main_app
        log.info("✅ Sintaxe OK")
        
        # Inicia a aplicação
        log.info("🚀 Iniciando servidor Flask...")
        log.info("🌐 Acesse: http://localhost:5001")
        log.info("🔑 Use as credenciais configuradas no .env")
        
        main_app.socketio.run(
            main_app.app, 
            host='0.0.0.0', 
            port=5001, 
            debug=False
        )
    except Exception as e:
        log.error(f"❌ Erro ao iniciar aplicação: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        start_application()
    except KeyboardInterrupt:
        print("\n⚠️ Aplicação interrompida pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Erro fatal: {e}")
        sys.exit(1)
