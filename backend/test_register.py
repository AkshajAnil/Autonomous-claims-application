import requests

print("Testing register endpoint...")
try:
    response = requests.post("http://localhost:8000/register", json={"username": "testuser1", "password": "password123"})
    print("Status code:", response.status_code)
    print("Response text:", response.text)
except Exception as e:
    print("Exception:", e)
