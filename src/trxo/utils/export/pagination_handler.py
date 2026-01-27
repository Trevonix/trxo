"""
Pagination handler for API requests.

Handles offset-based pagination for PingOne Advanced Identity Cloud API
responses.
"""

from typing import Any, Dict
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


from trxo.constants import DEFAULT_PAGE_SIZE


class PaginationHandler:
    """Handles pagination logic for API responses"""

    @staticmethod
    def is_paginated(response_data: Any) -> bool:
        """
        Check if response appears to be paginated.

        Args:
            response_data: API response data

        Returns:
            True if response looks like a paginated result
        """
        return (
            isinstance(response_data, dict)
            and isinstance(response_data.get("result"), list)
            and (
                "remainingPagedResults" in response_data
                or "resultCount" in response_data
                or "totalPagedResults" in response_data
                or "totalPagedResultsPolicy" in response_data
            )
        )

    @staticmethod
    def build_endpoint_with_params(endpoint: str, params: Dict[str, Any]) -> str:
        """
        Build endpoint URL with additional query parameters.

        Args:
            endpoint: Original endpoint URL
            params: Parameters to add/update

        Returns:
            Updated endpoint with parameters
        """
        parts = urlsplit(endpoint)
        query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
        query_params.update({k: str(v) for k, v in params.items() if v is not None})

        if parts.scheme:
            return urlunsplit(
                (
                    parts.scheme,
                    parts.netloc,
                    parts.path,
                    urlencode(query_params, doseq=True),
                    parts.fragment,
                )
            )
        else:
            query_string = urlencode(query_params, doseq=True) if query_params else ""
            return f"{parts.path}?{query_string}" if query_string else parts.path

    @staticmethod
    def fetch_all_pages(
        initial_response: Dict[str, Any],
        api_endpoint: str,
        http_requester,
        headers: Dict[str, str],
        api_base_url: str,
    ) -> Dict[str, Any]:
        """
        Fetch all pages of a paginated response.

        Args:
            initial_response: First page response
            api_endpoint: API endpoint
            http_requester: Object with make_http_request method
            headers: HTTP headers
            api_base_url: Base URL for API

        Returns:
            Aggregated response with all items
        """
        first_items = initial_response.get("result", [])

        # Check if we actually need more pages
        remaining = initial_response.get("remainingPagedResults")
        if not isinstance(remaining, int) or remaining <= 0:
            return initial_response

        # Determine page size
        page_size = DEFAULT_PAGE_SIZE
        try:
            parts = urlsplit(api_endpoint)
            query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
            if "_pageSize" in query_params and query_params["_pageSize"].isdigit():
                page_size = int(query_params["_pageSize"])
        except Exception:
            pass

        # Fetch remaining pages
        offset = len(first_items)
        combined = list(first_items)

        while True:
            # Build next page endpoint
            next_endpoint = PaginationHandler.build_endpoint_with_params(
                api_endpoint,
                {"_pagedResultsOffset": offset, "_pageSize": page_size},
            )

            next_url = f"{api_base_url}{next_endpoint}"
            next_response = http_requester.make_http_request(next_url, "GET", headers)
            next_data = next_response.json()
            next_items = (
                next_data.get("result") if isinstance(next_data, dict) else None
            )

            if not isinstance(next_items, list) or not next_items:
                break

            combined.extend(next_items)

            remaining_count = next_data.get("remainingPagedResults")
            if isinstance(remaining_count, int) and remaining_count <= 0:
                break

            offset += len(next_items)

        # Build aggregated response
        aggregated = dict(initial_response)
        aggregated["result"] = combined
        aggregated["resultCount"] = len(combined)
        aggregated["remainingPagedResults"] = 0

        if "totalPagedResults" in aggregated and isinstance(
            aggregated["totalPagedResults"], int
        ):
            aggregated["totalPagedResults"] = max(
                aggregated["totalPagedResults"], len(combined)
            )

        return aggregated
