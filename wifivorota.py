from flask import Flask, request, Response
from flask_sock import Sock
from flask_cors import CORS
import time
import urllib.parse
import threading

app = Flask(__name__)
sockets = Sock(app)
CORS(app)

class Camera:
    def __init__(self, socket):
        self.clients = 0
        self.latestFrameId = 0
        self.latestFrame = None
        self.socket = socket
        self.streamSocket = None
        self.socketLock = threading.Lock()

cameras = {}

@sockets.route('/api/')
def tunnel_socket(ws):
    global cameras
    login = request.args['login']
    cameras[login] = Camera(ws)
    print("camera '"+login+"' connected")
    while(True):
        time.sleep(1)

@sockets.route('/stream/')
def stream_socket(ws):
    global cameras
    login = request.args['login']
    cameras[login].streamSocket = ws
    print("camera '"+login+"' stream started")
    while(True):
        cameras[login].latestFrame = cameras[login].streamSocket.receive()
        cameras[login].latestFrameId += 1

@app.route('/api/')
def api():
    global cameras
    login = request.args['login']
    cameras[login].socketLock.acquire()
    cameras[login].socket.send('?'+request.query_string.decode())
    result = cameras[login].socket.receive()
    cameras[login].socketLock.release()
    return result

def gather_img(login,password):
    global cameras
    sentFrameId = 0
    try:
        cameras[login].clients += 1
        print("cameraClients = "+str(cameras[login].clients))

        cameras[login].socketLock.acquire()
        cameras[login].socket.send('?cmd=wan_stream&login='+urllib.parse.quote(login)+'&password='+urllib.parse.quote(password))
        print('?cmd=wan_stream&login='+urllib.parse.quote(login)+'&password='+urllib.parse.quote(password))
        print(cameras[login].socket.receive())
        cameras[login].socketLock.release()
        
        while True:
            while(cameras[login].latestFrameId==sentFrameId):
                time.sleep(0.01)
            sentFrameId = cameras[login].latestFrameId
            yield (b'--JPEG_FRAME\r\nContent-Type: image/jpeg\r\n\r\n' + cameras[login].latestFrame + b'\r\n')
    finally:
        cameras[login].clients -= 1
        print("cameraClients = "+str(cameras[login].clients))   
        if(cameras[login].clients == 0):
            cameras[login].streamSocket.close()

@app.route('/stream/')
def stream():
    login = request.args['login']
    password = request.args['password']
    return Response(gather_img(login,password), mimetype='multipart/x-mixed-replace; boundary=JPEG_FRAME')


if __name__ == "__main__":
    app.run(host="0.0.0.0",port=8080, threaded=True)