import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = 'super_secret_key_ticketing_tool'

DB_PATH = '/tmp/ticketing.db' if os.path.exists('/tmp') else 'ticketing.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            assigned_to INTEGER,
            FOREIGN KEY (created_by) REFERENCES users(user_id),
            FOREIGN KEY (assigned_to) REFERENCES users(user_id)
        )
    ''')

    # Seed initial demo users if table is freshly created
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('ADM-1001', 'Mani Admin', 'mani@helpdesk.com', 'admin123', 'ADMIN')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('ADM-1002', 'Santhosh Admin', 'santhosh@helpdesk.com', 'admin123', 'ADMIN')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('EMP-2001', 'Amulya', 'amulya@helpdesk.com', 'emp123', 'EMPLOYEE')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('EMP-2002', 'Taruni', 'taruni@helpdesk.com', 'emp123', 'EMPLOYEE')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('EMP-2003', 'Godha', 'godha@helpdesk.com', 'emp123', 'EMPLOYEE')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('EMP-2004', 'Amitha', 'amitha@helpdesk.com', 'emp123', 'EMPLOYEE')")
        cursor.execute("INSERT OR IGNORE INTO users (custom_id, username, email, password, role) VALUES ('CLT-1001', 'Rahul Client', 'client1@gmail.com', 'client123', 'CLIENT')")
        cursor.execute("INSERT OR IGNORE INTO tickets (title, description, category, priority, status, created_by, assigned_to) VALUES ('VPN Access Request', 'Need VPN configuration for remote office access.', 'IT Support', 'HIGH', 'OPEN', 7, 3)")

    conn.commit()
    conn.close()

def get_db():
    init_db()  # Guarantees tables exist on EVERY serverless invocation
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.before_request
def ensure_db_ready():
    init_db()

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password'].strip()

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid email or password!'

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'CLIENT').strip()

        conn = get_db()
        cursor = conn.cursor()

        # Generate custom_id safely
        prefix = 'CLT' if role == 'CLIENT' else ('EMP' if role == 'EMPLOYEE' else 'ADM')
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", (role,))
        count = cursor.fetchone()[0] + 1
        custom_id = f"{prefix}-{1000 + count}"

        try:
            cursor.execute(
                "INSERT INTO users (custom_id, username, email, password, role) VALUES (?, ?, ?, ?, ?)",
                (custom_id, username, email, password, role)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception as e:
            conn.close()
            return render_template('register.html', error=f"Registration failed: {str(e)}")

    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    role = session['role']
    conn = get_db()

    # Role-Based Data Isolation
    if role == 'ADMIN':
        query = '''
            SELECT t.*, u1.username as client_name, u2.username as emp_name 
            FROM tickets t 
            JOIN users u1 ON t.created_by = u1.user_id 
            LEFT JOIN users u2 ON t.assigned_to = u2.user_id
            ORDER BY t.ticket_id DESC
        '''
        tickets = conn.execute(query).fetchall()
    elif role == 'EMPLOYEE':
        query = '''
            SELECT t.*, u1.username as client_name, u2.username as emp_name 
            FROM tickets t 
            JOIN users u1 ON t.created_by = u1.user_id 
            LEFT JOIN users u2 ON t.assigned_to = u2.user_id
            WHERE t.assigned_to = ? OR t.assigned_to IS NULL
            ORDER BY t.ticket_id DESC
        '''
        tickets = conn.execute(query, (user_id,)).fetchall()
    else:
        query = '''
            SELECT t.*, u1.username as client_name, u2.username as emp_name 
            FROM tickets t 
            JOIN users u1 ON t.created_by = u1.user_id 
            LEFT JOIN users u2 ON t.assigned_to = u2.user_id
            WHERE t.created_by = ?
            ORDER BY t.ticket_id DESC
        '''
        tickets = conn.execute(query, (user_id,)).fetchall()

    employees = conn.execute("SELECT * FROM users WHERE role = 'EMPLOYEE'").fetchall()
    conn.close()

    return render_template('dashboard.html', tickets=tickets, employees=employees)

@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    if 'user_id' not in session or session['role'] != 'CLIENT':
        return redirect(url_for('login'))

    title = request.form['title']
    category = request.form['category']
    priority = request.form['priority']
    description = request.form['description']
    created_by = session['user_id']

    conn = get_db()
    conn.execute('''
        INSERT INTO tickets (title, description, category, priority, status, created_by)
        VALUES (?, ?, ?, ?, 'OPEN', ?)
    ''', (title, description, category, priority, created_by))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/assign_ticket/<int:ticket_id>', methods=['POST'])
def assign_ticket(ticket_id):
    if 'user_id' not in session or session['role'] != 'ADMIN':
        return redirect(url_for('login'))

    employee_id = request.form['employee_id']

    conn = get_db()
    conn.execute('UPDATE tickets SET assigned_to = ? WHERE ticket_id = ?', (employee_id, ticket_id))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/update_status/<int:ticket_id>', methods=['POST'])
def update_status(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    status = request.form['status']

    conn = get_db()
    conn.execute('UPDATE tickets SET status = ? WHERE ticket_id = ?', (status, ticket_id))
    conn.commit()
    conn.close()

    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)