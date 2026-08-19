class RunVersionConflict(Exception):
    """Raised when a run was modified by another worker."""