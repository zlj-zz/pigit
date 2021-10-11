import sys

from black import main

sys.path.insert(0, ".")

from pigit.interaction.status_interaction import InteractiveStatus
from pigit.interaction.commit_interaction import InteractiveCommit


def status():
    # Initialize to debug mode.
    i = InteractiveStatus(debug=False)
    i.run()


def commit():
    i = InteractiveCommit()
    i.run()


commit()
