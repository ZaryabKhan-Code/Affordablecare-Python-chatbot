import openai
import numpy as np
import pandas as pd
import requests
import pinecone

pinecone.init(
    api_key="7be192e0-b2fc-4ea7-8950-31ce6927c66f", environment="us-east1-gcp"
)
index_name = "health-insurance"
index = pinecone.Index(index_name)

EMBEDDING_MODEL = "text-embedding-ada-002"
start_chat_log = ""

df = pd.read_csv("acaContentOnly.csv", encoding="unicode_escape")
dfQnA = pd.read_csv("qnaModelAnswers.csv", encoding="Windows-1252")


def get_embedding(text: str, model: str = EMBEDDING_MODEL) -> list[float]:
    max_retries = 4
    retry_count = 0

    while retry_count < max_retries:
        try:
            result = openai.Embedding.create(model=model, input=text)
            return result["data"][0]["embedding"]
        except:
            retry_count += 1

            # Sleep with exponential backoff
            sleep_duration = 2**retry_count
            sleep(sleep_duration)


def load_embeddings(fname: str) -> dict:
    """
    Read the document embeddings and their keys from a CSV.

    fname is the path to a CSV with exactly these named columns:
        "0", "1", ... up to the length of the embedding vectors.
    """
    embeddingsDF = pd.read_csv(fname, header=0)
    # Get column names for embedding dimensions
    embeddings_columns = embeddingsDF.columns

    # Create dictionary with column names as keys
    embeddings_dict = {}
    for col in embeddings_columns:
        embeddings_dict[col] = list(embeddingsDF[col])

    return embeddings_dict


qna_embeddings = load_embeddings("qnaModelEmbeddings.csv")


def vector_similarity(x: list[float], y: list[float]) -> float:
    """
    Returns the similarity between two vectors.

    Because OpenAI Embeddings are normalized to length 1, the cosine similarity is the same as the dot product.
    """
    #    print(len(np.array(x)))
    #    print(len(np.array(y)))
    return np.dot(np.array(x), np.array(y))


def order_document_sections_by_query_similarity_pinecone(
    query: str,
) -> list[(float, (str))]:
    """
    Find the query embedding for the supplied query, and compare it against all of the pre-calculated document embeddings
    to find the most relevant sections.

    Return the list of document sections, sorted by relevance in descending order.
    """

    xq = get_embedding(query)

    res = index.query(xq, top_k=2, include_metadata=True, filter={"type": "ACA"})

    return res


def order_document_sections_by_query_similarity(
    query: str, contexts: dict[(str), np.array]
) -> list[(float, (str))]:
    """
    Find the query embedding for the supplied query, and compare it against all of the pre-calculated document embeddings
    to find the most relevant sections.

    Return the list of document sections, sorted by relevance in descending order.
    """
    query_embedding = get_embedding(query)

    document_similarities = sorted(
        [
            (vector_similarity(query_embedding, doc_embedding), doc_index)
            for doc_index, doc_embedding in contexts.items()
        ],
        reverse=True,
    )

    return document_similarities


def construct_prompt(
    question: str, aChatLog: str, botHeader: str, contentHeader: str, df: pd.DataFrame
) -> dict:
    """
    Fetch relevant
    """
    most_relevant_document_sections = (
        order_document_sections_by_query_similarity_pinecone(question)
    )
    #    print(most_relevant_document_sections)
    matches = most_relevant_document_sections["matches"]
    ids = [match["id"] for match in matches]
    matched_rows = df[df["Identifier"].isin(ids)]
    # Extract the text from the matched rows
    matched_text = list(matched_rows["Text"])
    document_section1 = matched_text[0]
    document_section2 = matched_text[1]

    thePrompt = [{"role": "system", "content": botHeader}]

    userPrompt = (
        contentHeader
        + "\n\nContext:\n"
        + "".join(document_section1)
        + "".join(document_section2)
        + "".join(aChatLog)
        + "\n\n Q: "
        + question
        + "\n A:"
    )

    thePrompt.append({"role": "user", "content": userPrompt})

    return thePrompt


