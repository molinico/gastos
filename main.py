
import os
import telebot
from flask import Flask, request
import database
import datetime
import calendar

# 1. Configuración de credenciales
TOKEN = '8828929514:AAE-I5D56CRhQ11eLHeNmjeJziHOPI27tyk'
# Cuando subas esto a Render, cambiarás esta URL por la que ellos te den.
URL_SERVIDOR = 'https://olotov.onrender.com'
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# 2. Configuración inicial de Base de Datos
def init_config():
    # Nos aseguramos de que exista una tabla para los cierres de tarjeta
    conn = database.conectar()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cierres_tarjetas (
            tarjeta TEXT PRIMARY KEY,
            dia_cierre INTEGER
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

init_config()

# Función matemática auxiliar para sumar meses correctamente
def sumar_meses(fecha_origen, meses):
    mes = fecha_origen.month - 1 + meses
    ano = fecha_origen.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha_origen.day, calendar.monthrange(ano, mes)[1])
    return datetime.date(ano, mes, dia)

# 3. Rutas Webhook de Flask
@app.route('/' + TOKEN, methods=['POST'])
def recibir_mensajes():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def index():
    bot.remove_webhook()
    bot.set_webhook(url=f"{URL_SERVIDOR}/{TOKEN}")
    return "¡Bot funcionando y Webhook configurado!", 200

# 4. Comandos del Bot
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Asistente financiero 24/7 listo para registrar gastos.")

@bot.message_handler(commands=['cierres'])
def set_cierres(message):
    # Formato esperado: /cierres galicia 22 pa 24
    try:
        partes = message.text.lower().split()[1:]
        if len(partes) % 2 != 0 or len(partes) == 0:
            bot.reply_to(message, "Formato incorrecto. Usá: /cierres galicia 22 pa 24")
            return
        
        conn = database.conectar()
        cur = conn.cursor()
        for i in range(0, len(partes), 2):
            tarjeta = partes[i]
            dia = int(partes[i+1])
            # Guarda o actualiza el cierre
            cur.execute('''
                INSERT INTO cierres_tarjetas (tarjeta, dia_cierre) 
                VALUES (%s, %s) 
                ON CONFLICT (tarjeta) DO UPDATE SET dia_cierre = EXCLUDED.dia_cierre
            ''', (tarjeta, dia))
        
        conn.commit()
        cur.close()
        conn.close()
        bot.reply_to(message, "✅ Fechas de cierre actualizadas correctamente para este mes.")
    except Exception as e:
        bot.reply_to(message, "❌ Error al guardar cierres. Revisá el formato.")

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def registrar_gasto(message):
    try:
        partes = message.text.lower().split()
        monto = float(partes[0])
        medio = partes[1]
        
        # Parseo flexible según medio de pago
        if medio in ['galicia', 'pa']:
            cuotas = int(partes[2])
            concepto = " ".join(message.text.split()[3:]) # Todo el resto del texto es el concepto
        elif medio in ['lemon', 'efectivo']:
            # Permite escribir "15000 lemon hamburguesa" o "15000 lemon 1 hamburguesa"
            if partes[2].isdigit():
                cuotas = int(partes[2])
                concepto = " ".join(message.text.split()[3:])
            else:
                cuotas = 1
                concepto = " ".join(message.text.split()[2:])
        else:
            bot.reply_to(message, "❌ Medio no reconocido. Usa: lemon, efectivo, galicia o pa.")
            return

        # Ajuste horario Argentina (UTC-3)
        tz_ar = datetime.timezone(datetime.timedelta(hours=-3))
        fecha_hoy = datetime.datetime.now(tz_ar).date()
        
        conn = database.conectar()
        cur = conn.cursor()

        # Guardamos el gasto histórico
        cur.execute('''
            INSERT INTO gastos (fecha, concepto, medio_pago, monto, cuotas)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (str(fecha_hoy), concepto, medio, monto, cuotas))
        gasto_id = cur.fetchone()[0]

        # Lógica de distribución de proyecciones
        if medio in ['galicia', 'pa']:
            cur.execute('SELECT dia_cierre FROM cierres_tarjetas WHERE tarjeta = %s', (medio,))
            resultado = cur.fetchone()
            if not resultado:
                bot.reply_to(message, f"⚠️ No tengo la fecha de cierre de {medio}. Usá el comando /cierres primero e intentá cargar el gasto de nuevo.")
                return
            dia_cierre = resultado[0]

            # Matemática de los resúmenes
            if fecha_hoy.day <= dia_cierre:
                mes_base = sumar_meses(fecha_hoy.replace(day=1), 1)
            else:
                mes_base = sumar_meses(fecha_hoy.replace(day=1), 2)

            monto_cuota = monto / cuotas
            for i in range(cuotas):
                mes_impacto = sumar_meses(mes_base, i)
                periodo = mes_impacto.strftime("%Y-%m")
                cuota_actual = f"{i+1}/{cuotas}"
                
                cur.execute('''
                    INSERT INTO proyeccion_cuotas (gasto_id, mes_anio, cuota_actual, monto)
                    VALUES (%s, %s, %s, %s)
                ''', (gasto_id, periodo, cuota_actual, monto_cuota))

        else:
            # Lemon o Efectivo impactan en el mes actual al 100%
            periodo = fecha_hoy.strftime("%Y-%m")
            cur.execute('''
                INSERT INTO proyeccion_cuotas (gasto_id, mes_anio, cuota_actual, monto)
                VALUES (%s, %s, %s, %s)
            ''', (gasto_id, periodo, "1/1", monto))

        conn.commit()
        cur.close()
        conn.close()

        bot.reply_to(message, f"✅ Guardado: {concepto}\n💰 ${monto}\n💳 {medio} ({cuotas} cuotas)")

    except Exception as e:
        bot.reply_to(message, "❌ Error de formato. Ejemplos:\n- 50000 galicia 3 zapatillas\n- 15000 lemon hamburguesa")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
