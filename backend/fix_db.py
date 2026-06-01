
import sqlite3
conn = sqlite3.connect('ace_local.db')
c = conn.cursor()
try:
    c.execute('UPDATE user_settings SET tts_provider=''gtts''')
    conn.commit()
    print('Updated user_settings')
except Exception as e:
    print('Error:', e)
conn.close()

