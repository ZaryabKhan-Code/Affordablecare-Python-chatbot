from flask import *
from flask_login import *
from model.oauth import *


admin = Blueprint('admin',__name__)

login_manager = LoginManager()
login_manager.login_view = 'admin.login'

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

@admin.route('/validator', methods=['POST'])
def validator():
    if request.method == 'POST':
        data = json.loads(request.data)
        username = data.get('username')
        password = data.get('password')
        user = Admin.query.filter_by(username=username).first()
        if user:
            if user.password == password:
                login_user(user)
                return jsonify({'redirect_url': url_for('admin.adminaca')})
            else:
                return jsonify({'error': 'Invalid password'}), 401
    return jsonify({'error': 'Invalid username'}), 401

@admin.route('/login',methods=['GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.adminaca'))
    return render_template('main/login.html')
    

@admin.route('/admin/aca')
@login_required
def adminaca():
    if not current_user.is_authenticated:
        return redirect(url_for('admin.login'))
    
    # Fetch records from the database, convert to a list, and ensure unique records based on UUID
    records = PDF.query.all()
    unique_records = {}
    
    for record in records:
        uuid = record.UUID.strip().lower()
        if uuid not in unique_records:
            unique_records[uuid] = record
    
    unique_records_list = sorted(unique_records.values(), key=lambda record: record.UUID, reverse=True)
    
    base_url = request.url_root

    return render_template('main/admin_portal.html', records=unique_records_list, base_url=base_url)

@admin.route('/logout')
@login_required
def logout():
    if not current_user.is_authenticated:
        return redirect(url_for('admin.login'))

    logout_user()
    return redirect(url_for('admin.login'))
