from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from users import check_user, get_user_role, register_user, update_password, load_users


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# -------------------
# LOGIN
# -------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if check_user(username, password):
            session['username'] = username
            session['role'] = get_user_role(username)
            flash('Berhasil login', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah', 'error')

    return render_template('auth/login.html')


# -------------------
# REGISTER
# -------------------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        success, message = register_user(username, password)

        flash(message, 'success' if success else 'error')
        if success:
            return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


# -------------------
# GANTI PASSWORD (Hanya jika login)
# -------------------
@auth_bp.route('/ganti-password', methods=['GET', 'POST'])
def ganti_password():
    if 'username' not in session:
        flash("Silakan login terlebih dahulu", "error")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not check_user(session['username'], old_password):
            flash("Password lama salah", 'error')
            return redirect(url_for('auth.ganti_password'))

        if new_password != confirm_password:
            flash("Konfirmasi password tidak cocok", 'error')
            return redirect(url_for('auth.ganti_password'))

        if update_password(session['username'], new_password):
            flash("Password berhasil diubah", 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("Gagal mengubah password", 'error')

    return render_template('auth/ganti_password.html')


# -------------------
# LUPA PASSWORD (Reset tanpa login)
# -------------------
@auth_bp.route('/lupa-password', methods=['GET', 'POST'])
def lupa_password():
    users = load_users()  # Pastikan ini ada!

    if request.method == 'POST':
        username = request.form.get('username')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if username not in users:
            flash("Username tidak ditemukan", 'error')
            return redirect(url_for('auth.lupa_password'))

        if new_password != confirm_password:
            flash("Konfirmasi password tidak cocok", 'error')
            return redirect(url_for('auth.lupa_password'))

        if update_password(username, new_password, from_lupa=True):
            flash("Password berhasil diubah. Silakan login kembali.", 'success')
            return redirect(url_for('auth.login'))
        else:
            flash("Gagal mengubah password.", 'error')

    return render_template('auth/lupa_password.html')
