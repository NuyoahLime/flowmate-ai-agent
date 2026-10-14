from __future__ import annotations

import math
import os
from typing import Any, Mapping

from flowmate.integrations.navigation.location_resolver import (
    AmapLocationResolver,
    NavigationHttpClient,
    UrllibNavigationHttpClient,
    query_explicitly_names_resolved_region,
    regions_match,
)
from flowmate.integrations.navigation.provider import (
    NavigationConfigurationError,
    NavigationMappingError,
    NavigationProviderQuery,
    NavigationResponseError,
    NavigationRouteNotFoundError,
    ResolvedNavigationLocation,
)
from flowmate.tools.navigation import NavigationToolResult


class AmapNavigationProvider:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_client: NavigationHttpClient | None = None,
        location_resolver: AmapLocationResolver | None = None,
        route_endpoint: str = "https://restapi.amap.com/v5/direction/driving",
        timeout_seconds: float | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else os.getenv("AMAP_WEB_SERVICE_KEY")
        if resolved_key is None or not resolved_key.strip():
            raise NavigationConfigurationError("AMAP_WEB_SERVICE_KEY is required.")
        timeout = timeout_seconds if timeout_seconds is not None else self._default_timeout()
        client = http_client or UrllibNavigationHttpClient()
        self.api_key = resolved_key
        self.http_client = client
        self.location_resolver = location_resolver or AmapLocationResolver(
            api_key=resolved_key,
            http_client=client,
            timeout_seconds=timeout,
        )
        self.route_endpoint = route_endpoint
        self.timeout_seconds = timeout

    def get_route(self, query: NavigationProviderQuery) -> NavigationToolResult:
        origin = self.location_resolver.resolve(query.origin)
        destination = self.location_resolver.resolve(
            query.destination,
            region_hint=origin,
        )
        destination = self._validate_region_context(origin, destination)
        response = self.http_client.get_json(
            self.route_endpoint,
            params={
                "key": self.api_key,
                "origin": origin.amap_location(),
                "destination": destination.amap_location(),
                "show_fields": "cost",
            },
            timeout_seconds=self.timeout_seconds,
        )
        return self._map_route(
            response,
            origin_query=query.origin,
            destination_query=query.destination,
            origin=origin,
            destination=destination,
        )

    def _map_route(
        self,
        response: Mapping[str, Any],
        *,
        origin_query: str,
        destination_query: str,
        origin: ResolvedNavigationLocation,
        destination: ResolvedNavigationLocation,
    ) -> NavigationToolResult:
        self._ensure_success(response)
        route = response.get("route")
        if not isinstance(route, Mapping):
            raise NavigationResponseError("Amap route data is required.")

        paths = route.get("paths")
        if not isinstance(paths, list):
            raise NavigationResponseError("Amap route.paths must be a list.")
        if not paths:
            raise NavigationRouteNotFoundError("Amap returned no driving route paths.")

        first_path = paths[0]
        if not isinstance(first_path, Mapping):
            raise NavigationResponseError("Amap route path must be a mapping.")

        distance_meters = self._numeric_path_field(first_path, "distance")
        duration_seconds = self._duration_seconds(first_path)

        return NavigationToolResult(
            origin=origin_query,
            destination=destination_query,
            distance_km=round(float(distance_meters) / 1000, 1),
            duration_minutes=math.ceil(float(duration_seconds) / 60),
            traffic=self._map_traffic(first_path),
        )

    def _validate_region_context(
        self,
        origin: ResolvedNavigationLocation,
        destination: ResolvedNavigationLocation,
    ) -> ResolvedNavigationLocation:
        if regions_match(origin, destination):
            return destination
        if (
            destination.source == "geocode"
            and query_explicitly_names_resolved_region(
                destination.query,
                destination,
            )
        ):
            return destination
        raise NavigationResponseError(
            "Navigation destination resolved outside the origin context."
        )

    def _ensure_success(self, response: Mapping[str, Any]) -> None:
        status = response.get("status")
        if status != "1":
            info = response.get("info")
            infocode = response.get("infocode")
            detail = "Amap driving route request failed."
            if isinstance(info, str) and info:
                detail = f"{detail} info={info}"
            if isinstance(infocode, str) and infocode:
                detail = f"{detail}, infocode={infocode}"
            raise NavigationResponseError(detail)

    def _numeric_path_field(self, path: Mapping[str, Any], field_name: str) -> float:
        value = path.get(field_name)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str) and value:
            try:
                return float(value)
            except ValueError as exc:
                raise NavigationMappingError(
                    f"Amap path.{field_name} must be numeric."
                ) from exc
        raise NavigationResponseError(f"Amap path.{field_name} is required.")

    def _duration_seconds(self, path: Mapping[str, Any]) -> float:
        if "duration" in path:
            return self._numeric_path_field(path, "duration")

        cost = path.get("cost")
        if not isinstance(cost, Mapping):
            raise NavigationResponseError("Amap path.cost.duration is required.")
        return self._numeric_path_field(cost, "duration")

    def _map_traffic(self, path: Mapping[str, Any]) -> str:
        restriction = path.get("restriction")
        if restriction in {"1", 1}:
            return "restricted"
        return "unknown"

    def _default_timeout(self) -> float:
        value = os.getenv("AMAP_TIMEOUT_SECONDS")
        if value is None or value.strip() == "":
            return 10.0
        try:
            timeout = float(value)
        except ValueError as exc:
            raise NavigationConfigurationError(
                "AMAP_TIMEOUT_SECONDS must be numeric."
            ) from exc
        if timeout <= 0:
            raise NavigationConfigurationError(
                "AMAP_TIMEOUT_SECONDS must be greater than 0."
            )
        return timeout
