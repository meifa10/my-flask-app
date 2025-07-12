from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Keuangan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tanggal = db.Column(db.Date, nullable=False)
    jenis = db.Column(db.String(50), nullable=False)
    nominal = db.Column(db.Float, nullable=False)
    keterangan = db.Column(db.String(200), nullable=False)

