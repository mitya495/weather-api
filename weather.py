import requests

API_KEY = "3MLUdwGGaZ2wuvy9O5NAAKZlEIfj0GEr"
LAT = 42.3478
LON = -71.0466

url = "https://api.tomorrow.io/v4/weather/forecast"
params = {
    "location": f"{LAT},{LON}",
    "apikey": API_KEY
}

response = requests.get(url, params=params)

print(response.status_code)
print(response.json())
