from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, timedelta
from bson import ObjectId
from werkzeug.exceptions import HTTPException
import logging
import os
from werkzeug.utils import secure_filename
from PIL import Image
import csv
from io import StringIO

from flask import Flask, render_template  # and your other imports

app = Flask(__name__, 
    template_folder='templates',
    static_folder='static'
)

UPLOAD_FOLDER = 'static/uploads/children'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # Set session lifetime
app.config['SESSION_COOKIE_SECURE'] = True  # For HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to session cookie

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.template_filter('grade_color')
def grade_color(grade):
    if grade in ['A', 'B']:
        return 'success'
    elif grade == 'C':
        return 'warning'
    else:
        return 'danger'
app.secret_key = 'your-secret-key'

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['children_home']
users = db['users']

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Role-based access decorator
def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('Please log in first', 'error')
                return redirect(url_for('login'))
            if session['role'] not in allowed_roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_form(*required_fields):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            for field in required_fields:
                if not request.form.get(field):
                    flash(f'{field.replace("_", " ").title()} is required.', 'error')
                    return redirect(url_for(f.__name__))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Error handling decorator (move this before the routes)
def handle_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}")
            flash('An error occurred. Please try again.', 'error')
            return redirect(url_for('staff_dashboard'))
    return decorated_function

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    role = session.get('role', 'user')
    return render_template('home.html', 
                         username=session['username'], 
                         role=role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            app.logger.info(f"Login attempt for username: {username}")
            
            # Check for static admin credentials
            if username == "System Admin" and password == "ADMIN2027254@@":
                session.permanent = True
                session['username'] = username
                session['role'] = 'admin'
                session['user_id'] = 'admin'
                flash('Logged in successfully!', 'success')
                app.logger.info("Admin login successful")
                return redirect(url_for('admin_dashboard'))
            
            # Regular user authentication
            user = db.users.find_one({'username': username})
            if user and check_password_hash(user['password'], password):
                session.permanent = True
                session['username'] = user['username']
                session['role'] = user['role']
                session['user_id'] = str(user['_id'])
                
                app.logger.info(f"User login successful. Role: {user['role']}")
                
                # Role-specific redirects
                role_redirects = {
                    'staff': 'staff_dashboard',
                    'nurse': 'nurse_dashboard',
                    'teacher': 'teacher_dashboard'
                }
                
                if user['role'] in role_redirects:
                    flash(f'Welcome, {user["username"]}!', 'success')
                    return redirect(url_for(role_redirects[user['role']]))
                else:
                    app.logger.error(f"Invalid role: {user['role']}")
                    flash('Invalid user role', 'error')
                    return redirect(url_for('login'))
                    
            app.logger.warning(f"Failed login attempt for username: {username}")
            flash('Invalid username or password', 'error')
            
        except Exception as e:
            app.logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login', 'error')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')
            email = request.form.get('email')
            full_name = request.form.get('full_name')
            
            # Check if username exists
            if db.users.find_one({'username': username}):
                flash('Username already exists', 'error')
                return redirect(url_for('register'))
            
            # Create new user
            new_user = {
                'username': username,
                'password': generate_password_hash(password),
                'role': role,
                'email': email,
                'full_name': full_name,
                'created_at': datetime.now()
            }
            
            db.users.insert_one(new_user)
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            app.logger.error(f"Registration error: {str(e)}")
            flash('An error occurred during registration', 'error')
            
    return render_template('register.html')

@app.route('/admin_dashboard')
@role_required(['admin'])
def admin_dashboard():
    try:
        # Get statistics
        stats = {
            'total_users': db.users.count_documents({}),
            'total_staff': db.users.count_documents({'role': 'staff'}),
            'pending_approvals': db.users.count_documents({'status': 'pending'}),
            'total_logs': db.system_logs.count_documents({
                'timestamp': {'$gte': datetime.now() - timedelta(days=1)}
            })
        }
        
        # Get all users
        users = list(db.users.find())
        
        # Get roles and their counts
        roles = []
        for role in db.roles.find():
            role['users_count'] = db.users.count_documents({'role': role['name']})
            roles.append(role)
        
        # Get system logs
        system_logs = list(db.system_logs.find().sort('timestamp', -1).limit(100))
        
        # Get system settings
        settings = db.settings.find_one() or {}
        
        return render_template('admin_dashboard.html',
                             stats=stats,
                             users=users,
                             roles=roles,
                             system_logs=system_logs,
                             settings=settings,
                             current_date=datetime.now().strftime("%B %d, %Y"))
                             
    except Exception as e:
        app.logger.error(f"Admin dashboard error: {str(e)}")
        flash('Error loading admin dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/staff_dashboard')
