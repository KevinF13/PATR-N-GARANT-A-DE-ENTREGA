from flask import Flask, request, render_template, redirect, url_for
import pika
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
import mysql.connector

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'

class MessageForm(FlaskForm):
    message = StringField('Message', validators=[DataRequired()])
    submit = SubmitField('Send')

# Conexión a RabbitMQ
try:
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'localhost', 5672, '/', pika.PlainCredentials('kevin', '13demayo')
    ))
    channel = connection.channel()
    channel.queue_declare(queue='myQueue', durable=True)
except pika.exceptions.AMQPConnectionError as e:
    print(f"Error al conectar con RabbitMQ: {e}")

# Conexión a MySQL
db_conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="mensajes_db"
)
db_cursor = db_conn.cursor()

@app.route('/', methods=['GET', 'POST'])
def index():
    form = MessageForm()
    if form.validate_on_submit():
        message = form.message.data
        try:
            # Publicar mensaje en RabbitMQ
            channel.basic_publish(exchange='',
                                  routing_key='myQueue',
                                  body=message,
                                  properties=pika.BasicProperties(delivery_mode=2))  # make message persistent

            # Guardar mensaje en MySQL
            sql = "INSERT INTO mensajes (contenido) VALUES (%s)"
            val = (message,)
            db_cursor.execute(sql, val)
            db_conn.commit()

            return redirect(url_for('index'))
        except Exception as e:
            return str(e), 500
    return render_template('index.html', form=form)

if __name__ == '__main__':
    app.run(port=3000)
