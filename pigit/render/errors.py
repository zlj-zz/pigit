class NotRenderableError(Exception):
    """Object is not renderable."""

    pass


class ColorError(Exception):
    """The error of ``Color`` class."""

    pass


class StyleSyntaxError(Exception):
    """Style was badly formatted."""

    pass


class MissingStyle(Exception):
    """No such style."""

    pass
