# bot_worker.py - Versão Corrigida e Otimizada
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
    Analisa setores de forma otimizada e mostra apenas informações relevantes.
    Retorna True se o setor alvo estiver disponível.
    """
    all_sector_elements = soup.find_all(class_="sector")
    
    if not all_sector_elements:
        log.warning("⚠️ Nenhum setor encontrado na página!")
        return False
    
    log.info("  📊 [ANÁLISE DOS SETORES]")
    
    target_found_and_available = False
    available_sectors = []
    unavailable_count = 0
    
    # Analisa todos os setores de forma eficiente
    for sector_element in all_sector_elements:
        sector_slug = sector_element.get('id', 'desconhecido')
        is_disabled = 'disabled' in sector_element.get('class', [])
        
        if sector_slug == TARGET_SECTOR_SLUG:
            # Setor alvo - sempre mostra com destaque
            if not is_disabled:
                log.info(f"  🎯 Setor '{sector_slug.upper()}': ✅ DISPONÍVEL <--- ALVO ENCONTRADO!")
                target_found_and_available = True
            else:
                log.info(f"  🎯 Setor '{sector_slug.upper()}': ❌ Indisponível <--- ALVO")
        elif not is_disabled:
            # Outros setores disponíveis
            available_sectors.append(sector_slug)
        else:
            unavailable_count += 1
    
    # Mostra resumo dos outros setores
    if available_sectors:
        # Mostra apenas os primeiros 5 para não poluir o log
        show_sectors = available_sectors[:5]
        log.info(f"  ✅ Outros setores disponíveis: {', '.join(show_sectors).upper()}")
        if len(available_sectors) > 5:
            log.info(f"  ➕ ... e mais {len(available_sectors) - 5} setores disponíveis")
    
    if unavailable_count > 0:
        log.info(f"  ❌ Setores indisponíveis: {unavailable_count}")
    
    log.info(f"  📈 Total analisado: {len(all_sector_elements)} setores")
    
    return target_found_and_available

def watch_and_attack(session_cookies: dict) -> bool:
    """
    Vigilância otimizada do setor alvo com melhor handling de erros.
    """
    log.info("▶️ FASE 2: Iniciando Vigilância Otimizada do Setor")
    log.info(f"🎯 Alvo: {TARGET_SECTOR_SLUG.upper()}")
    target_sector_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/"

    with httpx.Client(
        cookies=session_cookies, 
        headers=HEADERS, 
        timeout=30.0, 
        follow_redirects=True
    ) as client:
        
        for attempt in range(1, MAX_WATCH_ATTEMPTS + 1):
            log.info(f"🔍 --- Vigilância #{attempt}/{MAX_WATCH_ATTEMPTS} ---")
            
            try:
                # === VERIFICAÇÃO DA SESSÃO ===
                client.headers['Referer'] = CATEGORIA_URL
                response = client.get(SETORES_URL)
                
                # Verifica se a sessão expirou
                if "/auth/login/" in str(response.url):
                    log.error("❌ FALHA CRÍTICA: Sessão expirou! Necessário novo login.")
                    return False
                
                # Salva HTML para debug (opcional)
                DEBUG_HTML_FILE.write_text(response.text, encoding='utf-8')
                
                # === ANÁLISE DOS SETORES ===
                soup = BeautifulSoup(response.text, "html.parser")
                target_available = analyze_and_log_sectors(soup)
                
                # === ATAQUE SE DISPONÍVEL ===
                if target_available:
                    log.info(f"🚨 OPORTUNIDADE DETECTADA! Setor '{TARGET_SECTOR_SLUG.upper()}' disponível!")
                    log.info("⚡ Iniciando sequência de ataque...")
                    
                    try:
                        # 1. Acessa a página do setor
                        client.headers['Referer'] = SETORES_URL
                        sector_response = client.get(target_sector_url)
                        sector_response.raise_for_status()
                        
                        log.info("✅ Página do setor acessada")
                        
                        # 2. Extrai CSRF token
                        sector_soup = BeautifulSoup(sector_response.text, "html.parser")
                        csrf_element = sector_soup.find("input", {"name": "csrfmiddlewaretoken"})
                        
                        if not csrf_element:
                            log.error("❌ CSRF token não encontrado!")
                            return True  # Encerra para evitar spam
                        
                        csrf_token = csrf_element.get("value")
                        log.info("🔑 CSRF token extraído")
                        
                        # 3. Prepara payload para reserva
                        payload = {
                            "csrfmiddlewaretoken": csrf_token,
                            "dependentes": DEPENDENTE_ID
                        }
                        
                        # 4. Executa reserva
                        client.headers['Referer'] = target_sector_url
                        log.info("🎯 Executando reserva...")
                        
                        post_response = client.post(target_sector_url, data=payload)
                        
                        # 5. Verifica resultado
                        if post_response.history:
                            redirect_location = post_response.history[0].headers.get("location", "")
                            if "/ingressos/" in redirect_location:
                                success_url = f"{BASE_URL}{redirect_location}"
                                log.info(f"🎉 SUCESSO TOTAL! RESERVA CONFIRMADA!")
                                log.info(f"🎫 URL da reserva: {success_url}")
                                log.info("🏆 MISSÃO CUMPRIDA! Bot concluído com êxito.")
                                return True
                            else:
                                log.warning(f"⚠️ Redirecionamento inesperado: {redirect_location}")
                        
                        # Verifica se está na página de ingressos
                        if "/ingressos/" in post_response.url.path:
                            log.info(f"🎉 SUCESSO! Página de ingressos alcançada!")
                            log.info(f"🎫 URL final: {post_response.url}")
                            return True
                        
                        log.error("❌ ATAQUE FALHOU! Oportunidade não convertida.")
                        log.warning("🔄 Continuando vigilância...")
                        
                    except Exception as attack_error:
                        log.error(f"💥 Erro durante ataque: {attack_error}")
                        log.warning("🔄 Continuando vigilância...")
                
                else:
                    # Setor não disponível - continua vigilância
                    next_interval = random.uniform(WATCH_INTERVAL_MIN, WATCH_INTERVAL_MAX)
                    log.info(f"⏳ Próxima verificação em {next_interval:.1f}s...")
                    time.sleep(next_interval)
                    continue

            except httpx.RequestError as req_error:
                log.error(f"🌐 Erro de rede: {req_error}")
                log.info("⏳ Aguardando 10s antes de tentar novamente...")
                time.sleep(10)
                continue
                
            except Exception as unexpected_error:
                log.exception(f"💥 Erro inesperado na vigilância:")
                time.sleep(5)
                continue
        
    log.error(f"❌ Esgotadas as {MAX_WATCH_ATTEMPTS} tentativas de vigilância.")
    log.info("⏰ Limite de tentativas atingido. Encerrando.")
    return False

def main():
    """Função principal do bot worker."""
    log.info("🚀 BOT WORKER INICIADO!")
    log.info("=" * 60)
    log.info(f"🎯 Setor alvo: {TARGET_SECTOR_SLUG.upper()}")
    log.info(f"🎮 Jogo: {JOGO_SLUG}")
    log.info(f"👤 Dependente ID: {DEPENDENTE_ID}")
    log.info(f"🔄 Máximo de tentativas: {MAX_WATCH_ATTEMPTS}")
    log.info(f"⏱️ Intervalo: {WATCH_INTERVAL_MIN}s - {WATCH_INTERVAL_MAX}s")
    log.info("=" * 60)
    
    attempt_count = 0
    max_login_attempts = 5
    
    while attempt_count < max_login_attempts:
        attempt_count += 1
        log.info(f"🔑 Tentativa de autenticação #{attempt_count}/{max_login_attempts}")
        
        # Obtém sessão autenticada
        cookies = get_authenticated_session()
        
        if cookies:
            log.info("✅ Sessão autenticada obtida com sucesso!")
            log.info("🔍 Iniciando processo de vigilância...")
            
            # Executa vigilância
            mission_completed = watch_and_attack(cookies)
            
            if mission_completed:
                log.info("🏁 MISSÃO CONCLUÍDA COM SUCESSO! Encerrando worker.")
                break
            else:
                log.warning("⚠️ Vigilância finalizada sem sucesso.")
                
                if attempt_count < max_login_attempts:
                    log.info(f"🔄 Tentando nova autenticação em 2 minutos...")
                    time.sleep(120)  # Aguarda 2 minutos antes de tentar novo login
                else:
                    log.error("❌ Máximo de tentativas de login atingido.")
                    break
        else:
            log.error(f"❌ Falha na autenticação (tentativa {attempt_count})")
            
            if attempt_count < max_login_attempts:
                wait_time = min(300 * attempt_count, 1800)  # Aumenta o tempo de espera, máx 30min
                log.info(f"⏳ Aguardando {wait_time//60}min antes da próxima tentativa...")
                time.sleep(wait_time)
            else:
                log.error("❌ Máximo de tentativas de autenticação atingido.")
                break
    
    log.info("🔚 Worker finalizado.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("⚠️ Worker interrompido pelo usuário.")
    except Exception as e:
        log.exception(f"💥 Erro fatal no worker: {e}")
    finally:
        log.info("👋 Bot Worker encerrado.")
