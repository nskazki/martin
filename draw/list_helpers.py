def wrap_list(value):
    if isinstance(value, list):
        return value
    elif value is None:
        return []
    else:
        return [value]

def flatten_list(nested_list):
    flattened = []
    for item in nested_list:
        if isinstance(item, list):
            flattened.extend(flatten_list(item))
        else:
            flattened.append(item)
    return flattened

def difference(list_a, list_b):
    return [item for item in list_a if item not in list_b]
