import os
import datetime

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows = db.execute("SELECT * FROM stocks WHERE userID = :userID GROUP BY symbol", userID=session["user_id"])
    sumTotal = 0
    for i in rows:
        i["price"] = usd(i["price"])
        sumTotal += i["total"]
        i["total"] = usd(i["total"])
    cash = 10000 - sumTotal
    cash = usd(cash)
    return render_template("index.html", rows=rows, cash=cash)



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        if not request.form.get("shares"):
            return apology("must provide number of shares", 403)
        output = lookup(request.form.get("symbol"))
        if not output:
            return apology("symbol not found", 403)
        stockSum = output["price"] * (int(request.form.get("shares")))
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
        currentCash = cash[0]["cash"]
        if stockSum > currentCash:
            return apology("cannot afford", 403)
        db.execute("INSERT INTO stocks (userID, symbol, stockName, price, shares, total) VALUES (:userID, :symbol, :stockName, :price, :shares, :total)", userID=session["user_id"], symbol=output["symbol"], stockName=output["name"], price=output["price"], shares=(int(request.form.get("shares"))), total=stockSum)
        db.execute("INSERT INTO transactions (symbol, shares, price, time, userID) VALUES (:symbol, :shares, :price, :time, :userID)", symbol=output["symbol"], shares=(int(request.form.get("shares"))), price=output["price"], time=datetime.datetime.now(), userID=session["user_id"])
        return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT symbol, shares, price, time FROM transactions WHERE userID = :userID GROUP BY time", userID=session["user_id"])
    for i in transactions:
        i["price"] = usd(i["price"])
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        output = lookup(request.form.get("symbol"))
        if not output:
            return apology("symbol not found", 403)
        return render_template("quoted.html", output=output)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)
        elif not request.form.get("password"):
            return apology("must provide password", 403)
        elif len(request.form.get("password")) < 6:
            return apology("password must be at least 6 characters long", 403)
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 403)

        userExists = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
        if len(userExists) != 0:
            return apology("username already exists", 403)
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords do not match", 403)
        else:
            username = request.form.get("username")
            password = request.form.get("password")
            passwordHash = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=request.form.get("username"), hash=passwordHash)
            return redirect("/")
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        if not request.form.get("shares"):
            return apology("must provide number of shares", 403)
        numSharesSold = int(request.form.get("shares"))
        numShares = db.execute("SELECT shares FROM stocks WHERE userID = :userID AND symbol = :symbol", userID=session["user_id"], symbol=request.form.get("symbol"))
        numShares1 = numShares[0]["shares"]
        stock = lookup(request.form.get("symbol"))
        if numShares1 == numSharesSold:
            db.execute("DELETE FROM stocks WHERE userID = :userID AND symbol = :symbol", userID=session["user_id"], symbol=request.form.get("symbol"))
            sharesSold = 0 - numSharesSold
            db.execute("INSERT INTO transactions (symbol, shares, price, time, userID) VALUES (:symbol, :shares, :price, :time, :userID)", symbol=request.form.get("symbol"), shares=sharesSold, price=stock["price"], time=datetime.datetime.now(), userID=session["user_id"])
        elif numShares1 > numSharesSold:
            updateNumShares = numShares1 - numSharesSold
            sharesSold = 0 - numSharesSold
            totalPrice = updateNumShares * stock["price"]
            db.execute("UPDATE stocks SET shares = :shares, total = :total WHERE userId = :userID AND symbol = :symbol", shares=updateNumShares, total=totalPrice, userID=session["user_id"], symbol=request.form.get("symbol"))
            db.execute("INSERT INTO transactions (symbol, shares, price, time, userID) VALUES (:symbol, :shares, :price, :time, :userID)", symbol=request.form.get("symbol"), shares=sharesSold, price=stock["price"], time=datetime.datetime.now(), userID=session["user_id"])
        else:
            return apology("invalid number of shares", 403)
        return redirect("/")
    else:
        symbols = db.execute("SELECT symbol FROM stocks WHERE userID = :userID GROUP BY symbol", userID=session["user_id"])
        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
