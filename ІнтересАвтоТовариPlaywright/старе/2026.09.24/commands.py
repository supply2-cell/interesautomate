import json
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

                        # Видаляємо файл тільки після успішного читання
                        os.remove(self.command_file)

                        self.callback(command)

            except Exception as e:

                print(f"Command error: {e}")

            time.sleep(0.2)

    def _read_command(self):

        try:

            with open(
                self.command_file,
                "r",
                encoding="utf-8-sig"
            ) as file:

                text = file.read().strip()

        except (FileNotFoundError, PermissionError):

            # VBA міг саме в цей момент записувати файл.
            # Просто спробуємо ще раз на наступному циклі.
            return None

        if not text:

            return None

        try:

            command = json.loads(text)

        except json.JSONDecodeError as e:

            print(f"Invalid command JSON: {e}")

            return None

        if not isinstance(command, dict):

            print("Invalid command: expected JSON object")

            return None

        site = str(
            command.get("site", "")
        ).strip().upper()

        command_name = str(
            command.get("command", "")
        ).strip().upper()

        value = str(
            command.get("value", "")
        )

        if not site:

            print("Invalid command: missing site")

            return None

        if not command_name:

            print("Invalid command: missing command")

            return None

        return {
            "command": command_name,
            "site": site,
            "value": value
        }
