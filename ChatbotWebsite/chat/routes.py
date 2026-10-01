import json
import os

from flask import Blueprint, current_app, jsonify, render_template, request

chat = Blueprint("chat", __name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data")

with open(os.path.join(DATA_DIR, "topics.json"), encoding="utf-8") as file:
    topics_data = json.load(file)


def get_all_topics():
    return topics_data.get("topics", [])


def get_content(title):
    for topic in topics_data.get("topics", []):
        if topic["title"] == title:
            return topic.get("content", ["No content available"])
    return ["Topic not found"]


# Chat Page
@chat.route("/chat")
def chat_page():
    topics = {"topics": get_all_topics()}
    return render_template("chat/chat.html", title="Chat", topics=topics)


# Chat Messages
@chat.route("/chat_messages", methods=["POST"])
def chatting():
    message = request.form.get("msg", "")
    if not current_app.config["LOAD_INTENT_MODEL"]:
        return jsonify({"msg": "The chatbot model is disabled in this configuration."})
    # Imported lazily so TensorFlow only loads when the chat is actually used
    from ChatbotWebsite.chat.chatbot import get_response

    return jsonify({"msg": get_response(message)})


# Topic Selection
@chat.route("/topic", methods=["POST"])
def topic():
    title = request.form.get("title", "")
    return jsonify({"contents": get_content(title)})
