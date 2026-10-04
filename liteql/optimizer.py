from .logical_plan import Filter, Limit, Project, Scan, Sort


def optimize(plan):
    """Apply the two documented transformations: predicate then projection pushdown."""
    plan = _push_predicate(plan)
    return _push_projection(plan)


def _push_predicate(node):
    if isinstance(node, Filter) and isinstance(node.child, Scan):
        return Scan(node.child.source, node.child.columns, node.condition)
    if isinstance(node, (Project, Sort, Limit)):
        return type(node)(_push_predicate(node.child), *list(node.__dict__.values())[1:])
    if isinstance(node, Filter): return Filter(_push_predicate(node.child), node.condition)
    return node


def _push_projection(node):
    required = _required(node)
    return _set_scan_columns(node, required)


def _required(node):
    if isinstance(node, Scan): return set()
    needed = _required(node.child)
    if isinstance(node, Project) and node.columns is not None: needed.update(node.columns)
    if isinstance(node, Sort): needed.add(node.column)
    if isinstance(node, Filter): needed.update(_condition_columns(node.condition))
    return needed


def _condition_columns(node):
    from .ast import BinaryCondition, ColumnReference
    if isinstance(node, BinaryCondition): return _condition_columns(node.left) | _condition_columns(node.right)
    result = {node.column.name}
    if isinstance(node.value, ColumnReference): result.add(node.value.name)
    return result


def _set_scan_columns(node, columns):
    if isinstance(node, Scan): return Scan(node.source, tuple(sorted(columns)) or None, node.predicate)
    return type(node)(_set_scan_columns(node.child, columns), *list(node.__dict__.values())[1:])
