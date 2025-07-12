from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, flash, session
from werkzeug.utils import secure_filename
from fpdf import FPDF
import os
import pandas as pd
from db import get_db_connection
from datetime import datetime
import pdfplumber

keuangan_bp = Blueprint('keuangan', __name__, url_prefix='/keuangan')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'xlsx', 'xls', 'csv'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_viewer():
    return session.get('role') == 'viewer'

@keuangan_bp.route('/')
def index():
    q = request.args.get('q', '').strip()
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT id, tanggal, jenis, nominal, keterangan, bukti_transaksi 
        FROM keuangan
        WHERE 1=1
    """
    params = []
    if q:
        wildcard = f"%{q}%"
        query += """
            AND (
                jenis LIKE %s OR
                keterangan LIKE %s OR
                DATE_FORMAT(tanggal, '%%Y-%%m-%%d') LIKE %s
            )
        """
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY tanggal DESC"
    cursor.execute(query, tuple(params))
    data = cursor.fetchall()
    conn.close()

    return render_template('keuangan/index.html', data=data, q=q, is_viewer=is_viewer())

# tambah data keuangan
@keuangan_bp.route('/tambah', methods=['GET', 'POST'])
def tambah():
    if is_viewer():
        flash('Akses ditolak: Anda tidak memiliki izin menambah data.', 'danger')
        return redirect(url_for('keuangan.index'))

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        jenis = request.form['jenis']
        try:
            nominal = float(request.form.get('nominal', 0))
        except ValueError:
            nominal = 0
        keterangan = request.form['keterangan']
        file = request.files.get('bukti_transaksi')

        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO keuangan (tanggal, jenis, nominal, keterangan, bukti_transaksi)
            VALUES (%s, %s, %s, %s, %s)
        """, (tanggal, jenis, nominal, keterangan, filename))
        conn.commit()
        conn.close()

        flash("✅ Data berhasil ditambahkan.", "success")
        return redirect(url_for('keuangan.index'))

    return render_template('keuangan/create.html')

