from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
import os
import redis
from celery import Celery

app = FastAPI() # creates instance of FastAPI
load_dotenv()

redisUrl = ('redis-11349.c267.us-east-1-4.ec2.redns.redis-cloud.com:11349')

# creates instance of Celery 
celery = Celery(
    "tasks",
    broker=redisUrl,
    backend=redisUrl
)

# Celery configuration
celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Load environment variables
redis_key = 'A32n8yr7fseopvl5oet8nat4suov54r7oikqreghj7wc2xm949u'
client = OpenAI(api_key='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')

# Connect to Redis via Heroku-Redis add-on
r = redis.from_url('redis://localhost:6379/0')

# Middleware to allow CORS connection from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://resume-builder-frontend-nine.vercel.app/resume",
        "https://resume-builder-frontend-nine.vercel.app",
        "http://localhost:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define the request body for the chat endpoint
class MessageRequest(BaseModel):
    message: str

# Create endpoint for API call to OpenAI and run it as a Celery task
@celery.task(name="main.process_message")
def process_message(request_message: str):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are going to help with resume suggestions"},
                {"role": "user", "content": request_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error occurred during processing of message: {e}")
        return {"error": str(e)}

# Create endpoint for chat API
@app.post("/chat")
def chat(message: MessageRequest):
    try:
        task = process_message.delay(message.message) # Use .delay() to run the task asynchronously
        return {"task_id": task.id}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error with OpenAI API")

# Create endpoint to get the result of the chat API for state logging
@app.get("/result/{task_id}")
def get_result(task_id: str):
    result = celery.AsyncResult(task_id)  # Get the result of the task
    print(f"Task ID: {task_id}, Status: {result.state}")
    if result.state == 'PENDING':
        return {"status": result.state}
    elif result.state == 'FAILURE':
        print(f"Task Failed: {result.info}")
        return {"status": result.state, "error": str(result.info)}
    else:
        print(f"Task Completed: {result.result}")
        return {"status": result.state, "result": result.result}

@app.get("/")
async def root():
    return {"message": "testing access"}

