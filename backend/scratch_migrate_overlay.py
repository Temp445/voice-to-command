import sqlite3
import sys

def main():
    try:
        conn = sqlite3.connect('ace_local.db')
        conn.execute('ALTER TABLE settings ADD COLUMN enable_desktop_overlay BOOLEAN DEFAULT 1;')
        conn.commit()
        print("Column added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("Column already exists.")
        else:
            print(f"Error: {e}")
            sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
