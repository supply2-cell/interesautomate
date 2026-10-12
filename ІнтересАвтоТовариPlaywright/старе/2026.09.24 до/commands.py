import os
import threading
import time


class CommandListener:

    def __init__(self, command_file, callback):
        self.command_file = command_file
        self.callback = callback
        self.running = True

    def start(self):
        thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        while self.running:

            try:
                if os.path.exists(self.command_file):

                    command = self._read_command()

                    if command is not None:
                        os.remove(self.command_file)
                        self.callback(command)

            except Exception as e:
                print(f"Command error: {e}")

            time.sleep(0.2)

    def _read_command(self):

        with open(
            self.command_file,
            "r",
            encoding="utf-8-sig"
        ) as file:

            line = file.readline().strip()

        if not line:
            return None

        parts = line.split(" ", 2)

        if len(parts) < 2:
            return None

        command = parts[0].upper()
        site = parts[1].upper()

        value = ""

        if len(parts) == 3:
            value = parts[2]

        return {
            "command": command,
            "site": site,
            "value": value
        }