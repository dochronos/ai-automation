import argparse
import os
import time
from pathlib import Path
from typing import List

import requests
from dotenv import load_dotenv, find_dotenv
from PIL import Image

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# -------- Config / env --------
env_path = find_dotenv(usecwd=True)
load_dotenv(dotenv_path=env_path, override=True)

DASH_URL = os.getenv("DASH_URL", "http://localhost:8501")
API_URL = os.getenv("API_URL", "http://localhost:8001")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")

OUTPUT_DIR = Path("assets/screenshots")
DEFAULT_TABS = ["System Health", "DLQ"]  # podés sumar más tabs


# -------- HTTP helpers --------
def wait_for_http_ok(url: str, timeout: float = 60.0, sleep: float = 2.0) -> bool:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return True
            last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)
        time.sleep(sleep)
    print(f"[wait_for_http_ok] Timeout waiting for {url} (last: {last_err})")
    return False


def wait_for_ollama(timeout: float = 60.0) -> bool:
    return wait_for_http_ok(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=timeout)


def wait_for_api_metrics(timeout: float = 60.0) -> bool:
    return wait_for_http_ok(f"{API_URL.rstrip('/')}/metrics", timeout=timeout)


# -------- Selenium helpers --------
def _init_driver(headless: bool = True, width: int = 1600, height: int = 1200):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={width},{height}")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--force-device-scale-factor=1")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(120)
    return driver


def _text_norm(s: str) -> str:
    import re
    s = re.sub(r"[^\w\s&-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _click_tab(driver, tab_label: str, timeout: float = 20.0):
    target = _text_norm(tab_label)
    end = time.time() + timeout
    while time.time() < end:
        candidates = driver.find_elements(By.XPATH, "//button|//div[@role='tab']|//a")
        for el in candidates:
            txt = el.text or el.get_attribute("aria-label") or ""
            if not txt:
                continue
            if target in _text_norm(txt):
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.3)
                el.click()
                return
        time.sleep(0.4)
    raise TimeoutException(f"No se encontró la pestaña parecida a '{tab_label}'")


def _force_render(driver):
    # Scroll suave para forzar render perezoso
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.6)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.4)
    except Exception:
        pass


def _wait_for_tab_content(driver, tab_label: str, timeout: float = 45.0):
    """
    Espera contenido característico de la tab + métricas/elementos concretos.
    Luego agrega una espera extra para equipos lentos.
    """
    wait = WebDriverWait(driver, timeout)
    norm = _text_norm(tab_label)

    if "system health" in norm:
        # Esperar el contenedor y al menos un valor de métrica
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(., 'System Health')]")))
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='stMetricValue']")))
    elif "dlq" in norm:
        # Esperar el título y/o expanders o mensajes de estado
        wait.until(
            EC.any_of(
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Dead Letter Queue')]")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'DLQ')]")),
            )
        )
        wait.until(
            EC.any_of(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "[data-testid='stExpander']")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'DLQ vacío')]")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'No hay errores')]")),
                EC.presence_of_element_located((By.XPATH, "//*[contains(., 'Archivos recientes mostrados')]")),
            )
        )
    else:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[@data-testid='stAppViewContainer']")))

    _force_render(driver)
    # Espera generosa adicional
    time.sleep(6.0)


def _resize_full_page(driver, max_h: int = 3600):
    """
    Ajusta la ventana al alto total del documento.
    max_h más grande para evitar cortes en equipos lentos.
    """
    total_width = driver.execute_script(
        "return Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, document.body.offsetWidth, document.documentElement.offsetWidth);"
    )
    total_height = driver.execute_script(
        "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, document.body.offsetHeight, document.documentElement.offsetHeight);"
    )
    total_height = min(int(total_height), max_h)
    total_width = max(int(total_width), 1280)
    driver.set_window_size(total_width, total_height)
    time.sleep(0.5)  # pequeño respiro tras resize


def _screenshot(driver, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # asegúrate de estar arriba del todo antes de medir/capturar
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.4)
    _resize_full_page(driver)
    # doble check: volver arriba (algunos layouts cambian altura al resize)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.3)
    driver.save_screenshot(str(out_path))


