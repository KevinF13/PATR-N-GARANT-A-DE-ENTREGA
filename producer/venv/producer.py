from flask import Flask, request, render_template, redirect, url_for, session, flash
import pika
import json
import mysql.connector
from decimal import Decimal
from flask_wtf import FlaskForm
from wtforms import StringField, DecimalField, PasswordField, SubmitField
from wtforms.validators import DataRequired
import requests  # Importación del módulo requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'

RICK_AND_MORTY_API = 'https://rickandmortyapi.com/api/character/'

class TransactionForm(FlaskForm):
    monto = DecimalField('Monto', validators=[DataRequired()])
    submit = SubmitField('Enviar')

class LoginForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar sesión')

try:
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'localhost', 5672, '/', pika.PlainCredentials('kevin', '13demayo')
    ))
    channel = connection.channel()
    channel.queue_declare(queue='transaccionesQueue', durable=True)
except pika.exceptions.AMQPConnectionError as e:
    print(f"Error al conectar con RabbitMQ: {e}")

db_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="transacciones_db"
)
db_cursor = db_conn.cursor()

@app.route('/')
def main_page():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if username == 'admin' and password == 'admin':
            session['logged_in'] = True
            session['transaction_processed'] = False  # Inicializamos el estado de transacción
            return redirect(url_for('home'))
        else:
            flash('Credenciales incorrectas, intente nuevamente.')
    return render_template('login.html', form=form)

@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    response = requests.get(RICK_AND_MORTY_API)
    personajes = response.json()['results']
    return render_template('home.html', personajes=personajes)

@app.route('/select/<int:char_id>', methods=['GET'])
def select(char_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    session['selected_character'] = char_id
    session['transaction_processed'] = False  # Reiniciar el estado de transacción
    return redirect(url_for('transaction'))

@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('transaction_processed', False):
        return redirect(url_for('home'))  # Evitar reenvío de transacción

    form = TransactionForm()
    char_id = session.get('selected_character')
    if char_id:
        character = requests.get(f"{RICK_AND_MORTY_API}{char_id}").json()
    else:
        return redirect(url_for('home'))
    
    if form.validate_on_submit():
        transaccion = {
            'cuenta_origen': 'Cuenta Origen',
            'cuenta_destino': character['name'],
            'monto': float(form.monto.data)
        }
        try:
            mensaje_json = json.dumps(transaccion)
            channel.basic_publish(exchange='',
                                  routing_key='transaccionesQueue',
                                  body=mensaje_json,
                                  properties=pika.BasicProperties(delivery_mode=2))

            sql = "INSERT INTO transacciones (cuenta_origen, cuenta_destino, monto) VALUES (%s, %s, %s)"
            val = (transaccion['cuenta_origen'], transaccion['cuenta_destino'], transaccion['monto'])
            db_cursor.execute(sql, val)
            db_conn.commit()

            session['transaction_processed'] = True  # Marcar como procesada
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Error al procesar la transacción: {e}")
            return str(e), 500
    
    return render_template('transaction.html', form=form, character=character)

if __name__ == '__main__':
    app.run(port=3000)
