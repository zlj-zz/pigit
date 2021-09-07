# -*- coding: utf-8 -*-

# Pomodoro 番茄工作法 https://en.wikipedia.org/wiki/Pomodoro_Technique
# ====== 🍅 Tomato Clock =======
# ./tomato.py         # start a 25 minutes tomato clock + 5 minutes break
# ./tomato.py -t      # start a 25 minutes tomato clock
# ./tomato.py -t <n>  # start a <n> minutes tomato clock
# ./tomato.py -b      # take a 5 minutes break
# ./tomato.py -b <n>  # take a <n> minutes break
# ./tomato.py -h      # help


import sys
import time
import subprocess

WORK_MINUTES = 25
BREAK_MINUTES = 5


def main(command_str=[]):
    if not command_str:
        args = sys.argv
    else:
        args = command_str
    try:
        if len(args) <= 1:
            print("🍅 tomato {} minutes. Ctrl+C to exit".format(WORK_MINUTES))
            tomato(WORK_MINUTES, "It is time to take a break")
            print("🛀 break {} minutes. Ctrl+C to exit".format(BREAK_MINUTES))
            tomato(BREAK_MINUTES, "It is time to work")

        elif args[1] == "-t":
            minutes = int(args[2]) if len(args) > 2 else WORK_MINUTES
            print("🍅 tomato {} minutes. Ctrl+C to exit".format(minutes))
            tomato(minutes, "It is time to take a break")

        elif args[1] == "-b":
            minutes = int(args[2]) if len(args) > 2 else BREAK_MINUTES
            print("🛀 break {} minutes. Ctrl+C to exit".format(minutes))
            tomato(minutes, "It is time to work")

        elif args[1] == "-h":
            help(args[0])

        else:
            help(args[0])

    except KeyboardInterrupt:
        print("\n👋 goodbye")
    except Exception as e:
        print(str(e), str(e.__traceback__))


def tomato(minutes, notify_msg):
    start_time = time.time()
    while True:
        diff_seconds = int(round(time.time() - start_time))
        left_seconds = minutes * 60 - diff_seconds
        if left_seconds <= 0:
            print("")
            break

        countdown = "{}:{} ⏰".format(int(left_seconds / 60), int(left_seconds % 60))
        duration = min(minutes, 25)
        progressbar(diff_seconds, minutes * 60, duration, countdown)
        time.sleep(1)

    notify_me(notify_msg)


def progressbar(current, total, duration=10, extra=""):
    frac = current / total
    filled = int(round(frac * duration))
    print(
        "\r",
        "🍅" * filled + "--" * (duration - filled),
        "[{:.0%}]".format(frac),
        extra,
        end="",
    )
    sys.stdout.flush()


def notify_me(msg):
    """
    # macos desktop notification
    terminal-notifier -> https://github.com/julienXX/terminal-notifier#download
    terminal-notifier -message <msg>
    # ubuntu desktop notification
    notify-send
    # voice notification
    say -v <lang> <msg>
    lang options:
    - Daniel:       British English
    - Ting-Ting:    Mandarin
    - Sin-ji:       Cantonese
    """

    print(msg)
    try:
        if sys.platform == "darwin":
            # macos desktop notification
            subprocess.run(["terminal-notifier", "-title", "🍅", "-message", msg])
            subprocess.run(["say", "-v", "Daniel", msg])
        elif sys.platform.startswith("linux"):
            # ubuntu desktop notification
            subprocess.Popen(["notify-send", "🍅", msg])
        else:
            # windows?
            # TODO: windows notification
            pass

    except:
        # skip the notification error
        pass


def help(appname):
    appname = appname if appname.endswith(".py") else "tomato"  # tomato is pypi package
    print("====== 🍅 Tomato Clock =======")
    print(
        "{0}         # start a {1} minutes tomato clock + {2} minutes break".format(
            appname, WORK_MINUTES, BREAK_MINUTES
        )
    )
    print(
        "{0} -t      # start a {1} minutes tomato clock".format(appname, WORK_MINUTES)
    )
    print("{0} -t <n>  # start a <n> minutes tomato clock".format(appname))
    print("{0} -b      # take a {1} minutes break".format(appname, BREAK_MINUTES))
    print("{0} -b <n>  # take a <n> minutes break".format(appname))
    print("{0} -h      # help".format(appname))


if __name__ == "__main__":
    main()
