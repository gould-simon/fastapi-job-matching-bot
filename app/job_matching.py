import openai

def get_cv_embedding(cv_text):
    response = openai.Embedding.create(
        input=cv_text, model="text-embedding-ada-002"
    )
    return response["data"][0]["embedding"]
