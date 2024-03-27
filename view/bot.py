from flask import *
from celery.result import AsyncResult
import gspread
import re
import json
from model.oauth import *
import uuid
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from util.salesBot import *
from markupsafe import Markup
from pdfminer.high_level import extract_text
from model.celery import celery
from model.tasks import process_pdf_task

bot = Blueprint("bot", __name__)

credentials = service_account.Credentials.from_service_account_file(
    "static/Credentials/flowbot-380922-396cd267944e.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
)

gc = gspread.authorize(credentials)


sheet = gc.open_by_key("15IPEtgYTWXGPKIPqanL-Bl_-9XjDBua-wEUuJ6LnUQU").sheet1

SPREADSHEET_ID = "1MPItEnTI32s5pTKtr5OI6k9ZIYALeD4WepYNWYFIB9g"
SHEET_NAME = "Sheet1"
service = build("sheets", "v4", credentials=credentials)
range_ = "A:E"


chat_log = " "

user_id = " "
workflow = "HTML"


def getAgent(agent_id):
    try:
        with current_app.app_context():
            agent = Agent_Header.query.filter_by(agent_id=agent_id).first()
            if agent is None:
                return None
            return agent.header
    except Exception as e:
        return str(e)


def delete_chatlog(user_id):
    try:
        db.session.query(ChatbotMemory).filter(
            ChatbotMemory.user_id == user_id
        ).delete()
        db.session.commit()
        result = "Chat log deleted successfully."
    except Exception as e:
        db.session.rollback()
        result = f"Error deleting chat log: {str(e)}"
    finally:
        db.session.close()
    return result


def create_chatlog(user_id):
    try:
        chat_log_entries = (
            db.session.query(
                ChatbotMemory.time, ChatbotMemory.speaker, ChatbotMemory.content
            )
            .filter(ChatbotMemory.user_id == user_id)
            .order_by(ChatbotMemory.time.desc())
            .limit(10)
            .subquery()
        )
        chat_log_entries = (
            db.session.query(chat_log_entries.c.speaker, chat_log_entries.c.content)
            .order_by(chat_log_entries.c.time.asc())
            .all()
        )
        chat_log = "\n".join(
            [f"{speaker}: {content}" for speaker, content in chat_log_entries]
        )
    except Exception as e:
        chat_log = ""
    finally:
        db.session.close()
    return chat_log


def last_content(user_id):
    try:
        result = (
            db.session.query(ChatbotMemory.content)
            .filter(ChatbotMemory.user_id == user_id)
            .order_by(ChatbotMemory.time.desc())
            .first()
        )

        if result:
            return result[0]
        else:
            return None
    except Exception as e:
        return None
    finally:
        db.session.close()


def generate_initial_response():
    instructions = "Greet the user and offer to help."
    prompt = f"You are an efficient assistant. Keep responses brief and to the point"
    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": instructions},
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=thePrompt,
        )
        generated_response = response["choices"][0]["message"]["content"]
    except openai.error.OpenAIError:
        generated_response = "Hello! I'm here to assist you with your ACA questions."
    return generated_response


def generate_initial_response():
    instructions = "Greet the user and offer to help."
    prompt = f"You are an efficient assistant. Keep responses brief and to the point"
    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": instructions},
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=thePrompt,
        )
        generated_response = response["choices"][0]["message"]["content"]
    except openai.error.OpenAIError:
        generated_response = "Hello! I'm here to assist you with your ACA questions."
    return generated_response


def generate_initial_response_1():
    instructions = "Greet the user and offer to help with any questions.  To see a sample quote the user should provide their zip code."
    prompt = f"You are an efficient assistant. Keep responses brief and to the point and ask the user to provide their zipcode for sample quote"
    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": instructions},
    ]
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=thePrompt,
        )
        generated_response = response["choices"][0]["message"]["content"]
    except openai.error.OpenAIError:
        generated_response = "Hello! I'm here to assist you with your ACA questions."
    return generated_response


chat_dict = {}


def add_to_chat_dict(question, response):
    if len(chat_dict) == 3:
        oldest_question = list(chat_dict.keys())[0]
        del chat_dict[oldest_question]

    chat_dict[question] = response
    chat_log = ""
    for question, answer in chat_dict.items():
        chat_log += f"Q: {question}\nA: {answer}\n"
    session["chat_log"] = chat_log
    return