def qna_model_response(
    question: str, context_embeddings: dict, df: pd.DataFrame
) -> str:
    """
    Fetch relevant
    """
    most_relevant_document_sections = order_document_sections_by_query_similarity(
        question, context_embeddings
    )
    the_section = most_relevant_document_sections[0]
    section_index = int(the_section[1])
    aResponse = df.loc[section_index]
    theResponse = aResponse[0]
    print(type(theResponse))
    print(theResponse)
    print(the_section[0])

    if (the_section[0]) < 0.9:
        theResponse = "Nope"

    return theResponse


def construct_flow_prompt(aChatLog: str, botHeader: str, contentHeader: str) -> dict:
    thePrompt = [{"role": "system", "content": botHeader}]

    userPrompt = contentHeader + "\n\nContext:\n" + "".join(aChatLog) + "\n\n"

    thePrompt.append({"role": "user", "content": userPrompt})

    return thePrompt


def getName(userAnswer, getNameHeader, softSalesAsk3):
    #    print(question)

    message = (
        "You are a precise virtual assistant. Please follow the following instructions precisely. Extract the name from the following phrase: "
        + userAnswer
        + "Please return the name only.  A sentence is NOT acceptable.  Just the name.  If no name if found, say No name given."
    )
    messages = [{"role": "system", "content": message}]

    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    aResponse = response["choices"][0]["message"]
    theResponse = aResponse["content"]

    # print(type(theResponse))
    # print(theResponse)

    if "name" in theResponse:
        message = (
            getNameHeader
            + " Please tell me the phrase only.  No extra words. Remove outside quotation marks."
        )
        messages = [{"role": "system", "content": message}]

        response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

        anAnswer = response["choices"][0]["message"]
        answer = anAnswer["content"]
    else:
        answer = "Hi " + theResponse + ". Nice to meet you! " + softSalesAsk3
    #    answer = response.choices[0].text
    #    print(answer)
    return answer, theResponse


def confirmPurpose(userAnswer, confirmPurposeHeader, softSalesAsk):
    print(userAnswer)
    message = (
        "You are a virtual assistant. The user has just given this response. "
        + userAnswer
        + ". Please extract the sentiment of the user.  If the sentiment is positive tell me 'yes'.  Also, if the user's response was 'ok', 'indeed', 'yup', 'love to', 'sure', or 'I am' , please tell me 'Yes'. Please tell me 'Not now' if the person is not interested or if their answer was not clear. No extra words please."
    )
    messages = [{"role": "system", "content": message}]

    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    aResponse = response["choices"][0]["message"]
    theResponse = aResponse["content"]

    if "Not now" in theResponse:
        message = (
            confirmPurposeHeader
            + " Please tell me the phrase only.  No extra words. Remove outside quotation marks."
        )
        messages = [{"role": "system", "content": message}]

        response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

        anAnswer = response["choices"][0]["message"]
        answer = anAnswer["content"]

    else:
        answer = softSalesAsk
    #    answer = response.choices[0].text
    #    print(answer)
    return answer, theResponse


def confirmContent(userAnswer, confirmContentHeader, softSalesAsk2):
    print(userAnswer)
    message = (
        "You are a virtual assistant. The user has just given this response. "
        + userAnswer
        + ". Please extract the sentiment of the user.  If the sentiment is positive tell me 'yes'.  Also, if the user's response was 'ok', 'indeed', 'yup', 'love to', 'sure', or 'I am' , please tell me 'Yes'.  Please tell me 'Not a fit' if the person does not think the course is a good fit or if their answer was not clear. No extra words please."
    )
    messages = [{"role": "system", "content": message}]

    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    aResponse = response["choices"][0]["message"]
    theResponse = aResponse["content"]

    # print(type(theResponse))
    # print(theResponse)

    if "Not a fit" in theResponse:
        message = (
            confirmContentHeader
            + " Please tell me the phrase only.  No extra words. Remove outside quotation marks."
        )
        messages = [{"role": "system", "content": message}]

        response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

        anAnswer = response["choices"][0]["message"]
        answer = anAnswer["content"]

    else:
        answer = softSalesAsk2

    return answer, theResponse


