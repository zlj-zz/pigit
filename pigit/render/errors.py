class NotRenderableError(Exception):
    """Object is not renderable."""

    pass


class StyleSyntaxError(Exception):
    """Style was badly formatted."""

    pass


class MissingStyle(Exception):
    """No such style."""

    pass