@bot.route("/bot")
def index():
    initial_message = generate_initial_response()
    return jsonify({"initial_message": initial_message})


@bot.route("/bot/version")
def index_bot():
    initial_message = "Welcome! I'm here to assist with any questions you may have. Plus, get a sample quote instantly – just provide your zip code. Let's get started!"
    return jsonify({"initial_message": initial_message})


@bot.route("/version_1", methods=["POST"])
def version_1():
    botHeader = getAgent(1)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_2", methods=["POST"])
def version_2():
    botHeader = getAgent(2)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_3", methods=["POST"])
def version_3():
    botHeader = getAgent(3)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_4", methods=["POST"])
def version_4():
    botHeader = getAgent(4)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_5", methods=["POST"])
def version_5():
    botHeader = getAgent(5)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_6", methods=["POST"])
def version_6():
    botHeader = getAgent(6)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    try:
        purpose = "The user wants to know more about enrolling in ACA medical insurance. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Keep the response to the point and short."
        answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )
    except Exception as e:
        answer = "Oops, it seems there's been a hiccup. Please try again!"
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_7", methods=["POST"])
def version_7():
    botHeader = getAgent(7)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id
    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    count = check_user_id_exists(user_id)
    if count == 0:
        insert_user_get_id(user_id)
        update_state(user_id, "Neutral")
    currentState = check_user_id(user_id)
    if currentState == "Neutral":
        theInstructions = """You are a helpful assistant. You have the following functions available for creating a response for users. Please use the user <QUERY> along with the <chat_log> to determine which function to use.  Think step-by-step. First, carefully analyze the user query along with the chat log to determine the intent.  Then check each of the following functions to see which would best address the user's intent. 
                    [{'function_name': 'sample_quote', 'required_parameters': {'USER INPUT','ZIP CODE'}, 'behavior': 'A function that gets an ACA insurance quote for a user based on specific information provided by the the user. Always use this function if the user has provided a zipcode.'},
                    {'function_name': 'questionAndAnswer', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers questions from the user. After creating a response, always remind the user to select the 'Enroll Now' button. The <questionAndAnswer> function will always be the default choice if no other function is deemed suitable.'}]                    Your response will name exactly one function which will be used to fulfill the user's requirement."""
        thePrompt = [
            {"role": "system", "content": theInstructions},
            {"role": "system", "content": chat_log},
            {"role": "user", "content": query},
            {
                "role": "assistant",
                "content": f"Select a function that will fulfill the user's requirement.",
            },
        ]
        response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
        aResponse = response["choices"][0]["message"]
        print("A response: " + str(aResponse))
        solution = aResponse["content"]
        if solution.__contains__("sample_quote"):
            update_state(user_id, "sampleQuote")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to sample_quote",
            )
        elif solution.__contains__("questionAndAnswer"):
            update_state(user_id, "question_and_answer")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to questionAndAnswer",
            )
        return version_7()
    if currentState == "sampleQuote":
        try:
            exc_zip = extract_user_zipcode(query)
            print(exc_zip)
            validate_zipcode = check_zipcode_for(exc_zip)
            print("validate_zipcode" + str(validate_zipcode))
            counties = validate_zipcode.get("counties")
            if not counties:
                purpose = "The user needs to provide a valid US zipcode in order to get an aca quote. Please answer any question from the user and also instruct the user to provide their zipcode."
                answer = questionAndAnswer(
                    query, user_id, chat_dict, purpose, botHeader
                )
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
            else:
                if exc_zip.__contains__("None"):
                    purpose = "The user needs to provide a valid US zipcode in order to get an aca quote. Please answer any question from the user and also instruct the user to provide their zipcode."
                    answer = questionAndAnswer(
                        query, user_id, chat_dict, purpose, botHeader
                    )
                    update_state(user_id, "Neutral")
                    insert_chat(
                        now,
                        user_id,
                        workflow,
                        "System",
                        "Current state changed to neutral",
                    )
                else:
                    print("Comming Here")
                    get_sample, planData = get_sample_quote(exc_zip)
                    answer = get_sample
                    insert_chat(
                        now,
                        user_id,
                        workflow,
                        "System",
                        "Current state changed to neutral",
                    )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            print(e)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )

    elif currentState == "question_and_answer":
        try:
            purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
            answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/version_8", methods=["POST"])