# edit data keuangan
@keuangan_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if is_viewer():
        flash('Akses ditolak: Anda tidak memiliki izin mengedit data.', 'danger')
        return redirect(url_for('keuangan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        tanggal = request.form['tanggal']
        jenis = request.form['jenis']
        try:
            nominal = float(request.form.get('nominal', 0))
        except ValueError:
            nominal = 0
        keterangan = request.form['keterangan']
        file = request.files.get('bukti_transaksi')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            cursor.execute("""
                UPDATE keuangan 
                SET tanggal=%s, jenis=%s, nominal=%s, keterangan=%s, bukti_transaksi=%s
                WHERE id=%s
            """, (tanggal, jenis, nominal, keterangan, filename, id))
        else:
            cursor.execute("""
                UPDATE keuangan 
                SET tanggal=%s, jenis=%s, nominal=%s, keterangan=%s
                WHERE id=%s
            """, (tanggal, jenis, nominal, keterangan, id))

        conn.commit()
        conn.close()
        flash("✅ Data berhasil diupdate.", "success")
        return redirect(url_for('keuangan.index'))

    cursor.execute("SELECT * FROM keuangan WHERE id=%s", (id,))
    row = cursor.fetchone()
    conn.close()
    return render_template('keuangan/edit.html', row=row)

# hapus data keuangan
@keuangan_bp.route('/hapus/<int:id>', methods=['POST'])
def hapus(id):
    if is_viewer():
        flash('Akses ditolak: Anda tidak memiliki izin menghapus data.', 'danger')
        return redirect(url_for('keuangan.index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT bukti_transaksi FROM keuangan WHERE id=%s", (id,))
    row = cursor.fetchone()
    if row and row[0]:
        file_path = os.path.join(UPLOAD_FOLDER, row[0])
        if os.path.exists(file_path):
            os.remove(file_path)

    cursor.execute("DELETE FROM keuangan WHERE id=%s", (id,))
    conn.commit()
    conn.close()
    flash("🗑️ Data berhasil dihapus.", "success")
    return redirect(url_for('keuangan.index'))

# unduh excel data keuangan
@keuangan_bp.route('/unduh_excel')
def unduh_excel():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, jenis, nominal, keterangan FROM keuangan ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    # Buat DataFrame dan tambah kolom "No" (nomor urut)
    df = pd.DataFrame(rows, columns=['Tanggal', 'Jenis', 'Nominal', 'Keterangan'])
    df.insert(0, 'No', range(1, len(df) + 1))

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_sekarang}_keuangan_laporan.xlsx'
    xlsx_path = os.path.join('static', filename)

    df.to_excel(xlsx_path, index=False)
    return send_from_directory('static', filename, as_attachment=True)

# unduh pdf data keuangan
@keuangan_bp.route('/unduh_pdf')
def unduh_pdf():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tanggal, jenis, nominal, keterangan FROM keuangan ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Laporan Keuangan", ln=True, align='C')
    pdf.ln(10)

    headers = ['No', 'Tanggal', 'Jenis', 'Nominal', 'Keterangan']
    col_width = 38

    pdf.set_font("Arial", 'B', 10)
    for header in headers:
        pdf.cell(col_width, 10, header, border=1)
    pdf.ln()

    pdf.set_font("Arial", '', 10)
    for idx, row in enumerate(rows, 1):
        pdf.cell(col_width, 10, str(idx), border=1)  # Kolom No
        for item in row:
            pdf.cell(col_width, 10, str(item)[:20], border=1)
        pdf.ln()

    tanggal_sekarang = datetime.now().strftime('%Y-%m-%d')
    filename = f'{tanggal_sekarang}_keuangan_laporan.pdf'
    pdf_path = os.path.join('static', filename)

    pdf.output(pdf_path)
    return send_from_directory('static', filename, as_attachment=True)

# upload excel data keuangan (.xlsx, .xls, .csv)
@keuangan_bp.route('/upload_excel', methods=['GET', 'POST'])
def upload_excel():
    if is_viewer():
        flash('Akses ditolak: Anda tidak memiliki izin mengunggah data.', 'danger')
        return redirect(url_for('keuangan.index'))

    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                ext = filename.rsplit('.', 1)[1].lower()
                if ext == 'csv':
                    df = pd.read_csv(path)
                else:
                    df = pd.read_excel(path)

                required_columns = ['Tanggal', 'Jenis', 'Nominal', 'Keterangan']
                if not all(col in df.columns for col in required_columns):
                    flash("❌ Kolom tidak sesuai. Excel harus punya: Tanggal, Jenis, Nominal, Keterangan", "danger")
                    return redirect(url_for('keuangan.upload_excel'))

                conn = get_db_connection()
                cursor = conn.cursor()

                for _, row in df.iterrows():
                    if pd.isna(row['Tanggal']) or pd.isna(row['Jenis']) or pd.isna(row['Nominal']):
                        continue
                    try:
                        tanggal = pd.to_datetime(row['Tanggal']).strftime('%Y-%m-%d')
                        jenis = str(row['Jenis'])
                        nominal = float(row['Nominal'])
                        keterangan = str(row['Keterangan']) if not pd.isna(row['Keterangan']) else ""
                    except Exception:
                        continue

                    cursor.execute("""
                        INSERT INTO keuangan (tanggal, jenis, nominal, keterangan, bukti_transaksi)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (tanggal, jenis, nominal, keterangan, None))

                conn.commit()
                conn.close()
                flash("✅ Data berhasil diimpor dari file!", "success")

            except Exception as e:
                flash(f"❌ Gagal mengimpor file: {e}", "danger")
        else:
            flash("❗ Format file tidak didukung. Harap unggah file .xlsx, .xls, atau .csv", "warning")

        return redirect(url_for('keuangan.index'))

    return render_template('keuangan/upload_excel.html')

# upload pdf data keuangan
@keuangan_bp.route('/upload_pdf', methods=['GET', 'POST'])
def upload_pdf():
    if is_viewer():
        flash('Akses ditolak: Anda tidak memiliki izin mengunggah data.', 'danger')
        return redirect(url_for('keuangan.index'))

    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename) and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            try:
                with pdfplumber.open(path) as pdf:
                    first_page = pdf.pages[0]
                    table = first_page.extract_table()
                    if not table:
                        flash("❌ Tidak ada tabel ditemukan dalam file PDF.", "danger")
                        return redirect(url_for('keuangan.upload_pdf'))

                    conn = get_db_connection()
                    cursor = conn.cursor()
                    headers = [h.lower() for h in table[0]]

                    for row in table[1:]:
                        row_dict = dict(zip(headers, row))
                        try:
                            tanggal = pd.to_datetime(row_dict.get('tanggal', '')).strftime('%Y-%m-%d')
                            jenis = row_dict.get('jenis', '').strip()
                            nominal = float(row_dict.get('nominal', 0))
                            keterangan = row_dict.get('keterangan', '').strip()
                        except Exception:
                            continue

                        cursor.execute("""
                            INSERT INTO keuangan (tanggal, jenis, nominal, keterangan, bukti_transaksi)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (tanggal, jenis, nominal, keterangan, None))

                    conn.commit()
                    conn.close()
                    flash("✅ Data berhasil diimpor dari PDF!", "success")
            except Exception as e:
                flash(f"❌ Gagal membaca PDF: {e}", "danger")
        else:
            flash("❌ File tidak valid. Harap unggah file dengan format .pdf", "danger")

        return redirect(url_for('keuangan.index'))

    return render_template('keuangan/upload_pdf.html')
