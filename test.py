# @bot.route("/version_10", methods=["POST"])
# def version_10():
#     try:

#         user_id = session.get("user_id", str(uuid.uuid4()))
#         session["user_id"] = user_id
#         print(user_id)
#         botHeader = getAgent(10)
#         now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         query = request.form["user_input"]
#         get_plan = request.form["plan_data"]
#         benefits_url = request.form["benefits_url"]
#         plan_id = request.form["plan_id"]
#         print(plan_id)
#         answer = None
#         previous_content = last_content(user_id)
#         print(previous_content)
#         if previous_content != query:
#             now = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
#             insert_chat(now, user_id, workflow, "User", query)
#         chat_log = create_chatlog(user_id)
#         count = check_user_id_exists(user_id)
#         if count == 0:
#             insert_user_get_id(user_id)
#             update_state(user_id, "Neutral")
#         currentState = check_user_id(user_id)
#         if currentState == "Neutral":
#             theInstructions = """You are a helpful assistant. You have the following functions available for creating a response for users. Please use the user <QUERY> along with the <chat_log> to determine which function to use.  Think step-by-step. First, carefully analyze the user query along with the chat log to determine the intent.  Then check each of the following functions to see which would best address the user's intent.
#                         [{'function_name': 'your_benefit', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers about the plan.'},
#                         {'function_name': 'your_covered_drug', 'required_parameters': 'USER INPUT', 'behavior': 'A function that checks if a named prescription drug is covered by the insurance plan with the given <PLAN ID>. A user often needs to know if a particular drug is part of their insurance plan.  This function will check that information using the drug name and the plan id. If the plan id is not currently available, this function will generate a plan id.'},
#                         {'function_name': 'questionAndAnswer', 'required_parameters': 'USER INPUT', 'behavior': 'A function that answers questions from the user. The <questionAndAnswer> function will always be the default choice if no other function is deemed suitable.'}]
#                         Your response will name exactly one function which will be used to fulfill the user's requirement."""
#             thePrompt = [
#                 {"role": "system", "content": theInstructions},
#                 {"role": "system", "content": chat_log},
#                 {"role": "user", "content": query},
#                 {
#                     "role": "assistant",
#                     "content": f"Select a function that will fulfill the user's requirement.",
#                 },
#             ]
#             response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
#             aResponse = response["choices"][0]["message"]
#             print("A response: " + str(aResponse))
#             solution = aResponse["content"]

#             if solution.__contains__("your_benefit"):
#                 update_state(user_id, "yourBenefit")
#                 insert_chat(
#                     now,
#                     user_id,
#                     workflow,
#                     "System",
#                     "Current state changed to your_benefit",
#                 )

#             elif solution.__contains__("questionAndAnswer"):
#                 update_state(user_id, "question_and_answer")
#                 insert_chat(
#                     now,
#                     user_id,
#                     workflow,
#                     "System",
#                     "Current state changed to questionAndAnswer",
#                 )
#             elif solution.__contains__("your_covered_drug"):
#                 update_state(user_id, "yourcoveredDrug")
#                 insert_chat(
#                     now,
#                     user_id,
#                     workflow,
#                     "System",
#                     "Current state changed to your_covered_drug",
#                 )
#             return version_10()

#         if currentState == "yourBenefit":
#             try:
#                 print("Coming Here")
#                 answer = process_pdf(benefits_url, query, chat_log)
#                 insert_chat(
#                     now,
#                     user_id,
#                     workflow,
#                     "System",
#                     "Current state changed to neutral",
#                 )
#             except Exception as e:
#                 answer = "Oops, it seems there's been a hiccup. Please try again!"
#                 print(e)
#                 update_state(user_id, "Neutral")
#                 insert_chat(
#                     now, user_id, workflow, "System", "Current state changed to neutral"
#                 )
#         elif currentState == "yourcoveredDrug":
#             try:
#                 print("Coming Here DRUG")
#                 drug_name = extract_drug_name(query)
#                 print(drug_name)
#                 if drug_name.__contains__("None"):
#                     purpose = "The user needs to provide a valid drug."
#                     answer = questionAndAnswer(
#                         query, user_id, chat_log, purpose, botHeader
#                     )
#                     update_state(user_id, "Neutral")
#                     insert_chat(
#                         now,
#                         user_id,
#                         workflow,
#                         "System",
#                         "Current state changed to neutral",
#                     )
#                 else:
#                     getDrug = getDrugName(drug_name)
#                     if not getDrug:
#                         print("THE DRUG IN IF:" + str(getDrug))
#                         purpose = "The user needs to provide a valid drug."
#                         answer = questionAndAnswer(
#                             query, user_id, chat_log, purpose, botHeader
#                         )
#                         update_state(user_id, "Neutral")
#                         insert_chat(
#                             now,
#                             user_id,
#                             workflow,
#                             "System",
#                             "Current state changed to neutral",
#                         )
#                     else:
#                         planId = plan_id
#                         if planId:
#                             drugName = getDrugName(drug_name)
#                             rxcui_list = [item["rxcui"] for item in drugName]
#                             rxcui_string = ",".join(rxcui_list)
#                             drugCovered = getDrugCovered(planId, rxcui_string)
#                             covered_rxcui_list = [
#                                 item["rxcui"]
#                                 for item in drugCovered["coverage"]
#                                 if item["coverage"] == "Covered"
#                             ]
#                             if not covered_rxcui_list:
#                                 purpose = "The drug is not covered in plan."
#                                 answer = questionAndAnswer(
#                                     query, user_id, chat_log, purpose, botHeader
#                                 )
#                                 update_state(user_id, "Neutral")
#                                 insert_chat(
#                                     now,
#                                     user_id,
#                                     workflow,
#                                     "System",
#                                     "Current state changed to neutral",
#                                 )
#                             else:
#                                 covered_drugs_data = [
#                                     item
#                                     for item in drugName
#                                     if item["rxcui"] in covered_rxcui_list
#                                 ]
#                                 answer = generate_drugs_coverage_response(
#                                     covered_drugs_data
#                                 )
#                                 update_state(user_id, "Neutral")
#                                 insert_chat(
#                                     now,
#                                     user_id,
#                                     workflow,
#                                     "System",
#                                     "Current state changed to neutral",
#                                 )
#             except Exception as e:
#                 answer = "Oops, it seems there's been a hiccup. Please try again!"
#                 print(e)
#                 update_state(user_id, "Neutral")
#                 insert_chat(
#                     now, user_id, workflow, "System", "Current state changed to neutral"
#                 )

#         elif currentState == "question_and_answer":
#             try:
#                 purpose = "The human wants to know more about ACA medical insurance plans. Please use the user <QUERY> along with the <CHAT_LOG> to create the answer. Always end with instructions for the user's next step."
#                 answer = questionAndAnswer(
#                     query, user_id, chat_dict, purpose, botHeader
#                 )
#                 update_state(user_id, "Neutral")
#                 insert_chat(
#                     now, user_id, workflow, "System", "Current state changed to neutral"
#                 )
#             except Exception as e:
#                 answer = "Oops, it seems there's been a hiccup. Please try again!"
#                 update_state(user_id, "Neutral")
#                 insert_chat(
#                     now, user_id, workflow, "System", "Current state changed to neutral"
#                 )
#         addToMemory = insert_chat(now, user_id, workflow, "Assistant", answer)
#         return answer
#     except Exception as e:
#         print(e)
#         answer = "Oops, it seems there's been a hiccup. Please try again!"
#         update_state(user_id, "Neutral")
#         insert_chat(
#             now, user_id, workflow, "System", "Current state changed to neutral"
#         )