def version_8():
    botHeader = getAgent(8)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id
    query = request.form["user_input"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    count = check_user_id_exists(user_id)
    if count == 0:
        insert_user_get_id(user_id)
        update_state(user_id, "Neutral")
    currentState = check_user_id(user_id)
    if currentState == "Neutral":
        theInstructions = """You are a helpful assistant. You have the following functions available for creating a response for users. Please use the user <QUERY> along with the <chat_log> to determine which function to use.  Think step-by-step. First, carefully analyze the user query along with the chat log to determine the intent.  Then check each of the following functions to see which would best address the user's intent. 
                    [{'function_name': 'sample_quote', 'required_parameters': {'USER INPUT','ZIP CODE'}, 'behavior': 'A function that gets an ACA insurance quote for a user based on specific information provided by the the user. Always use this function if the user has provided a zipcode.'},
                    {'function_name': 'questionAndAnswer', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers questions from the user. After creating a response, always remind the user to select the 'Enroll Now' button. The <questionAndAnswer> function will always be the default choice if no other function is deemed suitable.'}]                    Your response will name exactly one function which will be used to fulfill the user's requirement."""
        thePrompt = [
            {"role": "system", "content": theInstructions},
            {"role": "system", "content": chat_log},
            {"role": "user", "content": query},
            {
                "role": "assistant",
                "content": f"Select a function that will fulfill the user's requirement.",
            },
        ]
        response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
        aResponse = response["choices"][0]["message"]
        print("A response: " + str(aResponse))
        solution = aResponse["content"]
        if solution.__contains__("sample_quote"):
            update_state(user_id, "sampleQuote")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to sample_quote",
            )
        elif solution.__contains__("questionAndAnswer"):
            update_state(user_id, "question_and_answer")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to questionAndAnswer",
            )
        return version_8()
    if currentState == "sampleQuote":
        try:
            exc_zip = extract_user_zipcode(query)
            print(exc_zip)
            validate_zipcode = check_zipcode_for(exc_zip)
            print("validate_zipcode" + str(validate_zipcode))
            counties = validate_zipcode.get("counties")
            if not counties:
                purpose = "The user needs to provide a valid US zipcode in order to get an aca quote. Please answer any question from the user and also instruct the user to provide their zipcode."
                answer = questionAndAnswer(
                    query, user_id, chat_dict, purpose, botHeader
                )
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
            else:
                if exc_zip.__contains__("None"):
                    purpose = "The user needs to provide a valid US zipcode in order to get an aca quote. Please answer any question from the user and also instruct the user to provide their zipcode."
                    answer = questionAndAnswer(
                        query, user_id, chat_dict, purpose, botHeader
                    )
                    update_state(user_id, "Neutral")
                    insert_chat(
                        now,
                        user_id,
                        workflow,
                        "System",
                        "Current state changed to neutral",
                    )
                else:
                    print("Comming Here")
                    get_sample, planData = get_sample_quote_2(exc_zip)
                    answer = get_sample
                    insert_chat(
                        now,
                        user_id,
                        workflow,
                        "System",
                        "Current state changed to neutral",
                    )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            print(e)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )

    elif currentState == "question_and_answer":
        try:
            purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
            answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/bot/plan", methods=["GET"])
def index_plan():
    if "user_id" in session:
        delete_chatlog(session.get("user_id"))
    initial_message = f"Welcome! I'm here to assist with any questions you may have. Plus, help find a plan tailored just for you! You can start with the 'edit' button at the top of this page. Here you can add your specific information!"
    return jsonify({"initial_message": initial_message})


