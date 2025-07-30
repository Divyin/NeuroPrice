# app.py

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session
import pickle
import os
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.cluster import KMeans
from sklearn.ensemble import GradientBoostingClassifier
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import current_user, login_user, logout_user, login_required, LoginManager, UserMixin
from datetime import datetime
import traceback # For detailed error logging

# --- Configuration ---
MODEL_DIR = 'trained_models'
# Corrected feature names to match the Colab notebook exactly for model input
SEGMENTATION_FEATURES = [
    'Age', 'Gender', 'City', 'Occupation', 'Product_Category',
    'Weather', 'Time_of_Day', 'Loyalty_Tier', 'Age_Group',
    'User_Product_Count', 'Purchase_Amount_Scaled'
]
GB_FEATURES = [
    'Age', 'Gender', 'City', 'Occupation', 'Product_Category',
    'Weather', 'Time_of_Day', 'Loyalty_Tier',
    'User_Product_Count', 'Age_Group',
    'Purchase_Amount_Scaled', 'CustomerSegment' # CustomerSegment is the numerical ID
]
# Categorical features that need Label Encoding
CATEGORICAL_COLS = [
    'Gender', 'City', 'Occupation', 'Product_Category',
    'Weather', 'Time_of_Day', 'Loyalty_Tier'
]
DATABASE = 'users_data.db'

# --- Global Model Variables ---
label_encoders = {}
scaler_purchase_amount = None
scaler_segmentation_features = None
kmeans_model = None
segment_mapping = {}
gb_model = None
loading_success = True

print("--- Attempting to Load Trained Models ---")
try:
    with open(os.path.join(MODEL_DIR, 'label_encoders.pkl'), 'rb') as f:
        label_encoders = pickle.load(f)
    print("✓ label_encoders loaded.")

    with open(os.path.join(MODEL_DIR, 'scaler_purchase_amount.pkl'), 'rb') as f:
        scaler_purchase_amount = pickle.load(f)
    print("✓ scaler_purchase_amount loaded.")

    with open(os.path.join(MODEL_DIR, 'scaler_segmentation_features.pkl'), 'rb') as f:
        scaler_segmentation_features = pickle.load(f)
    print("✓ scaler_segmentation_features loaded.")

    with open(os.path.join(MODEL_DIR, 'kmeans_model.pkl'), 'rb') as f:
        kmeans_model = pickle.load(f)
    print("✓ kmeans_model loaded.")

    with open(os.path.join(MODEL_DIR, 'segment_mapping.pkl'), 'rb') as f:
        segment_mapping = pickle.load(f)
    print("✓ segment_mapping loaded.")

    with open(os.path.join(MODEL_DIR, 'gb_model.pkl'), 'rb') as f:
        gb_model = pickle.load(f)
    print("✓ gb_model loaded.")

except FileNotFoundError as e:
    print(f"ERROR: A required model file was not found: {e}")
    print(f"Please ensure the '{MODEL_DIR}' directory exists in the same location as app.py "
            f"and contains all .pkl files from your Colab notebook.")
    loading_success = False
except Exception as e:
    print(f"ERROR: An unexpected error occurred during model loading: {e}")
    print("Check your model files for corruption or version incompatibility.")
    loading_success = False

print("--- All Models Loaded Successfully ---" if loading_success else "!!! API will operate with known model loading errors. !!!")


# --- Flask App Initialization ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_super_secret_key_here_please_change_this_for_security')

# --- Flask-Login Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, username=None):
        self._id = id
        self._username = username

    def get_id(self):
        return str(self._id)

    def get_username(self):
        return self._username

# Flask-Login user loader callback
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_data = conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_data:
        conn.close()
        return User(user_data['id'], username=user_data['username'])
        
    conn.close()
    return None

