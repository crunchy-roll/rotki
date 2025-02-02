import {
  type EthereumTransactionQueryData,
  EthereumTransactionsQueryStatus
} from '@/types/websocket-messages';

export const useTxQueryStatus = defineStore(
  'history/transactionsQueryStatus',
  () => {
    const queryStatus = ref<Record<string, EthereumTransactionQueryData>>({});

    const setQueryStatus = (data: EthereumTransactionQueryData): void => {
      const status = { ...get(queryStatus) };
      const address = data.address;

      if (data.status === EthereumTransactionsQueryStatus.ACCOUNT_CHANGE) {
        return;
      }

      if (
        data.status ===
        EthereumTransactionsQueryStatus.QUERYING_TRANSACTIONS_STARTED
      ) {
        status[address] = {
          ...data,
          status: EthereumTransactionsQueryStatus.QUERYING_TRANSACTIONS
        };
      } else {
        status[address] = data;
      }

      set(queryStatus, status);
    };

    const resetQueryStatus = (): void => {
      set(queryStatus, {});
    };

    return {
      queryStatus,
      setQueryStatus,
      resetQueryStatus
    };
  }
);

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useTxQueryStatus, import.meta.hot));
}
