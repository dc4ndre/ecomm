from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask import Flask, render_template
import sqlite3
import hashlib
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'qwertyasdfghxcvbn'

INSTANCE_PATH = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(INSTANCE_PATH, exist_ok=True)
app.config['DATABASE_PATH'] = os.path.join(INSTANCE_PATH, 'ecommerce.db')

class DatabaseManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or app.config['DATABASE_PATH']
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'customer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                price DECIMAL(10,2) NOT NULL,
                stock INTEGER NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # default admin user
        admin_password = self.hash_password("admin123")
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ("admin", "admin@ecommerce.com", admin_password, "admin"))
        
        conn.commit()
        conn.close()
    
    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()
    
    def execute_query(self, query, params=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        result = cursor.fetchall()
        conn.commit()
        conn.close()
        return result
    
    def execute_insert(self, query, params):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return last_id

# Initialize database
db = DatabaseManager()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Please fill in all fields'})
        
        # Hash password for comparison
        password_hash = db.hash_password(password)
        
        user_data = db.execute_query(
            "SELECT id, username, email, role FROM users WHERE (username = ? OR email = ?) AND password_hash = ?",
            (username, username, password_hash)
        )
        
        if user_data:
            user_id, username, email, role = user_data[0]
            
            # HASH TABLE: Store user session data
            session['user_id'] = user_id
            session['username'] = username
            session['email'] = email
            session['role'] = role
            
            return jsonify({
                'success': True, 
                'role': role,
                'redirect': '/admin' if role == 'admin' else '/dashboard'
            })
        else:
            return jsonify({'success': False, 'message': 'Invalid username/email or password'})
    
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    return render_template('admin_dashboard.html', user=session)

# Helper function for peso formatting
def format_peso(amount):
    return f"₱{amount:,.2f}"

@app.template_filter('peso')
def peso_filter(amount):
    return format_peso(float(amount))

@app.route('/api/admin/products')
def admin_get_products():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    products = db.execute_query('''
        SELECT p.id, p.name, p.description, p.price, p.stock, p.is_active
        FROM products p
        ORDER BY p.id DESC
    ''')
    
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'description': product[2],
            'price': product[3],
            'price_formatted': format_peso(product[3]),
            'stock': product[4],
            'is_active': bool(product[5])
        })
    
    return jsonify(products_list)

@app.route('/api/admin/products', methods=['POST'])
def admin_add_product():
    if 'user_id' not in session or session['role'] != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    
    try:
        db.execute_insert('''
            INSERT INTO products (name, description, price, stock, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['name'],
            data['description'],
            float(data['price']),
            int(data['stock']),
            bool(data.get('is_active', True))
        ))
        
        return jsonify({'success': True, 'message': 'Product added successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))

    return render_template('admin_products.html', user=session)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
