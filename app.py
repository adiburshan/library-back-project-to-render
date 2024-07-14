from cmath import e
from datetime import datetime, timedelta
import logging
import os
from tkinter import Image
from flask import Flask, current_app, jsonify, request, send_from_directory, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, select
from sqlalchemy.orm import relationship
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__)
jwt = JWTManager(app)


CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'my_secret_key'   #to get token

# Configuration for file upload folder
app.config['UPLOAD_FOLDER'] = 'media'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB maximum file size
# Ensure the 'media' folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])



# Initialize SQLAlchemy, Bcrypt and JWT with the Flask app
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
blacklist = set() #for the logout



# Define the Customers table
class Customers(db.Model):
    __tablename__ = 'customers'
    id = db.Column(Integer, primary_key=True)
    user_name = db.Column(String, unique=True, nullable=False)
    age = db.Column(Integer)
    email = db.Column(String, unique=True, nullable=False)
    phone_number = db.Column(Integer, unique=True, nullable=False)
    password = db.Column(String, nullable=False)
    is_admin = db.Column(Boolean, default=False)
    customer_active = db.Column(Boolean, default=True)
    loans = db.relationship('Loans', back_populates='customer')

    def customer_is_active(self):
        self.customer_active = True
    def customer_notactive(self):
        self.customer_active = False

    @staticmethod
    def create_admin():
        # Check if admin already exists
        admin = Customers.query.filter_by(is_admin=True).first()
        if not admin:
            # Create admin user
            admin_user = Customers(
                user_name='adi burshannn',
                email='adiii@gmail.com',
                age=22,
                password=bcrypt.generate_password_hash('adi1234').decode('utf-8'),
                phone_number='053-2815999',
                is_admin=True,
            )
            db.session.add(admin_user)
            db.session.commit()
            print('Admin user created successfully')



# Define the Books table
class Books(db.Model):
    __tablename__ = 'books'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    author = db.Column(db.String, nullable=False)
    published_date = db.Column(db.Integer, nullable=False)  
    availability = db.Column(Boolean, default=True)
    type = db.Column(db.Integer, nullable=False)
    active = db.Column(Boolean, default=True)
    photo = db.Column(db.String)
    loans = db.relationship('Loans', back_populates='book')

    def get_loan_period(self):
        loan_periods = {1: 15, 2: 10, 3: 5}
        return loan_periods.get(self.type, 0)  # Return 0 if type is not valid
    
    def book_active(self):
        self.active = True
    def book_notactive(self):
        self.active = False

@app.route('/photos/<filename>')
def get_photo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



# Define the Loans table
class Loans(db.Model):
    __tablename__ = 'loans'
    id = db.Column(Integer, primary_key=True)
    loan_date = db.Column(db.DateTime, nullable=True)
    return_date = db.Column(db.DateTime, nullable=True) # Nullable for books not returned yet
    late_loan = db.Column(Boolean, default=False)
    customer_id = db.Column(Integer, db.ForeignKey('customers.id'), nullable=False)
    book_id = db.Column(Integer, db.ForeignKey('books.id'), nullable=False)
    customer = db.relationship('Customers', back_populates='loans')
    book = db.relationship('Books', back_populates='loans')



## --------------------------------------------------------------------------------------------------------------------------------

# # # Register , Login , Logout , Account# # #

# Register
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user_name = data.get('user_name')
    age = data.get('age')
    email = data.get('email')
    password = bcrypt.generate_password_hash(data.get('password')).decode('utf-8')
    phone_number = data.get('phone_number')
    # Validate required fields
    if not user_name or not phone_number:
        return jsonify({'message': 'User name and phone number are required'}), 400
    if Customers.query.filter_by(email=email).first():
        return jsonify({'message': 'Customer already exists'}), 400

    new_customer = Customers(user_name=user_name, age=age, email=email, phone_number=phone_number, password=password, is_admin=False)
    db.session.add(new_customer)
    db.session.commit()
    return jsonify({'message': 'Customer created successfully'}), 201



# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    customer = Customers.query.filter_by(email=email).first()
    if customer and bcrypt.check_password_hash(customer.password, password):
        access_token = create_access_token(identity={
            'id': customer.id,
            'email': customer.email,
            'user_name': customer.user_name,
            'is_admin' : customer.is_admin
        })
        # Return access token and user_name in the response
        response = {
            'access_token': access_token,
            'user_name': customer.user_name, 
            'is_admin' : customer.is_admin
        }
        return jsonify(response), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401



# Logout
@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    # The current_user can be accessed directly via get_jwt_identity()
    current_user = get_jwt_identity()
    return jsonify({'message': f'Logged out user {current_user["user_name"]}'}), 200

