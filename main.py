import hmac
import hashlib
import base64
from fastapi import FastAPI, Request
import httpx
import logging
import os


app = FastAPI()

BITRIX_FORM_URL = "https://finideas.bitrix24.in/bitrix/services/main/ajax.php?action=crm.site.form.fill"
FORM_ID = "906"
SEC_CODE = "tzk3qe"

# Get this from Zoom App Marketplace → Feature → Event Subscriptions → Secret Token
ZOOM_SECRET_TOKEN = os.getenv("ZOOM_SECRET_TOKEN")

logging.basicConfig(level=logging.INFO)

@app.post("/zoom/webhook")
async def zoom_webhook(request: Request):
    data = await request.json()
    logging.info(f"Zoom Payload: {data}")

    # Step 1: Handle Zoom URL validation
    if data.get("event") == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]

        # Create HMAC-SHA256 using Zoom secret token
        hmac_obj = hmac.new(
            ZOOM_SECRET_TOKEN.encode(),
            plain_token.encode(),
            hashlib.sha256
        )
        encrypted_token = base64.b64encode(hmac_obj.digest()).decode()

        return {
            "plainToken": plain_token,
            "encryptedToken": encrypted_token
        }

    # Step 2: Meeting participant joined
    if data.get("event") == "meeting.participant_joined":
        participant = data.get("payload", {}).get("object", {}).get("participant", {})

        full_name = participant.get("user_name", "Unknown").split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        email = participant.get("email", "")
        phone = participant.get("phone_number", "")

        payload = {
            "id": FORM_ID,
            "sec": SEC_CODE,
            "lang": "en",
            "timeZoneOffset": -330,
            "values": {
                "LEAD_NAME": [first_name],
                "LEAD_LAST_NAME": [last_name],
                "LEAD_PHONE": [phone],
                "LEAD_EMAIL": [email]
            },
            "properties": {},
            "consents": {},
            "entities": [],
            "trace": {
                "url": "https://b24-fcy7lp.bitrix24.site/crm_form_cekqw/",
                "ref": "https://finideas.bitrix24.in/"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(BITRIX_FORM_URL, json=payload)

        return {"status": "submitted", "bitrix_response": response.json()}

    return {"status": "ignored"}
