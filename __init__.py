from . import operators
from . import preferences
from . import reminder


def register():
    operators.register()
    preferences.register()
    reminder.register()


def unregister():
    reminder.unregister()
    preferences.unregister()
    operators.unregister()
