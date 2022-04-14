import logging
from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
    overload,
)

from pysqlcipher3 import dbapi2 as sqlcipher

from rotkehlchen.accounting.constants import FREE_PNL_EVENTS_LIMIT, FREE_REPORTS_LOOKUP_LIMIT
from rotkehlchen.accounting.pnl import PnlTotals
from rotkehlchen.accounting.structures.processed_event import ProcessedAccountingEvent
from rotkehlchen.db.filtering import ReportDataFilterQuery
from rotkehlchen.db.settings import DBSettings
from rotkehlchen.errors import DeserializationError, InputError
from rotkehlchen.logging import RotkehlchenLogsAdapter
from rotkehlchen.types import Timestamp
from rotkehlchen.utils.misc import ts_now

logger = logging.getLogger(__name__)
log = RotkehlchenLogsAdapter(logger)

if TYPE_CHECKING:
    from rotkehlchen.db.dbhandler import DBHandler


@overload
def _get_reports_or_events_maybe_limit(
        entry_type: Literal['events'],
        entries_found: int,
        entries: List[ProcessedAccountingEvent],
        with_limit: bool,
) -> Tuple[List[ProcessedAccountingEvent], int]:
    ...


@overload
def _get_reports_or_events_maybe_limit(
        entry_type: Literal['reports'],
        entries_found: int,
        entries: List[Dict[str, Any]],
        with_limit: bool,
) -> Tuple[List[Dict[str, Any]], int]:
    ...


def _get_reports_or_events_maybe_limit(
        entry_type: Literal['events', 'reports'],
        entries_found: int,
        entries: Union[List[Dict[str, Any]], List[ProcessedAccountingEvent]],
        with_limit: bool,
) -> Tuple[Union[List[Dict[str, Any]], List[ProcessedAccountingEvent]], int]:
    if with_limit is False:
        return entries, entries_found

    if entry_type == 'events':
        limit = FREE_PNL_EVENTS_LIMIT
    elif entry_type == 'reports':
        limit = FREE_REPORTS_LOOKUP_LIMIT

    returning_entries_length = min(limit, len(entries))
    return entries[:returning_entries_length], entries_found


