# bot_worker.py - Versão com Extração Dinâmica de Dependentes
import logging
import time
import random
import httpx
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from config import (BASE_URL, JOGO_SLUG, TARGET_SECTOR_SLUG,
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

def extract_dependentes_from_page(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extrai todos os dependentes disponíveis da página do setor.
    Retorna lista de dicionários com informações dos dependentes.
    """
    dependentes = []
    
    # Procura por inputs com name="dependentes"
    dependente_inputs = soup.find_all("input", {"name": "dependentes", "type": "checkbox"})
    
    if not dependente_inputs:
        log.warning("⚠️ Nenhum input de dependente encontrado na página")
        return dependentes
    
    log.info(f"🔍 Encontrados {len(dependente_inputs)} dependentes disponíveis:")
    
    for input_elem in dependente_inputs:
        dependente_id = input_elem.get('value', '')
        dependente_html_id = input_elem.get('id', '')
        
        # Tenta extrair o nome do dependente do label associado
        dependente_name = "Desconhecido"
        
        # Procura pelo label associado
        if dependente_html_id:
            label = soup.find("label", {"for": dependente_html_id})
            if label:
                # Remove texto do input e pega só o nome
                name_text = label.get_text(strip=True)
                # Remove quebras de linha e espaços extras
                dependente_name = re.sub(r'\s+', ' ', name_text).strip()
        
        dependente_info = {
            'id': dependente_id,
            'name': dependente_name,
            'html_id': dependente_html_id
        }
        
        dependentes.append(dependente_info)
        log.info(f"  👤 ID: {dependente_id} | Nome: {dependente_name}")
    
    return dependentes

def select_best_dependente(dependentes: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    Seleciona o melhor dependente para usar na reserva.
    Por enquanto, usa o primeiro disponível, mas pode ser expandido com lógica mais complexa.
    """
    if not dependentes:
        log.error("❌ Nenhum dependente disponível para seleção")
        return None
    
    # Por enquanto, usa o primeiro dependente disponível
    selected = dependentes[0]
    log.info(f"🎯 Dependente selecionado: {selected['name']} (ID: {selected['id']})")
    
    return selected

def detect_sectors_page_type(soup: BeautifulSoup) -> str:
    """
    Detecta o tipo de página de setores.
    Retorna: 'svg_map', 'link_list', ou 'unknown'
    """
    # Verifica se existe mapa SVG com setores
    svg_sectors = soup.find_all(class_="sector")
    if svg_sectors:
        log.info("  📊 Tipo de página detectado: MAPA SVG")
        return "svg_map"
    
    # Verifica se existe lista de links para setores
    sector_links = soup.find_all("a", href=re.compile(r"/setor/[^/]+/modo-de-compra/"))
    if sector_links:
        log.info("  📊 Tipo de página detectado: LISTA DE LINKS")
        return "link_list"
    
    log.warning("  ⚠️ Tipo de página DESCONHECIDO - nenhum formato reconhecido")
    return "unknown"

def analyze_svg_sectors(soup: BeautifulSoup) -> bool:
    """
    Analisa setores no formato de mapa SVG (formato original).
    Retorna True se o setor alvo estiver disponível.
    """
    all_sector_elements = soup.find_all(class_="sector")
    
    if not all_sector_elements:
        log.warning("⚠️ Nenhum setor SVG encontrado!")
        return False
    
    log.info("  📊 [ANÁLISE DOS SETORES - MAPA SVG]")
    
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
        show_sectors = available_sectors[:5]
        log.info(f"  ✅ Outros setores disponíveis: {', '.join(show_sectors).upper()}")
        if len(available_sectors) > 5:
            log.info(f"  ➕ ... e mais {len(available_sectors) - 5} setores disponíveis")
    
    if unavailable_count > 0:
        log.info(f"  ❌ Setores indisponíveis: {unavailable_count}")
    
    log.info(f"  📈 Total analisado: {len(all_sector_elements)} setores")
    
    return target_found_and_available

def analyze_link_sectors(soup: BeautifulSoup) -> bool:
    """
    Analisa setores no formato de lista de links.
    Retorna True se o setor alvo estiver disponível.
    """
    # Procura por links que seguem o padrão /setor/NOME-SETOR/modo-de-compra/
    sector_links = soup.find_all("a", href=re.compile(r"/setor/[^/]+/modo-de-compra/"))
    
    if not sector_links:
        log.warning("⚠️ Nenhum link de setor encontrado!")
        return False
    
    log.info("  📊 [ANÁLISE DOS SETORES - LISTA DE LINKS]")
    
    target_found_and_available = False
    available_sectors = []
    
    # Analisa todos os links de setores
    for link in sector_links:
        href = link.get('href', '')
        
        # Extrai o slug do setor do link
        # Exemplo: /jogos/corinthians-x-sao-jose-cpb25/setor/cadeira-vip/modo-de-compra/
        # Padrão: /setor/([^/]+)/modo-de-compra/
        match = re.search(r"/setor/([^/]+)/modo-de-compra/", href)
        if not match:
            continue
            
        sector_slug = match.group(1)
        
        # Tenta extrair o nome do setor do texto do link
        sector_text = link.get_text(strip=True) if link.get_text(strip=True) else sector_slug.upper()
        
        if sector_slug == TARGET_SECTOR_SLUG:
            # Setor alvo encontrado - se existe o link, está disponível
            log.info(f"  🎯 Setor '{sector_slug.upper()}' ({sector_text}): ✅ DISPONÍVEL <--- ALVO ENCONTRADO!")
            target_found_and_available = True
        else:
            # Outros setores disponíveis
            available_sectors.append(f"{sector_slug} ({sector_text})")
    
    # Mostra resumo dos outros setores
    if available_sectors:
        show_sectors = available_sectors[:3]  # Reduzido para 3 porque os nomes são maiores
        log.info(f"  ✅ Outros setores disponíveis: {', '.join(show_sectors)}")
        if len(available_sectors) > 3:
            log.info(f"  ➕ ... e mais {len(available_sectors) - 3} setores disponíveis")
    
    log.info(f"  📈 Total analisado: {len(sector_links)} setores")
    
    return target_found_and_available

def analyze_and_log_sectors(soup: BeautifulSoup) -> bool:
    """
    Analisa setores de forma inteligente, detectando o tipo de página.
    Retorna True se o setor alvo estiver disponível.
    """
    # Detecta o tipo de página
    page_type = detect_sectors_page_type(soup)
    
    if page_type == "svg_map":
        return analyze_svg_sectors(soup)
    elif page_type == "link_list":
        return analyze_link_sectors(soup)
    else:
        log.error("❌ Tipo de página não reconhecido - impossível analisar setores")
        
        # Debug: salva conteúdo para análise
        debug_content = soup.get_text()[:500]
        log.info(f"  🔍 Debug - Primeiros 500 chars: {debug_content}")
        
        # Verifica se tem algum indicador de setores
        if "setor" in debug_content.lower():
            log.info("  💡 A palavra 'setor' foi encontrada, mas formato não reconhecido")
        
        return False

def get_target_sector_url() -> str:
    """
    Constrói a URL do setor alvo baseada no formato atual.
    Mantém compatibilidade com ambos os formatos.
    """
    # URL padrão (formato antigo)
    standard_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/"
    
    # URL com modo-de-compra (formato novo)
    new_format_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/modo-de-compra/"
    
    # Por padrão, retorna o formato padrão
    # A lógica do ataque tentará ambos se necessário
    return standard_url

def attempt_sector_attack(client: httpx.Client, soup: BeautifulSoup) -> bool:
    """
    Tenta atacar o setor alvo com estratégias múltiplas e extração dinâmica de dependentes.
    """
    log.info("⚡ Iniciando sequência de ataque...")
    
    # Estratégia 1: URL padrão (formato SVG)
    standard_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/"
    
    # Estratégia 2: URL com modo-de-compra (formato lista)
    modo_compra_url = f"{BASE_URL}/jogos/{JOGO_SLUG}/setor/{TARGET_SECTOR_SLUG}/modo-de-compra/"
    
    # Estratégia 3: Procurar o link exato na página atual (para formato lista)
    direct_link = None
    sector_links = soup.find_all("a", href=re.compile(rf"/setor/{re.escape(TARGET_SECTOR_SLUG)}/modo-de-compra/"))
    if sector_links:
        direct_link = BASE_URL + sector_links[0].get('href')
        log.info(f"  🔗 Link direto encontrado: {direct_link}")
    
    # Lista de URLs para tentar em ordem de prioridade
    urls_to_try = []
    
    if direct_link:
        urls_to_try.append(("Link Direto", direct_link))
    
    urls_to_try.extend([
        ("Padrão", standard_url),
        ("Modo Compra", modo_compra_url)
    ])
    
    for strategy_name, target_url in urls_to_try:
        try:
            log.info(f"  🎯 Tentativa {strategy_name}: {target_url}")
            
            # 1. Acessa a página do setor
            client.headers['Referer'] = SETORES_URL
            sector_response = client.get(target_url)
            
            # Verifica se houve redirecionamento para login (sessão expirou)
            if "/auth/login/" in str(sector_response.url):
                log.error("❌ SESSÃO EXPIROU durante o ataque!")
                return False
            
            # Verifica se a resposta é válida
            if sector_response.status_code != 200:
                log.warning(f"  ⚠️ {strategy_name} retornou status {sector_response.status_code}")
                continue
            
            log.info(f"  ✅ {strategy_name}: Página acessada com sucesso")
            
            # 2. Analisa o conteúdo da página do setor
            sector_soup = BeautifulSoup(sector_response.text, "html.parser")
            
            # Verifica se está realmente na página do setor correto
            if TARGET_SECTOR_SLUG.upper() not in sector_response.text.upper():
                log.warning(f"  ⚠️ {strategy_name}: Página não contém referência ao setor alvo")
                continue
            
            # 3. NOVA FUNCIONALIDADE: Extrai dependentes dinamicamente
            log.info(f"  👥 {strategy_name}: Extraindo dependentes da página...")
            dependentes = extract_dependentes_from_page(sector_soup)
            
            if not dependentes:
                log.error(f"  ❌ {strategy_name}: Nenhum dependente encontrado na página")
                continue
            
            # Seleciona o melhor dependente
            selected_dependente = select_best_dependente(dependentes)
            if not selected_dependente:
                log.error(f"  ❌ {strategy_name}: Falha na seleção de dependente")
                continue
            
            # 4. Extrai CSRF token
            csrf_element = sector_soup.find("input", {"name": "csrfmiddlewaretoken"})
            if not csrf_element:
                log.warning(f"  ⚠️ {strategy_name}: CSRF token não encontrado")
                continue
            
            csrf_token = csrf_element.get("value")
            log.info(f"  🔑 {strategy_name}: CSRF token extraído")
            
            # 5. Prepara payload para reserva com dependente selecionado
            payload = {
                "csrfmiddlewaretoken": csrf_token,
                "dependentes": selected_dependente['id']  # Usa ID extraído dinamicamente
            }
            
            log.info(f"  📋 {strategy_name}: Payload preparado com dependente {selected_dependente['name']}")
            
            # 6. Executa reserva
            client.headers['Referer'] = target_url
            log.info(f"  🎯 {strategy_name}: Executando reserva...")
            
            post_response = client.post(target_url, data=payload)
            
            # 7. Verifica resultado
            if post_response.history:
                redirect_location = post_response.history[0].headers.get("location", "")
                if "/ingressos/" in redirect_location:
                    success_url = f"{BASE_URL}{redirect_location}"
                    log.info(f"🎉 SUCESSO TOTAL! RESERVA CONFIRMADA via {strategy_name}!")
                    log.info(f"🎫 URL da reserva: {success_url}")
                    log.info(f"👤 Dependente usado: {selected_dependente['name']} (ID: {selected_dependente['id']})")
                    log.info("🏆 MISSÃO CUMPRIDA! Bot concluído com êxito.")
                    return True
                else:
                    log.warning(f"  ⚠️ {strategy_name}: Redirecionamento inesperado: {redirect_location}")
            
            # Verifica se está na página de ingressos
            if "/ingressos/" in post_response.url.path:
                log.info(f"🎉 SUCESSO! Reserva confirmada via {strategy_name}!")
                log.info(f"🎫 URL final: {post_response.url}")
                log.info(f"👤 Dependente usado: {selected_dependente['name']} (ID: {selected_dependente['id']})")
                return True
            
            log.warning(f"  ❌ {strategy_name}: Tentativa falhou")
            
        except Exception as attack_error:
            log.error(f"  💥 Erro na tentativa {strategy_name}: {attack_error}")
            continue
    
    log.error("❌ TODAS AS ESTRATÉGIAS DE ATAQUE FALHARAM!")
    return False

def watch_and_attack(session_cookies: dict) -> bool:
    """
    Vigilância otimizada do setor alvo com suporte a múltiplos formatos.
    """
    log.info("▶️ FASE 2: Iniciando Vigilância Otimizada do Setor")
    log.info(f"🎯 Alvo: {TARGET_SECTOR_SLUG.upper()}")

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
                    
                    attack_success = attempt_sector_attack(client, soup)
                    
                    if attack_success:
                        return True
                    else:
                        log.error("❌ ATAQUE FALHOU! Oportunidade não convertida.")
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
    log.info(f"👥 Dependentes: EXTRAÇÃO DINÂMICA")
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