@bot.route("/version_9", methods=["POST"])
def version_9():
    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    print(user_id)
    botHeader = getAgent(9)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    query = request.form["user_input"]
    get_plan = request.form["plan_data"]
    answer = None
    previous_content = last_content(user_id)
    print(previous_content)
    if previous_content != query:
        now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        insert_chat(now, user_id, workflow, "User", query)
    chat_log = create_chatlog(user_id)
    count = check_user_id_exists(user_id)
    if count == 0:
        insert_user_get_id(user_id)
        update_state(user_id, "Neutral")
    currentState = check_user_id(user_id)
    if currentState == "Neutral":
        theInstructions = """You are a helpful assistant. You have the following functions available for creating a response for users. Please use the user <QUERY> along with the <chat_log> to determine which function to use.  Think step-by-step. First, carefully analyze the user query along with the chat log to determine the intent.  Then check each of the following functions to see which would best address the user's intent. 
                    [{'function_name': 'your_plan', 'required_parameters': 'USER INPUT', 'behavior': 'A function that gets an ACA insurance quote for a user based on specific information provided by the the user. Always use this function if the user ask for the plan.'},
                    {'function_name': 'questionAndAnswer', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers questions from the user. After creating a response, always remind the user to select the 'Enroll Now' button. The <questionAndAnswer> function will always be the default choice if no other function is deemed suitable.'}]                    Your response will name exactly one function which will be used to fulfill the user's requirement."""
        thePrompt = [
            {"role": "system", "content": theInstructions},
            {"role": "system", "content": chat_log},
            {"role": "user", "content": query},
            {
                "role": "assistant",
                "content": f"Select a function that will fulfill the user's requirement.",
            },
        ]
        response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
        aResponse = response["choices"][0]["message"]
        print("A response: " + str(aResponse))
        solution = aResponse["content"]
        if solution.__contains__("your_plan"):
            update_state(user_id, "yourPlan")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to your_plan",
            )
        elif solution.__contains__("questionAndAnswer"):
            update_state(user_id, "question_and_answer")
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to questionAndAnswer",
            )
        return version_9()
    if currentState == "yourPlan":
        try:
            print("Coming    Here")
            purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
            answer = generate_plan_response(get_plan, chat_log)
            insert_chat(
                now,
                user_id,
                workflow,
                "System",
                "Current state changed to neutral",
            )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            print(e)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )

    elif currentState == "question_and_answer":
        try:
            purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
            answer = questionAndAnswer(query, user_id, chat_dict, purpose, botHeader)
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
        except Exception as e:
            answer = "Oops, it seems there's been a hiccup. Please try again!"
            update_state(user_id, "Neutral")
            insert_chat(
                now, user_id, workflow, "System", "Current state changed to neutral"
            )
    addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
    return answer


@bot.route("/bot/plan/benefits", methods=["GET"])
def index_plan_benefits():
    planname = request.args.get(
        "planname"
    )  # Access the 'planname' parameter from the URL
    initial_message = f"Thanks for selecting {planname}! I can assist with any specific questions you may have. Also, whenever you like, just hit the 'Enroll Now' button to get started with the application."
    return jsonify({"initial_message": initial_message})


# @bot.route("/version_10", methods=["POST"])
# def version_10():
#     query = request.form["user_input"]
#     get_plan = request.form["plan_data"]
#     benefits_url = request.form["benefits_url"]
#     plan_id = request.form["plan_id"]
#     run_newsletter_creation.delay(query, get_plan, benefits_url, plan_id)


