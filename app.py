import sqlite3
from datetime import datetime,timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
scheduler.start()
# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure secret key

# Initialize Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)  # Attach LoginManager to Flask app
login_manager.login_view = 'login'  # Redirect to 'login' if unauthenticated


class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Get the form data
        username = request.form['username']
        password = request.form['password']

        # Hash the password
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Check if the username already exists
        existing_user = get_user_by_username(username)
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return redirect(url_for('register'))

        # Insert the new user into the database
        conn = get_db_connection()
        conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
        conn.commit()
        conn.close()

        # Redirect to the login page with a success message
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    # Render the registration template for GET requests
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Retrieve form data
        username = request.form['username']
        password = request.form['password']

        # Fetch the user from the database
        user = get_user_by_username(username)

        # Check if user exists and password is correct
        if user and bcrypt.check_password_hash(user['password'], password):
            # Log in the user
            login_user(User(user['id'], user['username'], user['password']))
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    # Render the login template for GET requests
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user['id'], user['username'], user['password'])
    return None


def get_db_connection():
    # Update this path to match the location of your SQLite database
    conn = sqlite3.connect('todo.db')  # Change 'path_to_your_database.db'
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    conn = get_db_connection()

    # Check for overdue tasks
    overdue_tasks = conn.execute('''
        SELECT * FROM tasks 
        WHERE user_id = ? AND due_date < ? AND completed = 0
    ''', (current_user.id, datetime.now().date())).fetchall()

    if overdue_tasks:
        flash(f'You have {len(overdue_tasks)} overdue task(s).', 'warning')

    if request.method == 'POST':
        title = request.form['title']
        priority = request.form['priority']
        due_date = request.form['due_date']
        category = request.form['category']  # Get the category from the form
        user_id = current_user.id
        progress = request.form['progress']  # Get progress value from form

        # Insert new task into the database
        conn.execute('''
            INSERT INTO tasks (title, priority, due_date, category, user_id,progress)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, priority, due_date, category, user_id,progress))
        conn.commit()

    # Fetch tasks from the database
    tasks = conn.execute('''
        SELECT * FROM tasks 
        WHERE user_id = ? 
        ORDER BY 
            CASE 
                WHEN priority = 'High' THEN 1 
                WHEN priority = 'Medium' THEN 2 
                ELSE 3 
            END, id DESC
    ''', (current_user.id,)).fetchall()

    # Fetch tasks with upcoming due dates
    upcoming_tasks = conn.execute('''
        SELECT * FROM tasks
        WHERE user_id = ? AND due_date IS NOT NULL AND due_date >= ?
        ORDER BY due_date ASC
    ''', (current_user.id, datetime.now())).fetchall()

    # Fetch distinct categories for filtering
    categories = conn.execute('SELECT DISTINCT category FROM tasks WHERE user_id = ?', (current_user.id,)).fetchall()

    conn.close()

    return render_template('index.html', tasks=tasks, upcoming_tasks=upcoming_tasks, categories=categories)


from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

@app.route('/add', methods=['POST'])
def add_task():
    task_title = request.form['title']
    priority = request.form.get('priority', 'Medium')  # Default to Medium if not provided
    due_date = request.form['due_date']
    category = request.form['category']  # Get the category from the form
    recurrence = request.form['recurrence']  # Get the recurrence from the form
    progress = request.form.get('progress', 0)  # Default to 0 if not provided

    # Convert due_date from string to date
    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()

    conn = get_db_connection()

    # Insert the task into the database
    conn.execute('''
        INSERT INTO tasks (title, priority, due_date, category, recurrence, user_id,progress) 
        VALUES (?, ?, ?, ?, ?, ?,?)
    ''', (task_title, priority, due_date, category, recurrence, current_user.id,progress))
    conn.commit()

    # If it's a recurring task, schedule the next task
    if recurrence != 'None':
        next_due_date = calculate_next_due_date(due_date, recurrence)
        conn.execute('UPDATE tasks SET next_due_date = ? WHERE user_id = ? AND title = ?',
                     (next_due_date, current_user.id, task_title))
        conn.commit()

    conn.close()

    # If recurrence is set, add a scheduled task
    if recurrence != 'None':
        scheduler = BackgroundScheduler()
        scheduler.add_job(func=create_recurring_task, trigger='interval', days=1, next_run_time=datetime.now(), args=[current_user.id, task_title, recurrence])
        scheduler.start()

    return redirect('/')



@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    conn = get_db_connection()
    completed_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?', (completed_at, task_id))
    conn.commit()
    conn.close()
    return redirect('/')

def calculate_next_due_date(due_date, recurrence):
    if recurrence == 'Daily':
        return due_date + timedelta(days=1)
    elif recurrence == 'Weekly':
        return due_date + timedelta(weeks=1)
    elif recurrence == 'Monthly':
        # Adding 30 days as an approximation for monthly recurrence
        return due_date + timedelta(days=30)
    return due_date  # No recurrence

def create_recurring_task(user_id, task_title, recurrence):
    """Creates a new recurring task based on the recurrence setting."""
    conn = get_db_connection()

    # Fetch the last created task for the user with that title
    task = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND title = ? AND recurrence = ?',
                        (user_id, task_title, recurrence)).fetchone()

    if task:
        # Calculate next due date based on the recurrence
        next_due_date = calculate_next_due_date(task['due_date'], recurrence)

        # Insert the recurring task into the database
        conn.execute('INSERT INTO tasks (title, priority, due_date, category, recurrence, user_id, next_due_date) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                     (task['title'], task['priority'], next_due_date, task['category'], task['recurrence'], user_id, next_due_date))
        conn.commit()

    conn.close()


@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect('/')


@app.route('/view_all')
def view_all():
    conn = get_db_connection()
    tasks = conn.execute('SELECT * FROM tasks ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('view_all.html', tasks=tasks)


@app.route('/update/<int:task_id>', methods=['GET', 'POST'])
@login_required
def update_task(task_id):
    conn = get_db_connection()
    if request.method == 'POST':
        new_title = request.form['title']
        priority = request.form.get('priority', 'Medium')
        conn.execute('UPDATE tasks SET title = ?, priority = ? WHERE id = ? AND user_id = ?',
                     (new_title, priority, task_id, current_user.id))
        conn.commit()
        conn.close()
        return redirect('/')
    else:
        task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, current_user.id)).fetchone()
        conn.close()
        return render_template('update_task.html', task=task)
    
@app.route('/analytics')
@login_required
def analytics():
    conn = get_db_connection()
    
    # Calculate total tasks completed
    total_completed = conn.execute('''
        SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 1
    ''', (current_user.id,)).fetchone()[0]
    
    # Calculate average completion time (in days)
    avg_completion_time = conn.execute('''
        SELECT AVG(JULIANDAY(completed_at) - JULIANDAY(created_at)) 
        FROM tasks WHERE user_id = ? AND completed = 1
    ''', (current_user.id,)).fetchone()[0]
    
    # Calculate category-wise task distribution
    category_distribution = conn.execute('''
        SELECT category, COUNT(*) FROM tasks WHERE user_id = ? 
        GROUP BY category
    ''', (current_user.id,)).fetchall()
    
    conn.close()
    
    return render_template('analytics.html', total_completed=total_completed,
                           avg_completion_time=avg_completion_time, 
                           category_distribution=category_distribution)

@app.route('/update_progress/<int:task_id>', methods=['POST'])
def update_progress(task_id):
    new_progress = request.form['progress']
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE tasks
        SET progress = ?
        WHERE id = ? AND user_id = ?
    ''', (new_progress, task_id, current_user.id))
    conn.commit()
    conn.close()

    return redirect('/')

