#!/bin/python

import json
import sys

with open(sys.argv[1], "r") as source:
    state_machine = json.load(source)

    target_state = []
    defined_state = []
    transitions = state_machine["Transitions"]
    for transition in transitions:
        current_state = transition["State"]
        if current_state in defined_state:
            print("The state '%s' as already been defined ! " % current_state)
            sys.exit(-1)
        else:
            defined_state.append(current_state)
            triggers = transition["Triggers"]
            for trigger in triggers:
                target = trigger["Target"]
                if not target in target_state:
                    target_state.append(target)

    print("## Undefined States")
    for t in target_state:
        if not t in defined_state:
            print("- '%s'" % t)

    # Compute missing transitions

