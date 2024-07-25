from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit
import pika
import mysql.connector
import json
from decimal import Decimal
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app)


db_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="transacciones_db"
)
db_cursor = db_conn.cursor()


RICK_AND_MORTY_API = 'https://rickandmortyapi.com/api/character/'
PASSWORD = '123456'


response = requests.get(RICK_AND_MORTY_API)
characters = response.json()['results']
users = {char['name']: {'password': PASSWORD, 'id': char['id'], 'image': char['image']} for char in characters}

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        user_id = int(user_id)
    except ValueError:
        return None
    for username, info in users.items():
        if info['id'] == user_id:
            return User(user_id, username)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            user = User(users[username]['id'], username)
            login_user(user)
            return redirect(url_for('index'))
        flash('Nombre de usuario o contraseña incorrectos')
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    user_info = users[current_user.username]
    db_cursor.execute("SELECT * FROM transacciones WHERE cuenta_destino = %s", (current_user.username,))
    transacciones = db_cursor.fetchall()
    return render_template('index.html', transacciones=transacciones, user_info=user_info)

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def callback(ch, method, properties, body):
    mensaje_recibido = body.decode()
    print(f"Mensaje recibido: {mensaje_recibido}")

    try:
        transaccion = json.loads(mensaje_recibido, parse_float=Decimal)
        print(f'Transacción recibida: {transaccion}')

        sql = "INSERT INTO transacciones (cuenta_origen, cuenta_destino, monto) VALUES (%s, %s, %s)"
        val = (transaccion['cuenta_origen'], transaccion['cuenta_destino'], transaccion['monto'])
        db_cursor.execute(sql, val)
        db_conn.commit()

        transaccion_json = json.dumps(transaccion, default=decimal_default)
        socketio.emit('new_transaction', json.loads(transaccion_json))
        
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except json.JSONDecodeError as e:
        print(f"Error al decodificar JSON: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except mysql.connector.Error as err:
        print(f"Error de MySQL: {err}")
        db_conn.rollback()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def consume():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'localhost', 5672, '/', pika.PlainCredentials('kevin', '13demayo')
    ))
    channel = connection.channel()
    channel.queue_declare(queue='transaccionesQueue', durable=True)
    channel.basic_consume(queue='transaccionesQueue', on_message_callback=callback)
    print('Esperando transacciones. Presiona Ctrl+C para salir')
    channel.start_consuming()

@socketio.on('connect')
def handle_connect():
    emit('response', {'data': 'Connected'})

if __name__ == '__main__':
    socketio.start_background_task(target=consume)
    socketio.run(app, port=5000)
