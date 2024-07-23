import pika
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecret'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

def callback(ch, method, properties, body):
    message = body.decode()
    print(f'Mensaje recibido: {message}')
    socketio.emit('new_message', {'message': message})
    ch.basic_ack(delivery_tag=method.delivery_tag)

def consume():
    connection = pika.BlockingConnection(pika.ConnectionParameters(
        'localhost', 5672, '/', pika.PlainCredentials('kevin', '13demayo')
    ))
    channel = connection.channel()
    channel.queue_declare(queue='myQueue', durable=True)
    channel.basic_consume(queue='myQueue', on_message_callback=callback)
    print('Esperando mensajes. Presiona Ctrl+C para salir')
    channel.start_consuming()

@socketio.on('connect')
def handle_connect():
    emit('response', {'data': 'Connected'})

if __name__ == '__main__':
    socketio.start_background_task(target=consume)
    socketio.run(app, port=5000)