@role_required(['staff'])
def staff_dashboard():
    try:
        user_data = db.users.find_one({'username': session['username']})
        if not user_data:
            flash('User not found', 'error')
            return redirect(url_for('login'))
            
        # Get relevant data for staff dashboard
        stats = {
            'total_children': db.children.count_documents({}),
            'recent_activities': list(db.system_logs.find().sort('timestamp', -1).limit(5))
        }
        
        return render_template('staff/dashboard.html', 
                             user=user_data,
                             stats=stats)
    except Exception as e:
        app.logger.error(f"Staff Dashboard error: {str(e)}")
        flash('Error loading dashboard', 'error')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

# Children Management Routes
@app.route('/view_children')
@role_required(['staff'])
def view_children():
    if 'username' not in session:
        flash('Please login to continue', 'error')
        return redirect(url_for('login'))
        
    try:
        # Get all children and format their data
        children = list(db.children.find())
        for child in children:
            # Use registration_date if admission_date doesn't exist
            child['admission_date'] = child.get('registration_date', 
                                              child.get('admission_date', 'Not specified'))
            
        return render_template('children/view_children.html', children=children)
    except Exception as e:
        app.logger.error(f"Error viewing children: {str(e)}")
        flash('An error occurred while viewing children', 'error')
        return redirect(url_for('staff_dashboard'))

@app.route('/add_child', methods=['GET', 'POST'])
@role_required(['staff'])
def add_child():
    if 'username' not in session:
        flash('Session expired. Please login again.', 'error')
        return redirect(url_for('login'))

    try:
        if request.method == 'POST':
            # Handle photo upload
            photo = request.files.get('photo')
            photo_filename = None
            
            if photo and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                # Add timestamp to filename to make it unique
                photo_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

            child_data = {
                'name': request.form.get('name').strip(),
                'dob': request.form.get('dob'),
                'gender': request.form.get('gender'),
                'guardian_name': request.form.get('guardian_name').strip(),
                'guardian_contact': request.form.get('guardian_contact').strip(),
                'medical_conditions': request.form.get('medical_conditions', '').strip(),
                'notes': request.form.get('notes', '').strip(),
                'registration_date': datetime.now(),
                'registered_by': session['username'],
                'status': 'active',
                'child_id': generate_child_id(),
                'age': calculate_age(request.form.get('dob')),
                'photo': photo_filename  # Add the photo filename to database
            }

            db.children.insert_one(child_data)
            flash('Child added successfully!', 'success')
            return redirect(url_for('view_children'))

    except Exception as e:
        app.logger.error(f"Error in add_child: {str(e)}")
        flash('An error occurred while adding the child', 'error')
        
    return render_template('children/add_child.html')

def calculate_age(dob):
    """Calculate age from date of birth"""
    birth_date = datetime.strptime(dob, '%Y-%m-%d')
    today = datetime.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age

def generate_child_id():
    """Generate unique child ID"""
    prefix = 'CH'
    year = datetime.now().strftime('%y')
    # Get count of children for this year
    count = db.children.count_documents({
        'registration_date': {
            '$gte': datetime(datetime.now().year, 1, 1),
            '$lt': datetime(datetime.now().year + 1, 1, 1)
        }
    })
    # Format: CH23001 (CH + year + 3-digit sequential number)
    return f"{prefix}{year}{str(count + 1).zfill(3)}"

# Schedule Routes
@app.route('/view_schedule')
def view_schedule():
    if 'username' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    schedules = list(db.schedules.find({'date': current_date}))
    return render_template('schedule/view_schedule.html', schedules=schedules)

@app.route('/create_schedule', methods=['GET', 'POST'])
def create_schedule():
    if 'username' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        schedule_data = {
            'date': request.form.get('date'),
            'time': request.form.get('time'),
            'activity_type': request.form.get('activity_type'),
            'description': request.form.get('description'),
            'assigned_staff': request.form.get('assigned_staff'),
            'created_at': datetime.now()
        }
        db.schedules.insert_one(schedule_data)
        flash('Schedule created successfully!', 'success')
        return redirect(url_for('view_schedule'))
    
    return render_template('schedule/create_schedule.html')

