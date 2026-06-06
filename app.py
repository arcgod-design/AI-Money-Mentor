from flask import Flask, request, jsonify, render_template
import yfinance as yf
import os
import sys
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# ── Startup validation ───────────────────────────────────────
# Fail fast and clearly if the required API key is missing.
# Copy .env.example → .env and set your GROQ_API_KEY.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY or GROQ_API_KEY.strip() in ("", "your_groq_api_key_here"):
    print(
        "\n[ERROR] GROQ_API_KEY is not configured.\n"
        "  1. Copy .env.example to .env\n"
        "  2. Set your GROQ_API_KEY in .env\n"
        "  Obtain a free key at: https://console.groq.com/\n",
        file=sys.stderr,
    )
    sys.exit(1)
# ---------------- IMPORT UTILS ----------------
from utils.sip import calculate_sip
from utils.tax import calculate_tax
from utils.pdf_parser import extract_income
from utils.money_score import calculate_money_score
from utils.multi_agent import run_multi_agent
from utils.stock import get_stock_price
from utils.expense_track import calculate_expense, insights
from utils.validation import ValidationError, validate_string, validate_float, validate_int

app = Flask(__name__)

# ---------------- INIT DATABASE ----------------
from models import db, Expense, Asset, Liability

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///money_mentor.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

# ---------------- INIT GROQ ----------------
client = Groq(api_key=GROQ_API_KEY)

# ── Dev-mode startup message ─────────────────────────────────
if os.getenv("FLASK_ENV", "development") != "production":
    print("[OK] Groq client initialised successfully.")
# ---------------- HOME ----------------
@app.route("/")
def home():
    return render_template("index.html")


# ---------------- HEALTH CHECK ----------------
@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight liveness probe for deployment environments (Docker, Railway, etc.)."""
    return jsonify({"status": "ok", "service": "AI Money Mentor"}), 200


# ---------------- ERROR HANDLERS ----------------
@app.errorhandler(ValidationError)
def handle_validation_error(error):
    return jsonify({
        "error": "Bad Request",
        "message": str(error),
        "status_code": 400
    }), 400


@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        "error": "Bad Request",
        "message": str(error),
        "status_code": 400
    }), 400


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist.",
        "status_code": 404
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        "error": "Method Not Allowed",
        "message": str(error),
        "status_code": 405
    }), 405


@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later.",
        "status_code": 500
    }), 500


# ---------------- 🤖 AI CHAT ----------------
@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        msg = validate_string(data.get("message"), "message")
        history = data.get("history", [])
        if not isinstance(history, list):
            raise ValidationError("'history' must be a list")

        # Build messages: system prompt + last 10 history turns + current message
        messages = [{"role": "system", "content": "You are a financial advisor for India."}]
        messages += history[-10:]
        messages.append({"role": "user", "content": msg})

        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": """
You are an expert AI financial advisor for Indian users.

Your job:
- Help users manage money smartly
- Teach budgeting, saving, and investing
- Give simple, practical, real-life advice

Response rules:
- Always use structured format:

Income / Situation Summary:
- ...

Budget Breakdown (if applicable):
- Needs: 50%
- Wants: 30%
- Savings: 20%

Advice:
- Give clear steps
- Keep it simple and actionable

