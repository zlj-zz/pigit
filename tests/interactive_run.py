import sys

sys.path.insert(0, ".")

from pigit import InteractiveAdd

# Initialize to debug mode.
i = InteractiveAdd(debug=True)
i.add_interactive()
