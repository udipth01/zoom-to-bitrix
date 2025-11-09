import requests
import csv

# ✅ Replace with your valid Zoom bearer token
ZOOM_BEARER_TOKEN = "eyJzdiI6IjAwMDAwMiIsImFsZyI6IkhTNTEyIiwidiI6IjIuMCIsImtpZCI6ImRjMTM5YTI2LTZhMjEtNDMxZC1hNTQ4LThjMTExNTExNjhmMiJ9.eyJhdWQiOiJodHRwczovL29hdXRoLnpvb20udXMiLCJ1aWQiOiJadlYtQXB1elN6R2t4c2EtYVNzV0dRIiwidmVyIjoxMCwiYXVpZCI6IjQ4NTI2N2U2Njk0YTkyNTMyYzgxYmQ5N2FkNDAyNzZkZjg5ZjNhYWI1ZmZhNGJlZWQ2OTM0MjhmMmVjMTZjMzIiLCJuYmYiOjE3NjA0NDM1NDUsImNvZGUiOiI5YURtaU5ZR1NIU1lSTHh1RTF5RFlnV0lxUGJtaG5VdHYiLCJpc3MiOiJ6bTpjaWQ6RlNKZlNvV2tSQUNHMUE5aGN4Z0ptZyIsImdubyI6MCwiZXhwIjoxNzYwNDQ3MTQ1LCJ0eXBlIjozLCJpYXQiOjE3NjA0NDM1NDUsImFpZCI6IlJVc04yTDNhUzA2aS1YZnVxVUdCVWcifQ.jvVMfc7GGT_7v4QUstvwoIk506ipwCnOoUKtdXULFfm8CmsbvavIuPQpUoXLpm-INpXJgEUv5YJg2gy9Ff4GfQ"
meeting_id = "82079002963"

headers = {
    "Authorization": f"Bearer {ZOOM_BEARER_TOKEN}",
    "Content-Type": "application/json"
}

url = f"https://api.zoom.us/v2/report/meetings/{meeting_id}/polls"
response = requests.get(url, headers=headers)
print("Status:", response.status_code)

if response.status_code != 200:
    print("❌ Error fetching data:", response.text)
    exit()

data = response.json()

if "questions" not in data:
    print("⚠️ No poll data found")
    print(data)
    exit()

# ✅ Create CSV for clean export
with open("zoom_poll_responses.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["User Name", "Email", "Question", "Answer", "Date Time"])

    for participant in data["questions"]:
        name = participant.get("name", "Unknown")
        email = participant.get("email", "N/A")

        for q in participant.get("question_details", []):
            question = q.get("question", "")
            answer = q.get("answer", "")
            date_time = q.get("date_time", "")

            print(f"👤 {name} ({email})")
            print(f"   Q: {question}")
            print(f"   A: {answer}\n")

            writer.writerow([name, email, question, answer, date_time])

print("✅ Poll data exported to zoom_poll_responses.csv successfully.")
