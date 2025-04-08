import os
import requests
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from typing import Optional

app = FastAPI()

TOMORROW_API_KEY = os.getenv("TOMORROW_API_KEY")

# Список городов с координатами (можно расширить)
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

# Эндпоинт для получения погоды по конкретному городу
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
        # Преобразование данных в твой формат
        formatted_data = format_weather_data(city, data)
        return formatted_data
    except requests.RequestException as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

# Функция для форматирования данных Tomorrow.io в твой формат
def format_weather_data(city: str, data: dict) -> dict:
    # Получаем текущие данные (minutely или hourly)
    current = data.get("timelines", {}).get("hourly", [{}])[0].get("values", {})
    daily = data.get("timelines", {}).get("daily", [])
    hourly = data.get("timelines", {}).get("hourly", [])

    # Маппинг погодных кодов Tomorrow.io на твои условия
    weather_code_map = {
        1000: "Ясно",
        1100: "Облачно",
        1101: "Пасмурно",
        1102: "Туман",
        4000: "Небольшой дождь",
        4001: "Умеренный дождь",
        4200: "Сильный дождь",
        4201: "Ледяной дождь",
        5000: "Небольшой снег",
        5001: "Сильный снег",
        5100: "Мокрый снег",
        8000: "Гроза",
        # Добавь другие коды по документации Tomorrow.io
    }

    # Текущие данные
    weather_code = current.get("weatherCode", 1000)
    wind_direction = current.get("windDirection", 0)
    wind_dir_short = direction_to_short(wind_direction)

    # Форматируем текущие данные
    result = {
        "name": city,
        "temperature": f"{int(current.get('temperature', 0))}°",
        "feels_like": f"{int(current.get('temperatureApparent', 0))}°",
        "weather_condition": weather_code_map.get(weather_code, "Неизвестно"),
        "wind_speed": f"{current.get('windSpeed', 0)} м/с, {wind_dir_short}",
        "pressure": str(int(current.get("pressureSurfaceLevel", 0) * 0.750062)),  # Перевод из hPa в мм рт. ст.
        "humidity": f"{int(current.get('humidity', 0))}%",
        "warnings": "Жёлтое предупреждение о погоде",  # Tomorrow.io может возвращать alerts
        "air_quality": str(current.get("airQualityIndex", 0)),  # Проверить, есть ли в API
        "visibility": str(int(current.get("visibility", 10))),
        "uf_index": str(current.get("uvIndex", 0)),
        "moon": "Р 0,5 Восход: 13:14 Закат: 09:13",  # Пока статично, можно добавить API
        "data": "Шаблон",
        "sunrise": daily[0].get("values", {}).get("sunriseTime", "Восход: 08:00")[-8:-3],
        "sunset": daily[0].get("values", {}).get("sunsetTime", "Закат: 17:00")[-8:-3],
    }

    # Дневные прогнозы (5 дней)
    for i, day in enumerate(daily[:5], 1):
        day_values = day.get("values", {})
        result[f"condition_day_day{i}"] = weather_code_map.get(day_values.get("weatherCode", 1000), "Неизвестно")
        result[f"condition_night_day{i}"] = weather_code_map.get(day_values.get("weatherCode", 1000), "Неизвестно")  # Ночь отдельно не даётся, можно улучшить
        result[f"temperature_day_day{i}"] = f"{int(day_values.get('temperatureMax', 0))}°"
        result[f"temperature_night_day{i}"] = f"{int(day_values.get('temperatureMin', 0))}°"

    # Почасовые прогнозы (26 часов)
    for i, hour in enumerate(hourly[:27]):
        hour_values = hour.get("values", {})
        hour_time = hour.get("time", "")[-8:-3] if i > 0 else "Сейчас"
        if "sunrise" in result and hour_time == result["sunrise"]: hour_time = "Восход"
        if "sunset" in result and hour_time == result["sunset"]: hour_time = "Закат"
        result[f"temperature_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('temperature', 0))}°"
        result[f"time_hour_{'now' if i == 0 else i}"] = hour_time
        result[f"wind_hour_{'now' if i == 0 else i}"] = f"{hour_values.get('windSpeed', 0)} м/с, {direction_to_short(hour_values.get('windDirection', 0))}"
        result[f"rain_prob_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('precipitationProbability', 0))}%"
        result[f"pressure_hour_{'now' if i == 0 else i}"] = str(int(hour_values.get('pressureSurfaceLevel', 0) * 0.750062))
        result[f"uf_index_hour_{'now' if i == 0 else i}"] = str(hour_values.get("uvIndex", 0))
        result[f"humidity_hour_{'now' if i == 0 else i}"] = f"{int(hour_values.get('humidity', 0))}%"
        result[f"condition_hour_{'now' if i == 0 else i}"] = weather_code_map.get(hour_values.get("weatherCode", 1000), "Неизвестно")

    # Дни недели (можно улучшить с реальными датами)
    result["day3"] = "Ср"
    result["day4"] = "Чт"
    result["day5"] = "Пт"

    return result

# Вспомогательная функция для направления ветра
def direction_to_short(degrees: float) -> str:
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(degrees / 45) % 8
    return directions[index]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=port)