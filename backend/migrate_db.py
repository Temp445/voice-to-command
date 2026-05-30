import sqlite3

def migrate():
    print("Running database migration...")
    conn = sqlite3.connect("ace_local.db")
    cursor = conn.cursor()
    
    columns_to_add = [
        ("llm_enabled", "BOOLEAN DEFAULT 1"),
        ("llm_provider", "VARCHAR DEFAULT 'groq'"),
        ("llm_model", "VARCHAR DEFAULT 'llama-3.3-70b-versatile'"),
        ("llm_api_key_encrypted", "VARCHAR"),
        ("llm_temperature", "FLOAT DEFAULT 0.7"),
        ("llm_mode", "VARCHAR DEFAULT 'fallback'")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"Column already exists: {col_name}")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
