import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://ws.smn.gob.ar/map_items/weather"
DEFAULT_NAME = "Larroque"
DEFAULT_ID = 954


def descargar():
    req = urllib.request.Request(API_URL, headers={"User-Agent": "clima-larroque/1.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def numero(valor):
    try:
        return round(float(valor), 1) if valor is not None else None
    except (TypeError, ValueError):
        return None


def coord(item, *keys):
    for key in keys:
        value = item.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    location = item.get("location") or item.get("coordinates") or {}
    for key in keys:
        value = location.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return None


def transformar(item):
    weather = item.get("weather") or {}
    forecast_obj = (item.get("forecast") or {}).get("forecast") or {}
    if isinstance(forecast_obj, dict):
        dias = [forecast_obj[k] for k in sorted(forecast_obj, key=lambda x: int(x) if str(x).isdigit() else 999) if isinstance(forecast_obj[k], dict)]
    elif isinstance(forecast_obj, list):
        dias = forecast_obj
    else:
        dias = []

    pronostico = []
    for dato in dias[:6]:
        manana = dato.get("morning") or {}
        tarde = dato.get("afternoon") or {}
        pronostico.append({
            "fecha": dato.get("date"),
            "min": numero(dato.get("temp_min")),
            "max": numero(dato.get("temp_max")),
            "estado": tarde.get("description") or manana.get("description") or "",
            "weather_id": tarde.get("weather_id") or manana.get("weather_id"),
            "lluvia": dato.get("prob_precipitation", dato.get("probability_of_precipitation")),
        })

    return {
        "id": item.get("lid") or item.get("id"),
        "localidad": item.get("name") or "",
        "provincia": item.get("province") or "",
        "lat": coord(item, "lat", "latitude", "latitud"),
        "lon": coord(item, "lon", "lng", "longitude", "longitud"),
        "actual": {
            "temperatura": numero(weather.get("temp")),
            "sensacion": numero(weather.get("st")),
            "humedad": weather.get("humidity"),
            "presion": numero(weather.get("pressure")),
            "viento_kmh": weather.get("wind_speed"),
            "viento_direccion": weather.get("wind_deg"),
            "estado": weather.get("description") or weather.get("tempDesc") or "",
            "weather_id": weather.get("id"),
        },
        "pronostico": pronostico,
    }


def main():
    datos = descargar()
    if not isinstance(datos, list) or not datos:
        raise RuntimeError("El SMN no devolvió localidades")

    localidades = []
    for item in datos:
        nombre = str(item.get("name") or "").strip()
        if not nombre:
            continue
        localidades.append(transformar(item))

    localidades.sort(key=lambda x: (x.get("provincia") or "", x.get("localidad") or ""))
    salida = {
        "default": DEFAULT_NAME,
        "default_id": DEFAULT_ID,
        "fuente": "Servicio Meteorológico Nacional",
        "actualizado": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "localidades": localidades,
    }
    Path("clima-localidades.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Localidades guardadas: {len(localidades)}")


if __name__ == "__main__":
    main()
