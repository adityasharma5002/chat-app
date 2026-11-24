from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_socketio import SocketIO, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime


app = Flask(__name__)


# Secret key for login sessions
app.secret_key = "chat-app-secret-key"


# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chat.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Create database object
db = SQLAlchemy(app)


# Enable database migrations
migrate = Migrate(app, db)


# Enable SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")


# =========================================================
# DATABASE MODEL - CHAT MESSAGE
# =========================================================

class ChatMessage(db.Model):

    # Unique ID for every message
    id = db.Column(db.Integer, primary_key=True)

    # Message sender type
    sender = db.Column(db.String(20), nullable=False)

    # Actual message
    message = db.Column(db.Text, nullable=False)

    # User who sent the message
    sender_id = db.Column(db.Integer, nullable=True)

    # User who receives the message
    receiver_id = db.Column(db.Integer, nullable=True)

    # Time when the message was sent
    timestamp = db.Column(
        db.DateTime,
        default=datetime.now,
        nullable=False
    )


# =========================================================
# DATABASE MODEL - USER
# =========================================================

class User(db.Model):

    # Unique user ID
    id = db.Column(db.Integer, primary_key=True)

    # Username
    username = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    # Password
    password = db.Column(
        db.String(100),
        nullable=False
    )


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"].strip()

        # Check if username already exists
        existing_user = User.query.filter_by(
            username=username
        ).first()

        if existing_user:
            return "Username already exists."

        # Create new user
        new_user = User(
            username=username,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"].strip()

        # Find user
        user = User.query.filter_by(
            username=username,
            password=password
        ).first()

        if user:

            # Save user information in session
            session["user_id"] = user.id
            session["username"] = user.username

            return redirect(url_for("home"))

        return "Invalid username or password."

    return render_template("login.html")


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# GET ALL USERS EXCEPT CURRENT USER
# =========================================================

@app.route("/users")
def users():

    if "user_id" not in session:
        return jsonify([])

    current_user_id = session["user_id"]

    users = User.query.filter(
        User.id != current_user_id
    ).all()

    user_list = []

    for user in users:

        user_list.append({
            "id": user.id,
            "username": user.username
        })

    return jsonify(user_list)


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# MAIN CHAT PAGE
# =========================================================

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template(
        "index.html",
        username=session["username"]
    )


# =========================================================
# GET PRIVATE MESSAGES
# =========================================================

@app.route("/messages/<int:user_id>")
def get_messages(user_id):

    if "user_id" not in session:

        return jsonify({
            "error": "Please login first."
        }), 401

    current_user_id = session["user_id"]

    # Get messages in both directions:
    # Current user -> selected user
    # Selected user -> current user

    messages = ChatMessage.query.filter(
        db.or_(
            db.and_(
                ChatMessage.sender_id == current_user_id,
                ChatMessage.receiver_id == user_id
            ),
            db.and_(
                ChatMessage.sender_id == user_id,
                ChatMessage.receiver_id == current_user_id
            )
        )
    ).order_by(ChatMessage.id).all()

    message_list = []

    for msg in messages:

        sender_user = User.query.get(msg.sender_id)

        message_list.append({

            "sender_id": msg.sender_id,

            "sender_name": (
                sender_user.username
                if sender_user
                else "Unknown"
            ),

            "message": msg.message,

            # Send message time to JavaScript
            "time": msg.timestamp.strftime("%I:%M %p")
        })

    return jsonify(message_list)


# =========================================================
# SEND PRIVATE MESSAGE
# =========================================================

@app.route("/chat", methods=["POST"])
def chat():

    if "user_id" not in session:

        return jsonify({
            "error": "Please login first."
        }), 401

    data = request.get_json()

    message = data.get("message", "").strip()

    receiver_id = data.get("receiver_id")

    # Check empty message
    if message == "":

        return jsonify({
            "error": "Message cannot be empty."
        }), 400

    # Check receiver
    if not receiver_id:

        return jsonify({
            "error": "Please select a user first."
        }), 400

    # Find receiver
    receiver = User.query.get(receiver_id)

    if not receiver:

        return jsonify({
            "error": "User not found."
        }), 404

    # Save message in database
    new_message = ChatMessage(

        sender="user",

        message=message,

        sender_id=session["user_id"],

        receiver_id=receiver.id
    )

    db.session.add(new_message)

    db.session.commit()


    # Send message to receiver's personal room
    socketio.emit(

        "receive_message",

        {
            "sender_id": session["user_id"],

            "sender_name": session["username"],

            "receiver_id": receiver.id,

            "message": message,

            # Send message time
            "time": new_message.timestamp.strftime("%I:%M %p")
        },

        room=f"user_{receiver.id}"
    )


    return jsonify({

        "success": True,

        # Return time to sender
        "time": new_message.timestamp.strftime("%I:%M %p")
    })


# =========================================================
# SOCKET.IO CONNECT
# =========================================================

@socketio.on("connect")
def handle_connect():

    if "user_id" in session:

        user_id = session["user_id"]

        # Join user's personal room
        join_room(f"user_{user_id}")

        print(
            f"[connect] User {user_id} joined room user_{user_id}"
        )

    else:

        print(
            "[connect] Socket connected but no user_id in session."
        )


# =========================================================
# SOCKET.IO EXPLICIT JOIN
# =========================================================

@socketio.on("join")
def handle_join():

    # Get logged-in user from session
    user_id = session.get("user_id")

    if user_id:

        # Join personal room again
        join_room(f"user_{user_id}")

        print(
            f"[join] User {user_id} joined room user_{user_id}"
        )


# =========================================================
# CLEAR CHAT
# =========================================================

@app.route("/clear-chat", methods=["POST"])
def clear_chat():

    if "user_id" not in session:

        return jsonify({
            "success": False
        }), 401

    # Delete messages involving current user
    ChatMessage.query.filter(

        (ChatMessage.sender_id == session["user_id"]) |

        (ChatMessage.receiver_id == session["user_id"])

    ).delete(
        synchronize_session=False
    )

    db.session.commit()

    return jsonify({
        "success": True
    })


# =========================================================
# CREATE DATABASE TABLES
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# START FLASK SERVER
# =========================================================

if __name__ == "__main__":

    socketio.run(
        app,
        debug=True
    )