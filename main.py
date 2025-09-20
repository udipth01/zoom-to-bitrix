# main.py
import os
import hmac
import hashlib
import logging
import json
import time
from fastapi import FastAPI, Request, Header, HTTPException
import httpx

app = FastAPI()

# ------------------- CONFIG -------------------
BITRIX_FORM_URL = "https://finideas.bitrix24.in/bitrix/services/main/ajax.php?action=crm.site.form.fill"
FORM_ID = 906                  # integer
SEC_CODE = "tzk3qe"
TIMEZONE_OFFSET = -330         # IST

# Secret Token from Zoom App → Event Subscriptions → Secret Token
ZOOM_SECRET_TOKEN = os.getenv("ZOOM_SECRET_TOKEN")

logging.basicConfig(level=logging.INFO)

if not ZOOM_SECRET_TOKEN:
    logging.warning("ZOOM_SECRET_TOKEN is not set in environment. URL validation & signature checks will fail.")

# ------------------- ROUTE -------------------
@app.post("/zoom/webhook")
async def zoom_webhook(
    request: Request,
    x_zm_signature: str = Header(None),
    x_zm_request_timestamp: str = Header(None)
):
    # read raw body once
    body_bytes = await request.body()
    try:
        data = json.loads(body_bytes.decode())
    except Exception:
        logging.exception("Failed to parse JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logging.info("Zoom Payload:\n%s", json.dumps(data, indent=2))

    # ------------------- VERIFY SIGNATURE -------------------
    if not x_zm_signature or not x_zm_request_timestamp:
        raise HTTPException(status_code=400, detail="Missing Zoom headers")

    # Prevent replay attacks: timestamp should be within 5 mins
    current_ts = int(time.time())
    try:
        zoom_ts = int(x_zm_request_timestamp)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Zoom timestamp header")

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
        logging.warning("Signature mismatch. computed=%s header=%s", computed_signature, x_zm_signature)
        raise HTTPException(status_code=401, detail="Invalid Zoom signature")

    # ------------------- STEP 1: URL Validation -------------------
    if data.get("event") == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]
        encrypted_token = hmac.new(
            ZOOM_SECRET_TOKEN.encode(),
            plain_token.encode(),
            hashlib.sha256
        ).hexdigest()  # hex digest expected by Zoom
        logging.info("URL Validation -> plainToken: %s encryptedToken: %s", plain_token, encrypted_token)
        return {"plainToken": plain_token, "encryptedToken": encrypted_token}

    # ------------------- STEP 2: Participant Joined -------------------
    if data.get("event") == "meeting.participant_joined":
        participant = data.get("payload", {}).get("object", {}).get("participant", {})

        full_name = participant.get("user_name", "Unknown").split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        # Fallbacks if Zoom doesn't send these
        email = participant.get("email") 
        phone = participant.get("phone_number") 

        # Build form-data exactly like the curl you ran earlier
        bitrix_payload = {
            "id": str(FORM_ID),
            "sec": SEC_CODE,
            "lang": "en",
            "timeZoneOffset": str(TIMEZONE_OFFSET),
            "values": json.dumps({
                "LEAD_NAME": [first_name],
                "LEAD_LAST_NAME": [last_name],
                "LEAD_PHONE": [phone],
                "LEAD_EMAIL": [email]
            }),
            "properties": "{}",
            "consents": "{}",
            "entities": "[]",
            "trace": json.dumps({
                "url": "https://b24-fcy7lp.bitrix24.site/crm_form_cekqw/",
                "ref": "https://finideas.bitrix24.in/"
            })
        }

        logging.info("Payload sent to Bitrix (form-url-encoded):\n%s", json.dumps(bitrix_payload, indent=2))

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # send as form-data (application/x-www-form-urlencoded)
                response = await client.post(BITRIX_FORM_URL, data=bitrix_payload)
        except Exception as e:
            logging.exception("Error while calling Bitrix")
            raise HTTPException(status_code=502, detail="Failed to contact Bitrix")

        logging.info("Bitrix HTTP status: %s", response.status_code)
        logging.info("Bitrix Response body: %s", response.text)

        # Try parse JSON or return raw text
        try:
            bitrix_resp = response.json()
        except Exception:
            bitrix_resp = response.text

        return {"status": "submitted", "bitrix_response": bitrix_resp}

    return {"status": "ignored"}
