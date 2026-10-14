class CrossDeviceError(Exception):
    pass


class CrossDeviceNotFoundError(CrossDeviceError):
    pass


class CrossDeviceValidationError(CrossDeviceError):
    pass


class CrossDeviceAuthorizationError(CrossDeviceError):
    pass


class CrossDeviceConflictError(CrossDeviceError):
    pass
