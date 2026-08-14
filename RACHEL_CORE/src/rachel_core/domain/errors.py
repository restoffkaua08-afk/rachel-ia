class RachelError(Exception):
    code = "RACHEL_ERROR"


class ValidationError(RachelError):
    code = "VALIDATION_ERROR"


class ModelError(RachelError):
    code = "MODEL_ERROR"


class StorageError(RachelError):
    code = "STORAGE_ERROR"


class AuthorizationError(RachelError):
    code = "AUTHORIZATION_ERROR"

