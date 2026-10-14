class PersistenceError(Exception):
    pass


class PersistenceConfigurationError(PersistenceError):
    pass


class PersistenceSerializationError(PersistenceError):
    pass


class PersistenceIntegrityError(PersistenceError):
    pass
