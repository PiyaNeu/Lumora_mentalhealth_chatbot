from flask import Blueprint, render_template, request, jsonify
import json
from ChatbotWebsite.chatbot.chatbot import get_response

chatbot = Blueprint("chatbot", __name__)

# -------------------------
# Load topics from JSON
# -------------------------
with open("ChatbotWebsite/static/data/topics.json") as file:
    topics_data = json.load(file)


# -------------------------
# Get all topics
# -------------------------
def get_all_topics():
    return topics_data.get("topics", [])


# -------------------------
# Get content of a topic
# -------------------------
def get_content(title):
    for topic in topics_data.get("topics", []):
        if topic["title"] == title:
            return topic.get("content", ["No content available"])
    return ["Topic not found"]


# -------------------------
# Chat Page
# -------------------------
@chatbot.route("/chat")
def chat():
    topics = {"topics": get_all_topics()}
    return render_template("chat/chat.html", title="Chat", topics=topics)


# -------------------------
# Chat Messages
# -------------------------
@chatbot.route("/chat_messages", methods=["POST"])
def chatting():
    message = request.form.get("msg", "")
    response = get_response(message)
    return jsonify({"msg": response})


# -------------------------
# Topic Selection
# -------------------------
@chatbot.route("/topic", methods=["POST"])
def topic():
    title = request.form.get("title", "")
    contents = get_content(title)
    return jsonify({"contents": contents})
