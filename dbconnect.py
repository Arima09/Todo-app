import sqlite3

# Connect to the SQLite database (this will create 'todo.db' if it doesn't exist)
conn = sqlite3.connect('todo.db')
cursor = conn.cursor()

# Create the 'tasks' table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT 0,
    priority TEXT DEFAULT 'Medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    user_id INTEGER,
    due_date DATE,
    category TEXT,
    recurrence TEXT,
    next_due_date DATE,
    progress INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
''')

# Create the 'users' table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
''')

'''(CREATE TABLE subtasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL, 
    title TEXT NOT NULL, 
    completed INTEGER DEFAULT 0, 
    FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
)
)'''

# Commit the changes to the database
conn.commit()

# Close the connection
conn.close()


