"""Database models and persistence layer for AI-Money-Mentor.

Replaces the previous module-level in-memory lists (expense_data,
assets_data, liabilities_data) with SQLite-backed storage via
Flask-SQLAlchemy, so data survives server restarts.
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.String(40), nullable=False)

    def to_dict(self):
        # Matches the original expense dict shape exactly:
        # {"category", "amount", "date"}  (no id — frontend never used one)
        return {"category": self.category, "amount": self.amount, "date": self.date}


class Asset(db.Model):
    __tablename__ = "assets"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self, index):
        # Original shape: {"id", "name", "amount"} where id was the list index.
        # Frontend deletes by list position, so we expose the positional index as id.
        return {"id": index, "name": self.name, "amount": self.amount}


class Liability(db.Model):
    __tablename__ = "liabilities"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)

    def to_dict(self, index):
        return {"id": index, "name": self.name, "amount": self.amount}