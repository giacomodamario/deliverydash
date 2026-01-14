"""Glovo Partner Portal direct API client."""

import json
import logging
import time
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from .glovo_session import GlovoSessionManager


@dataclass
class GlovoOrder:
    """Represents a Glovo order."""
    order_id: str
    order_code: str
    created_at: datetime
    status: str
    store_id: str
    store_name: str
    gross_value: float
    commission: float
    net_value: float
    customer_name: Optional[str] = None
    delivery_address: Optional[str] = None
    products: Optional[List[dict]] = None


class GlovoAPIClient:
    """
    Direct HTTP/GraphQL client for Glovo Partner Portal.

    Uses session tokens from browser authentication to make
    direct API calls, bypassing browser automation and captcha.
    """

    # API endpoints
    GRAPHQL_ENDPOINT = "https://vagw-api.eu.prd.portal.restaurant/query"
    PORTAL_BASE = "https://portal.glovoapp.com"

    # Alternative endpoints (unprotected by PerimeterX)
    STORE_STATUS_API = "https://vss.eu.restaurant-partners.com"
    VENDOR_API = "https://vendor-api-03.eu.restaurant-partners.com"

    def __init__(self, session_file: Path, auto_refresh: bool = True):
        """
        Initialize API client.

        Args:
            session_file: Path to the Playwright storage state JSON.
            auto_refresh: Whether to automatically refresh tokens before expiry.
        """
        self.session_manager = GlovoSessionManager(session_file)
        self.auto_refresh = auto_refresh
        self.logger = logging.getLogger("glovo.api")

        self._session = requests.Session()
        self._setup_session()

    def _setup_session(self):
        """Configure requests session with default headers."""
        self._session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Origin': self.PORTAL_BASE,
            'Referer': f'{self.PORTAL_BASE}/dashboard',
        })

    def _get_auth_headers(self) -> dict:
        """Get authorization headers for API requests."""
        access_token = self.session_manager.get_access_token()
        device_token = self.session_manager.get_device_token()

        headers = {}
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
        if device_token:
            headers['X-Device-Token'] = device_token

        return headers

    def _ensure_valid_session(self) -> bool:
        """
        Ensure session is valid, attempting refresh if needed.

        Returns:
            True if session is valid and ready for use.
        """
        if not self.session_manager.is_session_valid():
            self.logger.error("Session is not valid")
            return False

        if self.auto_refresh and self.session_manager.is_token_expiring(min_minutes=30):
            self.logger.info("Token expiring soon, attempting refresh...")
            if not self.refresh_token():
                self.logger.warning("Token refresh failed")
                # Continue anyway if not expired yet
                if self.session_manager.is_token_expired():
                    return False

        return True

    def is_session_valid(self) -> bool:
        """Check if the current session is valid for API use."""
        return self.session_manager.is_session_valid()

    def get_session_info(self) -> dict:
        """Get session status information."""
        return self.session_manager.get_session_info()

    def refresh_token(self) -> bool:
        """
        Attempt to refresh the access token.

        Note: This requires knowing the refresh endpoint structure.
        May need to be discovered through browser network inspection.

        Returns:
            True if refresh succeeded.
        """
        refresh_token = self.session_manager.get_refresh_token()
        device_token = self.session_manager.get_device_token()

        if not refresh_token:
            self.logger.error("No refresh token available")
            return False

        # Common Glovo/DH auth refresh endpoints to try
        refresh_endpoints = [
            "https://vendorportal-eu.dh-auth.io/oauth/token",
            "https://auth.glovoapp.com/oauth/token",
            "https://api.glovoapp.com/oauth/refresh",
        ]

        for endpoint in refresh_endpoints:
            try:
                response = self._session.post(
                    endpoint,
                    json={
                        'grant_type': 'refresh_token',
                        'refresh_token': refresh_token,
                    },
                    headers={
                        'Authorization': f'Bearer {device_token}' if device_token else '',
                        'Content-Type': 'application/json',
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    data = response.json()
                    new_token = data.get('access_token') or data.get('accessToken')
                    if new_token:
                        self.session_manager.update_access_token(new_token)
                        self.logger.info(f"Token refreshed via {endpoint}")
                        return True

            except Exception as e:
                self.logger.debug(f"Refresh attempt failed for {endpoint}: {e}")
                continue

        self.logger.warning("Token refresh failed - all endpoints exhausted")
        return False

    def _graphql_request(self, query: str, variables: dict = None) -> dict:
        """
        Make a GraphQL request.

        Args:
            query: GraphQL query string.
            variables: Query variables.

        Returns:
            Response data dictionary.

        Raises:
            requests.exceptions.RequestException: On network errors.
            ValueError: On GraphQL errors.
        """
        if not self._ensure_valid_session():
            raise ValueError("Invalid session - re-authentication required")

        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        headers = self._get_auth_headers()

        response = self._session.post(
            self.GRAPHQL_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=60
        )

        if response.status_code == 401:
            self.logger.error("Authentication failed (401)")
            raise ValueError("Authentication failed - session may be invalid")

        if response.status_code == 429:
            self.logger.warning("Rate limited (429)")
            raise ValueError("Rate limited - please retry later")

        response.raise_for_status()

        data = response.json()

        if 'errors' in data:
            errors = data['errors']
            error_msgs = [e.get('message', str(e)) for e in errors]
            self.logger.error(f"GraphQL errors: {error_msgs}")
            raise ValueError(f"GraphQL errors: {error_msgs}")

        return data.get('data', {})

    def _rest_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make a REST API request with authentication.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Request URL.
            **kwargs: Additional requests arguments.

        Returns:
            Response object.
        """
        if not self._ensure_valid_session():
            raise ValueError("Invalid session - re-authentication required")

        headers = kwargs.pop('headers', {})
        headers.update(self._get_auth_headers())

        response = self._session.request(
            method,
            url,
            headers=headers,
            timeout=kwargs.pop('timeout', 60),
            **kwargs
        )

        return response

    def test_connection(self) -> dict:
        """
        Test API connectivity and return status.

        Returns:
            Dictionary with connection test results.
        """
        results = {
            'session_valid': self.is_session_valid(),
            'graphql_reachable': False,
            'auth_working': False,
            'error': None,
        }

        if not results['session_valid']:
            results['error'] = "Session is invalid"
            return results

        try:
            # Try a simple introspection query
            query = """
            query {
                __typename
            }
            """
            data = self._graphql_request(query)
            results['graphql_reachable'] = True
            results['auth_working'] = True

        except ValueError as e:
            results['error'] = str(e)
            if 'Authentication' in str(e):
                results['graphql_reachable'] = True
        except requests.exceptions.RequestException as e:
            results['error'] = f"Network error: {e}"

        return results

    def get_stores(self) -> List[dict]:
        """
        Get list of stores/vendors for the account.

        Returns:
            List of store dictionaries.
        """
        # First try from session (cached data)
        vendors = self.session_manager.get_selected_vendors()
        if vendors:
            stores = []
            for vendor_id in vendors:
                # Parse vendor ID format: "GV_IT;890642"
                parts = vendor_id.split(';')
                stores.append({
                    'id': vendor_id,
                    'platform': parts[0] if len(parts) > 0 else 'unknown',
                    'store_id': parts[1] if len(parts) > 1 else vendor_id,
                    'name': f"Store {parts[1]}" if len(parts) > 1 else vendor_id,
                })
            return stores

        # Try GraphQL query for stores
        # Note: Actual query structure needs to be discovered via browser inspection
        query = """
        query GetStores {
            stores {
                id
                name
                address
                status
            }
        }
        """

        try:
            data = self._graphql_request(query)
            return data.get('stores', [])
        except Exception as e:
            self.logger.warning(f"GraphQL stores query failed: {e}")
            return []

    def get_orders(
        self,
        store_id: str,
        start_date: datetime,
        end_date: datetime,
        limit: int = 100
    ) -> List[dict]:
        """
        Get orders for a store within a date range.

        Args:
            store_id: Store/vendor ID.
            start_date: Start of date range.
            end_date: End of date range.
            limit: Maximum orders to fetch.

        Returns:
            List of order dictionaries.
        """
        # Note: Actual query structure needs to be discovered via browser inspection
        # This is an estimated query based on common GraphQL patterns
        query = """
        query GetOrders($storeId: String!, $startDate: String!, $endDate: String!, $limit: Int) {
            orders(
                storeId: $storeId
                startDate: $startDate
                endDate: $endDate
                first: $limit
            ) {
                edges {
                    node {
                        id
                        code
                        createdAt
                        status
                        totalPrice
                        commission
                        netPrice
                        customer {
                            name
                        }
                        products {
                            name
                            quantity
                            price
                        }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
        """

        variables = {
            'storeId': store_id,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'limit': limit,
        }

        try:
            data = self._graphql_request(query, variables)
            edges = data.get('orders', {}).get('edges', [])
            return [edge['node'] for edge in edges]
        except Exception as e:
            self.logger.error(f"Failed to fetch orders: {e}")
            return []

    def get_order_history_csv(
        self,
        store_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Optional[str]:
        """
        Download order history as CSV.

        Args:
            store_id: Store/vendor ID.
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            CSV content string, or None if failed.
        """
        # Try the report export endpoint
        # Note: Actual endpoint needs to be discovered via browser inspection
        export_endpoints = [
            f"{self.PORTAL_BASE}/api/orders/export",
            f"{self.PORTAL_BASE}/api/reports/orders",
            f"{self.VENDOR_API}/orders/export",
        ]

        params = {
            'storeId': store_id,
            'startDate': start_date.strftime('%Y-%m-%d'),
            'endDate': end_date.strftime('%Y-%m-%d'),
            'format': 'csv',
        }

        for endpoint in export_endpoints:
            try:
                response = self._rest_request('GET', endpoint, params=params)

                if response.status_code == 200:
                    content_type = response.headers.get('Content-Type', '')
                    if 'csv' in content_type or 'text' in content_type:
                        self.logger.info(f"CSV export successful from {endpoint}")
                        return response.text

            except Exception as e:
                self.logger.debug(f"CSV export failed for {endpoint}: {e}")
                continue

        self.logger.warning("CSV export failed - no working endpoint found")
        return None

    def discover_graphql_schema(self) -> dict:
        """
        Attempt to discover the GraphQL schema via introspection.

        Returns:
            Schema information dictionary.
        """
        introspection_query = """
        query IntrospectionQuery {
            __schema {
                queryType { name }
                mutationType { name }
                types {
                    name
                    kind
                    fields {
                        name
                        args {
                            name
                            type { name kind }
                        }
                        type { name kind }
                    }
                }
            }
        }
        """

        try:
            data = self._graphql_request(introspection_query)
            return data.get('__schema', {})
        except Exception as e:
            self.logger.warning(f"Schema introspection failed: {e}")
            return {}

    def get_available_queries(self) -> List[str]:
        """
        Get list of available GraphQL query names.

        Returns:
            List of query names.
        """
        schema = self.discover_graphql_schema()
        query_type = schema.get('queryType', {})

        for type_def in schema.get('types', []):
            if type_def.get('name') == query_type.get('name'):
                fields = type_def.get('fields', [])
                return [f['name'] for f in fields]

        return []


class GlovoSyncService:
    """
    High-level sync service for Glovo data.

    Orchestrates data fetching and handles errors gracefully.
    """

    def __init__(self, session_file: Path):
        """
        Initialize sync service.

        Args:
            session_file: Path to session JSON file.
        """
        self.api = GlovoAPIClient(session_file)
        self.logger = logging.getLogger("glovo.sync")

    def check_health(self) -> dict:
        """
        Check sync service health.

        Returns:
            Health status dictionary.
        """
        session_info = self.api.get_session_info()
        connection = self.api.test_connection()

        return {
            'healthy': session_info['valid'] and connection['auth_working'],
            'session': session_info,
            'connection': connection,
            'needs_reauth': not session_info['valid'] or session_info['is_expired'],
        }

    def sync_orders(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        stores: List[str] = None
    ) -> dict:
        """
        Sync orders for specified date range and stores.

        Args:
            start_date: Start of date range (default: 7 days ago).
            end_date: End of date range (default: today).
            stores: List of store IDs (default: all stores).

        Returns:
            Sync result dictionary.
        """
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        result = {
            'success': False,
            'stores_synced': 0,
            'orders_fetched': 0,
            'errors': [],
        }

        # Get stores if not specified
        if stores is None:
            store_list = self.api.get_stores()
            stores = [s['id'] for s in store_list]

        self.logger.info(f"Syncing {len(stores)} stores from {start_date} to {end_date}")

        for store_id in stores:
            try:
                orders = self.api.get_orders(store_id, start_date, end_date)
                result['orders_fetched'] += len(orders)
                result['stores_synced'] += 1
                self.logger.info(f"Store {store_id}: fetched {len(orders)} orders")

            except Exception as e:
                error_msg = f"Store {store_id}: {e}"
                result['errors'].append(error_msg)
                self.logger.error(error_msg)

        result['success'] = result['stores_synced'] > 0
        return result


if __name__ == "__main__":
    # Quick test
    import sys
    logging.basicConfig(level=logging.INFO)

    session_path = Path("data/sessions/glovo_session.json")
    if len(sys.argv) > 1:
        session_path = Path(sys.argv[1])

    print("\nGlovo API Client Test")
    print("=" * 50)

    api = GlovoAPIClient(session_path)

    print("\n1. Session Info:")
    info = api.get_session_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

    print("\n2. Connection Test:")
    conn = api.test_connection()
    for key, value in conn.items():
        print(f"   {key}: {value}")

    print("\n3. Available Stores:")
    stores = api.get_stores()
    for store in stores[:5]:  # Show first 5
        print(f"   - {store}")
    if len(stores) > 5:
        print(f"   ... and {len(stores) - 5} more")
