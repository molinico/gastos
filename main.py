import os
import telebot
from flask import Flask, request
import database
import datetime
import calendar

# 1. Configuración de credenciales
TOKEN = '8828929514:AAE-I5D56CRhQ11eLHeNmjeJziHOPI27tyk'
URL_SERVIDOR = 'https://olotov.onrender.com'
bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# Función matemática auxiliar para sumar meses correctamente
def sumar_meses(fecha_origen, meses):
    mes = fecha_origen.month - 1 + meses
    ano = fecha_origen.year + mes // 12
    mes = mes % 12 + 1
    dia = min(fecha_origen.day, calendar.monthrange(ano, mes)[1])
    return datetime.date(ano, mes, dia)

# 2. Rutas Webhook de Flask
@app.route('/' + TOKEN, methods=['POST'])
def recibir_mensajes():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route('/')
def index():
    # Inicializamos tablas de base de datos de forma segura
    try:
        database.init_db()
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
    except Exception as e:
        print(f"Error al inicializar tablas: {e}")

    # Seteamos el Webhook en Telegram
    bot.remove_webhook()
    bot.set_webhook(url=f"{URL_SERVIDOR}/{TOKEN}")
    return "¡Bot funcionando y Webhook configurado!", 200

# 3. Comandos del Bot
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "¡Hola! Asistente financiero 24/7 listo para registrar gastos.")

@bot.message_handler(commands=['cierres'])
def set_cierres(message):
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

@bot.message_handler(commands=['resumen'])
def resumen_mes(message):
    try:
        partes = message.text.split()
        if len(partes) > 1:
            periodo = partes[1]
        else:
            tz_ar = datetime.timezone(datetime.timedelta(hours=-3))
            periodo = datetime.datetime.now(tz_ar).strftime("%Y-%m")
        
        conn = database.conectar()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT g.medio_pago, SUM(p.monto)
            FROM proyeccion_cuotas p
            JOIN gastos g ON p.gasto_id = g.id
            WHERE p.mes_anio = %s
            GROUP BY g.medio_pago
        ''', (periodo,))
        
        resultados = cur.fetchall()
        cur.close()
        conn.close()
        
        if not resultados:
            bot.reply_to(message, f"No tenés gastos registrados para el periodo {periodo}.")
            return
            
        texto = f"📊 *Resumen de {periodo}*\n\n"
        total = 0
        for medio, monto in resultados:
            texto += f"💳 {medio.capitalize()}: ${monto:,.2f}\n"
            total += monto
            
        texto += f"\n💰 *TOTAL A PAGAR: ${total:,.2f}*"
        
        bot.reply_to(message, texto, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, "❌ Hubo un error al generar el resumen. Usá el formato: /resumen 2026-07")

@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def registrar_gasto(message):
    try:
        partes = message.text.lower().split()
        monto = float(partes[0])
        medio = partes[1]
        
        if medio in ['galicia', 'pa']:
            cuotas = int(partes[2])
            concepto = " ".join(message.text.split()[3:])
        elif medio in ['lemon', 'efectivo']:
            if len(partes) > 2 and partes[2].isdigit():
                cuotas = int(partes[2])
                concepto = " ".join(message.text.split()[3:])
            else:
                cuotas = 1
                concepto = " ".join(message.text.split()[2:])
        else:
            bot.reply_to(message, "❌ Medio no reconocido. Usa: lemon, efectivo, galicia o pa.")
            return

        tz_ar = datetime.timezone(datetime.timedelta(hours=-3))
        fecha_hoy = datetime.datetime.now(tz_ar).date()
        
        conn = database.conectar()
        cur = conn.cursor()

        cur.execute('''
            INSERT INTO gastos (fecha, concepto, medio_pago, monto, cuotas)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
        ''', (str(fecha_hoy), concepto, medio, monto, cuotas))
        gasto_id = cur.fetchone()[0]

        if medio in ['galicia', 'pa']:
            cur.execute('SELECT dia_cierre FROM cierres_tarjetas WHERE tarjeta = %s', (medio,))
            resultado = cur.fetchone()
            if not resultado:
                bot.reply_to(message, f"⚠️ No tengo la fecha de cierre de {medio}. Usá el comando /cierres primero e intentá cargar el gasto de nuevo.")
                cur.close()
                conn.close()
                return
            dia_cierre = resultado[0]

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
