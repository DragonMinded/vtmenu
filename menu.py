import argparse
import configparser
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

from vtpy import Terminal, TerminalException


class Action:
    pass


class NullAction(Action):
    pass


class SelectAction(Action):
    def __init__(self, executable: str) -> None:
        self.executable = executable


class ExitAction(Action):
    pass


class SettingAction(Action):
    def __init__(self, setting: str, value: Optional[str]) -> None:
        self.setting = setting
        self.value = value


class RendererCore:
    def __init__(self, terminal: Terminal, top: int, bottom: int) -> None:
        self.terminal = terminal
        self.top = top
        self.bottom = bottom
        self.rows = (bottom - top) + 1

    def scrollUp(self) -> None:
        pass

    def scrollDown(self) -> None:
        pass

    def pageUp(self) -> None:
        pass

    def pageDown(self) -> None:
        pass

    def goToTop(self) -> None:
        pass

    def goToBottom(self) -> None:
        pass

    def processInput(self, inputStr: str) -> Optional[Action]:
        return None


class TextRendererCore(RendererCore):
    def __init__(self, terminal: Terminal, top: int, bottom: int) -> None:
        super().__init__(terminal, top, bottom)
        self.text: List[str] = []
        self.line: int = 0

    def wordWrap(self, text: str) -> str:
        # Make things easier to deal with.
        text = text.replace("\r\n", "\n")

        newText: str = ""
        curLine: str = ""

        def joinLines() -> None:
            nonlocal newText
            nonlocal curLine

            if not curLine:
                return

            if not newText:
                newText = curLine
                curLine = ""
            else:
                if newText[-1] == "\n":
                    newText = newText + curLine
                    curLine = ""
                else:
                    newText = newText + "\n" + curLine
                    curLine = ""

        def spaceLeft() -> int:
            nonlocal curLine

            return self.terminal.columns - len(curLine)

        while text:
            if len(text) <= spaceLeft():
                # Just append the end.
                curLine += text
                text = ""
            else:
                # First, if there's a newline somewhere, see if it falls within this line.
                # if so, then just add everything up to and including it and move on.
                newlinePos = text.find("\n")
                if newlinePos >= 0:
                    chunkLen = newlinePos + 1

                    # We intentionally allow the newline to trail off because we don't auto-wrap,
                    # so it's okay to "print" it at the end since the next word will be on the
                    # new line anyway.
                    if chunkLen <= (spaceLeft() + 1):
                        curLine += text[:chunkLen]
                        text = text[chunkLen:]
                        joinLines()
                        continue

                # If we get here, our closest newline is on the next line somewhere (or beyond), or
                # does not exist. So we need to find the first space character to determine that
                # word's length.
                spacePos = text.find(" ")
                nextIsSpace = True
                if spacePos < 0:
                    # If we don't find a space, treat the entire rest of the text as a single word.
                    spacePos = len(text)
                    nextIsSpace = False

                if spacePos < spaceLeft():
                    # We have enough room to add the word AND the space.
                    if nextIsSpace:
                        curLine += text[: (spacePos + 1)]
                        text = text[(spacePos + 1) :]
                    else:
                        curLine += text[:spacePos]
                        text = text[spacePos:]
                elif spacePos == spaceLeft():
                    # We have enough room for the word but not the space, so add a newline instead.
                    if nextIsSpace:
                        curLine += text[:spacePos] + "\n"
                        text = text[(spacePos + 1) :]
                    else:
                        curLine += text[:spacePos]
                        text = text[spacePos:]
                else:
                    # We can't fit this, leave it for the next line if possible. However, if the
                    # current line is empty, that means this word is longer than wrappable. In
                    # that case, split it with a newline at the wrap point.
                    if curLine:
                        joinLines()
                    else:
                        width = spaceLeft()
                        curLine += text[:width]
                        text = text[width:]
                        joinLines()

        # Join the final line.
        joinLines()
        return newText

    def displayText(self, text: str, forceRefresh: bool = False) -> None:
        # First, we need to wordwrap the text based on the terminal's width.
        text = self.wordWrap(text)
        self.text = text.split("\n")

        # Control our scroll region, only erase the text we want.
        self.terminal.moveCursor(self.top, 1)
        self.terminal.setScrollRegion(self.top, self.bottom)

        # Display the visible chunk of text. For an initial draw, we're good
        # relying on our parent renderer to have cleared the viewport.
        self.line = 0
        self._displayText(self.line, self.line + self.rows, forceRefresh)

        # No longer need scroll region protection.
        self.terminal.clearScrollRegion()

    def scrollUp(self) -> None:
        if self.line > 0:
            self.line -= 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_UP)
            self._displayText(self.line, self.line + 1, False)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def scrollDown(self) -> None:
        if self.line < (len(self.text) - self.rows):
            self.line += 1

            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self.terminal.moveCursor(self.bottom, 1)
            self.terminal.sendCommand(Terminal.MOVE_CURSOR_DOWN)
            self._displayText(self.line + (self.rows - 1), self.line + self.rows, False)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def boundsEnforce(self, line: int) -> int:
        if line > (len(self.text) - self.rows):
            line = len(self.text) - self.rows
        if line < 0:
            line = 0
        return line

    def pageUp(self) -> None:
        line = self.boundsEnforce(self.line - (self.rows - 1))
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def pageDown(self) -> None:
        line = self.boundsEnforce(self.line + (self.rows - 1))
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def goToTop(self) -> None:
        line = self.boundsEnforce(0)
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def goToBottom(self) -> None:
        line = self.boundsEnforce(len(self.text) - self.rows)
        if line != self.line:
            self.line = line

            # Gotta redraw the whole thing.
            self.terminal.sendCommand(Terminal.SAVE_CURSOR)
            self.terminal.sendCommand(Terminal.SET_NORMAL)
            self.terminal.moveCursor(self.top, 1)
            self.terminal.setScrollRegion(self.top, self.bottom)
            self._displayText(self.line, self.line + self.rows, True)
            self.terminal.clearScrollRegion()
            self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

    def _displayText(
        self, startVisible: int, endVisible: int, wipeNonText: bool
    ) -> None:
        bolded = False
        boldRequested = False

        def sendText(text: str) -> None:
            nonlocal bolded
            nonlocal boldRequested

            if bolded != boldRequested:
                bolded = boldRequested
                if bolded:
                    self.terminal.sendCommand(Terminal.SET_BOLD)
                else:
                    self.terminal.sendCommand(Terminal.SET_NORMAL)

            self.terminal.sendText(text)

        def setBold(bold: bool) -> None:
            nonlocal boldRequested
            boldRequested = bold

        displayed = 0
        line = 0
        linkDepth = 0
        lastLine = min(self.rows + self.line, len(self.text), endVisible)
        while line < lastLine:
            # Grab the text itself, add a newline if we aren't the last line (don't want to scroll).
            text = self.text[line]
            needsClear = wipeNonText and (len(text) < self.terminal.columns)
            line += 1

            while text:
                openLinkPos = text.find("[")
                closeLinkPos = text.find("]")

                if openLinkPos < 0 and closeLinkPos < 0:
                    # No links in this line.
                    if line > startVisible:
                        sendText(text)
                    text = ""
                elif openLinkPos >= 0 and closeLinkPos < 0:
                    # Started a link in this line, but didn't end it.
                    linkDepth += 1
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        sendText(before)
                    if linkDepth == 1:
                        # Only bold on the outermost link marker.
                        setBold(True)
                    if line > startVisible:
                        sendText("[")
                elif (openLinkPos < 0 and closeLinkPos >= 0) or (
                    closeLinkPos < openLinkPos
                ):
                    # Finished a link on in this line, but there's no second start or
                    # the second start comes later.
                    after, text = text.split("]", 1)

                    if line > startVisible:
                        sendText(after)
                        sendText("]")
                    if linkDepth == 1:
                        setBold(False)

                    linkDepth -= 1
                else:
                    # There's an open and close on this line. Simply highlight it as-is. No need
                    # to handle incrementing/decrementing the depth.
                    before, text = text.split("[", 1)

                    if line > startVisible:
                        sendText(before)
                    if linkDepth == 0:
                        # Only bold on the outermost link marker.
                        setBold(True)
                    if line > startVisible:
                        sendText("[")

                    after, text = text.split("]", 1)

                    if line > startVisible:
                        sendText(after)
                        sendText("]")
                    if linkDepth == 0:
                        setBold(False)

            if line > startVisible:
                displayed += 1

                if needsClear:
                    self.terminal.sendCommand(Terminal.CLEAR_TO_END_OF_LINE)

                if line != endVisible:
                    self.terminal.sendText("\n")

        if wipeNonText:
            clearAmount = endVisible - startVisible
            while displayed < clearAmount:
                self.terminal.sendCommand(Terminal.CLEAR_LINE)

                if displayed < (self.rows - 1):
                    self.terminal.sendText("\n")

                displayed += 1


