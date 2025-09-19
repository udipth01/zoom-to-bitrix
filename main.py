from fastapi import FastAPI, Request
import httpx

app = FastAPI()

BITRIX_FORM_URL = "https://finideas.bitrix24.in/bitrix/services/main/ajax.php?action=crm.site.form.fill"

@app.post("/zoom/webhook")
async def zoom_webhook(request: Request):
    data = await request.json()

    if data.get("event") == "meeting.participant_joined":
        participant = data.get("payload", {}).get("object", {}).get("participant", {})

        full_name = participant.get("user_name", "Unknown").split(" ", 1)
        first_name = full_name[0]
        last_name = full_name[1] if len(full_name) > 1 else ""

        email = participant.get("email", "")
        phone = participant.get("phone_number", "")

        # Mimic browser form submission
        payload = {
            "id": "906",            # form id
            "sec": "tzk3qe",        # security key
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
