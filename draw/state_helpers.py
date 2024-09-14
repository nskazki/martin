from collections import deque
from list_helpers import wrap_list, flatten_list
from random_helpers import low_chance, fair_chance

CAN = "can"
LOW = "low"
FAIR = "fair"
DEFAULT = "default"

def next_state(states, current_state, target_states):
    if target_states:
        path = bfs_path(states, current_state, target_states)
        if len(path) >= 2:
            return path[1]
        else:
            print(f"Couldn't find a path from {current_state} to {target_states}")

    rules = read_rules(states, current_state)

    for state in wrap_list(rules.get(LOW)):
        if low_chance():
            return state

    for state in wrap_list(rules.get(FAIR)):
        if fair_chance():
            return state

    return rules.get(DEFAULT, current_state)

def bfs_path(states, current_state, target_states):
    queue = deque([(current_state, [current_state])])
    visited = set()
    while queue:
        (state, path) = queue.popleft()

        if state in target_states and len(path) != 1:
            return path

        if state not in visited:
            visited.add(state)
            for neighbor in flatten_list(read_rules(states, state).values()):
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

    return []

def read_rules(states, state):
    result = states[state]
    if isinstance(result, str):
        return read_rules(states, result)
    else:
        return result