# Activities Routes
@app.route('/manage_activities', methods=['GET', 'POST'])
@role_required(['staff'])
def manage_activities():
    if request.method == 'POST':
        activity_data = {
            'title': request.form.get('title'),
            'date': request.form.get('date'),
            'time': request.form.get('time'),
            'description': request.form.get('description'),
            'participants': request.form.get('participants', '').split(','),
            'created_by': session['username'],
            'created_at': datetime.now()
        }
        db.activities.insert_one(activity_data)
        flash('Activity added successfully!', 'success')
        return redirect(url_for('manage_activities'))

    # GET request - fetch activities and render template
    activities = list(db.activities.find().sort('date', -1))
    return render_template('activities/manage_activities.html', activities=activities)

@app.route('/add_activity', methods=['GET', 'POST'])
def add_activity():
    if 'username' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        activity_data = {
            'title': request.form.get('title'),
            'date': request.form.get('date'),
            'time': request.form.get('time'),
            'description': request.form.get('description'),
            'participants': request.form.getlist('participants'),
            'status': 'scheduled',
            'created_by': session['username'],
            'created_at': datetime.now()
        }
        db.activities.insert_one(activity_data)
        flash('Activity added successfully!', 'success')
        return redirect(url_for('manage_activities'))
    
    children = list(db.children.find({}, {'name': 1}))
    return render_template('activities/add_activity.html', children=children)

# Health Records Routes
@app.route('/health_records')
@role_required(['staff', 'nurse'])
def health_records():
    if 'username' not in session or session.get('role') not in ['staff', 'nurse']:
        return redirect(url_for('login'))
    
    records = list(db.health_records.find({}).sort('date', -1))
    return render_template('health/health_records.html', records=records)

@app.route('/add_health_record', methods=['GET', 'POST'])
@role_required(['staff', 'nurse'])
def add_health_record():
    if 'username' not in session or session.get('role') not in ['staff', 'nurse']:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        health_data = {
            'child_id': ObjectId(request.form.get('child_id')),
            'date': request.form.get('date'),
            'record_type': request.form.get('record_type'),
            'description': request.form.get('description'),
            'treatment': request.form.get('treatment'),
            'doctor': request.form.get('doctor'),
            'next_appointment': request.form.get('next_appointment'),
            'created_by': session['username'],
            'created_at': datetime.now()
        }
        db.health_records.insert_one(health_data)
        flash('Health record added successfully!', 'success')
        return redirect(url_for('health_records'))
    
    children = list(db.children.find({}, {'name': 1}))
    return render_template('health/add_health_record.html', children=children)

# Add new routes for academic records
@app.route('/academic_records')
@role_required(['teacher'])
def academic_records():
    try:
        # Fetch all academic records with student and subject details
        records = list(db.academic_records.aggregate([
            {
                '$lookup': {
                    'from': 'children',
                    'localField': 'student_id',
                    'foreignField': '_id',
                    'as': 'student'
                }
            },
            {
                '$lookup': {
                    'from': 'subjects',
                    'localField': 'subject_id',
                    'foreignField': '_id',
                    'as': 'subject'
                }
            },
            {
                '$sort': {'date': -1}
            }
        ]))
        
        # Get all subjects for the filter dropdown
        subjects = list(db.subjects.find())
        
        return render_template('teacher/academic_records.html',
                             records=records,
                             subjects=subjects)
    except Exception as e:
        app.logger.error(f"Error fetching academic records: {str(e)}")
        flash('Error loading academic records', 'error')
        return redirect(url_for('teacher_dashboard'))

@app.route('/add_academic_record', methods=['GET', 'POST'])
@role_required(['staff', 'teacher'])
def add_academic_record():
    if request.method == 'POST':
        # Logic to add academic record
        flash('Academic record added successfully!', 'success')
        return redirect(url_for('academic_records'))
    return render_template('academic/add_academic_record.html')

# Helper route to delete records (optional but useful)
@app.route('/delete_record/<string:record_type>/<string:record_id>')
def delete_record(record_type, record_id):
    if 'username' not in session or session.get('role') != 'staff':
        return redirect(url_for('login'))
    
    collection_map = {
        'child': 'children',
        'schedule': 'schedules',
        'activity': 'activities',
        'health': 'health_records'
    }
    
    if record_type in collection_map:
        db[collection_map[record_type]].delete_one({'_id': ObjectId(record_id)})
        flash(f'{record_type.capitalize()} record deleted successfully!', 'success')
    
    return redirect(request.referrer or url_for('staff_dashboard'))

