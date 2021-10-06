import sys

sys.path.insert(0, ".")

from pigit.interaction.interaction import InteractiveAdd

# Initialize to debug mode.
i = InteractiveAdd(debug=True)
i.add_interactive()