class Renderer:
    def __init__(self, terminal: Terminal) -> None:
        self.terminal = terminal
        self.input = ""
        self.options: List[str] = []
        self.lastError = ""
        self.renderer = RendererCore(terminal, 3, self.terminal.rows - 2)

    def displayMenu(self, settings: Dict[str, str]) -> None:
        # Render status bar at the bottom.
        self.clearInput()

        # First, wipe the screen and display the title.
        self.terminal.moveCursor(self.terminal.rows - 2, 1)
        self.terminal.sendCommand(Terminal.CLEAR_LINE)
        self.terminal.sendCommand(Terminal.CLEAR_TO_ORIGIN)
        self.terminal.sendCommand(Terminal.MOVE_CURSOR_ORIGIN)

        # Reset text display and put title up.
        self.terminal.setAutoWrap()
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_BOLD)
        self.terminal.sendText("Dragon's Lair Control Terminal Main Menu")
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.clearAutoWrap()

        # Render out the text of the page.
        entries: List[str] = []
        options: List[str] = []
        for index, (key, value) in enumerate(settings.items()):
            entries.append(f"[!{index + 1}] {key}")
            options.append(value)
        self.options = options

        text = (
            'The following programs are available. To run, type "!" followed '
            + "by the selection number and press enter.\n\n"
            + "\n".join(entries)
        )
        self.renderer = TextRendererCore(self.terminal, 3, self.terminal.rows - 2)
        self.renderer.displayText(text)

        # Move cursor to where we expect it for input.
        self.terminal.moveCursor(self.terminal.rows, 1)

    def clearInput(self) -> None:
        # Clear error display.
        self.clearError()

        self.terminal.moveCursor(self.terminal.rows, 1)
        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_REVERSE)
        self.terminal.sendText(" " * self.terminal.columns)
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)

        # Clear command.
        self.input = ""

    def clearError(self) -> None:
        self.displayError("")

    def displayError(self, error: str) -> None:
        if error == self.lastError:
            return

        self.terminal.sendCommand(Terminal.SAVE_CURSOR)
        self.terminal.moveCursor(self.terminal.rows - 1, 1)
        self.terminal.sendCommand(Terminal.CLEAR_LINE)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.SET_BOLD)
        self.terminal.sendText(error)
        self.terminal.sendCommand(Terminal.SET_NORMAL)
        self.terminal.sendCommand(Terminal.RESTORE_CURSOR)
        self.lastError = error

    def processInput(self, inputVal: bytes) -> Optional[Action]:
        row, col = self.terminal.fetchCursor()
        if inputVal == Terminal.LEFT:
            if col > 1:
                col -= 1
                self.terminal.moveCursor(row, col)
        elif inputVal == Terminal.RIGHT:
            if col < (len(self.input) + 1):
                col += 1
                self.terminal.moveCursor(row, col)
        elif inputVal == Terminal.UP:
            self.renderer.scrollUp()
        elif inputVal == Terminal.DOWN:
            self.renderer.scrollDown()
        elif inputVal in {Terminal.BACKSPACE, Terminal.DELETE}:
            if self.input:
                # Just subtract from input.
                if col == len(self.input) + 1:
                    # Erasing at the end of the line.
                    self.input = self.input[:-1]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
                elif col == 1:
                    # Erasing at the beginning, do nothing.
                    pass
                elif col == 2:
                    # Erasing at the beginning of the line.
                    self.input = self.input[1:]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(self.input)
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
                else:
                    # Erasing in the middle of the line.
                    spot = col - 2
                    self.input = self.input[:spot] + self.input[(spot + 1) :]

                    col -= 1
                    self.terminal.moveCursor(row, col)
                    self.terminal.sendCommand(Terminal.SET_NORMAL)
                    self.terminal.sendCommand(Terminal.SET_REVERSE)
                    self.terminal.sendText(self.input[spot:])
                    self.terminal.sendText(" ")
                    self.terminal.moveCursor(row, col)
        elif inputVal == b"\r":
            # Ignore this.
            pass
        elif inputVal == b"\n":
            # Execute command.
            actual = self.input.strip()
            if not actual:
                return None

            # First, try to delegate to the actual page.
            subResponse = self.renderer.processInput(actual)
            if subResponse is not None:
                return subResponse

            if actual[0] == "!":
                # Link navigation.
                try:
                    link = int(actual[1:].strip())
                    link -= 1

                    if link < 0 or link >= len(self.options):
                        self.displayError("Unknown menu option!")
                    else:
                        return SelectAction(self.options[link])
                except ValueError:
                    self.displayError("Invalid link navigation request!")
            elif actual == "set" or actual.startswith("set "):
                if " " not in actual:
                    self.displayError("No setting requested!")
                else:
                    _, setting = actual.split(" ", 1)
                    setting = setting.strip()

                    if "=" in setting:
                        setting, value = setting.split("=", 1)
                        setting = setting.strip()
                        value = value.strip()
                    else:
                        setting = setting.strip()
                        value = None

                    return SettingAction(setting, value)
            else:
                self.displayError(f"Unrecognized command {actual}")
        else:
            if len(self.input) < (self.terminal.columns - 1):
                # If we got some unprintable character, ignore it.
                inputVal = bytes(v for v in inputVal if v >= 0x20)
                if inputVal:
                    # Just add to input.
                    char = inputVal.decode("ascii")

                    if col == len(self.input) + 1:
                        # Just appending to the input.
                        self.input += char
                        self.terminal.sendCommand(Terminal.SET_NORMAL)
                        self.terminal.sendCommand(Terminal.SET_REVERSE)
                        self.terminal.sendText(char)
                        self.terminal.moveCursor(row, col + 1)
                    else:
                        # Adding to mid-input.
                        spot = col - 1
                        self.input = self.input[:spot] + char + self.input[spot:]

                        self.terminal.sendCommand(Terminal.SET_NORMAL)
                        self.terminal.sendCommand(Terminal.SET_REVERSE)
                        self.terminal.sendText(self.input[spot:])
                        self.terminal.moveCursor(row, col + 1)

        # Nothing happening here!
        return None


