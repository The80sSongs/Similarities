from flask import Flask
from threading import Thread
#import socket

app = Flask('')

def run(port):
    app.run(host='0.0.0.0', port=port)

def keep_alive(port):
    t = Thread(target=run, args=(port,))
    t.start()
