# A simple Flask app demonstrating the use of sessions, variable sections
# in a URL, and the Jinja templating language.


# Note what has to be imported.
from flask import Flask,request,redirect,render_template, session, url_for, g
from psycopg2 import connect
from psycopg2.extras import DictCursor
from functools import wraps
from flask import abort



# Create the application object and configure it.  ALL configuration should
# be done in config.py, so that the application file (this file) only
# contains application logic.
app = Flask(__name__)
app.config.from_pyfile('config.py')


# Cleans up the response time and if it recieves a response

@app.after_request
def afterReq(response):
	closeDb()
	return response

# Retrive the Database BOB
# Connecting the to the Database BOB

def getDb():
	if 'db' not in g:
		g.db = connect(dbname=app.config['BOB_DB'],
		                user=app.config['BOB_USER'],
						password=app.config['BOB_PW'],
						cursor_factory=DictCursor)
	return g.db
	

def closeDb():
	db = g.pop('db', None)
	if db is not None:
		db.close()
		
@app.route('/')
def home():
    # Fetch users from the database (existing functionality)
    with getDb().cursor() as cur:
        cur.execute('SELECT * FROM Users ORDER BY ID ASC;')
        bob = cur.fetchall()

    # Fetch products from the database
    with getDb().cursor() as cur:
        cur.execute('SELECT * FROM items;')
        products = cur.fetchall()

    # Pass both 'bob' and 'products' to the template
    return render_template('bob.html', user=session.get('user'), bob=bob, products=products)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = getDb()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']  # 'admin' or 'user'
            return redirect(url_for('home'))
        else:
            return "Invalid credentials", 403
    return render_template('login.html')
    
@app.route('/add_products', methods=['GET', 'POST'])
def add_products():
	if request.method == 'POST':
		name = request.form['name']
		price = request.form['price']
		description = request.form['description']
		image_url = request.form['image_url']
		
		with getDb() as conn:
			with conn.cursor() as cur:
				cur.execute("""
    INSERT INTO items (name, price, description, image_url)
    VALUES (%s, %s, %s, %s)
""", (name, price, description, image_url))

				conn.commit()
		
		return redirect(url_for('home'))
	
	return render_template('add_product.html') 
	
@app.route('/products')
def show_products():
	with getDb() as conn:
		with conn.cursor() as cur:
			cur.execute("SELECT * FROM items")
			products = cur.fetchall()
			
	return render_template('product_list.html', products=products)
			
@app.route('/admin')
def admin_dashboard():
	if 'user' not in session:
		return redirect(url_for('login'))
	return "<h1>Welcome, Admin!</h1><p>You are now logged in.</p>"
	
@app.route('/search')
def search():
    query = request.args.get('query')
    results = []

    if query:
        with getDb().cursor() as cur:
            cur.execute("""
                SELECT name, price, description, image_url
                FROM items
                WHERE LOWER(name) LIKE %(query)s OR LOWER(description) LIKE %(query)s;
            """, {'query': f'%{query.lower()}%'})
            results = cur.fetchall()

    return render_template('search_results.html', query=query, results=results)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/add_products', methods=['GET', 'POST'])
@admin_required
def add_products_form():
    # Only admins can access this
    return render_template('add_product.html')
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with getDb() as conn:
            with conn.cursor() as cur:
                # Check if user already exists
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                existing_user = cur.fetchone()

                if existing_user:
                    return render_template('register.html', error="Username already taken.")
                
                # Insert new user with default role 'user'
                cur.execute("""
                    INSERT INTO users (username, password, role)
                    VALUES (%s, %s, 'user')
                """, (username, password))
                conn.commit()

        return redirect(url_for('login'))
    return render_template('register.html')
    

@app.route('/place_bid/<int:item_id>', methods=['POST'])
def place_bid(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Ensure user is logged in

    # Get the bid amount from the form
    bid_amount = request.form['bid_amount']

    # Update the item with the new bid amount
    with getDb() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE items
                SET price = %s
                WHERE id = %s
            """, (bid_amount, item_id))
            conn.commit()

    # Debug print statement to ensure bid was placed
    print(f"Bid of ${bid_amount} placed for item {item_id}")

    # Redirect to the confirmation page
    return redirect(url_for('show_bid_confirmation', item_id=item_id, bid_amount=bid_amount))


@app.route('/bid_confirmation/<int:item_id>/<bid_amount>')
def show_bid_confirmation(item_id, bid_amount):
    # Fetch the product to display the confirmation
    with getDb() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
            product = cur.fetchone()

    # Ensure product data is found
    if not product:
        return "Product not found!", 404

    # Debug print statement to confirm the confirmation page is reached
    print(f"Showing confirmation for item {item_id} with bid ${bid_amount}")

    # Return the bid confirmation page
    return render_template('bid_confirmation.html', product=product, bid_amount=bid_amount)

    

if __name__ != '__main__':
    application = app
