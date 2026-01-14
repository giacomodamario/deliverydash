"""
Glovo Partner Portal API client.

NOTE: Direct API access is blocked by PerimeterX (403 Forbidden).
Use the browser-based GlovoBot instead. This module is kept for
session validation and future use if API access becomes available.
"""

import logging
import requests
from pathlib import Path
from typing import List

from .glovo_session import GlovoSessionManager


class GlovoAPIClient:
    """
    API client for Glovo Partner Portal.

    Currently only used for session validation. Direct API calls
    are blocked by PerimeterX - use GlovoBot for data retrieval.
    """

    GRAPHQL_ENDPOINT = "https://vagw-api.eu.prd.portal.restaurant/query"

    def __init__(self, session_file: Path):
        self.session_manager = GlovoSessionManager(session_file)
        self.logger = logging.getLogger("glovo.api")

    def is_session_valid(self) -> bool:
        """Check if the current session is valid."""
        return self.session_manager.is_session_valid()

    def get_session_info(self) -> dict:
        """Get session status information."""
        return self.session_manager.get_session_info()

    def get_stores(self) -> List[dict]:
        """
        Get list of stores from cached session data.

        Returns:
            List of store dictionaries.
        """
        vendors = self.session_manager.get_selected_vendors()
        stores = []
        for vendor_id in vendors:
            parts = vendor_id.split(';')
            stores.append({
                'id': vendor_id,
                'platform': parts[0] if len(parts) > 0 else 'unknown',
                'store_id': parts[1] if len(parts) > 1 else vendor_id,
                'name': f"Store {parts[1]}" if len(parts) > 1 else vendor_id,
            })
        return stores

    def test_connection(self) -> dict:
        """
        Test API connectivity.

        Note: GraphQL endpoint is blocked by PerimeterX (403).
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

        # Test GraphQL endpoint (expected to fail with 403)
        try:
            access_token = self.session_manager.get_access_token()
            response = requests.post(
                self.GRAPHQL_ENDPOINT,
                json={'query': 'query { __typename }'},
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                },
                timeout=30
            )
            response.raise_for_status()
            results['graphql_reachable'] = True
            results['auth_working'] = True
        except requests.exceptions.HTTPError as e:
            results['error'] = f"API blocked: {e}"
        except requests.exceptions.RequestException as e:
            results['error'] = f"Network error: {e}"

        return results


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    session_path = Path("data/sessions/glovo_session.json")
    if len(sys.argv) > 1:
        session_path = Path(sys.argv[1])

    api = GlovoAPIClient(session_path)

    print("\nGlovo Session Status:")
    print("-" * 40)
    info = api.get_session_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    print(f"\nStores: {len(api.get_stores())} cached")
