# session_manager.py
import logging
import re
import time
from typing import Dict, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from config import (LOGIN_URL, USERNAME, PASSWORD, CAPTCHA_SOLVE_TIMEOUT,
                    JOGOS_URL, CATEGORIA_URL, CATEGORIA_ID, SETORES_URL, HEADERS, JOGO_SLUG)
from captcha_solvers import solve_with_openai, solve_with_2captcha

log = logging.getLogger(__name__)

def get_authenticated_session() -> Optional[Dict[str, str]]:
    log.info("▶️ FASE 1: Iniciando Login e Aquecimento via Navegador")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=HEADERS["user-agent"])
        page = context.new_page()
        try:
            page.goto(LOGIN_URL, timeout=60000)
            page.fill("input#id_username", USERNAME)
            page.fill("input#id_password", PASSWORD)

            login_successful = False
            for attempt in range(1, 3):
                log.info(f"--- Tentativa de Login #{attempt} ---")
                anchor_frame = page.frame_locator('iframe[src*="api2/anchor"]')
                anchor_frame.locator("#recaptcha-anchor").click()
                
                try:
                    with page.expect_timeout(CAPTCHA_SOLVE_TIMEOUT * 1000):
                        if solve_with_openai(page) == "SUCCESS":
                            log.info("✅ CAPTCHA resolvido com OpenAI.")
                        else:
                            raise ValueError("Falha no OpenAI, acionando fallback.")
                except Exception:
                    if solve_with_2captcha(page) == "SUCCESS":
                        log.info("✅ CAPTCHA resolvido com 2Captcha.")
                    else:
                        log.error("❌ Ambas as soluções de CAPTCHA falharam. Recarregando...")
                        page.reload(wait_until="domcontentloaded")
                        continue
                
                log.info("🔐 Submetendo formulário de login...")
                page.click('button[type="submit"]')
                
                try:
                    page.wait_for_url(re.compile(".*fieltorcedor.com.br(?!/auth/login/).*"), timeout=20000)
                    log.info("✅ Login confirmado!")
                    login_successful = True
                    break
                except PlaywrightTimeoutError:
                    log.warning("⚠️ Login falhou após submissão. Recarregando...")
                    page.reload(wait_until="domcontentloaded")

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
