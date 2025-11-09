import requests
import urllib.parse

# Replace with your values
ZOOM_BEARER_TOKEN = "eyJzdiI6IjAwMDAwMiIsImFsZyI6IkhTNTEyIiwidiI6IjIuMCIsImtpZCI6ImVmNzI5Nzk4LTU2YjktNGM1My1iZGU2LWY0ZjFjZTcwNzEyZCJ9.eyJhdWQiOiJodHRwczovL29hdXRoLnpvb20udXMiLCJ1aWQiOiJadlYtQXB1elN6R2t4c2EtYVNzV0dRIiwidmVyIjoxMCwiYXVpZCI6IjQ4NTI2N2U2Njk0YTkyNTMyYzgxYmQ5N2FkNDAyNzZkZjg5ZjNhYWI1ZmZhNGJlZWQ2OTM0MjhmMmVjMTZjMzIiLCJuYmYiOjE3NjAyODIyNjEsImNvZGUiOiJFM3VkdHNHN1F6cUJmd21NLXZvZGZBZDVaS3JtSDNlNTciLCJpc3MiOiJ6bTpjaWQ6RlNKZlNvV2tSQUNHMUE5aGN4Z0ptZyIsImdubyI6MCwiZXhwIjoxNzYwMjg1ODYxLCJ0eXBlIjozLCJpYXQiOjE3NjAyODIyNjEsImFpZCI6IlJVc04yTDNhUzA2aS1YZnVxVUdCVWcifQ.kTtg3oOoentr6bkMer9jWipcEWFXtuOy1N2MmooEfTGF4uv4HrG72D6mLVYff4TJjfFcvc95VsswNJXNkAi2iQ"
USER_ID = "ZvV-ApuzSzGkxsa-aSsWGQ"

headers = {
    "Authorization": f"Bearer {ZOOM_BEARER_TOKEN}",
    "Content-Type": "application/json"
}

# Step 1: Get all past meetings
meetings = []
next_page_token = ""
while True:
    url = f"https://api.zoom.us/v2/users/{USER_ID}/meetings?type=past&page_size=30&next_page_token={next_page_token}"
    resp = requests.get(url, headers=headers).json()
    meetings.extend(resp.get("meetings", []))
    next_page_token = resp.get("next_page_token", "")
    if not next_page_token:
        break

print(f"Total past meetings fetched: {len(meetings)}")

# Step 2: Check polls via REPORT endpoint
for meeting in meetings:
    uuid = meeting["uuid"]
    topic = meeting["topic"]

    encoded_uuid = urllib.parse.quote(uuid, safe="")

    poll_url = f"https://api.zoom.us/v2/report/meetings/{encoded_uuid}/polls"
    poll_resp = requests.get(poll_url, headers=headers).json()

    if poll_resp.get("code") == 3001:
        print(f"Meeting '{topic}' → expired or no polls.")
    elif "questions" in poll_resp:
        print(f"✅ Meeting '{topic}' has poll responses:")
        for q in poll_resp["questions"]:
            for detail in q["question_details"]:
                print(f"   Q: {detail['question']} → A: {detail['answer']}")
    else:
        print(f"Meeting '{topic}' → no poll responses found.")