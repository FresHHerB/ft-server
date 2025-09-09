# session_manager.py - Versão Robusta e Otimizada
import logging
import re
import time
from typing import Dict, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (LOGIN_URL, FT_USERNAME, FT_PASSWORD, CAPTCHA_SOLVE_TIMEOUT,
                    JOGOS_URL, CATEGORIA_URL, CATEGORIA_ID, SETORES_URL, HEADERS, JOGO_SLUG, BASE_URL)
from captcha_solvers import solve_with_openai, solve_with_2captcha

log = logging.getLogger(__name__)

def get_authenticated_session() -> Optional[Dict[str, str]]:
    """
    Orquestra o processo de login otimizado e aquecimento da sessão.
    """
    log.info("▶️ FASE 1: Iniciando Login e Aquecimento via Navegador")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # headless=True para produção
        context = browser.new_context(user_agent=HEADERS["user-agent"])
        page = context.new_page()
        
        try:
            # === SEÇÃO DE LOGIN ===
            log.info("🔐 Iniciando processo de login...")
            page.goto(LOGIN_URL, timeout=60000)
            
            # Preenche credenciais
            page.fill("input#id_username", FT_USERNAME)
            page.fill("input#id_password", FT_PASSWORD)
            log.info("✅ Credenciais preenchidas")

            login_successful = False
            
            # Máximo 2 tentativas de login
            for attempt in range(1, 3):
                log.info(f"--- Tentativa de Login #{attempt} ---")
                
                # Clica no checkbox do reCAPTCHA
                try:
                    anchor_frame = page.frame_locator('iframe[src*="api2/anchor"]')
                    anchor_frame.locator("#recaptcha-anchor").click(timeout=10000)
                    log.info("✅ Checkbox reCAPTCHA clicado")
                except Exception as e:
                    log.error(f"❌ Erro ao clicar no checkbox: {e}")
                    continue
                
                # Aguarda um pouco para o challenge aparecer (se necessário)
                time.sleep(2)
                
                # Tenta resolver CAPTCHA
                captcha_solved = False
                
                # PRIORIDADE 1: OpenAI (mais rápido e confiável)
                log.info("🧠 Tentando método OpenAI primeiro...")
                if solve_with_openai(page) == "SUCCESS":
                    log.info("✅ CAPTCHA resolvido com OpenAI!")
                    captcha_solved = True
                else:
                    log.warning("⚠️ OpenAI falhou, tentando 2Captcha...")
                    
                    # FALLBACK: 2Captcha
                    if solve_with_2captcha(page) == "SUCCESS":
                        log.info("✅ CAPTCHA resolvido com 2Captcha!")
                        captcha_solved = True
                    else:
                        log.error("❌ Ambos os métodos falharam")
                
                if not captcha_solved:
                    log.warning("🔄 Recarregando página para nova tentativa...")
                    page.reload(wait_until="domcontentloaded")
                    continue
                
                # === SUBMIT OTIMIZADO ===
                log.info("📝 Submetendo formulário...")
                
                # Aguarda um pouco para garantir que o captcha foi processado
                time.sleep(3)
                
                # Múltiplas estratégias de submit
                submit_success = False
                
                # Estratégia 1: Click normal
                try:
                    submit_button = page.locator('button[type="submit"]')
                    submit_button.wait_for(state="visible", timeout=5000)
                    submit_button.click(timeout=10000)
                    submit_success = True
                    log.info("✅ Submit realizado (click normal)")
                except PlaywrightTimeoutError as e:
                    if "intercepts pointer events" in str(e):
                        log.info("⚡ Tentando submit via JavaScript...")
                        # Estratégia 2: JavaScript click
                        try:
                            page.evaluate("""
                                const btn = document.querySelector('button[type="submit"]');
                                if (btn) btn.click();
                            """)
                            submit_success = True
                            log.info("✅ Submit realizado (JavaScript)")
                        except:
                            # Estratégia 3: Form submit
                            try:
                                page.evaluate("document.querySelector('form').submit();")
                                submit_success = True
                                log.info("✅ Submit realizado (form)")
                            except Exception as form_err:
                                log.error(f"❌ Todas as estratégias falharam: {form_err}")
                    else:
                        log.error(f"❌ Erro no submit: {e}")
                
                if not submit_success:
                    log.error("❌ Não foi possível submeter o formulário")
                    page.reload(wait_until="domcontentloaded")
                    continue
                
                # Verifica se o login foi bem-sucedido
                try:
                    page.wait_for_url(re.compile(".*fieltorcedor.com.br(?!/auth/login/).*"), timeout=20000)
                    log.info("🎉 LOGIN CONFIRMADO!")
                    login_successful = True
                    break
                except PlaywrightTimeoutError:
                    current_url = page.url
                    if "/auth/login/" not in current_url:
                        log.info("✅ Login bem-sucedido (URL mudou)")
                        login_successful = True
                        break
                    else:
                        log.warning("⚠️ Ainda na página de login, tentando novamente...")
                        page.reload(wait_until="domcontentloaded")

            if not login_successful:
                raise RuntimeError("❌ Não foi possível realizar o login após múltiplas tentativas")

            # === AQUECIMENTO DA SESSÃO (OTIMIZADO) ===
            log.info("🔥 Iniciando aquecimento da sessão...")
            
            # 1. Vai para página de jogos
            log.info(f"   📍 Navegando para: {JOGOS_URL}")
            page.goto(JOGOS_URL, timeout=30000)
            
            # 2. Clica no jogo específico
            log.info(f"   🎮 Procurando jogo: {JOGO_SLUG}")
            try:
                jogo_link = page.locator(f'a[href*="{JOGO_SLUG}"]').first
                jogo_link.wait_for(timeout=15000)
                jogo_link.click()
                log.info("✅ Jogo clicado")
            except PlaywrightTimeoutError:
                # Fallback: goto direto
                log.warning("⚠️ Link do jogo não encontrado, indo direto via URL")
                page.goto(CATEGORIA_URL, timeout=30000)
            
            # 3. Aguarda chegar na página de categoria
            try:
                page.wait_for_url(CATEGORIA_URL, timeout=15000)
                log.info("✅ Chegou na página de categoria")
            except PlaywrightTimeoutError:
                log.info("📍 Navegando diretamente para categoria...")
                page.goto(CATEGORIA_URL, timeout=30000)
            
            # 4. CORREÇÃO PRINCIPAL: Link categoria com fallback
            log.info(f"   🎯 Procurando categoria ID: {CATEGORIA_ID}")
            categoria_link_found = False
            
            try:
                # Tenta encontrar e clicar no link da categoria
                categoria_link = page.locator(f'a[href*="/categoria/{CATEGORIA_ID}/"]')
                categoria_link.wait_for(timeout=10000)  # Timeout reduzido
                categoria_link.click()
                categoria_link_found = True
                log.info("✅ Link da categoria encontrado e clicado")
            except PlaywrightTimeoutError:
                log.warning(f"⚠️ Link da categoria /{CATEGORIA_ID}/ não encontrado (possivelmente esgotado)")
                categoria_link_found = False
            
            # FALLBACK: Se link não encontrado, vai direto para setores
            if not categoria_link_found:
                log.info("🚀 Aplicando FALLBACK: navegando diretamente para setores...")
                setores_url_direct = f"{BASE_URL}/jogos/{JOGO_SLUG}/categoria/{CATEGORIA_ID}/"
                try:
                    page.goto(setores_url_direct, timeout=30000)
                    log.info("✅ Navegação direta para setores bem-sucedida")
                except Exception as e:
                    log.error(f"❌ Erro na navegação direta: {e}")
                    # Última tentativa: URL final dos setores
                    log.info("🎯 Última tentativa: URL final dos setores...")
                    page.goto(SETORES_URL, timeout=30000)
            
            # 5. Verifica se chegou na página de setores
            try:
                page.wait_for_url(SETORES_URL, timeout=15000)
                log.info("🎯 Chegou na página de setores!")
            except PlaywrightTimeoutError:
                # Se não chegou, força ir para setores
                log.info("🔧 Forçando navegação para setores...")
                page.goto(SETORES_URL, timeout=30000)
            
            # Verifica se realmente está na página de setores
            current_url = page.url
            if "setores" in current_url or SETORES_URL in current_url:
                log.info("✅ SESSÃO AQUECIDA COM SUCESSO na página de setores!")
            else:
                log.warning(f"⚠️ Pode não estar na página correta. URL atual: {current_url}")
            
            # === EXTRAÇÃO DE COOKIES ===
            log.info("🍪 Extraindo cookies da sessão...")
            all_cookies = context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in all_cookies}
            
            log.info(f"✅ {len(cookie_dict)} cookies extraídos")
            return cookie_dict

        except Exception as e:
            log.exception(f"❌ Erro fatal na Fase 1 (Login/Aquecimento): {e}")
            try:
                page.screenshot(path="fase1_failure_screenshot.png")
                log.info("📸 Screenshot de erro salvo")
            except:
                pass
            return None
            
        finally:
            log.info("🔒 Fechando navegador...")
            browser.close()