class DBAccountingReports():

    def __init__(self, database: 'DBHandler'):
        self.db = database

    def add_report(
            self,
            first_processed_timestamp: Timestamp,
            start_ts: Timestamp,
            end_ts: Timestamp,
            settings: DBSettings,
    ) -> int:
        cursor = self.db.conn_transient.cursor()
        timestamp = ts_now()
        query = """
        INSERT INTO pnl_reports(
            timestamp, start_ts, end_ts, first_processed_timestamp,
            last_processed_timestamp, processed_actions, total_actions
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)"""
        cursor.execute(
            query,
            (timestamp, start_ts, end_ts, first_processed_timestamp,
             0, 0, 0,  # will be set later
             ),
        )
        report_id = cursor.lastrowid
        cursor.executemany(
            'INSERT OR IGNORE INTO pnl_report_settings(report_id, name, type, value) '
            'VALUES(?, ?, ?, ?)',
            [
                (report_id, 'profit_currency', 'string', settings.main_currency.identifier),
                (report_id, 'taxfree_after_period', 'integer', settings.taxfree_after_period),
                (report_id, 'include_crypto2crypto', 'bool', settings.include_crypto2crypto),
                (report_id, 'calculate_past_cost_basis', 'bool', settings.calculate_past_cost_basis),  # noqa: E501
                (report_id, 'include_gas_costs', 'bool', settings.include_gas_costs),
                (report_id, 'account_for_assets_movements', 'bool', settings.account_for_assets_movements),  # noqa: E501
            ])
        self.db.conn_transient.commit()
        return report_id

    def add_report_overview(
            self,
            report_id: int,
            last_processed_timestamp: Timestamp,
            processed_actions: int,
            total_actions: int,
            pnls: PnlTotals,
    ) -> None:
        """Inserts the report overview data

        May raise:
        - InputError if the given report id does not exist
        """
        cursor = self.db.conn_transient.cursor()
        cursor.execute(
            'UPDATE pnl_reports SET last_processed_timestamp=?,'
            ' processed_actions=?, total_actions=? WHERE identifier=?',
            (last_processed_timestamp, processed_actions, total_actions, report_id),
        )
        if cursor.rowcount != 1:
            raise InputError(
                f'Could not insert overview for {report_id}. '
                f'Report id could not be found in the DB',
            )

        tuples = []
        for event_type, entry in pnls.items():
            tuples.append((report_id, event_type.serialize(), str(entry.taxable), str(entry.free)))  # noqa: E501
        cursor.executemany(
            'INSERT OR IGNORE INTO pnl_report_totals(report_id, name, taxable_value, free_value) VALUES(?, ?, ?, ?)',  # noqa: E501
            tuples,
        )
        self.db.conn_transient.commit()

    def _get_report_size(self, report_id: int) -> int:
        """Returns an approximation of the DB size in bytes for the given report.

        It's an approximation since length() in sqlite returns the string length
        and not the byte length of a field. Also integers are stored depending on
        their size and there is no easy way (apart from checking each integer) to
        figure out the byte size. Finally there probably is various padding and
        prefixes which are not taken into account.
        """
        cursor = self.db.conn_transient.cursor()
        result = cursor.execute(
            """SELECT SUM(row_size) FROM (SELECT
            8 + /*identifier - assume biggest int size */
            8 + /*report_id  - assume biggest int size */
            8 + /*timestamp  - assume biggest int size */
            1 + /*event_type */
            length(data) AS row_size FROM pnl_events WHERE report_id=?)""",
            (report_id,),
        ).fetchone()[0]
        return 0 if result is None else result

    def get_reports(
            self,
            report_id: Optional[int],
            with_limit: bool,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Queries all historical saved PnL reports.

        If `with_limit` is true then the api limit is applied
        """
        cursor = self.db.conn_transient.cursor()
        bindings: Union[Tuple, Tuple[int]] = ()
        query = 'SELECT * from pnl_reports'
        if report_id is not None:
            bindings = (report_id,)
            query += ' WHERE identifier=?'
        results = cursor.execute(query, bindings)

        reports: List[Dict[str, Any]] = []
        for report in results:
            this_report_id = report[0]
            size_result = self._get_report_size(this_report_id)
            other_cursor = self.db.conn_transient.cursor()
            other_cursor.execute(
                'SELECT name, taxable_value, free_value FROM pnl_report_totals WHERE report_id=?',
                (this_report_id,),
            )
            overview = {x[0]: {'taxable': x[1], 'free': x[2]} for x in other_cursor}
            other_cursor.execute(
                'SELECT name, type, value FROM pnl_report_settings WHERE report_id=?',
                (this_report_id,),
            )
            settings = {}
            for x in other_cursor:
                if x[1] == 'integer':
                    settings[x[0]] = int(x[2])
                elif x[1] == 'bool':
                    settings[x[0]] = x[2] == '1'
                else:
                    settings[x[0]] = x[2]
            reports.append({
                'identifier': this_report_id,
                'timestamp': report[1],
                'start_ts': report[2],
                'end_ts': report[3],
                'first_processed_timestamp': report[4],
                'size_on_disk': size_result,
                'last_processed_timestamp': report[5],
                'processed_actions': report[6],
                'total_actions': report[7],
                'overview': overview,
                'settings': settings,
            })

        if report_id is not None:
            results = cursor.execute('SELECT COUNT(*) FROM pnl_reports').fetchone()
            total_filter_count = results[0]
        else:
            total_filter_count = len(reports)

        return _get_reports_or_events_maybe_limit(
            entry_type='reports',
            entries=reports,
            entries_found=total_filter_count,
            with_limit=with_limit,
        )

    def purge_report_data(self, report_id: int) -> None:
        """Deletes all report data of the given report from the DB

        Raises InputError if the report did not exist in the DB.
        """
        cursor = self.db.conn_transient.cursor()
        cursor.execute('DELETE FROM pnl_reports WHERE identifier=?', (report_id,))
        if cursor.rowcount != 1:
            raise InputError(
                f'Could not delete PnL report {report_id} from the DB. Report was not found',
            )
        self.db.conn.commit()
        self.db.update_last_write()

    def add_report_data(
            self,
            report_id: int,
            time: Timestamp,
            ts_converter: Callable[[Timestamp], str],
            event: ProcessedAccountingEvent,
    ) -> None:
        """Adds a new entry to a transient report for the PnL history in a given time range
        May raise:
        - DeserializationError if there is a conflict at serialization of the event
        - InputError if the event can not be written to the DB. Probably report id does not exist.
        """
        cursor = self.db.conn_transient.cursor()
        data = event.serialize_for_db(ts_converter)
        query = """
        INSERT INTO pnl_events(
            report_id, timestamp, data
        )
        VALUES(?, ?, ?);"""
        try:
            cursor.execute(query, (report_id, time, data))
        except sqlcipher.IntegrityError as e:  # pylint: disable=no-member
            raise InputError(
                f'Could not write {event} data to the DB due to {str(e)}. '
                f'Probably report {report_id} does not exist?',
            ) from e
        self.db.conn_transient.commit()

    def get_report_data(
            self,
            filter_: ReportDataFilterQuery,
            with_limit: bool,
    ) -> Tuple[List[ProcessedAccountingEvent], int]:
        """Retrieve the event data of a PnL report depending on the given filter

        May raise:
        - InputError if the report ID does not exist in the DB
        """
        cursor = self.db.conn_transient.cursor()
        report_id = filter_.report_id
        query_result = cursor.execute(
            'SELECT COUNT(*) FROM pnl_reports WHERE identifier=?',
            (report_id,),
        )
        if query_result.fetchone()[0] != 1:
            raise InputError(
                f'Tried to get PnL events from non existing report with id {report_id}',
            )

        query, bindings = filter_.prepare()
        query = 'SELECT timestamp, data FROM pnl_events ' + query
        results = cursor.execute(query, bindings)

        records = []
        for result in results:
            try:
                record = ProcessedAccountingEvent.deserialize_from_db(result[0], result[1])
            except DeserializationError as e:
                self.db.msg_aggregator.add_error(
                    f'Error deserializing AccountingEvent from the DB. Skipping it.'
                    f'Error was: {str(e)}',
                )
                continue

            records.append(record)

        if filter_.pagination is not None:
            no_pagination_filter = deepcopy(filter_)
            no_pagination_filter.pagination = None
            query, bindings = no_pagination_filter.prepare()
            query = 'SELECT COUNT(*) FROM pnl_events ' + query
            results = cursor.execute(query, bindings).fetchone()
            total_filter_count = results[0]
        else:
            total_filter_count = len(records)

        return _get_reports_or_events_maybe_limit(
            entry_type='events',
            entries_found=total_filter_count,
            entries=records,
            with_limit=with_limit,
        )