import sys
import requests
import write_temp as w
import time
def main():
    sunsetTime = 3600 #tiempo en segundos que estara la animacion de afternoon admira
    api_key = "4a24b604a50c1ab4681b757e8b89b21b" 
    city = "Barcelona"
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "es",
    }
    while (True):
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException:
            continue
        # --- Lógica por weather id ---
        # OpenWeather devuelve una lista "weather"; normalmente usamos el primer elemento.
        weather_id = None
        try:
            weather_id = data["weather"][0]["id"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError("Respuesta inesperada: falta weather[0].id")

        sunrise = data["sys"]["sunrise"]
        sunset = data["sys"]["sunset"]
        tiempoActual = int(time.time())
        # 3 IFs (rellena tú el contenido)
        if (tiempoActual > sunrise) and (tiempoActual < sunset): #De dia
            if weather_id < 800: #Tormenta/lluvia/llovizna
                w.writeValor("DL")
            elif  weather_id == 800: #Despejado
                w.writeValor("DD")
            else: #Nublado
                w.writeValor("DN")
        elif (tiempoActual > sunset) and (tiempoActual < sunset + sunsetTime):
            if weather_id < 800: #Tormenta/lluvia/llovizna
                w.writeValor("DL")
            elif  weather_id == 800: #Despejado
                w.writeValor("A")
            else: #Nublado
                w.writeValor("DN")
        else:
            if weather_id < 800: #Tormenta/lluvia/llovizna
                w.writeValor("NL")
            elif  weather_id == 800: #Despejado
                w.writeValor("ND")
            else: #Nublado
                w.writeValor("NN")
if __name__ == "__main__":
    main()
