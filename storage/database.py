"""SQLite database for storing parsed invoice data."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict

from config import settings


@dataclass
class Location:
    """Represents a restaurant/brand location."""
    id: Optional[int] = None
    platform: str = ""
    external_id: str = ""  # ID from the platform
    brand: str = ""
    name: str = ""
    address: str = ""
    created_at: datetime = None


@dataclass
class Invoice:
    """Represents a parsed invoice record."""
    id: Optional[int] = None
    platform: str = ""
    location_id: int = None
    external_invoice_id: str = ""  # Invoice ID from platform
    invoice_date: datetime = None
    period_start: datetime = None
    period_end: datetime = None

    # Financial summary
    gross_sales: float = 0.0
    net_sales: float = 0.0
    commission: float = 0.0
    commission_rate: float = 0.0
    delivery_fees: float = 0.0
    tips: float = 0.0
    adjustments: float = 0.0
    taxes: float = 0.0
    total_payout: float = 0.0

    # Order stats
    total_orders: int = 0

    # File info
    source_file: str = ""
    file_hash: str = ""  # To detect duplicates

    created_at: datetime = None
    updated_at: datetime = None


class Database:
    """SQLite database manager for invoice storage."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or settings.database_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Locations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                external_id TEXT NOT NULL,
                brand TEXT,
                name TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(platform, external_id)
            )
        """)

        # Invoices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                location_id INTEGER,
                external_invoice_id TEXT,
                invoice_date DATE,
                period_start DATE,
                period_end DATE,
                gross_sales REAL DEFAULT 0,
                net_sales REAL DEFAULT 0,
                commission REAL DEFAULT 0,
                commission_rate REAL DEFAULT 0,
                delivery_fees REAL DEFAULT 0,
                tips REAL DEFAULT 0,
                adjustments REAL DEFAULT 0,
                taxes REAL DEFAULT 0,
                total_payout REAL DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                source_file TEXT,
                file_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(id),
                UNIQUE(platform, external_invoice_id, location_id)
            )
        """)

        # Line items table (for detailed breakdown)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_line_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                description TEXT,
                category TEXT,
                quantity INTEGER DEFAULT 1,
                unit_price REAL DEFAULT 0,
                total REAL DEFAULT 0,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id)
            )
        """)

        # Downloads tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                location_id INTEGER,
                file_path TEXT NOT NULL,
                file_hash TEXT,
                downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parsed BOOLEAN DEFAULT FALSE,
                parsed_at TIMESTAMP,
                error TEXT,
                FOREIGN KEY (location_id) REFERENCES locations(id)
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_platform ON invoices(platform)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_location ON invoices(location_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_downloads_hash ON downloads(file_hash)")

        conn.commit()
        conn.close()

    # Location methods
    def upsert_location(self, location: Location) -> int:
        """Insert or update a location, returning its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO locations (platform, external_id, brand, name, address)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(platform, external_id) DO UPDATE SET
                brand = excluded.brand,
                name = excluded.name,
                address = excluded.address
            RETURNING id
        """, (location.platform, location.external_id, location.brand,
              location.name, location.address))

        location_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return location_id

    def get_location(self, platform: str, external_id: str) -> Optional[Location]:
        """Get a location by platform and external ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM locations WHERE platform = ? AND external_id = ?
        """, (platform, external_id))

        row = cursor.fetchone()
        conn.close()

        if row:
            return Location(**dict(row))
        return None

    def get_all_locations(self, platform: str = None) -> List[Location]:
        """Get all locations, optionally filtered by platform."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if platform:
            cursor.execute("SELECT * FROM locations WHERE platform = ?", (platform,))
        else:
            cursor.execute("SELECT * FROM locations")

        rows = cursor.fetchall()
        conn.close()

        return [Location(**dict(row)) for row in rows]

    # Invoice methods
    def insert_invoice(self, invoice: Invoice) -> int:
        """Insert a new invoice, returning its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO invoices (
                platform, location_id, external_invoice_id, invoice_date,
                period_start, period_end, gross_sales, net_sales, commission,
                commission_rate, delivery_fees, tips, adjustments, taxes,
                total_payout, total_orders, source_file, file_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
        """, (
            invoice.platform, invoice.location_id, invoice.external_invoice_id,
            invoice.invoice_date, invoice.period_start, invoice.period_end,
            invoice.gross_sales, invoice.net_sales, invoice.commission,
            invoice.commission_rate, invoice.delivery_fees, invoice.tips,
            invoice.adjustments, invoice.taxes, invoice.total_payout,
            invoice.total_orders, invoice.source_file, invoice.file_hash
        ))

        invoice_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return invoice_id

    def invoice_exists(self, file_hash: str) -> bool:
        """Check if an invoice with this file hash already exists."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM invoices WHERE file_hash = ?", (file_hash,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def get_invoices(
        self,
        platform: str = None,
        location_id: int = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> List[Invoice]:
        """Query invoices with optional filters."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM invoices WHERE 1=1"
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if location_id:
            query += " AND location_id = ?"
            params.append(location_id)
        if start_date:
            query += " AND invoice_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND invoice_date <= ?"
            params.append(end_date)

        query += " ORDER BY invoice_date DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [Invoice(**dict(row)) for row in rows]

    # Download tracking methods
    def record_download(self, platform: str, file_path: str, file_hash: str,
                       location_id: int = None) -> int:
        """Record a downloaded file."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO downloads (platform, location_id, file_path, file_hash)
            VALUES (?, ?, ?, ?)
            RETURNING id
        """, (platform, location_id, file_path, file_hash))

        download_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()

        return download_id

    def download_exists(self, file_hash: str) -> bool:
        """Check if a file with this hash has already been downloaded."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM downloads WHERE file_hash = ?", (file_hash,))
        exists = cursor.fetchone() is not None

        conn.close()
        return exists

    def mark_download_parsed(self, download_id: int, error: str = None):
        """Mark a download as parsed (or failed)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE downloads SET
                parsed = ?,
                parsed_at = CURRENT_TIMESTAMP,
                error = ?
            WHERE id = ?
        """, (error is None, error, download_id))

        conn.commit()
        conn.close()

    # Summary methods
    def get_summary(self, platform: str = None, location_id: int = None) -> dict:
        """Get a summary of stored invoice data."""
        conn = self._get_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                COUNT(*) as total_invoices,
                SUM(gross_sales) as total_gross_sales,
                SUM(net_sales) as total_net_sales,
                SUM(commission) as total_commission,
                SUM(total_payout) as total_payout,
                SUM(total_orders) as total_orders,
                MIN(invoice_date) as earliest_date,
                MAX(invoice_date) as latest_date
            FROM invoices WHERE 1=1
        """
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if location_id:
            query += " AND location_id = ?"
            params.append(location_id)

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else {}
