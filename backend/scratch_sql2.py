import sqlite3
conn = sqlite3.connect('file_cache.db')
c = conn.cursor()
c.execute("SELECT count(*) FROM files WHERE path LIKE '%Nivin_Sync%'")
print(c.fetchall())
c.execute("SELECT name, path FROM files WHERE name LIKE '%demo45.txt%'")
print(c.fetchall())
