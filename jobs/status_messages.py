from enum import Enum

from celery import states


class StatusMessage(str, Enum):
    FAIL = 'Failed'
    SUCCESS = 'Finished successfully'
    IN_PROGRESS = 'In progress'


status_messages_mapping = {
    states.FAILURE: StatusMessage.FAIL.value,
    states.SUCCESS: StatusMessage.SUCCESS.value,
}
