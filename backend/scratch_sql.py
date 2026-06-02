import sqlite3
conn = sqlite3.connect('file_cache.db')
c = conn.cursor()
c.execute("SELECT name, path FROM files WHERE name LIKE '%demo45%'")
print(c.fetchall())
