import sys
import requests
import write_temp as w
import time
def main():
    sunsetTime = 3600 #tiempo en segundos que estara la animacion de afternoon admira
    api_key = "4a24b604a50c1ab4681b757e8b89b21b" 

    if not api_key:
        if len(sys.argv) >= 2:
            api_key = sys.argv[1]
        else:
            raise SystemExit("Error: falta API key. Pásala como argumento.")

    city = "Barcelona"
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "es",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError:
        # Opcional: si quieres manejar el payload de error sin imprimir
        try:
            err_payload = resp.json()
        except Exception:
            err_payload = resp.text
        raise RuntimeError(f"HTTP {resp.status_code} - Error en la API") from None
    except requests.exceptions.RequestException as e:
        raise RuntimeError("Error de red") from e

    # --- Lógica por weather id ---
    # OpenWeather devuelve una lista "weather"; normalmente usamos el primer elemento.
    weather_id = None
    try:
        weather_id = data["weather"][0]["id"]
    except (KeyError, IndexError, TypeError):
        # Manejo sin prints: decide qué hacer si la estructura no es la esperada
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

    # No se imprime nada; si quieres devolver algo, puedes retornar data o weather_id.

if __name__ == "__main__":
    main()
