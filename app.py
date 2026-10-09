import os
import requests
import logging
from flask import Flask, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# Configuración desde Variables de Entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

IMN_URL = "https://www.imn.ac.cr/"
IMAGE_URL = "https://www.imn.ac.cr/imagenes-sat/IRVISCR.png"

STATE_FILE = "last_state.txt"

logging.basicConfig(level=logging.INFO)

def get_last_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return f.read().strip()
    return ""

def save_last_state(state):
    with open(STATE_FILE, "w") as f:
        f.write(state)

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("Mensaje enviado a Telegram")
    except Exception as e:
        logging.error(f"Error al enviar mensaje: {e}")

def send_telegram_photo(caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        response = requests.get(IMAGE_URL, timeout=10)
        response.raise_for_status()
        files = {"photo": ("satelite.png", response.content, "image/png")}
        payload = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
        requests.post(url, data=payload, files=files, timeout=10)
        logging.info("Imagen enviada a Telegram")
    except Exception as e:
        logging.error(f"Error al enviar imagen: {e}")

def analizar_imn():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(IMN_URL, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        textos = soup.find_all(['p', 'a', 'div', 'span'])
        alertas = []
        palabras_clave = ["lluvia", "precipitación", "tormenta", "chaparrón", "onda tropical", "inestabilidad", "vigilancia", "alerta"]
        
        for texto in textos:
            texto_bajo = texto.get_text().lower()
            if any(palabra in texto_bajo for palabra in palabras_clave):
                limpio = texto.get_text(strip=True)
                if len(limpio) > 30 and limpio not in alertas:
                    alertas.append(limpio)
        
        if alertas:
            return " | ".join(list(set(alertas)))[:400]
        return None
    except Exception as e:
        logging.error(f"Error al analizar IMN: {e}")
        return None

def generar_interpretacion(texto_aviso):
    zonas = []
    texto = texto_aviso.lower()
    
    if "guanacaste" in texto or "pacifico norte" in texto:
        zonas.append("📍 **Pacífico Norte:** Guanacaste")
    if "puntarenas" in texto or "pacifico central" in texto:
        zonas.append("📍 **Pacífico Central:** Puntarenas, Jacó, Quepos")
    if "valle central" in texto or "san josé" in texto or "heredia" in texto or "alajuela" in texto or "cartago" in texto:
        zonas.append("📍 **Valle Central:** San José, Alajuela, Heredia, Cartago")
    if "caribe" in texto or "limón" in texto or "sarapiquí" in texto:
        zonas.append("📍 **Zona Caribe:** Limón, Sarapiquí, Guácimo")
    if "sur" in texto or "perez zeledon" in texto or "coto brus" in texto:
        zonas.append("📍 **Zona Sur:** Pérez Zeledón, Coto Brus, Osa")
        
    if not zonas:
        return "🔍 *Interpretación:* Inestabilidad detectada, pero sin provincias específicas. Revisa la imagen satelital: las zonas blancas brillantes indican mayor probabilidad de lluvia."
    
    return f"📊 *Zonas con probabilidad de lluvia:*\n" + "\n".join(zonas)

@app.route("/")
def home():
    return jsonify({"status": "Bot IMN Render funcionando correctamente 🇨🇷🌧️"})

@app.route("/check", methods=["GET", "POST"])
def check_imn():
    logging.info("Ejecutando revisión del IMN...")
    
    nuevo_aviso = analizar_imn()
    last_state = get_last_state()
    
    if nuevo_aviso and nuevo_aviso != last_state:
        save_last_state(nuevo_aviso)
        
        mensaje = f"🚨 *ACTUALIZACIÓN METEOROLÓGICA (IMN)*\n\n *Aviso detectado:*\n_{nuevo_aviso}_\n\n🛰️ *Imagen Satelital IR/VIS adjunta.*"
        interpretacion = generar_interpretacion(nuevo_aviso)
        
        send_telegram_message(mensaje)
        send_telegram_photo("📸 Imagen Satelital Actual")
        send_telegram_message(interpretacion)
        
        return jsonify({"status": "success", "message": "Alerta enviada"})
    else:
        logging.info("Sin cambios nuevos en el IMN.")
        return jsonify({"status": "no_changes", "message": "Todo tranquilo, sin nuevos avisos."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