def presentBill(userAnswer, confirmPresentationHeader, getEmailAsk):
    print(userAnswer)
    message = (
        "You are a virtual assistant. The user has just given this response when asked if all of that was clear. "
        + userAnswer
        + ". Please extract the sentiment of the user.  If the sentiment is positive tell me 'yes'.  Also, if the user's response was 'ok', 'indeed', 'yup', 'love to', 'sure', or 'I am' , please tell me 'Yes'.  Please tell me 'Not ready' if the person did not feel all of that was clear. No extra words please."
    )
    messages = [{"role": "system", "content": message}]

    response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

    aResponse = response["choices"][0]["message"]
    theResponse = aResponse["content"]

    # print(type(theResponse))
    # print(theResponse)

    if "Not ready" in theResponse:
        message = (
            confirmPresentationHeader
            + " Please tell me the phrase only.  No extra words. Remove outside quotation marks."
        )
        messages = [{"role": "system", "content": message}]

        response = openai.ChatCompletion.create(model="gpt-4", messages=messages)

        anAnswer = response["choices"][0]["message"]
        answer = anAnswer["content"]

    else:
        answer = getEmailAsk
    #    answer = response.choices[0].text
    #    print(answer)
    return answer, theResponse


def signUp(userAnswer, getEmailHeader):
    print(userAnswer)
    message = (
        "You are a precise virtual assistant. Please follow the following instructions precisely. Extract the email address from the following phrase:  "
        + userAnswer
        + ". It must be in a format for a functional email. Please return the email address only.  A sentence is NOT acceptable.  Just the email address.  If no email address if found, say No email address given."
    )
    messages = [{"role": "system", "content": message}]

    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)

    aResponse = response["choices"][0]["message"]
    theResponse = aResponse["content"]

    if "address" in theResponse:
        message = (
            getEmailHeader
            + " Please tell me the phrase only.  No extra words. Remove outside quotation marks."
        )
        messages = {"role": "system", "content": message}

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", messages=messages
        )

        anAnswer = response["choices"][0]["message"]
        answer = anAnswer["content"]

    else:
        query = {"api_key": "BkFlzwtGASkTgV-Q19R7AA", "email": theResponse}
        url = "https://api.convertkit.com/v3/forms/4924284/subscribe"
        ckResponse = requests.post(url, params=query)
        print(ckResponse)
        answer = (
            "Awesome. You will get a confirmation email in your inbox shortly. Thanks!"
        )
    return answer, theResponse


def salesAsk(question, chat_log, theBotHeader, theContentHeader):
    theAnswer = qna_model_response(question, qna_embeddings, dfQnA)
    thePrompt = question
    if theAnswer == "Nope":
        if chat_log == None:
            chat_log = ""
        thePrompt = construct_prompt(
            question, chat_log, theBotHeader, theContentHeader, df
        )
        print("QnA")
        print(thePrompt)
        response = None
        try:
            response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)
        except:
            pass
        if response:
            aResponse = response["choices"][0]["message"]
            answer = aResponse["content"]
        else:
            answer = (
                "Whoops. The server is overloaded. Give it a few seconds and try again."
            )

    else:
        answer = theAnswer

    return answer, thePrompt


def createFlow(chat_log, theBotHeader, theContentHeader):
    # print(chat_log, theBotHeader, theContentHeader)
    thePrompt = construct_flow_prompt(chat_log, theBotHeader, theContentHeader)
    print("flow prompt")
    print(thePrompt)
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", messages=thePrompt, max_tokens=90
    )
    #    response = openai.ChatCompletion.create(model="gpt-4", messages=thePrompt)

    aResponse = response["choices"][0]["message"]
    answer = aResponse["content"]

    return answer, thePrompt
