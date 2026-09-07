import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SMN_WEB = "https://ws2.smn.gob.ar/pronostico"
SMN_API = "https://ws1.smn.gob.ar/v1"
DEFAULT_NAME = "Larroque"
DEFAULT_PROVINCE = "Entre Ríos"

LOCALIDADES = [
    "Larroque", "Gualeguaychú", "Gualeguay", "Concordia", "Paraná",
    "Concepción del Uruguay", "Villaguay", "Victoria", "La Paz", "Chajarí",
    "Colón", "Federación", "Diamante", "Nogoyá", "Federal", "Feliciano",
    "San José", "San Salvador", "Rosario del Tala", "Basavilbaso", "Urdinarrain",
    "Crespo", "Viale", "Hasenkamp", "Hernandarias", "María Grande",
    "General Ramírez", "Seguí", "Villa Elisa", "Ibicuy", "Ceibas", "Santa Elena"
]


def get_text(url, headers=None, attempts=4):
    last = None
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers=headers or {"User-Agent": "Accion-Clima/2.1"})
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8")
        except Exception as exc:
            last = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise last


def get_json(url, headers=None, attempts=4):
    return json.loads(get_text(url, headers=headers, attempts=attempts))


def token_smn():
    html = get_text(SMN_WEB, {"User-Agent": "Accion-Clima/2.1", "Referer": "https://www.smn.gob.ar/"})
    patterns = [
        r"localStorage\.setItem\(['\"]token['\"],\s*['\"]([^'\"]+)",
        r'localStorage\.setItem\("token",\s*"([^"]+)"',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            return match.group(1)
    raise RuntimeError("No se pudo obtener el token JWT del SMN")


def headers(token):
    return {
        "User-Agent": "Accion-Clima/2.1",
        "Authorization": f"JWT {token}",
        "Referer": "https://www.smn.gob.ar/",
        "Accept": "application/json",
    }


def numero(value):
    try:
        return round(float(value), 1) if value is not None else None
    except (TypeError, ValueError):
        return None


def buscar_localidad(token, nombre):
    url = f"{SMN_API}/georef/location/search?name={urllib.parse.quote(nombre)}"
    resultados = get_json(url, headers(token))
    if not isinstance(resultados, list) or not resultados:
        return None

    exactos = [x for x in resultados if isinstance(x, list) and len(x) >= 4 and str(x[1]).strip().lower() == nombre.lower()]
    candidatos = exactos or resultados
    er = [x for x in candidatos if len(x) >= 4 and str(x[3]).strip().lower() == DEFAULT_PROVINCE.lower()]
    elegido = er[0] if er else candidatos[0]

    return {
        "id": str(elegido[0]),
        "localidad": str(elegido[1]),
        "departamento": str(elegido[2]) if len(elegido) > 2 else "",
        "provincia": str(elegido[3]) if len(elegido) > 3 else DEFAULT_PROVINCE,
    }


def obtener_actual(token, location_id):
    return get_json(f"{SMN_API}/weather/location/{location_id}", headers(token))


def obtener_pronostico(token, location_id):
    return get_json(f"{SMN_API}/forecast/location/{location_id}", headers(token))


def transformar_actual(actual):
    weather = actual.get("weather") or {}
    wind = actual.get("wind") or {}
    location = actual.get("location") or {}
    coord = location.get("coord") or {}
    return {
        "temperatura": numero(actual.get("temperature")),
        "sensacion": numero(actual.get("feels_like")),
        "humedad": numero(actual.get("humidity")),
        "presion": numero(actual.get("pressure")),
        "viento_kmh": numero(wind.get("speed")),
        "viento_direccion": wind.get("deg"),
        "estado": weather.get("description") or "",
        "weather_id": weather.get("id"),
        "fecha": actual.get("date"),
        "estacion_id": actual.get("station_id"),
        "visibilidad_km": numero(actual.get("visibility")),
    }, coord


def transformar_pronostico(datos):
    forecast = datos.get("forecast") if isinstance(datos, dict) else datos
    if not isinstance(forecast, list):
        return []

    salida = []
    for dia in forecast[:6]:
        if not isinstance(dia, dict):
            continue
        periodos = [dia[k] for k in ("early_morning", "morning", "afternoon", "night") if isinstance(dia.get(k), dict)]
        temps = [numero(p.get("temperature")) for p in periodos]
        temps = [x for x in temps if x is not None]
        estados = [p for p in periodos if p.get("weather")]
        principal = next((p for p in estados if p.get("weather", {}).get("description")), estados[0] if estados else {})
        weather = principal.get("weather") or {}
        probs = []
        for p in periodos:
            r = p.get("rain_prob_range")
            if isinstance(r, list) and r:
                try:
                    probs.append(float(r[1] if len(r) > 1 else r[0]))
                except (TypeError, ValueError):
                    pass
        salida.append({
            "fecha": dia.get("date"),
            "min": min(temps) if temps else None,
            "max": max(temps) if temps else None,
            "estado": weather.get("description") or "",
            "weather_id": weather.get("id"),
            "lluvia": max(probs) if probs else None,
        })
    return salida


def cargar_localidad(token, nombre):
    try:
        lugar = buscar_localidad(token, nombre)
        if not lugar:
            print(f"Sin resultado SMN: {nombre}")
            return None
        actual_raw = obtener_actual(token, lugar["id"])
        forecast_raw = obtener_pronostico(token, lugar["id"])
        actual, coord = transformar_actual(actual_raw)
        return {
            "id": lugar["id"],
            "localidad": lugar["localidad"],
            "provincia": lugar["provincia"],
            "departamento": lugar["departamento"],
            "lat": numero(coord.get("lat")),
            "lon": numero(coord.get("lon")),
            "actual": actual,
            "pronostico": transformar_pronostico(forecast_raw),
        }
    except Exception as exc:
        print(f"Error en {nombre}: {exc}")
        return None


def main():
    token = token_smn()
    localidades = []
    for nombre in LOCALIDADES:
        lugar = cargar_localidad(token, nombre)
        if lugar:
            localidades.append(lugar)
        time.sleep(0.25)

    if not localidades:
        raise RuntimeError("El SMN no devolvió ninguna localidad")

    predeterminada = next((x for x in localidades if x["localidad"].lower() == DEFAULT_NAME.lower()), localidades[0])
    salida = {
        "default": predeterminada["localidad"],
        "default_id": predeterminada["id"],
        "fuente": "Servicio Meteorológico Nacional",
        "actualizado": datetime.now(timezone.utc).astimezone().isoformat(timespec="minutes"),
        "localidades": localidades,
    }
    Path("clima-localidades.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Localidades cargadas: {len(localidades)}")


if __name__ == "__main__":
    main()