# Global error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('teacher_dashboard'))

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Unhandled exception: {str(e)}")
    flash('An unexpected error occurred.', 'error')
    return redirect(url_for('teacher_dashboard'))

# Nurse Dashboard and Related Routes
@app.route('/nurse_dashboard')
@role_required(['nurse'])
def nurse_dashboard():
    try:
        app.logger.info("Loading nurse dashboard")
        user_data = db.users.find_one({'username': session['username']})
        if not user_data:
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Dashboard data
        dashboard_data = {
            'current_date': datetime.now().strftime("%B %d, %Y"),
            'total_children': db.children.count_documents({}),
            'pending_checkups': db.health_records.count_documents({
                'type': 'checkup',
                'status': 'pending'
            }),
            'today_appointments': db.health_records.count_documents({
                'date': datetime.now().strftime("%Y-%m-%d"),
                'type': 'appointment'
            }),
            'recent_records': list(db.health_records.find().sort('date', -1).limit(5))
        }

        # Process recent records to include child names
        for record in dashboard_data['recent_records']:
            if 'child_id' in record:
                child = db.children.find_one({'_id': record['child_id']})
                record['child_name'] = child['name'] if child else 'Unknown Child'
            else:
                record['child_name'] = 'Unknown Child'
            
            # Ensure date is formatted properly
            if isinstance(record.get('date'), datetime):
                record['date'] = record['date']
            else:
                record['date'] = datetime.now()  # fallback date
        
        return render_template(
            'nurse/dashboard.html',
            user=user_data,
            **dashboard_data
        )
                             
    except Exception as e:
        app.logger.error(f"Error in nurse dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard.', 'error')
        return redirect(url_for('login'))

# Supporting routes for nurse functionality
@app.route('/medical_checkup', methods=['GET', 'POST'])
@role_required(['nurse'])
def medical_checkup():
    if request.method == 'POST':
        try:
            checkup_data = {
                'child_id': ObjectId(request.form['child_id']),
                'date': datetime.now(),
                'type': 'routine_checkup',
                'height': float(request.form['height']),
                'weight': float(request.form['weight']),
                'temperature': float(request.form['temperature']),
                'blood_pressure': request.form['blood_pressure'],
                'notes': request.form['notes'],
                'performed_by': session['username'],
                'status': 'completed'
            }
            db.health_records.insert_one(checkup_data)
            flash('Medical checkup recorded successfully!', 'success')
            return redirect(url_for('nurse_dashboard'))
            
        except Exception as e:
            app.logger.error(f"Error in medical checkup: {str(e)}")
            flash('Error recording medical checkup.', 'error')
            return redirect(url_for('medical_checkup'))
    
    children = list(db.children.find())
    return render_template('nurse/medical_checkup.html', children=children)

@app.route('/medication_schedule', methods=['GET', 'POST'])
@role_required(['nurse'])
def medication_schedule():
    if request.method == 'POST':
        try:
            med_data = {
                'child_id': ObjectId(request.form['child_id']),
                'medication_name': request.form['medication_name'],
                'dosage': request.form['dosage'],
                'frequency': request.form['frequency'],
                'start_date': datetime.strptime(request.form['start_date'], '%Y-%m-%d'),
                'end_date': datetime.strptime(request.form['end_date'], '%Y-%m-%d'),
                'notes': request.form['notes'],
                'created_by': session['username'],
                'created_at': datetime.now(),
                'status': 'active'
            }
            db.medications.insert_one(med_data)
            flash('Medication schedule added successfully!', 'success')
            return redirect(url_for('nurse_dashboard'))
            
        except Exception as e:
            app.logger.error(f"Error in medication schedule: {str(e)}")
            flash('Error adding medication schedule.', 'error')
            return redirect(url_for('medication_schedule'))
    
    children = list(db.children.find())
    return render_template('nurse/medication_schedule.html', children=children)

# Add necessary indexes for better performance
def setup_nurse_indexes():
    try:
        db.health_records.create_index([('child_id', 1), ('date', -1)])
        db.health_records.create_index([('type', 1), ('status', 1), ('scheduled_date', 1)])
        db.medications.create_index([('child_id', 1), ('status', 1), ('end_date', 1)])
        db.children.create_index([('name', 1)])
    except Exception as e:
        app.logger.error(f"Error setting up indexes: {str(e)}")

# Call this function when the app starts
if __name__ == '__main__':
    setup_nurse_indexes()

# Teacher Dashboard and Related Routes
@app.route('/teacher_dashboard')
@role_required(['teacher'])
def teacher_dashboard():
    try:
        app.logger.info("Loading teacher dashboard")
        user_data = db.users.find_one({'username': session['username']})
        if not user_data:
            flash('User not found', 'error')
            return redirect(url_for('login'))
        
        # Get dashboard statistics
        dashboard_data = {
            'current_date': datetime.now().strftime("%B %d, %Y"),
            'total_students': db.children.count_documents({}),
            'total_subjects': db.subjects.count_documents({}),
            'pending_assessments': db.academic_records.count_documents({'status': 'pending'}),
            'recent_records': list(db.academic_records.find().sort('created_at', -1).limit(5))
        }
        
        return render_template(
            'teacher/dashboard.html',
            user=user_data,
            **dashboard_data
        )
                             
    except Exception as e:
        app.logger.error(f"Error in teacher dashboard: {str(e)}")
        flash('An error occurred while loading the dashboard.', 'error')
        return redirect(url_for('login'))

@app.route('/student_assessment', methods=['GET', 'POST'])
@role_required(['teacher'])
def student_assessment():
    if request.method == 'POST':
        assessment_data = {
            'student_id': request.form['student_id'],
            'subject': request.form['subject'],
            'assessment_type': request.form['assessment_type'],
            'grade': request.form['grade'],
            'comments': request.form['comments'],
            'date': datetime.now(),
            'teacher_id': session['user_id'],
            'status': 'completed'
        }
        db.academic_records.insert_one(assessment_data)
        flash('Assessment added successfully!', 'success')
        return redirect(url_for('teacher_dashboard'))
    
    # Get students and subjects for the form
    students = list(db.children.find())
    subjects = list(db.subjects.find())
    return render_template('teacher/student_assessment.html', 
                         students=students, 
                         subjects=subjects)

@app.route('/manage_subjects', methods=['GET', 'POST'])
@role_required(['teacher'])
def manage_subjects():
    if request.method == 'POST':
        subject_data = {
            'name': request.form['name'],
            'description': request.form['description'],
            'grade_level': request.form['grade_level'],
            'created_by': session['user_id'],
            'created_at': datetime.now()
        }
        db.subjects.insert_one(subject_data)
        flash('Subject added successfully!', 'success')
        return redirect(url_for('manage_subjects'))
    
    subjects = list(db.subjects.find().sort('name', 1))
    return render_template('teacher/manage_subjects.html', subjects=subjects)

@app.route('/student_progress')
@role_required(['teacher'])
def student_progress():
    try:
        # Fetch all students
        students = list(db.children.find())
        
        # Fetch progress data (you'll need to implement the logic to calculate this)
        progress_data = calculate_student_progress()
        
        return render_template('teacher/progress_reports.html',
                             students=students,
                             progress_data=progress_data)
    except Exception as e:
        app.logger.error(f"Error loading progress reports: {str(e)}")
        flash('Error loading progress reports', 'error')
        return redirect(url_for('teacher_dashboard'))

def calculate_student_progress():
    # Implement your progress calculation logic here
    # This should analyze academic records and return structured progress data
    try:
        progress_data = []
        # Add your calculation logic here
        return progress_data
    except Exception as e:
        app.logger.error(f"Error calculating progress: {str(e)}")
        return []

@app.route('/edit_assessment/<assessment_id>', methods=['GET', 'POST'])
@role_required(['teacher'])
def edit_assessment(assessment_id):
    if request.method == 'POST':
        update_data = {
            'subject': request.form['subject'],
            'assessment_type': request.form['assessment_type'],
            'grade': request.form['grade'],
            'comments': request.form['comments'],
            'updated_at': datetime.now()
        }
        db.academic_records.update_one(
            {'_id': ObjectId(assessment_id)},
            {'$set': update_data}
        )
        flash('Assessment updated successfully!', 'success')
        return redirect(url_for('academic_records'))
    
    assessment = db.academic_records.find_one({'_id': ObjectId(assessment_id)})
    subjects = list(db.subjects.find())
    return render_template('teacher/edit_assessment.html',
                         assessment=assessment,
                         subjects=subjects)

# Add these indexes for better performance
db.academic_records.create_index([('student_id', 1), ('date', -1)])
db.academic_records.create_index([('subject', 1)])
db.subjects.create_index([('name', 1)])

@app.route('/update_profile', methods=['POST'])
@role_required(['teacher'])
def update_profile():
    if 'profile_image' in request.files:
        file = request.files['profile_image']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            db.users.update_one(
                {'username': session['username']},
                {'$set': {'profile_image': filename}}
            )
            session['profile_image'] = filename

    # Update other profile information
    update_data = {
        'full_name': request.form.get('full_name'),
        'email': request.form.get('email')
    }
    
    db.users.update_one(
        {'username': session['username']},
        {'$set': update_data}
    )
    
    session['full_name'] = update_data['full_name']
    session['email'] = update_data['email']
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('teacher_dashboard'))