@app.route('/add_subtask/<int:task_id>', methods=['POST'])
@login_required
def add_subtask(task_id):
    title = request.form['title']
    conn = get_db_connection()
    conn.execute('INSERT INTO subtasks (task_id, title) VALUES (?, ?)', (task_id, title))
    conn.commit()
    conn.close()
    flash('Subtask added successfully!', 'success')
    return redirect('/')

def update_task_progress(task_id):
    conn = get_db_connection()
    subtasks = conn.execute('SELECT COUNT(*) FROM subtasks WHERE task_id = ?', (task_id,)).fetchone()[0]
    completed_subtasks = conn.execute(
        'SELECT COUNT(*) FROM subtasks WHERE task_id = ? AND completed = 1', 
        (task_id,)
    ).fetchone()[0]
    
    progress = (completed_subtasks / subtasks * 100) if subtasks > 0 else 0
    conn.execute('UPDATE tasks SET progress = ? WHERE id = ?', (progress, task_id))
    conn.commit()
    conn.close()

@app.route('/complete_subtask/<int:subtask_id>', methods=['POST'])
@login_required
def complete_subtask(subtask_id):
    conn = get_db_connection()
    subtask = conn.execute('SELECT task_id, completed FROM subtasks WHERE id = ?', (subtask_id,)).fetchone()
    new_status = 1 if subtask['completed'] == 0 else 0
    conn.execute('UPDATE subtasks SET completed = ? WHERE id = ?', (new_status, subtask_id))
    conn.commit()
    update_task_progress(subtask['task_id'])
    conn.close()
    flash('Subtask updated successfully!', 'success')
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
