from __future__ import annotations

import json
import socket
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from flowmate.integrations.navigation.provider import (
    NavigationConfigurationError,
    NavigationLocationNotFoundError,
    NavigationMappingError,
    NavigationResponseError,
    NavigationTransportError,
    ResolvedNavigationLocation,
)


class NavigationHttpClient(Protocol):
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        ...


class UrllibNavigationHttpClient:
    def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        request_url = f"{url}?{urlencode(params, doseq=True)}"
        try:
            with urlopen(request_url, timeout=timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise NavigationTransportError(
                f"Amap HTTP request failed with status {exc.code}."
            ) from exc
        except (OSError, TimeoutError, URLError, socket.timeout) as exc:
            raise NavigationTransportError("Amap HTTP request failed.") from exc

        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise NavigationResponseError("Amap response was not valid JSON.") from exc
        if not isinstance(decoded, Mapping):
            raise NavigationResponseError("Amap response must be a mapping.")
        return decoded


class AmapLocationResolver:
    def __init__(
        self,
        *,
        api_key: str,
        http_client: NavigationHttpClient | None = None,
        endpoint: str = "https://restapi.amap.com/v3/geocode/geo",
        poi_endpoint: str = "https://restapi.amap.com/v5/place/text",
        timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key.strip():
            raise NavigationConfigurationError("AMAP_WEB_SERVICE_KEY is required.")
        self.api_key = api_key
        self.http_client = http_client or UrllibNavigationHttpClient()
        self.endpoint = endpoint
        self.poi_endpoint = poi_endpoint
        self.timeout_seconds = timeout_seconds

    def resolve(
        self,
        location: str,
        *,
        region_hint: ResolvedNavigationLocation | None = None,
    ) -> ResolvedNavigationLocation:
        query = location.strip()
        if not query:
            raise NavigationMappingError("Navigation location must not be blank.")
        if query.lower() in {"current_location", "current location", "当前位置"}:
            raise NavigationLocationNotFoundError(
                "Real navigation requires an explicit origin or destination."
            )

        response = self.http_client.get_json(
            self.endpoint,
            params={
                "key": self.api_key,
                "address": query,
            },
            timeout_seconds=self.timeout_seconds,
        )
        if response.get("status") != "1":
            response = self._resolve_poi_response(query, region_hint=region_hint)
            return self._map_poi_location(query, response)

        geocodes = response.get("geocodes")
        if not isinstance(geocodes, list):
            raise NavigationResponseError("Amap geocodes must be a list.")
        if not geocodes:
            raise NavigationLocationNotFoundError(
                f"Navigation location not found: {query}"
            )

        first = geocodes[0]
        if not isinstance(first, Mapping):
            raise NavigationResponseError("Amap geocode must be a mapping.")
        resolved = self._map_location(query, first)
        if self._requires_region_grounding(query, resolved, region_hint):
            response = self._resolve_poi_response(query, region_hint=region_hint)
            return self._map_poi_location(query, response)
        return resolved

    def _requires_region_grounding(
        self,
        query: str,
        resolved: ResolvedNavigationLocation,
        region_hint: ResolvedNavigationLocation | None,
    ) -> bool:
        if region_hint is None or regions_match(region_hint, resolved):
            return False
        return not query_explicitly_names_resolved_region(query, resolved)

    def _resolve_poi_response(
        self,
        query: str,
        *,
        region_hint: ResolvedNavigationLocation | None = None,
    ) -> Mapping[str, Any]:
        params: dict[str, Any] = {
            "key": self.api_key,
            "keywords": query,
            "page_size": 1,
            "page_num": 1,
        }
        if region_hint is not None and region_hint.region_name:
            params["region"] = region_hint.region_name
            params["city_limit"] = "true"
        response = self.http_client.get_json(
            self.poi_endpoint,
            params=params,
            timeout_seconds=self.timeout_seconds,
        )
        self._ensure_success(response, operation="Amap place text search")
        return response

    def _ensure_success(
        self,
        response: Mapping[str, Any],
        *,
        operation: str = "Amap geocoding",
    ) -> None:
        status = response.get("status")
        if status != "1":
            info = response.get("info")
            infocode = response.get("infocode")
            detail = f"{operation} request failed."
            if isinstance(info, str) and info:
                detail = f"{detail} info={info}"
            if isinstance(infocode, str) and infocode:
                detail = f"{detail}, infocode={infocode}"
            raise NavigationResponseError(detail)

    def _map_location(
        self,
        query: str,
        raw_location: Mapping[str, Any],
    ) -> ResolvedNavigationLocation:
        formatted_address = raw_location.get("formatted_address")
        location = raw_location.get("location")
        adcode = raw_location.get("adcode")
        city = raw_location.get("city")

        if not isinstance(formatted_address, str) or not formatted_address:
            raise NavigationResponseError("Amap formatted_address is required.")
        if not isinstance(location, str) or "," not in location:
            raise NavigationResponseError("Amap location must be longitude,latitude.")

        longitude_text, latitude_text = location.split(",", 1)
        try:
            longitude = float(longitude_text)
            latitude = float(latitude_text)
        except ValueError as exc:
            raise NavigationResponseError("Amap coordinates must be numeric.") from exc

        return ResolvedNavigationLocation(
            query=query,
            canonical_name=formatted_address,
            longitude=longitude,
            latitude=latitude,
            adcode=adcode if isinstance(adcode, str) and adcode else None,
            city=city if isinstance(city, str) and city else None,
            citycode=raw_location.get("citycode")
            if isinstance(raw_location.get("citycode"), str)
            and raw_location.get("citycode")
            else None,
            province=raw_location.get("province")
            if isinstance(raw_location.get("province"), str)
            and raw_location.get("province")
            else None,
            source="geocode",
        )

    def _map_poi_location(
        self,
        query: str,
        response: Mapping[str, Any],
    ) -> ResolvedNavigationLocation:
        pois = response.get("pois")
        if not isinstance(pois, list):
            raise NavigationResponseError("Amap POI results must be a list.")
        if not pois:
            raise NavigationLocationNotFoundError(
                f"Navigation location not found: {query}"
            )
        first = pois[0]
        if not isinstance(first, Mapping):
            raise NavigationResponseError("Amap POI result must be a mapping.")

        name = first.get("name")
        location = first.get("location")
        adcode = first.get("adcode")
        city = first.get("cityname")
        address = first.get("address")
        if not isinstance(name, str) or not name:
            raise NavigationResponseError("Amap POI name is required.")
        if not isinstance(location, str) or "," not in location:
            raise NavigationResponseError("Amap POI location must be longitude,latitude.")

        longitude_text, latitude_text = location.split(",", 1)
        try:
            longitude = float(longitude_text)
            latitude = float(latitude_text)
        except ValueError as exc:
            raise NavigationResponseError("Amap POI coordinates must be numeric.") from exc

        canonical = name
        if isinstance(address, str) and address:
            canonical = f"{name} ({address})"

        return ResolvedNavigationLocation(
            query=query,
            canonical_name=canonical,
            longitude=longitude,
            latitude=latitude,
            adcode=adcode if isinstance(adcode, str) and adcode else None,
            city=city if isinstance(city, str) and city else None,
            citycode=first.get("citycode") if isinstance(first.get("citycode"), str) and first.get("citycode") else None,
            province=first.get("pname") if isinstance(first.get("pname"), str) and first.get("pname") else None,
            source="poi",
        )


def normalized_region_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    for suffix in ("\u7279\u522b\u884c\u653f\u533a", "\u81ea\u6cbb\u533a", "\u5e02", "\u7701"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized or None


def regions_match(
    first: ResolvedNavigationLocation,
    second: ResolvedNavigationLocation,
) -> bool:
    first_region = normalized_region_name(first.region_name)
    second_region = normalized_region_name(second.region_name)
    return first_region is None or second_region is None or first_region == second_region


def query_explicitly_names_resolved_region(
    query: str,
    resolved: ResolvedNavigationLocation,
) -> bool:
    normalized_query = query.strip().casefold()
    region_tokens = {
        normalized_region_name(resolved.city),
        normalized_region_name(resolved.province),
    }
    return any(token and token in normalized_query for token in region_tokens)
