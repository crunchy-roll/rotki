import { type SemiPartial } from '@rotki/common';
import {
  type NotificationData,
  type NotificationPayload,
  Severity
} from '@rotki/common/lib/messages';
import { useSessionApi } from '@/services/session';
import { SocketMessageType } from '@/types/websocket-messages';
import { backoff } from '@/utils/backoff';
import { uniqueStrings } from '@/utils/data';
import { logger } from '@/utils/logging';
import {
  handleEthereumTransactionStatus,
  handleLegacyMessage,
  handleLoginStatus,
  handleSnapshotError
} from '@/utils/message-handling';

const notificationDefaults = (): NotificationPayload => ({
  title: '',
  message: '',
  severity: Severity.ERROR,
  display: false
});

const createNotification = (
  id = 0,
  { display, duration, message, severity, title }: NotificationPayload = {
    title: '',
    message: '',
    severity: Severity.INFO
  }
): NotificationData => ({
  title,
  message,
  severity,
  display: display ?? false,
  duration: duration ?? 5000,
  id,
  date: new Date()
});

export const emptyNotification = (): NotificationData => createNotification();

export const useNotificationsStore = defineStore('notifications', () => {
  const data = ref<NotificationData[]>([]);
  const { tc } = useI18n();
  const { consumeMessages } = useSessionApi();
  let isRunning = false;

  const count = computed(() => get(data).length);
  const nextId = computed(() => {
    const ids = get(data)
      .map(value => value.id)
      .sort((a, b) => b - a);

    let nextId: number;
    if (ids.length > 0) {
      nextId = ids[0] + 1;
    } else {
      nextId = 1;
    }
    return nextId;
  });
  const queue = computed(() =>
    get(data).filter(notification => notification.display)
  );

  function update(payload: NotificationData[]): void {
    set(data, [...get(data), ...payload]);
  }

  function remove(id: number): void {
    const notifications = [...get(data)];

    const index = notifications.findIndex(v => v.id === id);
    if (index > -1) {
      notifications.splice(index, 1);
    }

    set(data, notifications);
  }

  function setNotifications(notifications: NotificationData[]): void {
    set(data, notifications);
  }

  const notify = (
    data: SemiPartial<NotificationPayload, 'title' | 'message'>
  ): void => {
    update([
      createNotification(
        get(nextId),
        Object.assign(notificationDefaults(), data)
      )
    ]);
  };

  const displayed = (ids: number[]): void => {
    if (ids.length <= 0) {
      return;
    }

    const notifications = [...get(data)];
    for (const id of ids) {
      const index = notifications.findIndex(({ id: idA }) => idA === id);
      if (index < 0) {
        continue;
      }
      notifications[index] = { ...notifications[index], display: false };
    }
    setNotifications(notifications);
  };

  const handleNotification = async (
    message: string,
    isWarning: boolean
  ): Promise<void> => {
    try {
      const object = JSON.parse(message);
      if (!object.type) {
        notify(handleLegacyMessage(message, isWarning, tc));
      }

      if (object.type === SocketMessageType.BALANCES_SNAPSHOT_ERROR) {
        notify(handleSnapshotError(object, tc));
      } else if (
        object.type === SocketMessageType.ETHEREUM_TRANSACTION_STATUS
      ) {
        await handleEthereumTransactionStatus(object);
      } else if (object.type === SocketMessageType.LOGIN_STATUS) {
        await handleLoginStatus(object);
      } else {
        logger.error('unsupported message:', message);
      }
    } catch {
      notify(handleLegacyMessage(message, isWarning, tc));
    }
  };

  const consume = async (): Promise<void> => {
    if (isRunning) {
      return;
    }

    isRunning = true;
    const title = tc('actions.notifications.consume.message_title');

    try {
      const messages = await backoff(3, () => consumeMessages(), 10000);
      const existing = get(data).map(({ message }) => message);
      messages.errors
        .filter(uniqueStrings)
        .filter(error => !existing.includes(error))
        .forEach(message => handleNotification(message, false));
      messages.warnings
        .filter(uniqueStrings)
        .filter(warning => !existing.includes(warning))
        .forEach(message => handleNotification(message, true));
    } catch (e: any) {
      const message = e.message || e;
      notify({
        title,
        message,
        display: true
      });
    } finally {
      isRunning = false;
    }
  };

  return {
    data,
    count,
    nextId,
    queue,
    notify,
    displayed,
    remove,
    consume
  };
});
