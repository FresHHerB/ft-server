# bot_worker.py - Enhanced Logging Version
import logging
import time
import random
import httpx
from bs4 import BeautifulSoup
from config import (BASE_URL, JOGO_SLUG, DEPENDENTE_ID, TARGET_SECTOR_SLUG,
                    MAX_WATCH_ATTEMPTS, WATCH_INTERVAL_MIN, WATCH_INTERVAL_MAX,
                    HEADERS, DEBUG_HTML_FILE, SETORES_URL, CATEGORIA_URL)
from session_manager import get_authenticated_session

# Configuração do logging para este processo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("log_reserva_final.txt", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("bot-worker")

def analyze_and_log_sectors(soup: BeautifulSoup) -> bool:
    """
    Analisa setores e mostra apenas o setor alvo + setores disponíveis
    Retorna True se o setor alvo estiver disponível
    """
    all_sector_elements = soup.find_all(class_="sector")
    
    if not all_sector_elements:
        log.warning("⚠️ Nenhum setor encontrado na página!")
        return False
    
    log.info("  📊 [STATUS ATUAL DOS SETORES]")
    
    target_found_and_available = False
    available_sectors = []
    
    # Analisa todos os setores
    for sector_element in all_sector_elements:
        sector_slug = sector_element.get('id', 'desconhecido')
        is_disabled = 'disabled' in sector_element.get('class', [])
        
        if sector_slug == TARGET_SECTOR_SLUG:
            # Setor alvo - sempre mostra
            status = "DISPONÍVEL" if not is_disabled else "Indisponível"
            icon = "🎯" if not is_disabled else "❌"
            log.info(f"  {icon} Setor '{sector_slug.upper()}': {status} <--- ALVO")
            if not is_disabled:
                target_found_and_available = True
        elif not is_disabled:
            # Outros setores - apenas se disponíveis
            available_sectors.append(sector_slug)
    
    # Mostra apenas setores disponíveis (além do alvo)
    if available_sectors:
        for sector in sorted(available_sectors):
            log.info(f"  ✅ Setor '{sector.upper()}': DISPONÍVEL")
    
    return target_found_and_available

def watch_and_attack(session_cookies: dict) -> bool:
    log.info("▶️ FASE 2: Iniciando Vigilância do Setor via API (httpx)")
    target_sector_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/"

    with httpx.Client(cookies=session_cookies, headers=HEADERS, timeout=30.0, follow_redirects=True) as s:
        for attempt in range(1, MAX_WATCH_ATTEMPTS + 1):
            log.info(f"🔍 --- Vigilância #{attempt}/{MAX_WATCH_ATTEMPTS} ---")
            try:
                s.headers['Referer'] = CATEGORIA_URL
                response = s.get(SETORES_URL)
                DEBUG_HTML_FILE.write_text(response.text, encoding='utf-8')

                if "/auth/login/" in str(response.url):
                    log.error("❌ FALHA CRÍTICA: Sessão expirou!")
                    return False

                soup = BeautifulSoup(response.text, "html.parser")
                
                # Usa a nova função de análise melhorada
                target_available = analyze_and_log_sectors(soup)
                
                if target_available:
                    log.info(f"🚨 DETECTADO! Setor '{TARGET_SECTOR_SLUG.upper()}' está disponível! Iniciando ataque...")
                    
                    # Executa o ataque
                    s.headers['Referer'] = SETORES_URL
                    final_get_response = s.get(target_sector_url)
                    final_get_response.raise_for_status()
                    
                    csrf_token = BeautifulSoup(final_get_response.text, "html.parser").find("input", {"name": "csrfmiddlewaretoken"})["value"]
                    payload = {"csrfmiddlewaretoken": csrf_token, "dependentes": DEPENDENTE_ID}
                    s.headers['Referer'] = target_sector_url
                    post_response = s.post(target_sector_url, data=payload)

                    if post_response.history and "/ingressos/" in post_response.history[0].headers.get("location", ""):
                        log.info(f"🎉 SUCESSO! RESERVA REALIZADA! URL: {BASE_URL}{post_response.history[0].headers['location']}")
                        return True
                    else:
                        log.error("❌ ATAQUE FALHOU! Oportunidade perdida.")
                        return True
                else:
                    # Calcula próximo intervalo
                    next_interval = random.uniform(WATCH_INTERVAL_MIN, WATCH_INTERVAL_MAX)
                    log.info(f"⏳ Aguardando {next_interval:.2f} segundos...")

            except Exception as e:
                log.exception(f"💥 Erro inesperado durante a vigilância:")

            time.sleep(random.uniform(WATCH_INTERVAL_MIN, WATCH_INTERVAL_MAX))
        
    log.error(f"❌ Esgotadas as {MAX_WATCH_ATTEMPTS} tentativas de vigilância.")
    return False

if __name__ == "__main__":
    log.info("🚀 Bot Worker iniciado!")
    log.info(f"🎯 Setor alvo: {TARGET_SECTOR_SLUG.upper()}")
    log.info(f"🎮 Jogo: {JOGO_SLUG}")
    log.info(f"👤 Dependente ID: {DEPENDENTE_ID}")
    log.info(f"🔄 Máximo de tentativas: {MAX_WATCH_ATTEMPTS}")
    log.info(f"⏱️ Intervalo: {WATCH_INTERVAL_MIN}s - {WATCH_INTERVAL_MAX}s")
    log.info("=" * 60)
    
    while True:
        log.info("🔑 Obtendo sessão autenticada...")
        cookies = get_authenticated_session()
        if cookies:
            log.info("✅ Sessão obtida com sucesso!")
            completed = watch_and_attack(cookies)
            if completed:
                log.info("🏁 Processo concluído. Encerrando o worker.")
                break
        else:
            log.error("❌ Falha ao obter sessão. Tentando novamente em 5 minutos...")
            time.sleep(300)
