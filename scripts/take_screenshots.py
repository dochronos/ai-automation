import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Configuración
OUTPUT_DIR = Path("assets/screenshots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = {
    "week6_systemhealth": "http://localhost:8501/?tab=System%20Health",
    "week6_telegram": "http://localhost:8501/?tab=System%20Health"  # o donde quieras mostrar la alerta
}

def take_screenshot(name: str, url: str, driver):
    driver.get(url)
    time.sleep(4)  # espera a que cargue bien el dashboard
    path = OUTPUT_DIR / f"{name}.png"
    driver.save_screenshot(str(path))
    print(f"✅ Saved screenshot: {path}")

if __name__ == "__main__":
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # sin ventana
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        for name, url in PAGES.items():
            take_screenshot(name, url, driver)
    finally:
        driver.quit()