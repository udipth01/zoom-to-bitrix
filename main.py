import os
import hmac
import hashlib
import logging
from fastapi import FastAPI, Request, Header, HTTPException
import httpx
import time

app = FastAPI()

# ------------------- CONFIG -------------------
BITRIX_FORM_URL = "https://finideas.bitrix24.in/bitrix/services/main/ajax.php?action=crm.site.form.fill"
FORM_ID = "906"
SEC_CODE = "tzk3qe"
TIMEZONE_OFFSET = -330  # IST

# Secret Token from Zoom App → Event Subscriptions → Secret Token
ZOOM_SECRET_TOKEN = os.getenv("ZOOM_SECRET_TOKEN")

logging.basicConfig(level=logging.INFO)

# ------------------- ROUTE -------------------
@app.post("/zoom/webhook")
async def zoom_webhook(
    request: Request,
    x_zm_signature: str = Header(None),
    x_zm_request_timestamp: str = Header(None)
):
    body_bytes = await request.body()
    data = await request.json()
    logging.info(f"Zoom Payload: {data}")

    # ------------------- VERIFY SIGNATURE -------------------
    if not x_zm_signature or not x_zm_request_timestamp:
        raise HTTPException(status_code=400, detail="Missing Zoom headers")

    # Prevent replay attacks: timestamp should be within 5 mins
    current_ts = int(time.time())
    zoom_ts = int(x_zm_request_timestamp)
    if abs(current_ts - zoom_ts) > 300:
        raise HTTPException(status_code=400, detail="Zoom request timestamp too old")

    message = f"v0:{x_zm_request_timestamp}:{body_bytes.decode()}"
    computed_hmac = hmac.new(
        ZOOM_SECRET_TOKEN.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    computed_signature = f"v0={computed_hmac}"

    if computed_signature != x_zm_signature:
        raise HTTPException(status_code=401, detail="Invalid Zoom signature")

    # ------------------- STEP 1: URL Validation -------------------
    if data.get("event") == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]
        encrypted_token = hmac.new(
            ZOOM_SECRET_TOKEN.encode(),
            plain_token.encode(),
            hashlib.sha256
        ).hexdigest()  # Use hex instead of base64
        logging.info(f"URL Validation -> plainToken: {plain_token}, encryptedToken: {encrypted_token}")
        return {"plainToken": plain_token, "encryptedToken": encrypted_token}

    # ------------------- STEP 2: Participant Joined -------------------
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
            "timeZoneOffset": TIMEZONE_OFFSET,
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

        logging.info(f"Bitrix Response: {response.text}")
        return {"status": "submitted", "bitrix_response": response.json()}

    return {"status": "ignored"}