# JWT token revocation callback
@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(access_token, decrypted_token):
    jti = decrypted_token['jti']
    return jti in blacklist



# Account details
@app.route('/account', methods=['GET'])
@jwt_required()
def account_info():
    # Get the current user's identity from the JWT token
    current_user = get_jwt_identity()
    current_user_id = current_user["id"]
    print(current_user_id)
    # Query the database to find the customer by their ID
    customer = Customers.query.filter_by(id=current_user_id).first()

    if not customer:
        return jsonify({'message': 'Customer not found'}), 404
    # Return the customer's details as a dictionary with only the required fields
    details = {
        'id' : customer.id,
        'user_name': customer.user_name,
        'age': customer.age,
        'email': customer.email,
        'phone_number': customer.phone_number,
        'is_admin' : customer.is_admin
    }
    return jsonify(details), 200


## --------------------------------------------------------------------------------------------------------------------------------

# # # # FOR ADMIN ONLY # # # #

# Add Book
@app.route('/add_book', methods=['POST'])
@jwt_required()
def add_book():
    current_user = get_jwt_identity()
    if not current_user.get('is_admin'):
        return jsonify({'message': 'Admin access required'}), 403
    try:
        # Get JSON data
        data = request.form
        title = data.get('title')
        author = data.get('author')
        published_date = data.get('published_date')
        book_type = data.get('type')

        # Ensure required fields are present
        if not all([title, author, published_date, book_type]):
            return jsonify({'message': 'Missing required fields'}), 422
        # Handle file upload
        if 'photo' not in request.files:
            return jsonify({'message': 'No file part in the request'}), 422

        photo = request.files['photo']
        if photo.filename == '':
            return jsonify({'message': 'No selected file'}), 422
        if photo:
            photo_filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

            # Create new book object and add to database
        new_book = Books(
            title=title,
            author=author,
            published_date=published_date,
            type=book_type,
            photo=photo_filename,
            availability=True,
            active=True
            )
        db.session.add(new_book)
        db.session.commit()

        return jsonify({'message': 'Book added successfully'}), 201
    except Exception as e:
        return jsonify({'message': 'Error processing request', 'error': str(e)}), 500



# Show books
@app.route('/admin_show_books', methods=['GET'])
@jwt_required()
def admin_all_books():
    current_user = get_jwt_identity()
    if not current_user.get('is_admin'):
        return jsonify({'message': 'Admin access required'}), 403
    books = Books.query.filter_by().all()
    book_list = []
    for book in books:
        book_data = {
            'id': book.id , 
            'title': book.title,
            'author': book.author,
            'published_date': book.published_date,
            'availability': 'Available' if book.availability else 'Not Available',
            'photo': url_for('get_photo', filename=book.photo) if book.photo else None
        }
        book_list.append(book_data)
    return jsonify({'books': book_list}), 200



