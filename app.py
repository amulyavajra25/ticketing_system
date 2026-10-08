import os
import sqlite3
import uuid
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = 'super_secret_key_ticketing_tool'

DB_PATH = '/tmp/ticketing.db' if os.path.exists('/tmp') else 'ticketing.db'

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
    except sqlite3.OperationalError:
        pass
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            custom_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT CHECK(role IN ('ADMIN', 'EMPLOYEE', 'CLIENT')) NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT CHECK(priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')) NOT NULL,
            status TEXT CHECK(status IN ('OPEN', 'WORK_IN_PROGRESS', 'RESOLVED', 'CLOSED')) DEFAULT 'OPEN',
            created_by INTEGER NOT NULL,
            assigned_to INTEGER
        )
    ''')

    # Force update or insert demo users safely
    demo_users = [
        ('ADM-1001', 'Mani Admin', 'mani@helpdesk.com', 'admin123', 'ADMIN'),
        ('ADM-1002', 'Santhosh Admin', 'santhosh@helpdesk.com', 'admin123', 'ADMIN'),
        ('EMP-2001', 'Amulya', 'amulya@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('EMP-2002', 'Taruni', 'taruni@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('EMP-2003', 'Godha', 'godha@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('EMP-2004', 'Amitha', 'amitha@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('CLT-1001', 'Rahul Client', 'client1@gmail.com', 'client123', 'CLIENT'),
        ('CLT-1002', 'Client Two', 'client2@gmail.com', 'client123', 'CLIENT'),
        ('CLT-1003', 'Client Three', 'client3@gmail.com', 'client123', 'CLIENT')
    ]

    for user in demo_users:
        cursor.execute("SELECT user_id FROM users WHERE email = ?", (user[2],))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE users SET password = ?, role = ?, username = ? WHERE email = ?", (user[3], user[4], user[1], user[2]))
        else:
            cursor.execute("INSERT INTO users (custom_id, username, email, password, role) VALUES (?, ?, ?, ?, ?)", user)

    conn.commit()
    conn.close()

@app.before_request
def before_request_func():
    init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
            user = cursor.fetchone()
            if user:
                # Store email instead of ID to prevent serverless instance ID mismatch
                session['email'] = user['email']
                session['username'] = user['username']
                session['role'] = user['role']
                session['custom_id'] = user['custom_id']
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid email or password.'
        except Exception as e:
            error = f'Login error: {str(e)}'
        finally:
            conn.close()

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'CLIENT').strip()

        prefix = 'CLT' if role == 'CLIENT' else ('EMP' if role == 'EMPLOYEE' else 'ADM')
        custom_id = f"{prefix}-{uuid.uuid4().hex[:4].upper()}"

        conn = get_db()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (custom_id, username, email, password, role) VALUES (?, ?, ?, ?, ?)",
                (custom_id, username, email, password, role)
            )
            conn.commit()
            return redirect(url_for('login'))
        except Exception as e:
            error = f"Registration failed: {str(e)}"
        finally:
            conn.close()

    return render_template('register.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    conn = get_db()
    try:
        cursor = conn.cursor()
        role = session.get('role')
        email = session.get('email')

        # Fetch current user's DB ID dynamically
        cursor.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        current_user = cursor.fetchone()
        if not current_user:
            session.clear()
            return redirect(url_for('login'))
        user_id = current_user['user_id']

        if role == 'ADMIN':
            cursor.execute('''
                SELECT t.*, u.username as creator_name, COALESCE(e.username, 'Unassigned') as assignee_name 
                FROM tickets t 
                JOIN users u ON t.created_by = u.user_id 
                LEFT JOIN users e ON t.assigned_to = e.user_id
            ''')
        elif role == 'EMPLOYEE':
            cursor.execute('''
                SELECT t.*, u.username as creator_name, COALESCE(e.username, 'Unassigned') as assignee_name 
                FROM tickets t 
                JOIN users u ON t.created_by = u.user_id 
                LEFT JOIN users e ON t.assigned_to = e.user_id 
                WHERE t.assigned_to = ? OR t.assigned_to IS NULL
            ''', (user_id,))
        else: # CLIENT
            cursor.execute('''
                SELECT t.*, u.username as creator_name, COALESCE(e.username, 'Unassigned') as assignee_name 
                FROM tickets t 
                JOIN users u ON t.created_by = u.user_id 
                LEFT JOIN users e ON t.assigned_to = e.user_id 
                WHERE t.created_by = ?
            ''', (user_id,))
        
        tickets = cursor.fetchall()
        cursor.execute("SELECT * FROM users WHERE role = 'EMPLOYEE'")
        employees = cursor.fetchall()
    finally:
        conn.close()

    return render_template('dashboard.html', tickets=tickets, employees=employees)

@app.route('/create_ticket', methods=['GET', 'POST'])
def create_ticket():
    if 'email' not in session:
        return redirect(url_for('login'))
    
    error = None
    conn = get_db()
    try:
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            category = request.form.get('category', '').strip()
            priority = request.form.get('priority', 'MEDIUM').strip()
            description = request.form.get('description', '').strip()
            
            # Dynamically fetch user_id based on session email to prevent ID mismatches
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE email = ?", (session['email'],))
            user_row = cursor.fetchone()
            
            if not user_row:
                return redirect(url_for('login'))
            
            created_by = user_row['user_id']

            cursor.execute('''
                INSERT INTO tickets (title, description, category, priority, status, created_by)
                VALUES (?, ?, ?, ?, 'OPEN', ?)
            ''', (title, description, category, priority, created_by))
            conn.commit()
            return redirect(url_for('dashboard'))
    except Exception as e:
        error = f"Ticket creation failed: {str(e)}"
    finally:
        conn.close()

    return render_template('create_ticket.html', error=error)

@app.route('/update_ticket/<int:ticket_id>', methods=['POST'])
def update_ticket(ticket_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    status = request.form.get('status')
    assigned_to = request.form.get('assigned_to')

    conn = get_db()
    try:
        cursor = conn.cursor()
        if status:
            cursor.execute("UPDATE tickets SET status = ? WHERE ticket_id = ?", (status, ticket_id))
        if assigned_to is not None:
            cursor.execute("UPDATE tickets SET assigned_to = ? WHERE ticket_id = ?", (assigned_to if assigned_to else None, ticket_id))
        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)