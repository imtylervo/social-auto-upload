import sqlite3
import json
import os

# Database file path (created automatically if it does not exist)
db_file = './database.db'

# If the database already exists, delete the old tables (optional)
# if os.path.exists(db_file):
#     os.remove(db_file)

# Connect to the SQLite database (the file is created automatically if it does not exist)
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Create the account table
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,  -- 存储文件路径
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0
)
''')

# Create the file records table
cursor.execute('''CREATE TABLE IF NOT EXISTS file_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 唯一标识每条记录
    filename TEXT NOT NULL,               -- 文件名
    filesize REAL,                     -- 文件大小（单位：MB）
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 上传时间，默认当前时间
    file_path TEXT                        -- 文件路径
)
''')


# Commit the changes
conn.commit()
print("✅ Tables created")
# Close the connection
conn.close()