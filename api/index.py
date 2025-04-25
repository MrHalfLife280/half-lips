import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from waitress import serve

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///half_lips.db'
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/profile_pics'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    profile_pic = db.Column(db.String(100), nullable=True, default='default.png')
    display_name = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    birthdate = db.Column(db.Date, nullable=True)  # Used to calculate age

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(280), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='posts')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def save_profile_picture(image_file):
    filename = secure_filename(image_file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    image_file.save(filepath)  # Save directly without resizing
    return filename

@app.route('/')
def home():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('home.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
        else:
            profile_pic = 'default.png'
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file.filename:
                    profile_pic = save_profile_picture(file)

            user = User(username=username, password=password, profile_pic=profile_pic)
            db.session.add(user)
            db.session.commit()
            flash('Registered successfully! You can now log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and bcrypt.check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('home'))
        flash('Login failed. Check username and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/post', methods=['POST'])
@login_required
def post():
    content = request.form['content']
    if 0 < len(content) <= 280:
        new_post = Post(content=content, user_id=current_user.id)
        db.session.add(new_post)
        db.session.commit()
    return redirect(url_for('home'))

@app.route('/profile/<username>', methods=['GET'])
@login_required
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.display_name = request.form['display_name']
        current_user.bio = request.form['bio']
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename:
                current_user.profile_pic = save_profile_picture(file)
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile', username=current_user.username))
    
    return render_template('edit_profile.html')

@app.route('/find_people')
@login_required
def find_people():
    return render_template('find_people.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/help')
@login_required
def help():
    return render_template('help.html')

# Only run database creation in local development
with app.app_context():
    db.create_all()

# Production deployment using Waitress
if __name__ == '__main__':
    if os.environ.get("VERCEL") == "true":
        # Vercel environment, use the handler to serve as serverless function
        def handler(event, context):
            return app(event, context)
    else:
        # Local or development mode using Waitress
        serve(app, host='0.0.0.0', port=5000)