@bot.route("/version_10", methods=["POST"])
def version_10():
    try:

        user_id = session.get("user_id", str(uuid.uuid4()))
        session["user_id"] = user_id
        print(user_id)
        botHeader = getAgent(10)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = request.form["user_input"]
        get_plan = request.form["plan_data"]
        benefits_url = request.form["benefits_url"]
        plan_id = request.form["plan_id"]
        print(plan_id)
        answer = None
        previous_content = last_content(user_id)
        print(previous_content)
        if previous_content != query:
            now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
            insert_chat(now, user_id, workflow, "User", query)
        chat_log = create_chatlog(user_id)
        count = check_user_id_exists(user_id)
        if count == 0:
            insert_user_get_id(user_id)
            update_state(user_id, "Neutral")
        currentState = check_user_id(user_id)
        if currentState == "Neutral":
            theInstructions = """You are a helpful assistant. You have the following functions available for creating a response for users. Please use the user <QUERY> along with the <chat_log> to determine which function to use.  Think step-by-step. First, carefully analyze the user query along with the chat log to determine the intent.  Then check each of the following functions to see which would best address the user's intent.
                        [{'function_name': 'your_benefit', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers about the plan benefits.'},
                        {'function_name': 'your_plan', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers about the plan details.'}
                        {'function_name': 'your_covered_drug', 'required_parameters': 'USER INPUT', 'behavior': 'A function that checks if a named prescription drug is covered by the insurance plan with the given <PLAN ID>. A user often needs to know if a particular drug is part of their insurance plan.  This function will check that information using the drug name and the plan id. If the plan id is not currently available, this function will generate a plan id.'},
                        {'function_name': 'questionAndAnswer', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers questions from the user. The <questionAndAnswer> function will always be the default choice if no other function is deemed suitable.'}]
                        Your response will name exactly one function which will be used to fulfill the user's requirement."""
            thePrompt = [
                {"role": "system", "content": theInstructions},
                {"role": "system", "content": chat_log},
                {"role": "user", "content": query},
                {
                    "role": "assistant",
                    "content": f"Select a function that will fulfill the user's requirement.",
                },
            ]
            response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
            aResponse = response["choices"][0]["message"]
            print("A response: " + str(aResponse))
            solution = aResponse["content"]

            if solution.__contains__("your_benefit"):
                update_state(user_id, "yourBenefit")
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to your_benefit",
                )
            elif solution.__contains__("your_plan"):
                update_state(user_id, "yourPlan")
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to your_plan",
                )

            elif solution.__contains__("questionAndAnswer"):
                update_state(user_id, "question_and_answer")
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to questionAndAnswer",
                )
            elif solution.__contains__("your_covered_drug"):
                update_state(user_id, "yourcoveredDrug")
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to your_covered_drug",
                )
            return version_10()

        if currentState == "yourPlan":
            try:
                answer = generate_plan_response_2(get_plan, chat_log)
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to neutral",
                )
            except Exception as e:
                answer = "Oops, it seems there's been a hiccup. Please try again!"
                print(e)
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
        if currentState == "yourBenefit":
            # task = process_pdf_task.delay(
            #     benefits_url, query, chat_log, user_id, now, workflow
            # )

            # task_id = task.id
            # result = task.get()  # Wait for the task to complete and get the result
            # answer = task_id
            # return jsonify({"message": result})
            try:
                print("Coming Here")
                answer = process_pdf(benefits_url, query, chat_log)
                insert_chat(
                    now,
                    user_id,
                    workflow,
                    "System",
                    "Current state changed to neutral",
                )
            except Exception as e:
                answer = "Oops, it seems there's been a hiccup. Please try again!"
                print(e)
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
        elif currentState == "yourcoveredDrug":
            try:
                print("Coming Here DRUG")
                drug_name = extract_drug_name(query)
                print(drug_name)
                if drug_name.__contains__("None"):
                    purpose = "The user needs to provide a valid drug."
                    answer = questionAndAnswer(
                        query, user_id, chat_log, purpose, botHeader
                    )
                    update_state(user_id, "Neutral")
                    insert_chat(
                        now,
                        user_id,
                        workflow,
                        "System",
                        "Current state changed to neutral",
                    )
                else:
                    getDrug = getDrugName(drug_name)
                    if not getDrug:
                        print("THE DRUG IN IF:" + str(getDrug))
                        purpose = "The user needs to provide a valid drug."
                        answer = questionAndAnswer(
                            query, user_id, chat_log, purpose, botHeader
                        )
                        update_state(user_id, "Neutral")
                        insert_chat(
                            now,
                            user_id,
                            workflow,
                            "System",
                            "Current state changed to neutral",
                        )
                    else:
                        planId = plan_id
                        if planId:
                            drugName = getDrugName(drug_name)
                            rxcui_list = [item["rxcui"] for item in drugName]
                            rxcui_string = ",".join(rxcui_list)
                            drugCovered = getDrugCovered(planId, rxcui_string)
                            covered_rxcui_list = [
                                item["rxcui"]
                                for item in drugCovered["coverage"]
                                if item["coverage"] == "Covered"
                            ]
                            if not covered_rxcui_list:
                                purpose = "The drug is not covered in plan."
                                answer = questionAndAnswer(
                                    query, user_id, chat_log, purpose, botHeader
                                )
                                update_state(user_id, "Neutral")
                                insert_chat(
                                    now,
                                    user_id,
                                    workflow,
                                    "System",
                                    "Current state changed to neutral",
                                )
                            else:
                                covered_drugs_data = [
                                    item
                                    for item in drugName
                                    if item["rxcui"] in covered_rxcui_list
                                ]
                                answer = generate_drugs_coverage_response(
                                    covered_drugs_data
                                )
                                update_state(user_id, "Neutral")
                                insert_chat(
                                    now,
                                    user_id,
                                    workflow,
                                    "System",
                                    "Current state changed to neutral",
                                )
            except Exception as e:
                answer = "Oops, it seems there's been a hiccup. Please try again!"
                print(e)
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )

        elif currentState == "question_and_answer":
            try:
                purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
                answer = questionAndAnswer(
                    query, user_id, chat_dict, purpose, botHeader
                )
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
            except Exception as e:
                answer = "Oops, it seems there's been a hiccup. Please try again!"
                update_state(user_id, "Neutral")
                insert_chat(
                    now, user_id, workflow, "System", "Current state changed to neutral"
                )
        addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
        return answer
    except Exception as e:
        print(e)
        answer = "Oops, it seems there's been a hiccup. Please try again!"
        update_state(user_id, "Neutral")
        insert_chat(
            now, user_id, workflow, "System", "Current state changed to neutral"
        )


