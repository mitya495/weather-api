from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, Railway!"}

@app.get("/weather")
def get_weather(city: str = "Moscow"):
    # Замените это место на реальную логику получения данных о погоде.
    return {"city": city, "weather": "sunny", "temperature": "25°C"}
