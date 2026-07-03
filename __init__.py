from . import operators
from . import preferences


def register():
    operators.register()
    preferences.register()


def unregister():
    preferences.unregister()
    operators.unregister()