# Create directories if they don't exist
def create_upload_directory():
    upload_dir = os.path.join('static', 'uploads')
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

# Financial Management Routes
@app.route('/financial')
@role_required(['staff'])
def view_financial_records():
    try:
        # Get all financial records
        transactions = list(db.financial_transactions.find().sort('date', -1))
        donations = list(db.donations.find().sort('date', -1))
        
        # Calculate totals
        total_balance = sum(t['amount'] for t in transactions if t['type'] == 'income') - \
                       sum(t['amount'] for t in transactions if t['type'] == 'expense')
        total_donations = sum(d['amount'] for d in donations)
        total_expenses = sum(t['amount'] for t in transactions if t['type'] == 'expense')
        
        # Get monthly summaries
        current_month = datetime.now().strftime('%Y-%m')
        monthly_transactions = db.financial_transactions.aggregate([
            {
                '$match': {
                    'date': {'$regex': f'^{current_month}'}
                }
            },
            {
                '$group': {
                    '_id': '$category',
                    'total': {'$sum': '$amount'}
                }
            }
        ])

        return render_template('financial/dashboard.html',
                             transactions=transactions,
                             donations=donations,
                             total_balance=total_balance,
                             total_donations=total_donations,
                             total_expenses=total_expenses,
                             monthly_summary=list(monthly_transactions))
    except Exception as e:
        app.logger.error(f"Error in financial records: {str(e)}")
        flash('Error loading financial records', 'error')
        return redirect(url_for('staff_dashboard'))

