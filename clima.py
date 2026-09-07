import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://ws.smn.gob.ar/map_items/weather"
LUGAR = "LARROQUE"
LOCATION_ID = 954


def descargar():
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "clima-larroque/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def numero(valor):
    try:
        return round(float(valor), 1) if valor is not None else None
    except (TypeError, ValueError):
        return None


def transformar(item):
    weather = item.get("weather") or {}
    forecast_obj = (item.get("forecast") or {}).get("forecast") or {}

    if isinstance(forecast_obj, dict):
        dias = []
        for key in sorted(forecast_obj, key=lambda x: int(x) if str(x).isdigit() else 999):
            dato = forecast_obj[key]
            if isinstance(dato, dict):
                dias.append(dato)
    elif isinstance(forecast_obj, list):
        dias = forecast_obj
    else:
        dias = []

    pronostico = []
    for dato in dias[:6]:
        manana = dato.get("morning") or {}
        tarde = dato.get("afternoon") or {}
        estado = tarde.get("description") or manana.get("description") or ""
        weather_id = tarde.get("weather_id") or manana.get("weather_id")
        pronostico.append({
            "fecha": dato.get("date"),
            "min": numero(dato.get("temp_min")),
            "max": numero(dato.get("temp_max")),
            "estado": estado,
            "weather_id": weather_id,
            "lluvia": dato.get("prob_precipitation", dato.get("probability_of_precipitation")),
        })

    return {
        "localidad": item.get("name") or LUGAR,
        "provincia": item.get("province") or "Entre Ríos",
        "actual": {
            "temperatura": numero(weather.get("temp")),
            "sensacion": numero(weather.get("st")),
            "humedad": weather.get("humidity"),
            "presion": numero(weather.get("pressure")),
            "viento_kmh": weather.get("wind_speed"),
            "viento_direccion": weather.get("wind_deg"),
            "visibilidad_km": weather.get("visibility"),
            "estado": weather.get("description") or weather.get("tempDesc") or "",
            "weather_id": weather.get("id"),
        },
        "pronostico": pronostico,
        "fuente": "Servicio Meteorológico Nacional",
        "actualizado": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
    }


def main():
    datos = descargar()
    if not isinstance(datos, list):
        raise RuntimeError("El SMN no devolvió una lista de localidades")

    item = next(
        (
            x for x in datos
            if x.get("lid") == LOCATION_ID
            or str(x.get("name", "")).strip().upper() == LUGAR
        ),
        None,
    )

    if item is None:
        raise RuntimeError("No se encontró Larroque en la respuesta del SMN")

    salida = transformar(item)
    Path("clima.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(salida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
