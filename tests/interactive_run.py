import sys

sys.path.insert(0, ".")

from pigit.interaction.status_interaction import InteractiveAdd

# Initialize to debug mode.
i = InteractiveAdd(debug=False)
i.run()
