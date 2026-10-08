from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'super_secret_key_ticketing_tool'

def get_db():
    conn = sqlite3.connect('ticketing.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        role = request.form['role']

        conn = get_db()
        existing_user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if existing_user:
            error = 'Email address already registered!'
            conn.close()
        else:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (username, email, password, role)
                VALUES (?, ?, ?, ?)
            ''', (username, email, password, role))
            conn.commit()
            
            new_user_id = cursor.lastrowid
            session['user_id'] = new_user_id
            session['username'] = username
            session['role'] = role
            conn.close()

            return redirect(url_for('dashboard'))

    return render_template('register.html', error=error)

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