import azure.functions as func
import logging
import json
from datetime import datetime, timezone
import asyncio
from daily import run_daily_task_for_user

from firebase_manager import FirebaseManager

from main import android_chat


app = func.FunctionApp()


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
}


@app.route(route="chat", auth_level=func.AuthLevel.FUNCTION)
def chat_handler(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handles POST requests to process a user's message via the chatbot.
    """
    logging.info('Chat handler function processed a request.')

    
    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=204, headers=CORS_HEADERS)

    try:
        try:
            req_body = req.get_json()
            email = req_body.get('email')
            message = req_body.get('message')
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON format."}),
                status_code=400, mimetype="application/json", headers=CORS_HEADERS
            )

        if not email or not message:
            return func.HttpResponse(
                json.dumps({"error": "Please provide 'email' and 'message'."}),
                status_code=400, mimetype="application/json", headers=CORS_HEADERS
            )

        
        
        chat_response = android_chat(user_prompt=message, user_email=email)


        response_data = {
            "message": chat_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return func.HttpResponse(
            json.dumps(response_data),
            mimetype="application/json",
            status_code=200,
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"An error occurred in chat_handler: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "An internal server error occurred."}),
            status_code=500, mimetype="application/json", headers=CORS_HEADERS
        )
        
        
        
@app.route(route="dailytask", auth_level=func.AuthLevel.FUNCTION)
def daily_task_handler(req: func.HttpRequest) -> func.HttpResponse:
    
    logging.info('Daily Task HTTP handler received a request.')

    if req.method == "OPTIONS":
        return func.HttpResponse("", status_code=204, headers=CORS_HEADERS)

    try:
        try:
            req_body = req.get_json()
            email = req_body.get('email')
        except ValueError:
            return func.HttpResponse(
                json.dumps({"error": "Invalid JSON format."}),
                status_code=400, mimetype="application/json", headers=CORS_HEADERS
            )

        if not email:
            return func.HttpResponse(
                json.dumps({"error": "Please provide an 'email' in the request body."}),
                status_code=400, mimetype="application/json", headers=CORS_HEADERS
            )
        
        
        # config = Config()
        # task_manager = DailyTaskManager(config)
        greeting, notification = run_daily_task_for_user(email)

        response_data = {
            "greeting": greeting,
            "notification": notification,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return func.HttpResponse(
            json.dumps(response_data),
            mimetype="application/json",
            status_code=200,
            headers=CORS_HEADERS
        )

    except Exception as e:
        logging.error(f"An error occurred in daily_task_handler: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"error": "An internal server error occurred."}),
            status_code=500, mimetype="application/json", headers=CORS_HEADERS
        )

@app.function_name(name="DailyTaskTimer")
@app.timer_trigger(schedule="0 0 */5 * * *",  
                   arg_name="timer",
                   run_on_startup=False)
def daily_task_timer(timer: func.TimerRequest) -> None:
    
    if timer.past_due:
        logging.info('The timer is past due!')

    logging.info('Daily Task Timer function is executing.')
    
    
    
    try:
        
        firebase_manager = FirebaseManager()
        
        all_user_emails = firebase_manager.get_all_user_emails()
        
        
        if not all_user_emails:
            logging.info("No users found in the database. Timer task finished.")
            return
        
        for email in all_user_emails:
            try:
                run_daily_task_for_user(email)
                logging.info(f"Daily task completed for {email}")
            except Exception as e:
                logging.error(f"Error processing daily task for {email}: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"The timer trigger failed with an exception: {e}", exc_info=True)