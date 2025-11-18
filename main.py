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

# ---------------- CONFIG ----------------
BITRIX_DOMAIN = "https://finideas.bitrix24.in"
BITRIX_USER_TOKEN = os.getenv("BITRIX_USER_TOKEN")  # You must set your Bitrix webhook token

BITRIX_FORM_URL = f"{BITRIX_DOMAIN}/bitrix/services/main/ajax.php?action=crm.site.form.fill"
BITRIX_LEAD_SEARCH_URL = f"{BITRIX_DOMAIN}/rest/24/{BITRIX_USER_TOKEN}/crm.lead.list"

FORM_ID = 906
SEC_CODE = "tzk3qe"
TIMEZONE_OFFSET = -330  # IST
ZOOM_SECRET_TOKEN = os.getenv("ZOOM_SECRET_TOKEN")

logging.basicConfig(level=logging.INFO)


# ---------------- MAIN ROUTE ----------------
@app.post("/zoom/webhook")
async def zoom_webhook(
    request: Request,
    x_zm_signature: str = Header(None),
    x_zm_request_timestamp: str = Header(None)
):
    raw_body = await request.body()
    try:
        data = json.loads(raw_body.decode())
    except Exception:
        logging.exception("Invalid JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    logging.info("Zoom Payload:\n%s", json.dumps(data, indent=2))

    # ---------------- URL VALIDATION ----------------
    if data.get("event") == "endpoint.url_validation":
        plain_token = data["payload"]["plainToken"]
        encrypted_token = hmac.new(
            ZOOM_SECRET_TOKEN.encode(),
            plain_token.encode(),
            hashlib.sha256
        ).hexdigest()
        logging.info("URL Validation successful")
        return {"plainToken": plain_token, "encryptedToken": encrypted_token}

    # ---------------- VERIFY SIGNATURE ----------------
    if not x_zm_signature or not x_zm_request_timestamp:
        raise HTTPException(status_code=400, detail="Missing Zoom headers")

    now = int(time.time())
    zoom_ts = int(x_zm_request_timestamp)
    if abs(now - zoom_ts) > 300:
        raise HTTPException(status_code=400, detail="Zoom timestamp too old")

    msg = f"v0:{x_zm_request_timestamp}:{raw_body.decode()}"
    expected_sig = "v0=" + hmac.new(
        ZOOM_SECRET_TOKEN.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    if expected_sig != x_zm_signature:
        logging.warning("Signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid Zoom signature")

    # ---------------- PARTICIPANT JOINED ----------------
    if data.get("event") == "meeting.participant_joined":
        participant = data["payload"]["object"]["participant"]
        name_parts = participant.get("user_name", "Unknown").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        email = participant.get("email")
        phone = participant.get("phone_number")

        # if not email:
        #     logging.warning("No email in Zoom event; cannot search existing lead.")
        #     email = "unknown@zoom.com"

        # -------- STEP 1: SEARCH EXISTING LEAD --------
        lead_id = None
        lead_title = None

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                params = {
                    "filter[=EMAIL]": email,
                    "select[]": ["ID", "TITLE", "SOURCE_ID", "SOURCE_DESCRIPTION"],
                    "order[DATE_CREATE]": "ASC"
                }
                r = await client.get(BITRIX_LEAD_SEARCH_URL, params=params)
                result = r.json().get("result", [])
                if result:
                    first_lead = result[0]
                    lead_id = first_lead.get("ID")
                    lead_title = first_lead.get("TITLE")
                    logging.info(f"Found existing lead: ID={lead_id}, Title={lead_title}")
                else:
                    logging.info("No existing lead found for email %s", email)
        except Exception as e:
            logging.exception("Error fetching lead from Bitrix")

        # -------- STEP 2: BUILD FORM PAYLOAD --------
        bitrix_payload = {
            "id": str(FORM_ID),
            "sec": SEC_CODE,
            "lang": "en",
            "timeZoneOffset": str(TIMEZONE_OFFSET),
            "values": json.dumps({
                "LEAD_NAME": [first_name],
                "LEAD_LAST_NAME": [last_name],
                "LEAD_PHONE": [phone],
                "LEAD_EMAIL": [email],
                "LEAD_UF_CRM_1638592220": [lead_id or ""],
                "LEAD_UF_CRM_1731490501": [lead_title or ""]
            }),
            "properties": "{}",
            "consents": "{}",
            "entities": "[]",
            "trace": json.dumps({
                "url": "https://b24-fcy7lp.bitrix24.site/crm_form_cekqw/",
                "ref": "https://finideas.bitrix24.in/"
            })
        }

        logging.info("Payload sent to Bitrix:\n%s", json.dumps(bitrix_payload, indent=2))

        # -------- STEP 3: SUBMIT TO FORM --------
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(BITRIX_FORM_URL, data=bitrix_payload)
            logging.info("Bitrix Response [%s]: %s", response.status_code, response.text)
        except Exception:
            logging.exception("Failed to send to Bitrix")
            raise HTTPException(status_code=502, detail="Error calling Bitrix")

        return {"status": "submitted", "lead_id": lead_id, "lead_title": lead_title}

    return {"status": "ignored"}
