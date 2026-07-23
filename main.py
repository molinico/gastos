import os
import telebot
from flask import Flask, request
import database

# 1. Configuración de credenciales
TOKEN = '8828929514:AAE-I5D56CRhQ11eLHeNmjeJziHOPI27tyk'
# Cuando subas esto a Render, cambiarás esta URL por la que ellos te den.
URL_SERVIDOR = 'https://olotov.onrender.com'

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Inicializamos la base de datos local
database.init_db()

# 2. La ruta secreta que escucha a Telegram (Webhook)
@app.route('/' + TOKEN, methods=['POST'])
def recibir_mensajes():
    # Telegram nos manda un paquete (JSON) con el mensaje. Lo desciframos:
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    
    # Le pasamos el mensaje al bot para que lo procese
    bot.process_new_updates([update])
    return "!", 200

# 3. Ruta principal para activar el Webhook fácilmente
@app.route('/')
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{URL_SERVIDOR}/{TOKEN}")
    return "¡Bot funcionando y Webhook configurado!", 200

# 4. Los comandos del bot
@bot.message_handler(commands=['start', 'ayuda'])
def bienvenida(message):
    texto = "¡Hola! Soy tu asistente financiero 24/7.\\n\\nPronto podré registrar tus gastos."
    bot.reply_to(message, texto)

# 5. Arranque del servidor
if __name__ == "__main__":
    # Gunicorn/Render usan el puerto 5000 por defecto
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