def extract_drug_name(sentence):
    prompt = (
        "You are a precise virtual assistant. Please follow the following instructions precisely. Extract the drug name from the following phrase: "
        + f"{sentence}"
        + "Please return the drug name only.  A sentence is NOT acceptable.  Just the name.  If no name if found, say None."
    )
    thePrompt = [{"role": "system", "content": prompt}]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=thePrompt,
    )
    extracted_text = response["choices"][0]["message"]
    theDrug = extracted_text["content"]
    return theDrug


def getDrugName(aName):
    urlDrugName = "https://marketplace.api.healthcare.gov/api/v1/drugs/autocomplete?q="
    apikey = "6PgIlDan5b5hx6FtRHE6fu8EEw5P8Lo8"
    url = urlDrugName + str(aName)
    response = requests.get(url, params={"apikey": apikey, "year": "2024"})
    return response.json()


def getDrugCovered(aPlanID, drugIDs):
    urlDrugCovered = (
        "https://marketplace.api.healthcare.gov/api/v1/drugs/covered?planids="
    )
    apikey = "6PgIlDan5b5hx6FtRHE6fu8EEw5P8Lo8"
    params = {"apikey": apikey, "year": "2024"}

    url = urlDrugCovered + aPlanID + "&drugs=" + drugIDs
    response = requests.get(url, params=params)
    data = response.json()
    return data


def generate_drugs_coverage_response(covered_drugs_data):
    instructions = "The following drugs are covered by your plan."
    prompt = f"You are an efficient assistant. Your job is to rewrite the included instructions.\n"
    for drug in covered_drugs_data:
        drug_name = drug["full_name"]
        instructions += f"- Drug Name: {drug_name}\n"
    print("INSTRUCNTION: " + instructions)
    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "assistant", "content": instructions},
    ]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=thePrompt,
    )

    generated_response = response["choices"][0]["message"]["content"]
    print("GENERATED_RESPONE: " + generated_response)
    return generated_response


from io import BytesIO


def download_pdf(link):
    response = requests.get(link)
    pdf_in_memory = BytesIO(response.content)
    return pdf_in_memory


def process_pdf(link, query, chat_log):
    pdf_in_memory = download_pdf(link)
    text = extract_text(pdf_in_memory)
    text = re.sub(r"\n+", "\n", text)

    text = " ".join(word for word in text.split() if all(ord(c) < 128 for c in word))
    pdfText = text
    openai.api_key = "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"
    memory = {}
    theInstructions = """You are a helpful assistant with a specialty in answering questions about a specific ACA insurance policy based on information extracted from a pdf.  Please consider the user's <QUERY> and then carefully read the <PDFTEXT> in order to respond.  Reason step by step."""
    thePrompt = [
        {"role": "system", "content": theInstructions},
        {"role": "system", "content": pdfText},
        {"role": "system", "content": chat_log},
        {"role": "user", "content": query},
        {
            "role": "assistant",
            "content": "Use the text to help respond to the query from the user.",
        },
    ]
    memory = thePrompt
    response = openai.ChatCompletion.create(model="gpt-4", messages=memory)
    aResponse = response["choices"][0]["message"]
    solution = aResponse["content"]
    return solution