# Make sure all other financial routes use consistent naming
@app.route('/financial/add-transaction', methods=['POST'])
@role_required(['staff'])
def add_transaction():
    try:
        transaction_data = {
            'type': request.form.get('type'),
            'amount': float(request.form.get('amount')),
            'category': request.form.get('category'),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'notes': request.form.get('notes'),
            'recorded_by': session['username']
        }
        db.financial_transactions.insert_one(transaction_data)
        flash('Transaction recorded successfully!', 'success')
        return redirect(url_for('view_financial_records'))
    except Exception as e:
        flash('Error recording transaction', 'error')
        app.logger.error(f"Error recording transaction: {str(e)}")
        return redirect(url_for('view_financial_records'))

@app.route('/financial/add-donation', methods=['POST'])
@role_required(['staff'])
def record_donation():
    try:
        donation_data = {
            'donor_name': request.form.get('donor_name'),
            'amount': float(request.form.get('amount')),
            'date': datetime.now().strftime('%Y-%m-%d'),
            'notes': request.form.get('notes'),
            'recorded_by': session['username']
        }
        db.donations.insert_one(donation_data)
        flash('Donation recorded successfully!', 'success')
        return redirect(url_for('view_financial_records'))
    except Exception as e:
        flash('Error recording donation', 'error')
        app.logger.error(f"Error recording donation: {str(e)}")
        return redirect(url_for('view_financial_records'))

@app.route('/financial/report')
@role_required(['staff'])
def generate_financial_report():
    # Basic implementation
    return redirect(url_for('view_financial_records'))

