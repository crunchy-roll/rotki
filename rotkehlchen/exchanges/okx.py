from typing import Any, Optional

from rotkehlchen.accounting.ledger_actions import LedgerAction
from rotkehlchen.exchanges.data_structures import AssetMovement, MarginPosition, Trade
from rotkehlchen.exchanges.exchange import ExchangeInterface, ExchangeQueryBalances
from rotkehlchen.types import Timestamp, ApiKey, ApiSecret, Location


class Okx(ExchangeInterface):
    def __init__(self, name: str, location: Location, api_key: ApiKey, secret: ApiSecret, database: 'DBHandler'):
        super().__init__(
            name=name,
            location=location,
            api_key=api_key,
            secret=secret,
            database=database
        )

    def edit_exchange_credentials(
            self,
            api_key: Optional[ApiKey],
            api_secret: Optional[ApiSecret],
            passphrase: Optional[str],
    ) -> bool:
        pass

    def query_balances(self, **kwargs: Any) -> ExchangeQueryBalances:
        pass

    def first_connection(self) -> None:
        pass

    def validate_api_key(self) -> tuple[bool, str]:
        pass

    def query_online_trade_history(self, start_ts: Timestamp, end_ts: Timestamp) -> tuple[
        list[Trade], tuple[Timestamp, Timestamp]]:
        pass

    def query_online_margin_history(self, start_ts: Timestamp, end_ts: Timestamp) -> list[MarginPosition]:
        pass

    def query_online_deposits_withdrawals(self, start_ts: Timestamp, end_ts: Timestamp) -> list[AssetMovement]:
        pass

    def query_online_income_loss_expense(self, start_ts: Timestamp, end_ts: Timestamp) -> list[LedgerAction]:
        pass
