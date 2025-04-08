import os
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

TOMORROW_API_KEY = os.getenv("TOMORROW_API_KEY")
LOCATION = "42.3478,-71.0466"  # Пример: Бостон. Можно будет менять.

@app.get("/")
def root():
    return {"message": "Привет, Railway!"}

@app.get("/weather")
def get_weather():
    if not TOMORROW_API_KEY:
        return JSONResponse(content={"error": "API ключ не найден"}, status_code=500)

    url = f"https://api.tomorrow.io/v4/weather/forecast?location={LOCATION}&apikey={TOMORROW_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data  # Или можно фильтровать под нужные данные
    except requests.RequestException as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=port)
