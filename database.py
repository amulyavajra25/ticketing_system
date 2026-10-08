import sqlite3

def init_db():
    conn = sqlite3.connect('ticketing.db')
    cursor = conn.cursor()

    # Create Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # Create Tickets Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_by INTEGER NOT NULL,
            assigned_to INTEGER,
            FOREIGN KEY (created_by) REFERENCES users (user_id),
            FOREIGN KEY (assigned_to) REFERENCES users (user_id)
        )
    ''')

    # Insert All Demo Users
    users = [
        # Administrators
        ('Mani', 'mani@helpdesk.com', 'admin123', 'ADMIN'),
        ('Santhosh', 'santhosh@helpdesk.com', 'admin123', 'ADMIN'),
        
        # Employees
        ('Amulya', 'amulya@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('Taruni', 'taruni@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('Godha', 'godha@helpdesk.com', 'emp123', 'EMPLOYEE'),
        ('Amitha', 'amitha@helpdesk.com', 'emp123', 'EMPLOYEE'),
        
        # Clients
        ('Client 1', 'client1@gmail.com', 'client123', 'CLIENT'),
        ('Client 2', 'client2@gmail.com', 'client123', 'CLIENT'),
        ('Client 3', 'client3@gmail.com', 'client123', 'CLIENT')
    ]

    cursor.executemany('''
        INSERT OR IGNORE INTO users (username, email, password, role)
        VALUES (?, ?, ?, ?)
    ''', users)

    conn.commit()
    conn.close()
    print("Database initialized successfully with updated accounts!")

if __name__ == '__main__':
    init_db()