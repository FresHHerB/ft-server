# captcha_solvers.py - Versão Otimizada e Robusta
import logging
import time
import requests
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config import OPENAI_API_KEY, TWOCAPTCHA_API_KEY, LOGIN_URL, AUDIO_FILE

log = logging.getLogger(__name__)

def solve_with_openai(page: Page) -> str:
    """Tenta resolver o reCAPTCHA usando o desafio de áudio e a API da OpenAI."""
    log.info("  -> Tentando resolver com OpenAI (Áudio)...")
    
    try:
        # 1. Localiza o iframe do challenge com timeout maior
        log.info("     🎯 Localizando iframe do challenge...")
        challenge_frame = page.frame_locator('iframe[src*="api2/bframe"]')
        
        # 2. Aguarda o iframe estar pronto
        try:
            challenge_frame.locator("button#recaptcha-audio-button").wait_for(timeout=15000)
            log.info("     ✅ Iframe do challenge carregado")
        except PlaywrightTimeoutError:
            log.error("     ❌ Iframe do challenge não carregou")
            return "FAIL"
        
        # 3. Clica no botão de áudio
        log.info("     🎵 Solicitando desafio de áudio...")
        challenge_frame.locator("button#recaptcha-audio-button").click(timeout=10000)
        
        # 4. Aguarda o link de download aparecer
        log.info("     ⏳ Aguardando link de download...")
        try:
            download_link = challenge_frame.locator("a.rc-audiochallenge-tdownload-link").get_attribute("href", timeout=15000)
            log.info("     🔗 Link de download obtido")
        except PlaywrightTimeoutError:
            log.error("     ❌ Link de download não apareceu")
            return "FAIL"
        
        if not download_link:
            log.error("     ❌ Link de download está vazio")
            return "FAIL"
        
        # 5. Baixa o áudio
        log.info("     💾 Baixando áudio...")
        try:
            resp = requests.get(download_link, timeout=30)
            resp.raise_for_status()
            AUDIO_FILE.write_bytes(resp.content)
            log.info(f"     ✅ Áudio baixado ({len(resp.content)} bytes)")
        except Exception as e:
            log.error(f"     ❌ Erro ao baixar áudio: {e}")
            return "FAIL"
        
        # 6. Transcreve via OpenAI
        log.info("     🧠 Transcrevendo áudio via OpenAI Whisper...")
        try:
            with open(AUDIO_FILE, "rb") as f:
                api_resp = requests.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": f},
                    data={"model": "whisper-1", "language": "en"},
                    timeout=30
                )
            api_resp.raise_for_status()
            
            transcription = api_resp.json().get("text", "").strip()
            if not transcription:
                log.error("     ❌ Transcrição vazia recebida")
                return "FAIL"
                
            log.info(f"     📝 Transcrição recebida: '{transcription}'")
            
        except Exception as e:
            log.error(f"     ❌ Erro na transcrição OpenAI: {e}")
            return "FAIL"
        
        # 7. Preenche a resposta
        log.info("     ✏️ Preenchendo resposta...")
        try:
            audio_input = challenge_frame.locator("input#audio-response")
            audio_input.wait_for(timeout=10000)
            audio_input.fill(transcription)
            log.info("     ✅ Resposta preenchida")
        except Exception as e:
            log.error(f"     ❌ Erro ao preencher resposta: {e}")
            return "FAIL"
        
        # 8. Clica em verificar
        log.info("     🔍 Clicando em verificar...")
        try:
            verify_button = challenge_frame.locator("button#recaptcha-verify-button")
            verify_button.click(timeout=10000)
            log.info("     ✅ Botão verificar clicado")
        except Exception as e:
            log.error(f"     ❌ Erro ao clicar em verificar: {e}")
            return "FAIL"
        
        # 9. Aguarda um pouco para processamento
        time.sleep(3)
        
        # 10. Verifica se o iframe do challenge desapareceu (sucesso)
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
            log.info("     ✅ Challenge iframe removido - CAPTCHA resolvido!")
            return "SUCCESS"
        except PlaywrightTimeoutError:
            log.warning("     ⚠️ Challenge iframe ainda presente - possível falha")
            return "FAIL"
            
    except Exception as e:
        log.error(f"     ❌ Erro inesperado no OpenAI: {type(e).__name__}: {e}")
        return "FAIL"

def solve_with_2captcha(page: Page) -> str:
    """Resolve o reCAPTCHA usando o serviço 2Captcha de forma otimizada."""
    log.info("  -> Recorrendo ao Fallback: 2Captcha...")
    
    try:
        # 1. Extrai sitekey
        site_key_element = page.locator('.g-recaptcha')
        site_key = site_key_element.get_attribute('data-sitekey', timeout=5000)
        if not site_key:
            log.error("     ❌ Sitekey não encontrado")
            return "FAIL"
        log.info(f"     🔑 Sitekey extraído: {site_key}")

        # 2. Cria tarefa no 2Captcha
        create_payload = {
            "clientKey": TWOCAPTCHA_API_KEY,
            "task": {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": LOGIN_URL,
                "websiteKey": site_key
            }
        }
        
        resp = requests.post("https://api.2captcha.com/createTask", json=create_payload, timeout=20)
        resp.raise_for_status()
        
        result = resp.json()
        if result.get('errorId', 0) != 0:
            log.error(f"     ❌ Erro ao criar tarefa: {result.get('errorDescription')}")
            return "FAIL"
            
        task_id = result['taskId']
        log.info(f"     ✅ Tarefa criada. ID: {task_id}")

        # 3. Aguarda solução (polling otimizado)
        result_payload = {"clientKey": TWOCAPTCHA_API_KEY, "taskId": task_id}
        start_time = time.time()
        
        while time.time() - start_time < 180:  # 3 minutos max
            time.sleep(5)  # Check a cada 5 segundos
            
            try:
                resp = requests.post("https://api.2captcha.com/getTaskResult", json=result_payload, timeout=15)
                resp.raise_for_status()
                result = resp.json()
                
                if result.get('status') == 'ready':
                    g_response = result['solution']['gRecaptchaResponse']
                    log.info(f"     🔑 Solução recebida: {g_response[:20]}...")
                    
                    # 4. INJEÇÃO RÁPIDA E SIMPLES
                    log.info("     💉 Injetando token...")
                    
                    page.evaluate(f"""
                        const textarea = document.getElementById('g-recaptcha-response');
                        if (textarea) {{
                            textarea.innerHTML = '{g_response}';
                            textarea.value = '{g_response}';
                            textarea.style.display = 'block';
                        }}
                    """)
                    
                    # 5. Aguarda apenas 2 segundos (otimizado)
                    time.sleep(2)
                    
                    log.info("     ✅ Token injetado com sucesso")
                    return "SUCCESS"
                    
                elif result.get('status') not in ['processing', 'new']:
                    log.error(f"     ❌ Erro 2Captcha: {result.get('errorDescription')}")
                    return "FAIL"
                    
            except Exception as e:
                log.warning(f"     ⚠️ Erro no polling: {e}")
                continue
        
        log.error("     ❌ Timeout aguardando solução 2Captcha")
        return "FAIL"
        
    except Exception as e:
        log.error(f"     ❌ Erro crítico 2Captcha: {e}")
        return "FAIL"