Tone:
- Friendly, practical, and easy to understand
"""
                },
                {"role": "user", "content": msg}
            ]
        )
        return jsonify({
            "reply": res.choices[0].message.content
        })

    except ValidationError as e:
        raise e
    except Exception as e:
        app.logger.error(f"Groq API Error: {str(e)}")

        return jsonify({
            "reply": "Unable to generate a response at the moment. Please try again later."
        }), 500


# ---------------- 💸 SIP ----------------
@app.route("/sip", methods=["POST"])
def sip():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        monthly = validate_float(data.get("monthly"), "monthly", min_val=0.0)
        rate = validate_float(data.get("rate"), "rate", min_val=0.0)
        years = validate_int(data.get("years"), "years", min_val=1)
        inflation = validate_float(data.get("inflation", 0.0), "inflation", min_val=0.0)
        
        result = calculate_sip(monthly, rate, years, inflation)
        return jsonify({
            "future_value": result["nominal_value"],
            "nominal_value": result["nominal_value"],
            "inflation_adjusted_value": result["inflation_adjusted_value"],
            "inflation_applied": result["inflation_applied"]
        })

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------- 📊 STOCK ----------------
@app.route("/portfolio", methods=["POST"])
def portfolio():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        stock = validate_string(data.get("stock"), "stock").upper()
        result = get_stock_price(stock)
        if "error" in result:
            raise ValidationError(result["error"])
        return jsonify(result)

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
# ---------------- 💸 TAX ----------------
@app.route("/tax", methods=["POST"])
def tax():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        income = validate_float(data.get("income"), "income", min_val=0.0)
        deduction_80c = validate_float(data.get("deduction_80c", 0.0), "deduction_80c", min_val=0.0)
        deduction_80d = validate_float(data.get("deduction_80d", 0.0), "deduction_80d", min_val=0.0)
        deduction_hra = validate_float(data.get("deduction_hra", 0.0), "deduction_hra", min_val=0.0)
        
        result = calculate_tax(
            income,
            deduction_80c=deduction_80c,
            deduction_80d=deduction_80d,
            deduction_hra=deduction_hra
        )
        return jsonify({"tax": result})

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------- 📄 PDF ----------------
@app.route("/upload", methods=["POST"])
def upload():
    try:
        file = request.files["file"]
        result = extract_income(file)
        return jsonify({"data": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------- 🧠 MULTI AGENT ----------------
@app.route("/agent", methods=["POST"])
def run_agent_route():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        query = validate_string(data.get("query"), "query")
        response = run_multi_agent(client, query)
        return jsonify({"response": response})

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ---------------- 💰 MONEY SCORE ----------------
@app.route("/money-score", methods=["POST"])
def money_score():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        
        income = validate_float(data.get("income"), "income", min_val=0.0)
        expenses = validate_float(data.get("expenses"), "expenses", min_val=0.0)
        savings = validate_float(data.get("savings"), "savings", min_val=0.0)
        investments = validate_float(data.get("investments"), "investments", min_val=0.0)
        debt = validate_float(data.get("debt"), "debt", min_val=0.0)
        emergency = validate_float(data.get("emergency"), "emergency", min_val=0.0)

        score = calculate_money_score(income, expenses, savings, investments, debt, emergency)

        if score >= 80:
            status = "Excellent 💚"
        elif score >= 60:
            status = "Good 👍"
        elif score >= 40:
            status = "Average ⚠️"
        else:
            status = "Needs Improvement ❌"

        return jsonify({
            "score": score,
            "status": status
        })

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# Expense Tracker Features

@app.route("/add_expense", methods=["POST"])
def add_expense():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        category = validate_string(data.get("category"), "category")
        amount = validate_float(data.get("amount"), "amount", min_val=0.01)
        date = validate_string(data.get("date"), "date")
        
        expense = Expense(
            category=category,
            amount=amount,
            date=date
        )
        db.session.add(expense)
        db.session.commit()
        return jsonify({"status": "success"})

    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/calculate", methods=["GET"])
def calculate():
    expense_data = [e.to_dict() for e in Expense.query.order_by(Expense.id).all()]
    result = calculate_expense(expense_data)
    result["expenses"] = expense_data
    return jsonify(result)

@app.route("/insights", methods=["GET"])
def expense_insights():
    expense_data = [e.to_dict() for e in Expense.query.order_by(Expense.id).all()]
    result = insights(client, expense_data)
    return jsonify(result)

# ---------------- NET WORTH TRACKER ----------------
# Net Worth Tracker Features

@app.route("/net-worth", methods=["GET", "POST"])
def get_net_worth():
    assets = Asset.query.order_by(Asset.id).all()
    liabilities = Liability.query.order_by(Liability.id).all()
    assets_data = [a.to_dict(i) for i, a in enumerate(assets)]
    liabilities_data = [l.to_dict(i) for i, l in enumerate(liabilities)]
    total_assets = sum(item['amount'] for item in assets_data)
    total_liabilities = sum(item['amount'] for item in liabilities_data)
    return jsonify({
        "assets": assets_data,
        "liabilities": liabilities_data,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": total_assets - total_liabilities
    })

@app.route("/add-asset", methods=["POST"])
def add_asset():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        name = validate_string(data.get("name"), "name")
        amount = validate_float(data.get("amount"), "amount", min_val=0.0)
        
        asset = Asset(name=name, amount=amount)
        db.session.add(asset)
        db.session.commit()
        return jsonify({"status": "success"})
    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/add-liability", methods=["POST"])
def add_liability():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        name = validate_string(data.get("name"), "name")
        amount = validate_float(data.get("amount"), "amount", min_val=0.0)
        
        liability = Liability(name=name, amount=amount)
        db.session.add(liability)
        db.session.commit()
        return jsonify({"status": "success"})
    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/delete-item", methods=["POST"])
def delete_item():
    try:
        data = request.json or {}
        if not isinstance(data, dict):
            raise ValidationError("Request body must be a JSON object")
        item_type = validate_string(data.get("type"), "type")
        if item_type not in ('asset', 'liability'):
            raise ValidationError("'type' must be either 'asset' or 'liability'")
        item_id = validate_int(data.get("id"), "id", min_val=0)

        if item_type == 'asset':
            rows = Asset.query.order_by(Asset.id).all()
            if item_id >= len(rows):
                raise ValidationError("Invalid asset ID")
            db.session.delete(rows[item_id])
        else:
            rows = Liability.query.order_by(Liability.id).all()
            if item_id >= len(rows):
                raise ValidationError("Invalid liability ID")
            db.session.delete(rows[item_id])

        db.session.commit()
        return jsonify({"status": "success"})
    except ValidationError as e:
        raise e
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ---------------- RUN ----------------
if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(debug=debug_mode)
