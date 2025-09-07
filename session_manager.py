# session_manager.py - Versão corrigida para aguardar iframe
import logging
import re
import time
from typing import Dict, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (LOGIN_URL, FT_USERNAME, FT_PASSWORD, CAPTCHA_SOLVE_TIMEOUT,
                    JOGOS_URL, CATEGORIA_URL, CATEGORIA_ID, SETORES_URL, HEADERS, JOGO_SLUG)
from captcha_solvers import solve_with_openai, solve_with_2captcha

log = logging.getLogger(__name__)

def get_authenticated_session() -> Optional[Dict[str, str]]:
    log.info("▶️ FASE 1: Iniciando Login e Aquecimento via Navegador")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # headless=True para produção
        context = browser.new_context(user_agent=HEADERS["user-agent"])
        page = context.new_page()
        try:
            page.goto(LOGIN_URL, timeout=60000)
            page.fill("input#id_username", FT_USERNAME)
            page.fill("input#id_password", FT_PASSWORD)

            login_successful = False
            for attempt in range(1, 3):
                log.info(f"--- Tentativa de Login #{attempt} ---")
                anchor_frame = page.frame_locator('iframe[src*="api2/anchor"]')
                anchor_frame.locator("#recaptcha-anchor").click()
                
                # Aguarda um pouco após clicar no checkbox
                time.sleep(2)
                
                captcha_solved = False
                try:
                    with page.expect_timeout(CAPTCHA_SOLVE_TIMEOUT * 1000):
                        if solve_with_openai(page) == "SUCCESS":
                            log.info("✅ CAPTCHA resolvido com OpenAI.")
                            captcha_solved = True
                        else:
                            raise ValueError("Falha no OpenAI, acionando fallback.")
                except Exception:
                    if solve_with_2captcha(page) == "SUCCESS":
                        log.info("✅ CAPTCHA resolvido com 2Captcha.")
                        captcha_solved = True
                    else:
                        log.error("❌ Ambas as soluções de CAPTCHA falharam. Recarregando...")
                        page.reload(wait_until="domcontentloaded")
                        continue
                
                if not captcha_solved:
                    continue
                
                # AGUARDAR ANTES DO SUBMIT - CRÍTICO PARA O SERVIDOR
                log.info("🔐 Submetendo formulário de login...")
                log.info("     ⏳ Aguardando página estar pronta para submit...")
                
                # 1. Aguarda mais um tempo para garantir que o reCAPTCHA foi processado
                time.sleep(3)
                
                # 2. Verifica se ainda há iframe bloqueando
                iframe_present = page.evaluate("""
                    () => {
                        const iframe = document.querySelector('iframe[src*="api2/bframe"]');
                        return iframe && iframe.offsetParent && iframe.style.display !== 'none';
                    }
                """)
                
                if iframe_present:
                    log.info("     ⚠️ Iframe ainda presente, aguardando remoção...")
                    try:
                        page.wait_for_function("""
                            () => {
                                const iframe = document.querySelector('iframe[src*="api2/bframe"]');
                                return !iframe || 
                                       iframe.style.display === 'none' || 
                                       iframe.offsetWidth === 0 || 
                                       iframe.offsetHeight === 0 ||
                                       !iframe.offsetParent;
                            }
                        """, timeout=10000)
                        log.info("     ✅ Iframe removido, prosseguindo...")
                    except:
                        log.warning("     ⚠️ Forçando remoção do iframe...")
                        page.evaluate("""
                            const iframe = document.querySelector('iframe[src*="api2/bframe"]');
                            if (iframe) {
                                iframe.style.display = 'none';
                                iframe.style.pointerEvents = 'none';
                                iframe.remove();
                            }
                        """)
                
                # 3. Verifica se o botão está clicável
                try:
                    submit_button = page.locator('button[type="submit"]')
                    submit_button.wait_for(state="visible", timeout=5000)
                    log.info("     ✅ Botão submit pronto")
                except:
                    log.warning("     ⚠️ Botão submit pode não estar pronto")
                
                # 4. TENTATIVAS MÚLTIPLAS DE CLICK
                submit_success = False
                
                # Método 1: Click normal com timeout menor
                try:
                    page.click('button[type="submit"]', timeout=10000)
                    submit_success = True
                    log.info("     ✅ Submit realizado (método normal)")
                except PlaywrightTimeoutError as e:
                    if "intercepts pointer events" in str(e):
                        log.warning("     ⚠️ Iframe ainda interceptando, tentando JavaScript...")
                        
                        # Método 2: JavaScript click
                        try:
                            page.evaluate("""
                                const submitBtn = document.querySelector('button[type="submit"]');
                                if (submitBtn) {
                                    submitBtn.click();
                                }
                            """)
                            submit_success = True
                            log.info("     ✅ Submit realizado (método JavaScript)")
                        except:
                            log.warning("     ⚠️ JavaScript click falhou, tentando form submit...")
                            
                            # Método 3: Form submit
                            try:
                                page.evaluate("""
                                    const form = document.querySelector('form');
                                    if (form) {
                                        form.submit();
                                    }
                                """)
                                submit_success = True
                                log.info("     ✅ Submit realizado (método form)")
                            except:
                                log.error("     ❌ Todos os métodos de submit falharam")
                    else:
                        log.error(f"     ❌ Erro no submit: {e}")
                
                if not submit_success:
                    log.error("❌ Não foi possível submeter o formulário")
                    page.reload(wait_until="domcontentloaded")
                    continue
                
                # 5. Aguarda redirecionamento
                try:
                    page.wait_for_url(re.compile(".*fieltorcedor.com.br(?!/auth/login/).*"), timeout=20000)
                    log.info("✅ Login confirmado!")
                    login_successful = True
                    break
                except PlaywrightTimeoutError:
                    log.warning("⚠️ Login falhou após submissão. Verificando página...")
                    
                    # Verifica se ainda está na página de login
                    current_url = page.url
                    if "/auth/login/" in current_url:
                        log.warning("     Ainda na página de login, tentando novamente...")
                        page.reload(wait_until="domcontentloaded")
                    else:
                        log.info("     ✅ Login pode ter sido bem-sucedido")
                        login_successful = True
                        break

            if not login_successful:
                raise RuntimeError("Não foi possível realizar o login.")

            log.info("🔥 Aquecendo a sessão...")
            page.goto(JOGOS_URL)
            page.locator(f'a[href*="{JOGO_SLUG}"]').first.click()
            page.wait_for_url(CATEGORIA_URL)
            page.locator(f'a[href*="/categoria/{CATEGORIA_ID}/"]').click()
            page.wait_for_url(SETORES_URL)
            log.info("✅ Sessão aquecida na página de setores.")
            
            log.info("🍪 Extraindo cookies...")
            all_cookies = context.cookies()
            return {c['name']: c['value'] for c in all_cookies}
        except Exception as e:
            log.exception(f"❌ Erro fatal na Fase 1: {e}")
            page.screenshot(path="fase1_failure_screenshot.png")
            return None
        finally:
            browser.close()
