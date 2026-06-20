"""Reverse geocoding: GPS coords -> city/county/state. Uses free Nominatim."""
from __future__ import annotations
from functools import lru_cache
from .schemas import Location


@lru_cache(maxsize=512)
def reverse_geocode(lat: float, lng: float) -> Location:
    from geopy.geocoders import Nominatim
    geo = Nominatim(user_agent="lexlocator-app")
    loc = geo.reverse((lat, lng), exactly_one=True, language="en",
                      zoom=14, addressdetails=True)
    if not loc:
        return Location(lat=lat, lng=lng)
    a = loc.raw.get("address", {})
    city = (a.get("city") or a.get("town") or a.get("village")
            or a.get("hamlet") or a.get("municipality") or "")
    state_code = a.get("ISO3166-2-lvl4", "")
    state = state_code.split("-")[-1] if state_code else a.get("state", "")
    return Location(
        city=city,
        county=a.get("county", ""),
        state=state,
        country=(a.get("country_code", "") or "US").upper(),
        lat=lat,
        lng=lng,
    )
