# captcha_solvers.py
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
                page.evaluate(f"document.getElementById('g-recaptcha-response').innerHTML = '{g_response}';")
                return "SUCCESS"
            elif result.get('status') != 'processing':
                raise RuntimeError(f"2Captcha retornou um erro: {result.get('errorDescription')}")
        raise TimeoutError("Timeout esperando a solução do 2Captcha.")
    except Exception as e:
        log.error(f"     ❌ Falha crítica ao usar 2Captcha: {e}")
        return "FAIL"