def generate_plan_response_2(data, chat_log):
    instructions = f"""
        Plan selection page processes.
        1) Plan Data
            This the user plan {data} use that to answer user query.
        """
    prompt = "You are an efficient assistant. Your job is to guide the user through the topics on the Plan selection page using <chat_log> and the data. Please make responses short and to the point"
    instructions_1 = instructions[:8100]
    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": chat_log},
        {"role": "system", "content": instructions_1},
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=thePrompt,
    )
    generated_response = response["choices"][0]["message"]["content"]

    return generated_response


def generate_plan_response(data, chat_log):
    instructions = f"""
        Plan selection page processes.
        1) Plan Data
            This the user plan {data} use that to answer user query include that data to every step.
        2) Ask about basic plan info
            The user can ask about basic plan information such as premium and metal level from the displayed list.
        3) Edit personal information
            The user should know to select the <edit> button to modify personal information.  This allows the plan selection page to display plan data selected specifically of rthe user.
        4) Modify filters
            This is an optional step, but it can be useful to filter the plans being shown to a specific Metal type.  Silver is probably the most used option.  select this by using the <Metal Level> dropdown and selecting <Silver>.
        5) Select a plan
            The user can scroll through the list of displayed plans, select one of interest and then get more details by selecting <view plan details>
        """
    prompt = "You are an efficient assistant. Your job is to guide the user through the topics on the Plan selection page using <chat_log> and the data, but always remember that the primary goal is to have the user speak to an agent. Please make responses short and to the point"

    thePrompt = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": chat_log},
        {"role": "system", "content": instructions},
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=thePrompt,
    )
    generated_response = response["choices"][0]["message"]["content"]

    return generated_response


def make_report(planData):
    report = f"The lowest cost silver plan is {planData['name']}  * Metal Level: {planData['metal_level']}  * Premium with tax credit: ${planData['premium_w_credit']}. Ready to secure your coverage? Click 'Enroll Now' to begin your journey to peace of mind!"
    return report


def make_report_2(planData):
    report = f"The lowest cost silver plan is {planData['name']}  * Metal Level: {planData['metal_level']}  * Premium with tax credit: ${planData['premium_w_credit']}. Ready to secure your coverage? Click 'Contact an Agent' to begin your journey to peace of mind!"
    return report