# Delete Book (mark as not active)
@app.route('/delete_book/<int:book_id>', methods=['DELETE'])
@jwt_required()
def delete_book(book_id):
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
       return jsonify({'message': 'Admin access required'}), 403

    book = Books.query.get(book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404
    if not book.active:
        return jsonify({'message': 'Book is already deleted'}), 400
    book.active = False  # Mark the book as inactive
    book.availability = False
    db.session.commit()
    return jsonify({'message': 'Book deleted successfully'}), 200



# Update Book
@app.route('/update_book/<int:book_id>', methods=['PUT'])
@jwt_required()
def update_book(book_id):
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    data = request.get_json()
    id = data.get('id')
    title = data.get('title')
    author = data.get('author')
    published_date = data.get('published_date')
    type = data.get('type')

    book = Books.query.get(book_id)
    if not book or not book.active:
        return jsonify({'message': 'Book not found'}), 404
    if title:
        book.title = title
    if author:
        book.author = author
    if published_date:
        book.published_date = published_date
    if type:
        book.type = type
    db.session.commit()
    return jsonify({'message': 'Book updated successfully'}), 200



# Show all customers 
@app.route('/show_customers', methods=['GET'])
@jwt_required()
def show_customers():
    current_user = get_jwt_identity()
    print('Current user:', current_user)
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    customers = Customers.query.all()
    customer_list = []
    for customer in customers:
        customer_data = {
            'id': customer.id,
            'user_name': customer.user_name,
            'age': customer.age,
            'email': customer.email,
            'phone_number': customer.phone_number,
            'is_admin': customer.is_admin,
            'customer_active': customer.customer_active
        }
        customer_list.append(customer_data)
    return jsonify({'customers': customer_list}), 200



# Delete customer (mark as not active)
@app.route('/delete_customer/<int:customer_id>', methods=['DELETE'])
@jwt_required()
def delete_customer(customer_id):
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    customer = Customers.query.get(customer_id)
    if not customer:
        return jsonify({'message': 'Customer not found'}), 404
    if not customer.customer_active:
        return jsonify({'message': 'Customer is already deleted'}), 400

    customer.customer_active = False  # Mark the customer as inactive
    db.session.commit()
    return jsonify({'message': 'Customer deleted successfully'}), 200



# Update customer
@app.route('/update_customer/<int:customer_id>', methods=['PUT'])
@jwt_required()
def update_customer(customer_id):
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    data = request.get_json()
    user_name = data.get('user_name')
    age = data.get('age')
    email = data.get('email')
    phone_number = data.get('phone_number')
    is_admin = data.get('is_admin')
    customer_active = data.get('customer_active')

    customer = Customers.query.get(customer_id)
    if not customer:
        return jsonify({'message': 'Customer not found'}), 404

    if user_name:
        customer.user_name = user_name
    if age:
        customer.age = age
    if email:
        customer.email = email
    if phone_number:
        customer.phone_number = phone_number
    if is_admin is not None:
        customer.is_admin = is_admin
    if customer_active is not None:
        customer.customer_active = customer_active

    db.session.commit()
    return jsonify({'message': 'Customer updated successfully'}), 200



# show all loans exist in db
@app.route('/all_loans', methods=['GET'])
@jwt_required()
def get_all_loans():
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    loans = Loans.query.all()
    all_loans = []
    for loan in loans:
        book = Books.query.get(loan.book_id)
        if book:

            loan_data = {
                'loan_id': loan.id,
                'customer_id': loan.customer_id,
                'customer_name': loan.customer.user_name,
                'book_id': loan.book_id,
                'book_title': book.title,
                'loan_date': loan.loan_date.strftime('%Y-%m-%d'),
                'return_date': loan.return_date.strftime('%Y-%m-%d') if loan.return_date else "Not returned yet",
                                        }
            all_loans.append(loan_data)
    return jsonify({'loans': all_loans}), 200



@app.route('/all_late_loans', methods=['GET'])
@jwt_required()
def get_all_late_loans():
    current_user = get_jwt_identity()
    if not current_user['is_admin']:
        return jsonify({'message': 'Admin access required'}), 403

    loans = Loans.query.all()
    overdue_books = []
    for loan in loans:
        book = Books.query.get(loan.book_id)
        if book:
            due_date = loan.loan_date + timedelta(days=book.get_loan_period())
            if loan.return_date is None and datetime.now() > due_date:
                overdue_book_data = {
                    'loan_id': loan.id,
                    'customer_id': loan.customer_id,
                    'customer_name': loan.customer.user_name,
                    'book_id': loan.book_id,
                    'book_title': book.title,
                    'loan_date': loan.loan_date,
                    'return_date': loan.return_date if loan.return_date else "Not returned yet",
                    'late_loan' : loan.late_loan
                }
                overdue_books.append(overdue_book_data)
            return jsonify(overdue_books), 200


## --------------------------------------------------------------------------------------------------------------------------------

# # # # FOR EVERYONE # # # #

# Show all Books (available and not available)
@app.route('/show_books', methods=['GET'])
def get_all_books():
    books = Books.query.filter_by().all()
    book_list = []
    for book in books:
        book_data = {
            'id': book.id , 
            'title': book.title,
            'author': book.author,
            'published_date': book.published_date,
            'availability': 'Available' if book.availability else 'Not Available',
            'photo': url_for('get_photo', filename=book.photo) if book.photo else None
        }
        book_list.append(book_data)
    return jsonify({'books': book_list}), 200



# Loan Book by Title
@app.route('/loan_book/<string:book_title>', methods=['POST'])
@jwt_required()
def loan_book_by_title(book_title):
    current_user = get_jwt_identity()
    if not current_user:
        return jsonify({'message': 'Login required'}), 401

    # Find the book by title
    book = Books.query.filter_by(title=book_title).with_for_update().first()
    if not book:
        return jsonify({'message': 'Book not found'}), 404
    # Check if the book is already loaned
    existing_loan = Loans.query.filter_by(book_id=book.id, return_date=None).with_for_update().first()
    if existing_loan:
        return jsonify({'message': 'Book is already loaned'}), 400
    if not book.availability:
        return jsonify({'message': 'Book is not available'}), 400

    loan_date = datetime.now()
    loan_period = book.get_loan_period()  # Get the loan period based on book type
    return_date = loan_date + timedelta(days=loan_period)
    # Create a new loan
    new_loan = Loans(
        customer_id=current_user['id'],
        book_id=book.id,
        loan_date=loan_date,
        return_date=return_date
    )
    db.session.add(new_loan)
    # Update book availability status
    book.availability = False
    db.session.add(book)
    db.session.commit()
    return jsonify({'message': 'Book loaned successfully'}), 200



# Return Book
@app.route('/return_book/<int:loan_id>', methods=['PUT'])
@jwt_required()
def return_book(loan_id):
    current_user = get_jwt_identity()
    loan = Loans.query.filter_by(id=loan_id).first()
    if not loan:
        return jsonify({'message': 'Loan not found'}), 404
    if not current_user['is_admin'] and loan.customer_id != current_user['id']:
        return jsonify({'message': 'Unauthorized to return this book'}), 403

    # Calculate due date based on loan period
    book = Books.query.get(loan.book_id)
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    due_date = loan.loan_date + timedelta(days=book.get_loan_period())
    # Check if the book has already been returned
    if loan.return_date and loan.return_date <= datetime.now():
        return jsonify({'message': 'Book has already been returned'}), 400
    # Check if the book is returned late
    late_loan = datetime.now() > due_date
    # Update loan return_date and late_loan status
    loan.return_date = datetime.now()
    loan.late_loan = late_loan
    # Update book availability
    book.availability = True
    db.session.commit()
    return jsonify({'message': 'Book returned successfully', 'late_loan': late_loan}), 200



# Show Customer's Loans
@app.route('/my_loans', methods=['GET'])
@jwt_required()
def get_my_loans():
    current_user = get_jwt_identity()
    user_id = current_user['id']  # Extract user ID from JWT payload

    # Query loans for the current user
    loans = Loans.query.filter_by(customer_id=user_id).all()
    loan_data = []
    for loan in loans:
        loan_info = {
            'id': loan.id,
            'book_title': loan.book.title,
            'loan_date': loan.loan_date.strftime('%Y-%m-%d %H:%M:%S'),
            'return_date': loan.return_date.strftime('%Y-%m-%d %H:%M:%S') if loan.return_date else None
        }
        loan_data.append(loan_info)
    return jsonify({'loans': loan_data}), 200



#update customer info 
@app.route('/update_customer_info', methods=['PUT'])
@jwt_required()
def update_account():
    # Get the current user's identity from the JWT token
    current_user = get_jwt_identity()
    current_user_id = current_user["id"]

    # Query the database to find the customer by their ID
    customer = Customers.query.filter_by(id=current_user_id).first()
    if not customer:
        return jsonify({'message': 'Customer not found'}), 404

    # Get the request JSON data
    data = request.get_json()
    # Update the customer fields with the provided data
    if 'user_name' in data:
        customer.user_name = data['user_name']
    if 'age' in data:
        customer.age = data['age']
    if 'email' in data:
        customer.email = data['email']
    if 'phone_number' in data:
        customer.phone_number = data['phone_number']
    
    # Commit the changes to the database
    db.session.commit()
    return jsonify({'message': 'Account updated successfully'}), 200



# Show my late loans
@app.route('/my_late_loans', methods=['GET'])
@jwt_required()
def get_my_late_loans():
    current_user = get_jwt_identity()
    customer_id = current_user['id']
    loans = Loans.query.filter_by(customer_id=customer_id).all()
    if not loans:
        return jsonify({'message': 'No loans found for this customer'}), 404

    overdue_books = []
    for loan in loans:
        book = Books.query.get(loan.book_id)
        if book:
            due_date = loan.loan_date + timedelta(days=book.get_loan_period())
            if loan.return_date is None and datetime.now() > due_date:
                overdue_book_data = {
                    'loan_id': loan.id,
                    'book_id': loan.book_id,
                    'book_title': book.title,
                    'loan_date': loan.loan_date,
                    'return_date': loan.return_date if loan.return_date else "Not returned yet",
                    'late_loan': loan.late_loan
                }
                overdue_books.append(overdue_book_data)

    return jsonify(overdue_books), 200



# Find Book by Title
@app.route('/find_book', methods=['GET'])
def find_book_by_title():
    title = request.args.get('title')
    if not title:
        return jsonify({'message': 'Book name is required'}), 400

    book = Books.query.filter_by(title=title).first()
    if not book:
        return jsonify({'message': 'Book not found'}), 404

    book_data = {
        'id': book.id,
        'title': book.title,
        'author': book.author,
        'published_date': book.published_date,
        'availability': 'Available' if book.availability else 'Not Available',
        'type': book.type
    }
    return jsonify({'book': book_data}), 200



# Protected route example
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


if __name__ == "__main__":
# Create all tables in the engine
    with app.app_context():
        db.create_all()
    app.run(debug=True)