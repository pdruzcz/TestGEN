# Golden taint fixture (Story 4.14): request input flows into an exec sink.
# Intentionally vulnerable reference sample for taint-analysis regression tests.

import os


def backup(request):
    target = request.GET["path"]              # source: user_input
    command = "tar -czf backup.tgz " + target  # transform
    os.system(command)                         # sink: exec (command_injection)
