import sqlite3

def conectar():
    # Esto crea (o se conecta a) un archivo llamado finanzas.db en la misma carpeta
    return sqlite3.connect('finanzas.db')

def init_db():
    conexion = conectar()
    cursor = conexion.cursor()
    
    # Tabla para el historial completo de gastos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gasto_id INTEGER,
            mes_anio TEXT,
            cuota_actual TEXT,
            monto REAL,
            FOREIGN KEY(gasto_id) REFERENCES gastos(id)
        )
    ''')
    
    conexion.commit()
    conexion.close()
    print("Base de datos inicializada correctamente.")