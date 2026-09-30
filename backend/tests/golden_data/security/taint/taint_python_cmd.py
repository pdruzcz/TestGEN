# Golden taint sample (Story 4.3): user input flows into an exec sink.
# Reference fixture — intentionally vulnerable.

import os


def ping(request):
    host = request.GET["host"]   # source: user_input
    command = "ping -c 1 " + host  # transform
    os.system(command)           # sink: exec (command_injection)
