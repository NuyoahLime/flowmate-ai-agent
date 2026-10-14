class TriggerError(Exception):
    pass


class TriggerConfigurationError(TriggerError):
    pass


class TriggerPersistenceError(TriggerError):
    pass


class TriggerEvaluationError(TriggerError):
    pass


class TriggerTaskCreationError(TriggerError):
    pass
