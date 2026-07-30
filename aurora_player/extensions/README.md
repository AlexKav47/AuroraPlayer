# Aurora Player extensions

An extension is a Python file with a `register(application)` function.

The application object exposes `new_window(path=None)` and a `windows` list.
Extensions run with the same permissions as the player, so install only code
you trust.
