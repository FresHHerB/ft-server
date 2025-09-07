# captcha_solvers.py - Versão corrigida para o servidor
import logging
import time
import requests
from playwright.sync_api import Page
from config import OPENAI_API_KEY, TWOCAPTCHA_API_KEY, LOGIN_URL, AUDIO_FILE

log = logging.getLogger(__name__)

def solve_with_openai(page: Page) -> str:
    """Tenta resolver o reCAPTCHA usando o desafio de áudio e a API da OpenAI."""
    log.info("  -> Tentando resolver com OpenAI (Áudio)...")
    try:
        challenge_frame = page.frame_locator('iframe[src*="api2/bframe"]')
        challenge_frame.locator("button#recaptcha-audio-button").click(timeout=10000)
        download_link = challenge_frame.locator("a.rc-audiochallenge-tdownload-link").get_attribute("href", timeout=10000)
        
        resp = requests.get(download_link)
        AUDIO_FILE.write_bytes(resp.content)

        with open(AUDIO_FILE, "rb") as f:
            api_resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": f},
                data={"model": "whisper-1", "language": "en"}
            )
        api_resp.raise_for_status()
        transcription = api_resp.json().get("text", "").strip()
        log.info(f"     📝 Transcrição recebida: '{transcription}'")

        challenge_frame.locator("input#audio-response").fill(transcription)
        challenge_frame.locator("button#recaptcha-verify-button").click()
        return "SUCCESS"
    except Exception as e:
        log.warning(f"     ⚠️ Falha ao resolver com OpenAI: {type(e).__name__}")
        return "FAIL"

def solve_with_2captcha(page: Page) -> str:
    """Resolve o reCAPTCHA usando o serviço 2Captcha e injeta o token."""
    log.info("  -> Recorrendo ao Fallback: 2Captcha...")
    try:
        site_key = page.locator('.g-recaptcha').get_attribute('data-sitekey')
        if not site_key:
            raise ValueError("Não foi possível encontrar o sitekey do reCAPTCHA.")
        log.info(f"     🔑 Sitekey extraído: {site_key}")

        create_url = "https://api.2captcha.com/createTask"
        create_payload = {"clientKey": TWOCAPTCHA_API_KEY, "task": {"type": "RecaptchaV2TaskProxyless", "websiteURL": LOGIN_URL, "websiteKey": site_key}}
        resp = requests.post(create_url, json=create_payload, timeout=20)
        task_id = resp.json()['taskId']
        log.info(f"     ✅ Tarefa 2Captcha criada. ID: {task_id}. Aguardando solução...")

        result_url = "https://api.2captcha.com/getTaskResult"
        result_payload = {"clientKey": TWOCAPTCHA_API_KEY, "taskId": task_id}
        start_time = time.time()
        while time.time() - start_time < 180:
            time.sleep(10)
            resp = requests.post(result_url, json=result_payload, timeout=20)
            result = resp.json()
            if result.get('status') == 'ready':
                g_response = result['solution']['gRecaptchaResponse']
                log.info(f"     🔑 Solução 2Captcha recebida: {g_response[:20]}...")
                
                # INJEÇÃO ROBUSTA DO TOKEN COM AGUARDO
                log.info("     💉 Injetando token e aguardando iframe desaparecer...")
                
                # 1. Injeta o token
                page.evaluate(f"""
                    const textarea = document.getElementById('g-recaptcha-response');
                    if (textarea) {{
                        textarea.innerHTML = '{g_response}';
                        textarea.value = '{g_response}';
                        textarea.style.display = 'block';
                        
                        // Dispara eventos
                        textarea.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        textarea.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        
                        console.log('Token 2Captcha injetado');
                    }}
                """)
                
                # 2. Aguarda um pouco para o reCAPTCHA processar
                time.sleep(3)
                
                # 3. AGUARDA O IFRAME DO CHALLENGE DESAPARECER
                log.info("     ⏳ Aguardando iframe challenge desaparecer...")
                try:
                    # Aguarda até 20 segundos para o iframe desaparecer ou ficar invisível
                    page.wait_for_function("""
                        () => {
                            const iframe = document.querySelector('iframe[src*="api2/bframe"]');
                            return !iframe || 
                                   iframe.style.display === 'none' || 
                                   iframe.offsetWidth === 0 || 
                                   iframe.offsetHeight === 0 ||
                                   !iframe.offsetParent;
                        }
                    """, timeout=20000)
                    log.info("     ✅ Iframe challenge removido/ocultado")
                except Exception as e:
                    log.warning(f"     ⚠️ Iframe ainda presente após timeout: {e}")
                    # Tenta forçar a remoção/ocultação do iframe
                    log.info("     🔧 Tentando forçar remoção do iframe...")
                    page.evaluate("""
                        const iframe = document.querySelector('iframe[src*="api2/bframe"]');
                        if (iframe) {
                            iframe.style.display = 'none';
                            iframe.style.visibility = 'hidden';
                            iframe.style.opacity = '0';
                            iframe.style.pointerEvents = 'none';
                            iframe.style.position = 'absolute';
                            iframe.style.left = '-9999px';
                            iframe.remove();
                        }
                    """)
                
                # 4. Aguarda mais um pouco para garantir
                time.sleep(2)
                
                # 5. Verifica se o botão submit está clicável
                try:
                    submit_button = page.locator('button[type="submit"]')
                    submit_button.wait_for(state="visible", timeout=5000)
                    log.info("     ✅ Botão submit está visível e pronto")
                except:
                    log.warning("     ⚠️ Botão submit pode não estar totalmente pronto")
                
                return "SUCCESS"
                
            elif result.get('status') != 'processing':
                raise RuntimeError(f"2Captcha retornou um erro: {result.get('errorDescription')}")
        
        raise TimeoutError("Timeout esperando a solução do 2Captcha.")
    except Exception as e:
        log.error(f"     ❌ Falha crítica ao usar 2Captcha: {e}")
        return "FAIL"
