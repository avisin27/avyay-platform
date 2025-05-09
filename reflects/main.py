from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def home():
    return {"msg": "Avyay Reflects API is live!"}
