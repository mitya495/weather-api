import os
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import pytz
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("weather_api.log"),  # Логи в файл
        logging.StreamHandler()  # Логи в консоль (для Railway)
    ]
)
logger = logging.getLogger(__name__)

# Создаем приложение FastAPI
app = FastAPI()

# Список районов Москвы с их координатами
CITIES = {
    "Очаково-Матвеевское": {"lat": 55.6833, "lon": 37.4667},
    "Солнцево": {"lat": 55.6371, "lon": 37.3913},
    "Кузьминки": {"lat": 55.7000, "lon": 37.7667},
    "Текстильщики": {"lat": 55.7092, "lon": 37.7315},
    "Войковский": {"lat": 55.8167, "lon": 37.5000},
    "Багратионовский": {"lat": 55.7436, "lon": 37.4978},
    "Даниловский": {"lat": 55.7167, "lon": 37.6167},
}

# Соответствие кодов погоды Tomorrow.io текстовым описаниям на русском
WEATHER_CODE_MAP = {
    1000: "Ясно",
    1001: "Облачно",
    1100: "Переменная облачность",
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
}

# Функция для преобразования градусов направления ветра в краткие обозначения
def direction_to_short(degrees: float) -> str:
    directions = ["С", "СВ", "В", "ЮВ", "Ю", "ЮЗ", "З", "СЗ"]
    index = round(degrees / 45) % 8
    return directions[index]

# Эндпоинт для получения погоды по району
@app.get("/weather/{city}")
def get_city_weather(city: str):
    """Получает погодные данные для указанного района."""
    if city not in CITIES:
        logger.error(f"Город не найден: {city}")
        raise HTTPException(status_code=404, detail="Город не найден")

    lat, lon = CITIES[city]["lat"], CITIES[city]["lon"]
    api_key = os.getenv("TOMORROW_API_KEY")
    if not api_key:
        logger.error("API ключ не найден в переменных окружения")
        raise HTTPException(status_code=500, detail="API ключ не найден")

    # Формируем запрос к API Tomorrow.io
    url = f"https://api.tomorrow.io/v4/weather/forecast?location={lat},{lon}&timesteps=1h,1d&apikey={api_key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        api_data = response.json()
        
        # Логируем полный ответ API
        logger.info(f"Ответ API для {city}: {api_data}")
        
        formatted_data = format_weather_data(city, api_data)
        return JSONResponse(content=formatted_data)
    except requests.RequestException as e:
        logger.error(f"Ошибка при запросе к API для {city}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при запросе к API: {str(e)}")

# Функция для форматирования данных в требуемый JSON
def format_weather_data(city: str, data: dict) -> dict:
    """Обрабатывает данные API и возвращает их в требуемом формате."""
    moscow_tz = pytz.timezone("Europe/Moscow")
    
    timelines = data.get("timelines", {})
    hourly = timelines.get("hourly", [])
    daily = timelines.get("daily", [])

    if not hourly or not daily:
        logger.error(f"Отсутствуют необходимые данные в ответе API для {city}: hourly={bool(hourly)}, daily={bool(daily)}")
        raise HTTPException(status_code=500, detail="Отсутствуют необходимые данные в ответе API")

    # Текущие погодные данные из первого элемента почасового прогноза
    current = hourly[0].get("values", {})

    result = {
        "name": city,
        "temperature": f"{int(current.get('temperature', 0))}°",
        "feels_like": f"{int(current.get('temperatureApparent', 0))}°",
        "weather_condition": WEATHER_CODE_MAP.get(current.get("weatherCode", 1000), "Неизвестно"),
        "wind_speed": f"{current.get('windSpeed', 0):.1f} м/с, {direction_to_short(current.get('windDirection', 0))}",
        "pressure": str(int(current.get("pressureSurfaceLevel", 0) * 0.750062)) if current.get("pressureSurfaceLevel") else "0",
        "humidity": f"{int(current.get('humidity', 0))}%",
        "warnings": "Нет предупреждений" if "alerts" not in data else "Жёлтое предупреждение",
        "air_quality": "0",  # Замените на реальные данные, если доступны
        "visibility": str(int(current.get("visibility", 10))),
        "uf_index": str(current.get("uvIndex", 0)),
        "moon": "Р 0,5 Восход: 13:14 Закат: 09:13",  # Замените на динамические данные, если доступны
        "data": "Шаблон",
    }

    # Восход и закат солнца с правильным преобразованием времени
    sunrise_utc = datetime.fromisoformat(daily[0]["values"]["sunriseTime"].replace("Z", "+00:00"))
    sunset_utc = datetime.fromisoformat(daily[0]["values"]["sunsetTime"].replace("Z", "+00:00"))
    result["sunrise"] = sunrise_utc.astimezone(moscow_tz).strftime("%H:%M")
    result["sunset"] = sunset_utc.astimezone(moscow_tz).strftime("%H:%M")

    # Дневной прогноз на 5 дней
    for i, day in enumerate(daily[:5], 1):
        values = day.get("values", {})
        result[f"condition_day_day{i}"] = WEATHER_CODE_MAP.get(values.get("weatherCodeMax", 1000), "Неизвестно")
        result[f"condition_night_day{i}"] = WEATHER_CODE_MAP.get(values.get("weatherCodeMin", 1000), "Неизвестно")
        result[f"temperature_day_day{i}"] = f"{int(values.get('temperatureMax', 0))}°"
        result[f"temperature_night_day{i}"] = f"{int(values.get('temperatureMin', 0))}°"
        if i > 2:
            day_date = datetime.fromisoformat(day["time"].replace("Z", "+00:00")).astimezone(moscow_tz)
            result[f"day{i}"] = day_date.strftime("%a")[:2]

    # Почасовой прогноз на 26 часов
    for i in range(26):
        if i < len(hourly):
            hour = hourly[i]
            values = hour.get("values", {})
            time_utc = datetime.fromisoformat(hour["time"].replace("Z", "+00:00"))
            time_moscow = time_utc.astimezone(moscow_tz)
            hour_str = "Сейчас" if i == 0 else time_moscow.strftime("%H:%M")
            weather_code = values.get("weatherCode", 1000)
        else:
            hour_str = "N/A"
            values = {}
            weather_code = 1000

        result[f"temperature_hour_{'now' if i == 0 else i}"] = f"{int(values.get('temperature', 0))}°"
        result[f"time_hour_{'now' if i == 0 else i}"] = hour_str
        result[f"wind_hour_{'now' if i == 0 else i}"] = f"{values.get('windSpeed', 0):.1f} м/с, {direction_to_short(values.get('windDirection', 0))}" if values else "N/A"
        result[f"rain_prob_hour_{'now' if i == 0 else i}"] = f"{int(values.get('precipitationProbability', 0))}%"
        result[f"pressure_hour_{'now' if i == 0 else i}"] = str(int(values.get('pressureSurfaceLevel', 0) * 0.750062)) if values.get('pressureSurfaceLevel') else "0"
        result[f"uf_index_hour_{'now' if i == 0 else i}"] = str(values.get("uvIndex", 0))
        result[f"humidity_hour_{'now' if i == 0 else i}"] = f"{int(values.get('humidity', 0))}%"
        result[f"condition_hour_{'now' if i == 0 else i}"] = WEATHER_CODE_MAP.get(weather_code, "Неизвестно")

    return result

# Запуск сервера
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))  # Railway использует переменную PORT
    import uvicorn
    logger.info(f"Запуск сервера на порту {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)