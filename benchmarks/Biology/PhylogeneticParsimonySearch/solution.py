"""Weak legal caterpillar-tree baseline."""
def build_tree(problem):
 taxa=problem["taxa"]; tree=f"({taxa[0]},{taxa[1]})"
 for name in taxa[2:]: tree=f"({tree},{name})"
 return tree+";"
