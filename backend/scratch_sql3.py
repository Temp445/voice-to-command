import sqlite3
conn = sqlite3.connect('file_cache.db')
c = conn.cursor()
c.execute("SELECT id, name, path FROM files ORDER BY id DESC LIMIT 10")
for row in c.fetchall(): print(row)