def get_sample_quote_2(zipCode):
    url = "https://marketplace.api.healthcare.gov/api/v1/counties/by/zip/" + zipCode
    urlPlanSearch = "https://marketplace.api.healthcare.gov/api/v1/plans/search"

    apikey = "kagpoNXkkxFNuPq10KflnAcXIOKWN8RI"

    params = {"apikey": apikey, "year": "2024"}

    headers = {"Content-Type": "application/json", "apikey": apikey}

    response = requests.get(url, params=params)
    data = response.json()

    print(data["counties"])

    county = data["counties"][0]
    state = county["state"]
    countyFIPS = county["fips"]

    payload = {
        "filter": {"metal_levels": ["Silver"]},
        "household": {
            "income": 20000,
            "people": [
                {
                    "age": 40,
                    "aptc_eligible": True,
                    "gender": "Female",
                    "uses_tobacco": False,
                }
            ],
        },
        "market": "Individual",
        "place": {"countyfips": countyFIPS, "state": state, "zipcode": zipCode},
        "year": 2024,
    }

    print(payload)

    age = payload["household"]["people"][0]["age"]
    income = payload["household"]["income"]

    response = requests.post(urlPlanSearch, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        data = response.json()
        # print(data)
        planData = data["plans"][0]
        report = make_report_2(planData)
        print(report)

    else:
        print("Error:", response.status_code, response.text)
        data = json.loads(response.text)
        error_message = data["error"]
        theResponse = "Marketplace data currently not available for your state. Please select the button below to talk with an agent."
        return theResponse

    return report, planData


def get_sample_quote(zipCode):
    url = "https://marketplace.api.healthcare.gov/api/v1/counties/by/zip/" + zipCode
    urlPlanSearch = "https://marketplace.api.healthcare.gov/api/v1/plans/search"

    apikey = "kagpoNXkkxFNuPq10KflnAcXIOKWN8RI"

    params = {"apikey": apikey, "year": "2024"}

    headers = {"Content-Type": "application/json", "apikey": apikey}

    response = requests.get(url, params=params)
    data = response.json()

    print(data["counties"])

    county = data["counties"][0]
    state = county["state"]
    countyFIPS = county["fips"]

    payload = {
        "filter": {"metal_levels": ["Silver"]},
        "household": {
            "income": 20000,
            "people": [
                {
                    "age": 40,
                    "aptc_eligible": True,
                    "gender": "Female",
                    "uses_tobacco": False,
                }
            ],
        },
        "market": "Individual",
        "place": {"countyfips": countyFIPS, "state": state, "zipcode": zipCode},
        "year": 2024,
    }

    print(payload)

    age = payload["household"]["people"][0]["age"]
    income = payload["household"]["income"]

    response = requests.post(urlPlanSearch, headers=headers, data=json.dumps(payload))

    if response.status_code == 200:
        data = response.json()
        # print(data)
        planData = data["plans"][0]
        report = make_report(planData)
        print(report)

    else:
        print("Error:", response.status_code, response.text)
        data = json.loads(response.text)
        error_message = data["error"]
        theResponse = "Marketplace data currently not available for your state. Please select the button below to talk with an agent."
        return theResponse

    return report, planData


def check_user_id_exists(the_user_id):
    try:
        count = UserInfo.query.filter_by(messenger_id=the_user_id).count()
        return count
    except Exception as e:
        return 0


def insert_user_get_id(the_user_id):
    try:
        new_user = UserInfo(messenger_id=the_user_id)
        db.session.add(new_user)
        db.session.commit()
        inserted_id = new_user.id
        return inserted_id
    except Exception as e:
        db.session.rollback()
        return None


def update_state(user_id, current_state):
    try:
        user = UserInfo.query.filter_by(messenger_id=user_id).first()
        if user:
            user.currentState = current_state
            db.session.commit()  # Commit the changes
            return True
        else:
            return False  # User with the provided messenger_id not found
    except Exception as e:
        db.session.rollback()  # Rollback in case of an error
        return False  # Error occurred during the update


def check_user_id(the_user_id):
    try:
        user = UserInfo.query.filter_by(messenger_id=the_user_id).first()
        if user:
            return user.currentState
        else:
            return None  # User with the provided messenger_id not found
    except Exception as e:
        return None  # Error occurred during the query


def check_zipcode_for(zipCode):
    url = "https://marketplace.api.healthcare.gov/api/v1/counties/by/zip/" + zipCode
    apikey = "kagpoNXkkxFNuPq10KflnAcXIOKWN8RI"
    params = {"apikey": apikey, "year": "2024"}

    headers = {"Content-Type": "application/json", "apikey": apikey}

    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    return data


def extract_user_zipcode(sentence):
    prompt = (
        "You are a precise virtual assistant. Please follow the following instructions precisely. Extract the zipcode from the following phrase: "
        + f"{sentence}"
        + "Please return the zipcode only. Zipcode character should be 5. A sentence is NOT acceptable.  Just the zipcode.  If no zipcode if found, say None."
    )
    thePrompt = [{"role": "system", "content": prompt}]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=thePrompt,
    )

    extracted_text = response["choices"][0]["message"]
    theZip = extracted_text["content"]
    return theZip


def questionAndAnswer(query, user_id, chat_log, thePurpose, botHeader):
    answer, thePrompt = salesAsk(query, chat_log, botHeader, thePurpose)
    thePrompt_string = json.dumps(thePrompt)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values = [[now, user_id, workflow, query, answer, thePrompt_string]]
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=SPREADSHEET_ID,
            range=range_,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        )
        .execute()
    )
    add_to_chat_dict(query, answer)
    return answer


def format_newlines(text):
    return text.replace("\n", "<br>")


def insert_chat(now, user_id, workflow, speaker, content):
    try:
        chat_entry = ChatbotMemory(
            time=now,
            user_id=user_id,
            workflow=workflow,
            speaker=speaker,
            content=content,
        )

        db.session.add(chat_entry)
        db.session.commit()

        return "Success"
    except Exception as e:
        db.session.rollback()
        return str(e)


def linkify(text, theText):
    # Regular expression to match URLs with trailing periods
    url_regex = r"(https?://\S+[\w./]+)(?<=\w)"
    link_text = theText
    urls = re.findall(url_regex, text)

    for i in range(len(urls)):
        if urls[i][-1] == ".":
            urls[i] = urls[i][:-1]

    # Replace each URL with an <a> tag containing the custom link text
    for url in urls:
        text = text.replace(url, f'<a href="{url}" target="_blank">{link_text}</a>')
    return Markup(text)
