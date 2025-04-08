import os
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import pytz

app = FastAPI()

TOMORROW_API_KEY = os.getenv("TOMORROW_API_KEY")

CITIES = {
    "Очаково-Матвеевское": {"lat": 55.6833, "lon": 37.4667},
    "Солнцево": {"lat": 55.6371, "lon": 37.3913},
    "Кузьминки": {"lat": 55.7000, "lon": 37.7667},
    "Текстильщики": {"lat": 55.7092, "lon": 37.7315},
    "Войковский": {"lat": 55.8167, "lon": 37.5000},
    "Багратионовский": {"lat": 55.7436, "lon": 37.4978},
    "Даниловский": {"lat": 55.7167, "lon": 37.6167},
}

@app.get("/")
def root():
    return {"message": "Привет, Railway!"}

@app.get("/weather/{city}")
def get_city_weather(city: str):
    if not TOMORROW_API_KEY:
        return JSONResponse(content={"error": "API ключ не найден"}, status_code=500)
    
    if city not in CITIES:
        return JSONResponse(content={"error": "Город не найден"}, status_code=404)
    
    lat, lon = CITIES[city]["lat"], CITIES[city]["lon"]
    url = f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}&apikey={TOMORROW_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        formatted_data = format_weather_data(city, data)
        return formatted_data
    except requests.RequestException as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

def format_weather_data(city: str, data: dict) -> dict:
    weather_code_map = {
        1000: "Ясно", 1001: "Облачно", 1100: "Переменная облачность", 1101: "Пасмурно",
        1102: "Туман", 4000: "Небольшой дождь", 4001: "Умеренный дождь", 4200: "Сильный дождь",
        4201: "Ледяной дождь", 5000: "Небольшой снег", 5001: "Сильный снег", 5100: "Мокрый снег",
        8000: "Гроза",
    }

    # Временная зона Москвы
    moscow_tz = pytz.timezone("Europe/Moscow")
    now_utc = datetime.now(pytz.utc)

    # Данные из API
    current = data.get("timelines", {}).get("minutely", [{}])[0].get("values", {})
    hourly = data.get("timelines", {}).get("hourly", [])
    daily = data.get("timelines", {}).get("daily", [])

    # Если hourly пустой, используем minutely, но предупреждаем
    if not hourly and len(data.get("timelines", {}).get("minutely", [])) > 0:
        hourly = data.get("timelines", {}).get("minutely", [])[:26]  # Ограничиваем до 26

    # Текущие данные
    weather_code = current.get("weatherCode", 1000)
    wind_dir_short = direction_to_short(current.get("windDirection", 0))

    result = {
        "name": city,
        "temperature": f"{int(current.get('temperature', 0))}°",
        "feels_like": f"{int(current.get('temperatureApparent', 0))}°",
        "weather_condition": weather_code_map.get(weather_code, "Неизвестно"),
        "wind_speed": f"{current.get('windSpeed', 0):.1f} м/с, {wind_dir_short}",
        "pressure": str(int(current.get("pressureSurfaceLevel", 0) * 0.750062)),
        "humidity": f"{int(current.get('humidity', 0))}%",
        "warnings": "Нет предупреждений" if "alerts" not in data else "Жёлтое предупреждение о погоде",
        "air_quality": "0",
        "visibility": str(int(current.get("visibility", 10))),
        "uf_index": str(current.get("uvIndex", 0)),
        "moon": "Р 0,5 Восход: 13:14 Закат: 09:13",  # Пока статично
        "data": "Шаблон",
        "sunrise": daily[0].get("values", {}).get("sunriseTime", "06:00")[11:16],  # HH:MM
        "sunset": daily[0].get("values", {}).get("sunsetTime", "18:00")[11:16],   # HH:MM
    }

    # Дневной прогноз (5 дней)
    for i, day in enumerate(daily[:5], 1):
        day_values = day.get("values", {})
        weather_code_day = day_values.get("weatherCode", 1000)
        day_date = datetime.fromisoformat(day.get("time").replace("Z", "+00:00")).astimezone(moscow_tz)
        result[f"condition_day_day{i}"] = weather_code_map.get(weather_code_day, "Неизвестно")
        result[f"condition_night_day{i}"] = weather_code_map.get(weather_code_day, "Неизвестно")
        result[f"temperature_day_day{i}"] = f"{int(day_values.get('temperatureMax', 0))}°"
        result[f"temperature_night_day{i}"] = f"{int(day_values.get('temperatureMin', 0))}°"
        if i > 2:  # Дни недели для 3, 4, 5
            result[f"day{i}"] = day_date.strftime("%a")[:2]

    # Почасовой прогноз (26 часов)
    for i, hour in enumerate(hourly[:26]):
        hour_values = hour.get("values", {})
        hour_time_utc = datetime.fromisoformat(hour.get("time").replace("Z", "+00:00"))
        hour_time_moscow = hour_time_utc.astimezone(moscow_tz)
        hour_str = "Сейчас" if i == 0 else hour_time_moscow.strftime("%H:%M")
        if hour_str == result["sunrise"]: hour_str = "Восход"
        if hour_str == result["sunset"]: hour_str = "Закат"
        weather_code_hour = hour_values.get("weatherCode", 1000)
        wind_dir_short = direction_to_short(hour_values.get("windDirection", 0))

        result[f"temperature_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('temperature', 0))}°"
        result[f"time_hour_{'now' if i == 0 else i}"] = hour_str
        result[f"wind_hour_{'now' if i == 0 else i}"] = f"{hour_values.get('windSpeed', 0):.1f} м/с, {wind_dir_short}"
        result[f"rain_prob_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('precipitationProbability', 0))}%"
        result[f"pressure_hour_{'now' if i == 0 else i}"] = str(int(hour_values.get('pressureSurfaceLevel', 0) * 0.750062))
        result[f"uf_index_hour_{'now' if i == 0 else i}"] = str(hour_values.get("uvIndex", 0))
        result[f"humidity_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('humidity', 0))}%"
        result[f"condition_hour_{'now' if i == 0 else i}"] = weather_code_map.get(weather_code_hour, "Неизвестно")

    return result

def direction_to_short(degrees: float) -> str:
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(degrees / 45) % 8
    return directions[index]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=port)