def _stitch_horiz(images: List[Path], out_path: Path, bg=(255, 255, 255)):
    pil_images = [Image.open(p).convert("RGB") for p in images]
    h = max(img.height for img in pil_images)
    scaled = []
    for img in pil_images:
        if img.height != h:
            new_w = int(img.width * (h / img.height))
            img = img.resize((new_w, h), Image.LANCZOS)
        scaled.append(img)
    total_w = sum(img.width for img in scaled)
    canvas = Image.new("RGB", (total_w, h), bg)
    x = 0
    for img in scaled:
        canvas.paste(img, (x, 0))
        x += img.width
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")


def _capture_tab_with_retries(driver, tab: str, out_path: Path, rounds: int = 3) -> bool:
    """
    Intenta capturar una tab con hasta 'rounds' reintentos:
    - Click tab
    - Wait content
    - Scroll/render
    - Screenshot
    Devuelve True si logró capturar, False si no.
    """
    for i in range(1, rounds + 1):
        try:
            print(f"   · intento {i}/{rounds} en '{tab}' ...")
            _click_tab(driver, tab)
            _wait_for_tab_content(driver, tab)

            # estabilizar arriba del todo antes de capturar
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.8)

            _screenshot(driver, out_path)
            return True
        except Exception as e:
            print(f"   ⚠️ intento {i} falló: {e}")
            # recarga suave
            try:
                driver.refresh()
                time.sleep(3.0)
            except Exception:
                time.sleep(2.0)
    return False


# -------- Main capture flow --------
def capture_week(
    week: int,
    tabs: List[str],
    make_composite: bool = True,
    headless: bool = True,
    check_ollama: bool = True,
    wait_api: bool = True,
):
    if wait_api:
        print(f"⏳ Esperando API metrics en {API_URL} ...")
        wait_for_api_metrics(timeout=90.0)

    if check_ollama:
        print(f"⏳ Esperando Ollama en {OLLAMA_HOST} ...")
        wait_for_ollama(timeout=90.0)

    driver = _init_driver(headless=headless)
    try:
        print(f"→ Abriendo dashboard {DASH_URL}")
        driver.get(DASH_URL)

        # Espera a que cargue el contenedor principal
        WebDriverWait(driver, 90).until(
            EC.presence_of_element_located((By.XPATH, "//*[@data-testid='stAppViewContainer']"))
        )
        time.sleep(1.5)

        outputs = []
        for tab in tabs:
            safe = tab.lower().replace(" ", "").replace("&", "and")
            fname = f"week{week}_{safe}.png"
            out_path = OUTPUT_DIR / fname

            print(f"→ Capturando tab: {tab}")
            ok = _capture_tab_with_retries(driver, tab, out_path, rounds=3)
            if not ok:
                print(f"   ❌ No se pudo capturar '{tab}' — guardo igualmente el último intento.")
                try:
                    _screenshot(driver, out_path)
                except Exception:
                    pass
            else:
                print(f"   ✅ Saved: {out_path}")
                outputs.append(out_path)

        if make_composite and len(outputs) >= 2:
            comp = OUTPUT_DIR / f"week{week}_composite.png"
            _stitch_horiz(outputs, comp)
            print(f"🧩 Composite: {comp}")

    finally:
        driver.quit()


# -------- CLI --------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture Streamlit dashboard screenshots for a given week.")
    parser.add_argument("--week", type=int, required=True, help="Week number (e.g., 5, 6)")
    parser.add_argument("--tabs", nargs="+", default=DEFAULT_TABS, help='Tab labels to capture, e.g. "System Health" "DLQ"')
    parser.add_argument("--no-composite", action="store_true", help="Do not create composite image")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible)")
    parser.add_argument("--skip-ollama", action="store_true", help="Do not wait for Ollama health")
    parser.add_argument("--skip-api", action="store_true", help="Do not wait for API /metrics")
    args = parser.parse_args()

    capture_week(
        week=args.week,
        tabs=args.tabs,
        make_composite=not args.no_composite,
        headless=not args.headed,
        check_ollama=not args.skip_ollama,
        wait_api=not args.skip_api,
    )
