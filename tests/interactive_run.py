import sys

sys.path.insert(0, ".")

from pigit.interaction.status_interaction import InteractiveStatus

# Initialize to debug mode.
i = InteractiveStatus(debug=False)
i.run()