@app.route('/manage_schedule', methods=['GET', 'POST'])
@role_required(['staff'])
def manage_schedule():
    if request.method == 'POST':
        schedule_data = {
            'day': request.form.get('day'),
            'time_slot': request.form.get('time_slot'),
            'activity': request.form.get('activity'),
            'responsible_staff': request.form.get('responsible_staff'),
            'updated_by': session['username'],
            'updated_at': datetime.now()
        }
        db.daily_schedule.update_one(
            {'day': schedule_data['day'], 'time_slot': schedule_data['time_slot']},
            {'$set': schedule_data},
            upsert=True
        )

@app.route('/report_incident', methods=['GET', 'POST'])
@role_required(['staff'])
def report_incident():
    try:
        if 'username' not in session:
            flash('Please login to continue', 'error')
            return redirect(url_for('login'))
            
        if request.method == 'POST':
            incident_data = {
                'date': request.form.get('date'),
                'time': request.form.get('time'),
                'location': request.form.get('location'),
                'children_involved': request.form.getlist('children_involved'),
                'description': request.form.get('description'),
                'action_taken': request.form.get('action_taken'),
                'reported_by': session['username'],
                'reported_at': datetime.now(),
                'severity': request.form.get('severity'),
                'status': 'open'
            }
            db.incidents.insert_one(incident_data)
            flash('Incident reported successfully!', 'success')
            return redirect(url_for('staff_dashboard'))
        
        # GET request - render the incident report form
        children = list(db.children.find({'status': 'active'}))
        return render_template('incidents/report_incident.html',
                             children=children,
                             today=datetime.now().strftime('%Y-%m-%d'),
                             now=datetime.now().strftime('%H:%M'))
                             
    except Exception as e:
        app.logger.error(f"Incident report error: {str(e)}")
        flash('Error reporting incident', 'error')
        return redirect(url_for('staff_dashboard'))

@app.route('/mark_attendance', methods=['GET', 'POST'])
@role_required(['staff'])
def mark_attendance():
    try:
        if 'username' not in session:
            flash('Please login to continue', 'error')
            return redirect(url_for('login'))
            
        if request.method == 'POST':
            attendance_data = {
                'child_id': request.form.get('child_id'),
                'date': request.form.get('attendance_date'),
                'status': request.form.get('status'),
                'marked_by': session['username'],
                'marked_at': datetime.now()
            }
            db.attendance.insert_one(attendance_data)
            flash('Attendance marked successfully!', 'success')
            return redirect(url_for('staff_dashboard'))
        
        # GET request - render the attendance form
        children = list(db.children.find({'status': 'active'}))
        return render_template('staff/mark_attendance.html', 
                             children=children,
                             today=datetime.now().strftime('%Y-%m-%d'))
                             
    except Exception as e:
        app.logger.error(f"Attendance error: {str(e)}")
        flash('Error processing attendance', 'error')
        return redirect(url_for('staff_dashboard'))

@app.route('/visitor_log', methods=['GET', 'POST'])
@role_required(['staff'])
def visitor_log():
    if request.method == 'POST':
        visitor_data = {
            'name': request.form.get('name'),
            'purpose': request.form.get('purpose'),
            'visiting': request.form.get('visiting'),
            'check_in': datetime.now(),
            'id_type': request.form.get('id_type'),
            'id_number': request.form.get('id_number'),
            'phone': request.form.get('phone'),
            'logged_by': session['username']
        }
        db.visitors.insert_one(visitor_data)

@app.route('/manage_inventory', methods=['GET', 'POST'])
@role_required(['staff'])
def manage_inventory():
    if request.method == 'POST':
        inventory_data = {
            'item_name': request.form.get('item_name'),
            'category': request.form.get('category'),
            'quantity': int(request.form.get('quantity')),
            'unit': request.form.get('unit'),
            'last_updated': datetime.now(),
            'updated_by': session['username'],
            'minimum_threshold': int(request.form.get('minimum_threshold', 0))
        }
        db.inventory.update_one(
            {'item_name': inventory_data['item_name']},
            {'$set': inventory_data},
            upsert=True
        )

@app.route('/staff_tasks', methods=['GET', 'POST'])
@role_required(['staff'])
def staff_tasks():
    if request.method == 'POST':
        task_data = {
            'title': request.form.get('title'),
            'description': request.form.get('description'),
            'assigned_to': request.form.get('assigned_to'),
            'due_date': request.form.get('due_date'),
            'priority': request.form.get('priority'),
            'status': 'pending',
            'created_by': session['username'],
            'created_at': datetime.now()
        }
        db.tasks.insert_one(task_data)

