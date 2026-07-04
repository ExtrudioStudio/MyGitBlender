from . import health
from . import operators
from . import preferences
from . import reminder


def register():
    operators.register()
    health.register()
    preferences.register()
    reminder.register()


def unregister():
    reminder.unregister()
    preferences.unregister()
    health.unregister()
    operators.unregister()
