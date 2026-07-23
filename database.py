import psycopg2
import os

# Acá pegás la URL que te dio Neon
DATABASE_URL = 'postgresql://neondb_owner:npg_AUKcns57mzMQ@ep-odd-cloud-ayvfaagt.c-5.us-east-2.aws.neon.tech/neondb?sslmode=require'

def conectar():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conexion = conectar()
    cursor = conexion.cursor()
    
    # Tabla para el historial completo de gastos (Postgres usa SERIAL en lugar de AUTOINCREMENT)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id SERIAL PRIMARY KEY,
            fecha TEXT,
            concepto TEXT,
            medio_pago TEXT,
            monto REAL,
            cuotas INTEGER
        )
    ''')
    
    # Tabla para proyectar las cuotas mes a mes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proyeccion_cuotas (
            id SERIAL PRIMARY KEY,
            gasto_id INTEGER,
            mes_anio TEXT,
            cuota_actual TEXT,
            monto REAL,
            FOREIGN KEY(gasto_id) REFERENCES gastos(id)
        )
    ''')
    
    conexion.commit()
    cursor.close()
    conexion.close()
    print("Base de datos en la nube inicializada correctamente.")
