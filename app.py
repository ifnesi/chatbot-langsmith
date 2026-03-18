"""
Flask Web Application for RAG Chatbot
Provides a web interface for the CloudSync Pro Support Chatbot
"""

import os
import logging

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv

from utils import set_logging_format, check_env_vars
from utils.chatbot import RAGChatbot


# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "your-secret-key-change-this-in-production",
)

# Store chatbot instances per session
chatbots = dict()


def get_chatbot(session_id):
    """Get or create a chatbot instance for the session."""
    if session_id not in chatbots:
        chatbots[session_id] = RAGChatbot(verbose=False)
    return chatbots[session_id]


@app.route("/")
def index():
    """Redirect to login or chat based on session."""
    if "username" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page - just capture username."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if username:
            session["username"] = username
            session["session_id"] = os.urandom(16).hex()
            return redirect(url_for("chat"))
        return render_template(
            "login.html",
            error="Please enter a username",
        )

    return render_template("login.html")


@app.route("/chat")
def chat():
    """Chat interface page."""
    if "username" not in session:
        return redirect(url_for("login"))

    return render_template(
        "chat.html",
        username=session["username"],
    )


@app.route("/logout")
def logout():
    """Logout and clear session."""
    session_id = session.get("session_id")

    # Clean up chatbot instance
    if session_id and session_id in chatbots:
        del chatbots[session_id]

    session.clear()
    return redirect(url_for("login"))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """API endpoint for chat messages."""
    if "username" not in session:
        return (
            jsonify(
                {
                    "error": "Not authenticated",
                }
            ),
            401,
        )

    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return (
            jsonify(
                {
                    "error": "Question is required",
                }
            ),
            400,
        )

    try:
        session_id = session.get("session_id")
        chatbot = get_chatbot(session_id)

        # Query the chatbot
        response = chatbot.query(
            question,
            show_sources=True,
        )

        return jsonify(
            {
                "answer": response["answer"].replace("\n", "<br>"),
                "sources": response["sources"],
                "success": True,
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "success": False,
                }
            ),
            500,
        )


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """API endpoint to reset conversation history."""
    if "username" not in session:
        return (
            jsonify(
                {
                    "error": "Not authenticated",
                }
            ),
            401,
        )

    try:
        session_id = session.get("session_id")
        chatbot = get_chatbot(session_id)
        chatbot.reset_conversation()

        return jsonify(
            {
                "success": True,
                "message": "Conversation history cleared",
            }
        )

    except Exception as e:
        return (
            jsonify(
                {
                    "error": str(e),
                    "success": False,
                }
            ),
            500,
        )


@app.route("/health")
def health():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
        }
    )


if __name__ == "__main__":
    """Run the Flask development server."""
    set_logging_format()
    check_env_vars()
    logging.info("🚀 Starting Flask web application for RAG Chatbot...")

    # Development server settings
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 8888)),
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
    )
