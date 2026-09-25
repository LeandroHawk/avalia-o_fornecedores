import os
import sys

from django.core.management import execute_from_command_line


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    args = sys.argv
    if len(args) == 1:
        args = [args[0], "runserver"]
    execute_from_command_line(args)


if __name__ == "__main__":
    main()
