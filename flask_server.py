from flask import Flask, render_template, session, request, redirect, url_for, escape
from flask.helpers import send_from_directory
from pathlib import Path
from werkzeug.exceptions import RequestTimeout
from Messages_Manager import Messages_Manager, DisplayMessage
from pprint import pprint
import logging

app = Flask(__name__)
app.secret_key = b'_5#y2U"F1Q8z\n\xec]/'


def msg_callback(messages_manager: Messages_Manager):
    print("New Message was added")
    pprint(messages_manager.messages)

debug_toggle_sleep = True
def debug_display_sleep_callback():
    print("Toggled sleep")
    global debug_toggle_sleep
    debug_toggle_sleep = not debug_toggle_sleep
    if debug_toggle_sleep:
        return "sleeping"
    else:
        return "awaking"

messages_manager = Messages_Manager()
display_sleep_callback = debug_display_sleep_callback

@app.route("/togglesleep")
def toggle_sleep():
    global display_sleep_callback
    return display_sleep_callback()
 

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(Path(app.root_path, "static"),
                        "favicon.ico",mimetype="image/vnd.microsoft.icon")


@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory(Path(app.root_path, "static"), "apple-touch-icon.png",mimetype="image/vnd.microsoft.icon")

@app.route("/mark-message-as-unread")
def mark_message_as_unread():
    global messages_manager
    number_of_unread_messages_left = messages_manager.mark_oldest_unread_message_as_read()
    ret_str = number_of_unread_messages_left
    try:
        number_unread_int = int(number_of_unread_messages_left)
        if number_unread_int <= 0:
            ret_str = "Keine weiteren Nachrichten!"
        elif number_unread_int == 1:
            ret_str = "Letzte Nachricht."
        else:
            ret_str = "Noch " + str(number_unread_int-1) + " weitere Nachrichten verfügbar."
    except:
        pass
    return ret_str

@app.route("/", methods=['GET', 'POST'])
def start():
    logging.error("Test")
    print(str(request.form))
    if not 'username' in session:
        if "username" in request.form:
            print("Name entered")
            session['username'] = request.form['username']
            return redirect(url_for('start'))
        print("User with no username enters")
        return render_template("EnterName.html")
    elif request.method == "POST" and request.form["submitButton"] == "NewMessage":
        new_message = request.form["message"]
        print("New Message: " + new_message)
        global messages_manager
        messages_manager.new_message(DisplayMessage(session["username"], new_message))
        return redirect(url_for('message_sent'))
    elif request.method == 'POST' and request.form["submitButton"] == "logout":
        print("Logout requested")
        session.pop('username', None)
        return redirect(url_for("start"))
    elif request.method == 'POST':
        print("Name entered")
        session['username'] = request.form['username']
        return redirect(url_for('start'))
    else:
        print("Logged in user on main page")
        return render_template("index.html")
    

@app.route("/message-sent", methods=["GET", "POST"])
def message_sent():
    if request.method == "GET":
        return render_template("messageSent.html", message=messages_manager.get_last_message_from(session["username"]))
    else:
        return redirect(url_for("start"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
    

def start_server(sleeping_callback, msg_manager):
    print("Web-Server is starting...")
    global messages_manager
    messages_manager = msg_manager
    global display_sleep_callback
    display_sleep_callback = sleeping_callback
    #app.run(host="0.0.0.0", debug=True, use_reloader=False)
    app.run(port=5478, host="::")
