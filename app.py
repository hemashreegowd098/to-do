# =============================================================
#  app.py — Flask To-Do List Backend (SQLAlchemy version)
#  Database : Auto-switches between Neon PostgreSQL & Local SQLite
#  Auth     : Session-based login (fixed credentials)
# =============================================================

import os
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime, date

# ── Load environment variables from .env ──────────────────────
load_dotenv()

# ── Flask app — points to frontend folders ───────────────────
app = Flask(
    __name__,
    template_folder='../frontend/templates',   # uses existing HTML files
    static_folder='../frontend/static'         # uses existing style.css
)

# Secret key for sessions
app.secret_key = os.getenv('SECRET_KEY', 'change-me-in-production')

# ── Fixed credentials (Fallback if needed, not used anymore since we have DB auth) ─────────────────
ADMIN_USERNAME = os.getenv('APP_USERNAME', 'admin')
ADMIN_PASSWORD = os.getenv('APP_PASSWORD', 'password123')

# =============================================================
#  DATABASE SETUP (SQLAlchemy)
# =============================================================

db_url = os.getenv('DATABASE_URL')
if db_url:
    db_url = db_url.strip("'").strip('"')

# Smart fallback: If a real Neon database isn't provided yet, 
# seamlessly use a local SQLite database file so the app works instantly!
if not db_url or "your_host.neon.tech" in db_url:
    print("⚠️  Warning: Real Neon database not detected in .env.")
    print("✨  Falling back to temporary local SQLite database.")
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///local_todo.db'
else:
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    # Fix 'server closed the connection unexpectedly' on Neon PostgreSQL
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database extension
db = SQLAlchemy(app)

# ── Database Models ───────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    tasks = db.relationship('Task', backref='user', lazy=True)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Allowed for guests
    tasks = db.relationship('Task', backref='project', lazy=True)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task = db.Column(db.Text, nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    due_date = db.Column(db.Date, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # nullable=True to not break old local testing db
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)

# ── Manual SQL Migration (If using Raw Postgres instead of SQLAlchemy)
# CREATE TABLE projects ( id SERIAL PRIMARY KEY, name TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT NOW(), user_id INTEGER REFERENCES users(id) );
# ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id);

def init_db():
    """Creates the tables if they don't already exist."""
    with app.app_context():
        db.create_all()
        print("✅  Database initialised.")


# =============================================================
#  AUTH DECORATOR
# =============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access your tasks.', 'error')
            return redirect(url_for('login'))
            
        # Verify user actually exists in the database
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash('Your session expired or your account was reset. Please log in again.', 'error')
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated


# =============================================================
#  ROUTES
# =============================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Welcome back! 👋', 'success')
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password. Please try again.'

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            error = "Both fields are required."
        elif User.query.filter_by(username=username).first():
            error = "Username already exists. Please choose another."
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


@app.route('/')
@app.route('/project/<int:project_id>')
@login_required
def index(project_id=None):
    filter_type = request.args.get('filter', 'inbox')
    search_query = request.args.get('search', '').strip()
    base_query = Task.query.filter_by(user_id=session.get('user_id'))
    
    # Process the section filter
    if search_query:
        filter_type = 'search'
        tasks = base_query.filter(Task.task.ilike(f'%{search_query}%')).order_by(Task.created_at.desc()).all()
    elif project_id:
        filter_type = 'project'
        tasks = base_query.filter_by(project_id=project_id).order_by(Task.created_at.desc()).all()
    elif filter_type == 'today':
        tasks = base_query.filter(Task.due_date == date.today()).order_by(Task.created_at.desc()).all()
    elif filter_type == 'upcoming':
        tasks = base_query.filter(Task.due_date > date.today()).order_by(Task.due_date.asc()).all()
    else:
        # Default Inbox shows all tasks
        filter_type = 'inbox'
        tasks = base_query.order_by(Task.created_at.desc()).all()

    # Pre-compute sidebar counts for the active user
    all_tasks = base_query.all()
    total_inbox = len(all_tasks)
    total_today = sum(1 for t in all_tasks if t.due_date == date.today() and not t.completed)
    total_upcoming = sum(1 for t in all_tasks if t.due_date and t.due_date > date.today() and not t.completed)
    
    # Fetch all projects for the sidebar
    projects = Project.query.filter_by(user_id=session.get('user_id')).order_by(Project.created_at.desc()).all()
    
    # We still show global completed counts purely for stats if needed
    total = len(tasks)
    completed = sum(1 for t in tasks if t.completed)
    remaining = total - completed

    return render_template(
        'index.html',
        tasks=tasks,
        projects=projects,
        active_project_id=project_id,
        username=session.get('username'),
        total=total,
        completed_count=completed,
        remaining=remaining,
        filter_type=filter_type,
        total_inbox=total_inbox,
        total_today=total_today,
        total_upcoming=total_upcoming,
        today=date.today(),
        search_query=search_query
    )

@app.route('/add_project', methods=['POST'])
@login_required
def add_project():
    project_name = request.form.get('project_name', '').strip()
    if project_name:
        new_proj = Project(name=project_name, user_id=session.get('user_id'))
        db.session.add(new_proj)
        db.session.commit()
        flash('Project created! 🎉', 'success')
    return redirect(url_for('index'))

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.filter_by(id=project_id).first()
    if project:
        # Move all tasks in this project back to Inbox to prevent foreign key errors
        Task.query.filter_by(project_id=project.id).update({Task.project_id: None})
        db.session.delete(project)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
@login_required
def add_task():
    task_text = request.form.get('task', '').strip()
    due_date_str = request.form.get('due_date', '').strip()
    project_id = request.form.get('project_id', '')

    if not task_text:
        flash('Task cannot be empty.', 'error')
        return redirect(url_for('index'))

    # Parse the date if provided
    parsed_date = None
    if due_date_str:
        try:
            parsed_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        except ValueError:
            parsed_date = None
            
    # Process project
    valid_project_id = None
    if project_id and project_id.isdigit():
        valid_project_id = int(project_id)

    new_task = Task(task=task_text, completed=False, due_date=parsed_date, project_id=valid_project_id, user_id=session.get('user_id'))
    db.session.add(new_task)
    db.session.commit()

    # Redirect back to the exact folder we were in
    current_filter = request.form.get('current_filter', 'inbox')
    flash('Task added successfully! ✅', 'success')
    return redirect(url_for('index', filter=current_filter))


@app.route('/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session.get('user_id')).first()
    if task:
        db.session.delete(task)
        db.session.commit()
        flash('Task deleted.', 'success')
    return redirect(url_for('index'))


@app.route('/complete/<int:task_id>', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.filter_by(id=task_id, user_id=session.get('user_id')).first()
    if task:
        task.completed = not task.completed
        db.session.commit()
    return redirect(url_for('index'))


# =============================================================
#  ENTRY POINT
# =============================================================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
