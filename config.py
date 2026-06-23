import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required!")

CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@saniedit9')
if not CHANNEL_USERNAME.startswith('@'):
    CHANNEL_USERNAME = '@' + CHANNEL_USERNAME

REQUIRED_REFS = 2
FREE_LINKS = 2
MAX_LINKS_PER_HOUR = 5

DB_PATH = '/data/database.sqlite'
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000').rstrip('/')
PORT = int(os.environ.get('PORT', '8000'))