# --- Database Setup Functions ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        db = get_db_connection()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER NOT NULL,
                gender TEXT NOT NULL,
                city TEXT NOT NULL,
                occupation TEXT NOT NULL,
                loyalty_tier TEXT NOT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_category TEXT NOT NULL,
                original_price REAL NOT NULL,
                quantity INTEGER NOT NULL,
                purchase_date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        db.commit()

        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            db.execute("INSERT INTO users (id, username, password, name, age, gender, city, occupation, loyalty_tier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('user_001', 'alice_u', generate_password_hash('alicepass'), 'Alice', 28, 'Female', 'New York', 'Engineer', 'Gold'))
            db.execute("INSERT INTO users (id, username, password, name, age, gender, city, occupation, loyalty_tier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('user_002', 'bob_u', generate_password_hash('bobpass'), 'Bob', 45, 'Male', 'Los Angeles', 'Artist', 'Silver'))
            # Added a new user for better testing of dynamic creation
            db.execute("INSERT INTO users (id, username, password, name, age, gender, city, occupation, loyalty_tier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('user_003', 'charlie_u', generate_password_hash('charliepass'), 'Charlie', 35, 'Male', 'Houston', 'Doctor', 'Bronze'))
            print("Sample users added.")
        
        # Add sample purchases for user_001 if none exist
        if db.execute("SELECT COUNT(*) FROM purchases WHERE user_id = 'user_001'").fetchone()[0] == 0:
            db.execute("INSERT INTO purchases (user_id, product_name, product_category, original_price, quantity, purchase_date) VALUES (?, ?, ?, ?, ?, ?)",
                       ('user_001', 'Smartphone', 'Electronics', 1499.0, 1, datetime.now().isoformat()))
            db.execute("INSERT INTO purchases (user_id, product_name, product_category, original_price, quantity, purchase_date) VALUES (?, ?, ?, ?, ?, ?)",
                       ('user_001', 'Organic Rice Pack', 'Grocery', 299.0, 2, datetime.now().isoformat()))
            print("Sample purchases for user_001 added.")

        db.commit()
    print("Database initialized and populated with sample data.")

# Call init_db() on app startup to ensure DB is ready
with app.app_context():
    init_db()

# --- Helper Functions ---
# Match Colab notebook's Age_Group function
def get_age_group(age):
    if age < 30:
        return 0  # Young
    elif age < 50:
        return 1  # Mid-age
    else:
        return 2  # Senior

# Match Colab notebook's smart_pricing logic more closely.
def calculate_optimized_price(original_price, conversion_prob, segment_label):
    segment_discount_caps = {
        'Premium Buyer': 0.95,
        'Impulse Buyer': 0.90,
        'Bargain Hunter': 0.88,
        'Budget Buyer': 0.85,
        'New Customer': 0.85
    }
    
    threshold = segment_discount_caps.get(segment_label, 0.90) 
    price_factor = max(threshold, conversion_prob) 
    
    raw_price = original_price * price_factor
    
    capped_by_flat_discount = max(raw_price, original_price - 100) # Price should not go below original - 100
    
    capped_by_percentage = max(capped_by_flat_discount, original_price * 0.70) # Max 30% discount
    
    return max(0.0, capped_by_percentage)

# Helper function for fetching user data and calculating user_product_count
# This will return a dictionary with keys matching your Colab's feature names
def get_user_data_from_db(user_id):
    conn = get_db_connection()
    user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user_row:
        # Calculate User_Product_Count: Sum of quantities from purchases table for the user
        total_products_bought = conn.execute("SELECT SUM(quantity) FROM purchases WHERE user_id = ?", (user_id,)).fetchone()[0] or 0
        
        # Construct dictionary with keys matching Colab notebook's feature names
        user_data = {
            'Age': user_row['age'], 
            'Gender': user_row['gender'],
            'City': user_row['city'],
            'Occupation': user_row['occupation'],
            'Loyalty_Tier': user_row['loyalty_tier'],
            'User_Product_Count': total_products_bought
        }
        conn.close()
        return user_data
    
    conn.close()
    return None


# --- Authentication Routes ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('predict_page'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        age = int(request.form['age'])
        gender = request.form['gender']
        city = request.form['city']
        occupation = request.form['occupation']
        loyalty_tier = request.form['loyalty_tier']

        conn = get_db_connection()
        user_exists = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if user_exists:
            conn.close()
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html', 
                                   user_data=request.form, # Pass form data back to pre-populate (without password)
                                   genders=list(label_encoders.get('Gender', {'classes_': ['Male', 'Female', 'Other']}).classes_), 
                                   cities=list(label_encoders.get('City', {'classes_': ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Miami']}).classes_), 
                                   occupations=list(label_encoders.get('Occupation', {'classes_': ['Engineer', 'Artist', 'Doctor', 'HR', 'Software Dev', 'Other']}).classes_), 
                                   loyalty_tiers=list(label_encoders.get('Loyalty_Tier', {'classes_': ['Gold', 'Silver', 'Bronze', 'None']}).classes_))
        
        hashed_password = generate_password_hash(password)
        
        try:
            last_user_id_num = conn.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM users").fetchone()[0] or 0
            new_id = f"user_{last_user_id_num + 1:03d}"
            conn.execute("INSERT INTO users (id, username, password, name, age, gender, city, occupation, loyalty_tier) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (new_id, username, hashed_password, name, age, gender, city, occupation, loyalty_tier))
            conn.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            conn.rollback()
            flash(f'An error occurred during registration: {e}', 'danger')
        finally:
            conn.close()
    
    # Pre-populate form options for GET request or on error (get from LabelEncoders if possible)
    genders = list(label_encoders.get('Gender', {'classes_':[]}).classes_) if 'Gender' in label_encoders else ['Male', 'Female', 'Other']
    cities = list(label_encoders.get('City', {'classes_':[]}).classes_) if 'City' in label_encoders else ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Miami']
    occupations = list(label_encoders.get('Occupation', {'classes_':[]}).classes_) if 'Occupation' in label_encoders else ['Engineer', 'Artist', 'Doctor', 'HR', 'Software Dev', 'Other']
    loyalty_tiers = list(label_encoders.get('Loyalty_Tier', {'classes_':[]}).classes_) if 'Loyalty_Tier' in label_encoders else ['Gold', 'Silver', 'Bronze', 'None']

    # Default options if label_encoders are not loaded
    if not genders: genders = ['Male', 'Female', 'Other']
    if not cities: cities = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Miami']
    if not occupations: occupations = ['Engineer', 'Artist', 'Doctor', 'HR', 'Software Dev', 'Other']
    if not loyalty_tiers: loyalty_tiers = ['Gold', 'Silver', 'Bronze', 'None']

    return render_template('register.html', 
                           genders=genders, 
                           cities=cities, 
                           occupations=occupations, 
                           loyalty_tiers=loyalty_tiers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash('You are already logged in.', 'info')
        return redirect(url_for('predict_page'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user_row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user_row and check_password_hash(user_row['password'], password):
            user = User(user_row['id'], username=user_row['username'])
            login_user(user)
            flash(f'Logged in successfully as {user.get_username()}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('predict_page'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required 
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


# --- Routes for Serving HTML Pages ---
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', current_user=current_user)

@app.route('/shop', methods=['GET'])
def shop():
    return render_template('shop.html', current_user=current_user)

@app.route('/cart', methods=['GET'])
def cart():
    return render_template('cart.html', current_user=current_user)

@app.route('/predict', methods=['GET'])
def predict_page():
    user_data_for_template = None
    if current_user.is_authenticated:
        user_id = current_user.get_id()
        user_data_for_template = get_user_data_from_db(user_id) 
        
        if not user_data_for_template:
            flash("Your profile data could not be retrieved. Please try logging in again.", "warning")
            logout_user()
            return redirect(url_for('login'))

    # Provide all possible options for dropdowns for guest users dynamically from label_encoders
    # Use .get with a default dictionary to avoid errors if LabelEncoder not loaded
    genders = list(label_encoders.get('Gender', {'classes_':['Male', 'Female', 'Other']}).classes_) 
    cities = list(label_encoders.get('City', {'classes_':['New York', 'Los Angeles', 'Chicago', 'Houston', 'Miami']}).classes_) 
    occupations = list(label_encoders.get('Occupation', {'classes_':['Engineer', 'Artist', 'Doctor', 'HR', 'Software Dev', 'Other']}).classes_) 
    loyalty_tiers = list(label_encoders.get('Loyalty_Tier', {'classes_':['Gold', 'Silver', 'Bronze', 'None']}).classes_) 
    product_categories = list(label_encoders.get('Product_Category', {'classes_':['Electronics', 'Fashion', 'Grocery', 'Home']}).classes_) 
    weather_options = list(label_encoders.get('Weather', {'classes_':['Sunny', 'Rainy', 'Cloudy', 'Snowy', 'Foggy']}).classes_) 
    time_of_day_options = list(label_encoders.get('Time_of_Day', {'classes_':['Morning', 'Afternoon', 'Evening', 'Night']}).classes_) 

    return render_template('predict.html', 
                           current_user=current_user, 
                           current_user_data=user_data_for_template,
                           genders=genders,
                           cities=cities,
                           occupations=occupations,
                           loyalty_tiers=loyalty_tiers,
                           product_categories=product_categories,
                           weather_options=weather_options,
                           time_of_day_options=time_of_day_options
                           )

@app.route('/my_orders', methods=['GET'])
@login_required # Only logged-in users can view orders
def my_orders():
    user_id = current_user.get_id()
    conn = get_db_connection()
    # Fetch all purchases for the current user, ordered by date
    orders = conn.execute("SELECT * FROM purchases WHERE user_id = ? ORDER BY purchase_date DESC", (user_id,)).fetchall()
    conn.close()
    return render_template('my_orders.html', current_user=current_user, orders=orders)


# --- API Endpoint for Price Prediction ---
@app.route('/predict_price', methods=['POST'])
def predict_price_api():
    if not loading_success:
        return jsonify({"error": "API is not fully functional due to model loading errors. Please check server logs."}), 503

    request_data = request.get_json() # Renamed to avoid clash with `data` variable for prediction DataFrame

    customer_input_data = {}

    if current_user.is_authenticated:
        user_id = current_user.get_id()
        user_db_info = get_user_data_from_db(user_id) 
        
        if not user_db_info:
            return jsonify({"error": "Logged-in user data not found in database."}), 500
        
        # Populate customer_input_data with fetched user profile data (ensuring correct keys)
        # Using .get safely in case a new column is added to 'users' but not accounted for here
        customer_input_data['Age'] = user_db_info.get('Age') 
        customer_input_data['Gender'] = user_db_info.get('Gender')
        customer_input_data['City'] = user_db_info.get('City')
        customer_input_data['Occupation'] = user_db_info.get('Occupation')
        customer_input_data['Loyalty_Tier'] = user_db_info.get('Loyalty_Tier')
        customer_input_data['User_Product_Count'] = user_db_info.get('User_Product_Count') # Dynamically calculated from DB
        
        # Take product and environmental data from the request (from frontend form)
        expected_from_form_loggedIn = ['Product_Category', 'Purchase_Amount', 'Weather', 'Time_of_Day']
        for field in expected_from_form_loggedIn:
            if field not in request_data or request_data[field] is None:
                return jsonify({"error": f"Missing required field for logged-in user: '{field}'"}), 400
            customer_input_data[field] = request_data[field]

    else: # Guest User
        expected_from_form_guest = [
            "Age", "Gender", "City", "Occupation", "Loyalty_Tier", "User_Product_Count",
            "Product_Category", "Purchase_Amount", "Weather", "Time_of_Day"
        ]
        for field in expected_from_form_guest:
            if field not in request_data or request_data[field] is None:
                return jsonify({"error": f"Missing or null value for required field for guest user: '{field}'"}), 400
            customer_input_data[field] = request_data[field]
            
    try:
        # Convert types and validate values before creating DataFrame
        customer_input_data['Age'] = int(customer_input_data['Age'])
        if not (0 < customer_input_data['Age'] < 120):
            return jsonify({"error": "Age must be a realistic number (1-119)."}), 400

        customer_input_data['Purchase_Amount'] = float(customer_input_data['Purchase_Amount'])
        if customer_input_data['Purchase_Amount'] <= 0:
            return jsonify({"error": "Original purchase amount must be positive."}), 400

        customer_input_data['User_Product_Count'] = int(customer_input_data['User_Product_Count'])
        if customer_input_data['User_Product_Count'] < 0:
            return jsonify({"error": "User product count cannot be negative."}), 400

        # Create DataFrame with a single row for prediction.
        # Ensure column order is not random. It's best practice to build DF from a dict that matches order if possible
        # or reorder it explicitly. Pandas usually preserves dict key order (Python 3.7+).
        input_df = pd.DataFrame([customer_input_data])
        original_purchase_amount_float = input_df['Purchase_Amount'].iloc[0]

        # Apply LabelEncoders for all categorical features
        # Keep track of column order, especially if you had a fixed order from Colab
        for col in CATEGORICAL_COLS: 
            if col not in label_encoders:
                return jsonify({"error": f"LabelEncoder for '{col}' not found. Models might be incomplete or mismatched."}), 500

            le = label_encoders[col]
            input_value = input_df[col].iloc[0]
            # Handle unseen labels by returning an error instead of raising one
            if input_value not in le.classes_:
                return jsonify({"error": f"Unseen label for '{col}': '{input_value}'. Please provide a valid value from: {list(le.classes_)}"}), 422
            input_df[col] = le.transform(input_df[col])

        # Apply Age_Group transformation
        input_df['Age_Group'] = input_df['Age'].apply(get_age_group)

        # Apply Purchase_Amount_Scaled transformation using the correct scaler
        input_df['Purchase_Amount_Scaled'] = scaler_purchase_amount.transform(input_df[['Purchase_Amount']])
        
        # --- Debugging Print Statement ---
        # print("\n--- DataFrame before Segmentation/GB Prediction ---")
        # print("Columns:", input_df.columns.tolist())
        # print("DataFrame content:\n", input_df)
        # print("--- End Debugging ---")

        # --- Segmentation ---
        # Verify that input_df contains all features required by SEGMENTATION_FEATURES in the correct order/presence
        df_for_segmentation = input_df[SEGMENTATION_FEATURES]
        scaled_for_segmentation = scaler_segmentation_features.transform(df_for_segmentation)
        cluster_id = kmeans_model.predict(scaled_for_segmentation)[0]
        customer_segment_label = segment_mapping.get(cluster_id, "Unknown Segment")
        input_df['CustomerSegment'] = cluster_id # Add numerical segment ID for GB model


        # --- Conversion Prediction ---
        # Verify that input_df contains all features required by GB_FEATURES in the correct order/presence
        df_for_gb_prediction = input_df[GB_FEATURES]
        conversion_probability = gb_model.predict_proba(df_for_gb_prediction)[:, 1][0]


    except Exception as e:
        traceback.print_exc() # Print full traceback to console
        return jsonify({"error": f"Error during model prediction pipeline: {str(e)}. Check server logs for details."}), 500

    try:
        optimized_price = calculate_optimized_price(
            original_purchase_amount_float, conversion_probability, customer_segment_label
        )
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Error during optimized price calculation: {str(e)}. Check server logs for details."}), 500

    response = {
        "customer_segment": customer_segment_label,
        "original_price": original_purchase_amount_float, # Keep as float, frontend formats
        "optimized_price": optimized_price, # Keep as float, frontend formats
        "predicted_conversion_probability": conversion_probability, # Keep as float
        "notes": "Price is dynamically adjusted based on predicted conversion and customer segment and rules."
    }

    return jsonify(response)


# --- Purchase Completion API (Logs purchases to DB) ---
@app.route('/complete_purchase', methods=['POST'])
@login_required 
def complete_purchase():
    user_id = current_user.get_id()
    data = request.get_json()

    cart_items = data.get('cart_items')
    
    if not cart_items or not isinstance(cart_items, list):
        return jsonify({"error": "No cart items provided."}), 400

    conn = get_db_connection()
    try:
        for item in cart_items:
            product_name = item.get('name')
            product_category = item.get('category') 
            original_price = item.get('original_price') 
            if not original_price: 
                original_price = item.get('price')
            
            quantity = item.get('quantity', 1) 

            if not all([product_name, product_category, original_price, quantity is not None]):
                raise ValueError(f"Missing product details in cart item: {item}. Must have name, category, original_price, quantity.")

            conn.execute("INSERT INTO purchases (user_id, product_name, product_category, original_price, quantity, purchase_date) VALUES (?, ?, ?, ?, ?, ?)",
                         (user_id, product_name, product_category, original_price, quantity, datetime.now().isoformat()))
        conn.commit()
        return jsonify({"message": "Purchase recorded successfully!", "total_items_purchased": len(cart_items)})
    except Exception as e:
        conn.rollback()
        traceback.print_exc()
        return jsonify({"error": f"Failed to record purchase: {e}. Check server logs."}), 500
    finally:
        conn.close()


# --- Run the Flask App (if running directly via python app.py) ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)