@app.route('/add_progress_note/<child_id>', methods=['POST'])
@role_required(['staff'])
def add_progress_note(child_id):
    note_data = {
        'child_id': child_id,
        'date': datetime.now(),
        'category': request.form.get('category'),
        'note': request.form.get('note'),
        'recorded_by': session['username'],
        'attachments': []
    }
    
    # Handle file attachments
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                note_data['attachments'].append(filename)
                
    db.progress_notes.insert_one(note_data)

@app.route('/emergency_contacts', methods=['GET', 'POST'])
@role_required(['staff'])
def emergency_contacts():
    if request.method == 'POST':
        contact_data = {
            'name': request.form.get('name'),
            'relationship': request.form.get('relationship'),
            'primary_phone': request.form.get('primary_phone'),
            'secondary_phone': request.form.get('secondary_phone'),
            'email': request.form.get('email'),
            'address': request.form.get('address'),
            'notes': request.form.get('notes'),
            'added_by': session['username'],
            'added_at': datetime.now()
        }
        db.emergency_contacts.insert_one(contact_data)

@app.route('/manage_documents', methods=['GET', 'POST'])
@role_required(['staff'])
def manage_documents():
    if request.method == 'POST':
        file = request.files['document']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            document_data = {
                'title': request.form.get('title'),
                'category': request.form.get('category'),
                'filename': filename,
                'uploaded_by': session['username'],
                'upload_date': datetime.now(),
                'description': request.form.get('description'),
                'tags': request.form.get('tags', '').split(',')
            }
            db.documents.insert_one(document_data)

@app.route('/admin/update_user_role', methods=['POST'])
@role_required(['admin'])
def admin_update_user_role():
    data = request.get_json()
    username = data.get('username')
    new_role = data.get('role')
    
    try:
        db.users.update_one(
            {'username': username},
            {'$set': {'role': new_role}}
        )
        
        log_action(f'Updated role for user {username} to {new_role}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/reset_password', methods=['POST'])
@role_required(['admin'])
def reset_user_password():
    data = request.get_json()
    username = data.get('username')
    
    try:
        # Generate temporary password
        temp_password = generate_temporary_password()
        
        # Update user password
        db.users.update_one(
            {'username': username},
            {'$set': {'password': generate_password_hash(temp_password)}}
        )
        
        # Send email with temporary password
        send_password_reset_email(username, temp_password)
        
        # Log the action
        log_action(f'Reset password for user {username}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete_user', methods=['DELETE'])
@role_required(['admin'])
def delete_user():
    data = request.get_json()
    username = data.get('username')
    
    try:
        # Check if user exists and is not the last admin
        if username == session['username']:
            raise Exception("Cannot delete your own account")
            
        admin_count = db.users.count_documents({'role': 'admin'})
        user = db.users.find_one({'username': username})
        
        if user['role'] == 'admin' and admin_count <= 1:
            raise Exception("Cannot delete the last admin account")
        
        # Delete the user
        db.users.delete_one({'username': username})
        
        # Log the action
        log_action(f'Deleted user {username}')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/update_settings', methods=['POST'])
@role_required(['admin'])
def update_settings():
    try:
        settings_data = {
            'system_name': request.form.get('system_name'),
            'maintenance_mode': request.form.get('maintenance_mode') == 'on',
            'updated_by': session['username'],
            'updated_at': datetime.now()
        }
        
        db.settings.update_one({}, {'$set': settings_data}, upsert=True)
        
        # Log the action
        log_action('Updated system settings')
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Add these helper functions near the top of the file, after imports

def log_action(message):
    """Log administrative actions to database"""
    log_entry = {
        'action': message,
        'user': session.get('username'),
        'timestamp': datetime.now()
    }
    db.system_logs.insert_one(log_entry)

def generate_temporary_password(length=12):
    """Generate a random temporary password"""
    import string
    import random
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

def send_password_reset_email(username, temp_password):
    """Send password reset email to user"""
    user = db.users.find_one({'username': username})
    if user and user.get('email'):
        # Add your email sending logic here
        # For now, just log it
        log_action(f'Password reset email would be sent to {username}')
        return True
    return False

# Replace imghdr.what() with PIL validation
def validate_image(stream):
    try:
        Image.open(stream)
        return True
    except Exception:
        return False

if __name__ == '__main__':
    app.run(debug=True) 