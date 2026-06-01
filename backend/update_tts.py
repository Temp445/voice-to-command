import sqlite3
conn = sqlite3.connect('ace_local.db')
c = conn.cursor()
c.execute("UPDATE settings SET tts_provider='gtts'")
conn.commit()
print("Updated TTS provider to gtts")
conn.close()
