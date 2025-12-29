from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum
import re


class Platform(Enum):
    DELIVEROO = "deliveroo"
    GLOVO = "glovo"
    JUSTEAT = "justeat"
    UNKNOWN = "unknown"


@dataclass
class ParsedOrder:
    platform: Platform
    order_id: str
    order_number: str
    restaurant_name: str
    restaurant_address: str
    order_datetime: Optional[datetime]
    gross_value: float
    commission_amount: float
    commission_rate: float
    vat_amount: float
    net_payout: float
    refund_amount: float = 0.0
    refund_reason: str = ""
    refund_fault: str = ""
    promo_restaurant_funded: float = 0.0
    promo_platform_funded: float = 0.0
    cash_payment_adjustment: float = 0.0
    is_cash_order: bool = False
    ad_fee: float = 0.0
    discount_commission: float = 0.0
    wait_time_fee: float = 0.0
    prime_fee: float = 0.0
    flash_deals_fee: float = 0.0
    admin_fee: float = 0.0
    notes: str = ""
    items_description: str = ""
    store_id: str = ""
    restaurant_id: str = ""
    order_type: str = "delivery"


@dataclass
class ParsedInvoice:
    platform: Platform
    filename: str
    parse_date: datetime
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    orders: List[ParsedOrder] = field(default_factory=list)
    fees: List[Dict] = field(default_factory=list)
    credits: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    restaurant_name: str = ""
    restaurant_id: str = ""
    summary_net_payout: float = 0.0
    summary_gross_sales: float = 0.0
    summary_total_orders: int = 0


def parse_european_number(value) -> float:
    if value is None or value == "" or (isinstance(value, float) and str(value) == 'nan'):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    value = value.replace(".", "").replace(",", ".")
    value = re.sub(r'[^\d.\-]', '', value)
    try:
        return float(value) if value else 0.0
    except ValueError:
        return 0.0
