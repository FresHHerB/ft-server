# config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Credenciais do Dashboard ---
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change_this_password")

# --- Credenciais do Fiel Torcedor ---
FT_USERNAME = os.getenv("FT_USERNAME")
FT_PASSWORD = os.getenv("FT_PASSWORD")

# --- Chaves de API ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")

# --- Configurações do Jogo ---
JOGO_SLUG = os.getenv("JOGO_SLUG")
DEPENDENTE_ID = os.getenv("DEPENDENTE_ID")
TARGET_SECTOR_SLUG = os.getenv("TARGET_SECTOR_SLUG")
CATEGORIA_ID = os.getenv("CATEGORIA_ID", "1")

# --- URLs ---
BASE_URL = "https://www.fieltorcedor.com.br"
LOGIN_URL = f"{BASE_URL}/auth/login/"
JOGOS_URL = f"{BASE_URL}/jogos/"
CATEGORIA_URL = f"{BASE_URL}/jogos/{JOGO_SLUG}/categoria/"
SETORES_URL = f"{BASE_URL}/jogos/{JOGO_SLUG}/setores/"

# --- Configurações de Automação ---
MAX_WATCH_ATTEMPTS = int(os.getenv("MAX_WATCH_ATTEMPTS", "900"))
WATCH_INTERVAL_MIN = float(os.getenv("WATCH_INTERVAL_MIN", "3.0"))
WATCH_INTERVAL_MAX = float(os.getenv("WATCH_INTERVAL_MAX", "5.0"))
CAPTCHA_SOLVE_TIMEOUT = int(os.getenv("CAPTCHA_SOLVE_TIMEOUT", "45"))

# --- Headers e Arquivos ---
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "origin": BASE_URL
}
LOG_FILE = Path("log_reserva_final.txt")
AUDIO_FILE = Path("audio_captcha.mp3")
DEBUG_HTML_FILE = Path("debug_setores.html")
SCREENSHOT_ERROR_FILE = Path("fatal_error_screenshot.png")