def spawnTerminalAndRenderer(port: str, baudrate: int) -> Tuple[Terminal, Renderer]:
    print("Attempting to contact VT-100...", end="")
    sys.stdout.flush()

    while True:
        try:
            terminal = Terminal(port, baudrate)
            print("SUCCESS!")

            break
        except TerminalException:
            # Wait for terminal to re-awaken.
            time.sleep(1.0)

            print(".", end="")
            sys.stdout.flush()

    return terminal, Renderer(terminal)


def main(settings: str, port: str, baudrate: int) -> int:
    # Parse out options.
    cfg = configparser.ConfigParser()
    cfg.read(settings)

    settingsDict: Dict[str, str] = {}
    for section in cfg.sections():
        for key, val in cfg.items(section):
            if key == "cmd":
                settingsDict[section] = val

    exiting = False
    while not exiting:
        # The runnable command, if we have something to run.
        cmd: Optional[str] = None

        # First, render the current page to the display.
        terminal, renderer = spawnTerminalAndRenderer(port, baudrate)
        renderer.displayMenu(settingsDict)
        renderer.clearInput()

        try:
            while cmd is None and not exiting:
                # Grab input, de-duplicate held down up/down presses so they don't queue up.
                # This can cause the entire message loop to desync as we pile up requests to
                # scroll the screen, ultimately leading in rendering issues and a crash.
                inputVal = terminal.recvInput()
                if inputVal in {Terminal.UP, Terminal.DOWN}:
                    while inputVal == terminal.peekInput():
                        terminal.recvInput()

                if inputVal:
                    action = renderer.processInput(inputVal)
                    if isinstance(action, SelectAction):
                        renderer.displayError("Loading requested program...")
                        cmd = action.executable
                    elif isinstance(action, SettingAction):
                        if action.setting in {"cols", "columns"}:
                            if action.value not in {"80", "132"}:
                                renderer.displayError(
                                    f"Unrecognized column setting {action.value}"
                                )
                            elif action.value == "80":
                                if terminal.columns != 80:
                                    terminal.set80Columns()
                                    renderer.displayMenu(settingsDict)
                                else:
                                    renderer.clearInput()
                            elif action.value == "132":
                                if terminal.columns != 132:
                                    terminal.set132Columns()
                                    renderer.displayMenu(settingsDict)
                                else:
                                    renderer.clearInput()
                        else:
                            renderer.displayError(
                                f"Unrecognized setting {action.setting}"
                            )
                    elif isinstance(action, ExitAction):
                        print("Got request to end session!")
                        exiting = True
        except TerminalException:
            # Terminal went away mid-transaction.
            print("Lost terminal, will attempt a reconnect.")
        except KeyboardInterrupt:
            print("Got request to end session!")
            exiting = True

        if cmd is not None:
            # Execute the command itself, wait for the command to finish, and then redisplay.
            del terminal
            os.system(cmd)
        else:
            # Restore the screen before exiting.
            terminal.reset()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VT-100 terminal menu")

    parser.add_argument(
        "--port",
        default="/dev/ttyUSB0",
        type=str,
        help="Serial port to open, defaults to /dev/ttyUSB0",
    )
    parser.add_argument(
        "--baud",
        default=9600,
        type=int,
        help="Baud rate to use with VT-100, defaults to 9600",
    )
    parser.add_argument(
        "--settings",
        default="settings.ini",
        type=str,
        help="Settings file to parse for menu entries",
    )
    args = parser.parse_args()

    sys.exit(main(args.settings, args.port, args.baud))
