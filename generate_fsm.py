#!/bin/python3

import sys
import json
import queue
from pprint import pprint
import getopt

def generate_specific(config_filepath, controls, generate_debug):
    control_id = {}
    for i in range(len(controls)):
        control_id[controls[i]] = i

    order_matters = []
    sequences = {}
    config_name = ""
    sequence_timeout = 0
    # Command line arguments are controls.
    with open(config_filepath, "r") as config_file:
        configuration = json.load(config_file)
        config_file.close()
        order_matters = configuration["Rules"]["Order"]
        sequences = configuration["Rules"]["Sequences"]
        config_name = configuration["Name"]
        sequence_timeout = configuration["Rules"]["Sequences"]["Timeout"]

    # Sequences define a tree. Each leaf is a special movement.

    sequences_tree = {}

    for s in sequences["List"]:
        cursor_node = sequences_tree
        controls_sequence = s["Sequence"]
        for key in controls_sequence:
            if not key in controls:
                print("!!! The sequence control '%s' is not a declared control !!!" % key)
                sys.exit(-1)
            if not key in cursor_node:
                cursor_node[key] = {}
            elif "Name" in cursor_node[key]:
                print("!!! The sequence '%s' collides with sequence '%s'!!!" % (s["Name"], cursor_node[key]["Name"]))
                sys.exit(-1)
            cursor_node = cursor_node[key]
        # At the end, the cursor node will contain informations about special move.
        if cursor_node:
            print("!!! The sequence '%s' is a prefix of another one ! ABORT !!!" % s["Name"])
            sys.exit(-1)
        else:
            cursor_node["Name"] = s["Name"]
            cursor_node["Duration"] = s["Duration"]
            cursor_node["Cooldown"] = s["Cooldown"]


    print("## The sequence tree has been correctly defined has follow")
    pprint(sequences_tree)
    
    # THE important dictionary.
    states = {}
    ##########################

    # Start Node : "Idle"
    idle_state_controls = {}
    for c in controls:
        idle_state_controls[c] = False

    idle_state = {
            "Transitions" : [],                  # Transition to other state.
            "Pressed" : [],                      # Pressed key, ordered as stated in the computation rules.
            "Controls" : idle_state_controls,    # Controls status.
            "Sequence" : sequences_tree,          # Current sequence tree node.
            "Progress" : []                      # Current sequence progression.
    }

    states["Idle"] = idle_state

    # Until there's no state left to expand.

    state_seeds = queue.Queue()
    state_seeds.put("Idle")

    while not state_seeds.empty():
        current_state = state_seeds.get()
        print("-------------")
        print("Expand '%s' state" % current_state)

        ## Timeout management.
        ## It is actually pretty easy as we only have one timer.
        ## We just need to go to the state without any sequence.
        if len(states[current_state]["Progress"]) > 0:
            target_name = "_".join(states[current_state]["Pressed"])
            if target_name == "":
                target_name = "Idle"
            trigger = {
                    "Timeout" : "SequenceTimer",
                    "Target" : target_name
            }
            states[current_state]["Transitions"].append(trigger)
            if not target_name in states:
                states[target_name] = {
                        "Transitions" : [],
                        "Pressed" : states[current_state]["Pressed"],
                        "Controls" : states[current_state]["Controls"],
                        "Sequence" : sequences_tree,
                        "Progress" : []
                }
                state_seeds.put(target_name)

        ## Controls management.
        print("-? Controls order : %s" % states[current_state]["Pressed"])
        current_state_controls = states[current_state]["Controls"]
        # We can change only one control at a time
        for c in controls:
            trigger = {}
            trigger["Control"] = c
            new_controls = current_state_controls.copy()
            new_controls[c] = not current_state_controls[c]
            print("- Control %s=%s" % (c, new_controls[c]))
            control_order = states[current_state]["Pressed"].copy()
            if new_controls[c]:
                control_order.append(c)
            else:
                control_order.remove(c)
            trigger["Pressed"] = new_controls[c]

            # Sequence progression.
            new_progress = states[current_state]["Progress"].copy()
            new_sequence = states[current_state]["Sequence"]
            if new_controls[c]:
                if c in new_sequence:
                    if "Name" in new_sequence[c]:
                        # Combo activation
                        seq_finish = new_sequence[c]
                        trigger["Fire"] = seq_finish["Name"]
                        trigger["Cooldown"] = seq_finish["Cooldown"]
                        trigger["Duration"] = seq_finish["Duration"]
                        new_sequence = sequences_tree
                        new_progress = []
                    else:
                        trigger["Timer"] = "SequenceTimer"
                        new_sequence = new_sequence[c]
                        new_progress.append(c)
                else:
                    new_progress = []
                    new_sequence = sequences_tree


            # State name building
            # Use order to generate new state depending on the activation order.
            # Order will always be in prefix.
            # For count activated controls
            name_controls = []
            toinsert_controls = new_controls.copy()
            # First, ordered controls
            print("-- New controls : %s" % new_controls)
            for k in states[current_state]["Pressed"]:
                if k in order_matters and current_state_controls[k] and new_controls[k]:
                    print("-- Add %s" % k)
                    name_controls.append(k)
                    toinsert_controls.pop(k)
            for k in toinsert_controls:
                if new_controls[k]:
                    print("-+ Add %s" % k)
                    name_controls.append(k)
            tokens = name_controls.copy()
            new_name = "_".join(tokens)
            if new_name == "":
                new_name = "Idle"
            # Second, add sequence
            sequence_tag = "-".join(new_progress)
            if not sequence_tag == "":
                new_name = "%s#%s" % (new_name, sequence_tag)

            trigger["Target"] = new_name

            if not (new_name == "Idle" or new_name in states):
                states[new_name] = {
                        "Transitions" : [],
                        "Pressed" : name_controls,
                        "Controls" : new_controls,
                        "Sequence" : new_sequence,
                        "Progress" : new_progress
                }
                print("--+ Add '%s' state" % new_name)
                print("--+ With control order %s" % control_order)
                state_seeds.put(new_name)
            else:
                print("--! Existing state or start state '%s'" % new_name)

            found = False
            for i in states[current_state]["Transitions"]:
                found |= i["Target"] == new_name
            if not found:
                states[current_state]["Transitions"].append(trigger)

    print("--- End of Computation ---")

    print("There is %d states" % len(states))

    sequences_list = sequences["List"]
    sequences_id = {}
    pre_computed_sequences = []
    for i in range(len(sequences_list)):
        sequences_id[sequences_list[i]["Name"]] = i
        new_sequence = {}
        new_sequence["Cooldown"] = sequences_list[i]["Cooldown"]
        new_sequence["Duration"] = sequences_list[i]["Duration"]
        pre_computed_sequences.append(new_sequence)

    # Generate human readable description file.
    enhanced_transitions = []

    for name in states:
        new_state = {}
        new_state["Description"] = ""
        new_state["State"] = name
        new_state["Triggers"] = states[name]["Transitions"]
        enhanced_transitions.append(new_state)

    complete_content = { "Start" : "Idle", "SequenceTimeout" : sequence_timeout, "Transitions" : enhanced_transitions }

    file_content = json.dumps(complete_content, indent=4)

    save_target = "build/%s_fsm.json" % config_name
    with open(save_target, "w") as generated_file:
        generated_file.write(file_content)
        generated_file.close()
        print("Result stored in %s" % save_target)

    # Generate pre-computed description file.
    states_id = {}
    for i in range(len(enhanced_transitions)):
        states_id[enhanced_transitions[i]["State"]] = i

    pre_computed = {
            "Start" : states_id["Idle"],
            "ControlCount" : len(controls),
            "SequenceTimeout" : sequence_timeout
    }
    pre_computed["Sequences"] = pre_computed_sequences
    pre_computed_transitions = []
    for name in states:
        new_state = []
        # No need to identify the state as the ID = index in the array
        for t in states[name]["Transitions"]:
            new_transition = {}
            if "Control" in t:
                new_transition["Control"] = control_id[t["Control"]]
                new_transition["Pressed"] = t["Pressed"]
            new_transition["Target"] = states_id[t["Target"]]
            if "Timer" in t:
                new_transition["Timer"] = t["Timer"]
            if "Timeout" in t:
                new_transition["Timeout"] = t["Timeout"]
            if "Fire" in t:
                new_transition["Fire"] = sequences_id[t["Fire"]]
            new_state.append(new_transition)
        pre_computed_transitions.append(new_state)
    pre_computed["Transitions"] = pre_computed_transitions

    file_content = json.dumps(pre_computed, indent=4)

    save_target = "build/%s_fsm_pc.json" % config_name
    with open(save_target, "w") as generated_file:
        generated_file.write(file_content)
        generated_file.close()
        print("Precomputed result stored in %s" % save_target)

    with open("build/%sControls.gd" % config_name, "w") as specific_constants_singleton:
        specific_constants_singleton.write("# Constants for character '%s' controls\nextends Node\n\n" % config_name)
        sequences_list = sequences["List"]
        for s in range(len(sequences_list)):
            specific_constants_singleton.write("const SEQUENCE_%s_%s : int = %d\n" % (config_name.upper(), sequences_list[s]["Name"].upper(), s))

    if generate_debug:
        with open("build/%s_debug.dot" % config_name, "w") as debug_file:
            debug_file.write("digraph debug_fsm {\n")
            debug_file.write("\tedge [arrowhead=normal, fontsize=6];\n")
            debug_file.write("\tnode [shape=box, fontsize=8];\n")
            for s in enhanced_transitions:
                start_name = s["State"]
                for t in s["Triggers"]:
                    edge_description = "Timeout"
                    edge_color = "blue"
                    edge_fire = ""
                    if "Control" in t:
                        edge_description = t["Control"]
                        edge_color = "green" if t["Pressed"] else "red"
                        if "Fire" in t:
                            edge_fire = ", headlabel = \"%s\", style=\"bold\"" % t["Fire"]
                    debug_file.write("\t\"%s\" -> \"%s\" [taillabel = \"%s\", color=%s%s];\n" % (start_name, t["Target"], edge_description, edge_color, edge_fire))
            debug_file.write("}\n")
            debug_file.close()

def generate_main_constants(controls):
    with open("build/GlobalControls.gd", "w") as global_constants_singleton:
        global_constants_singleton.write("# Global constants for player controls identification\nextends Node\n\n")
        for c in range(len(controls)):
            global_constants_singleton.write("const PLAYER_CONTROL_%s : int = %d\n" % (controls[c], c))
        global_constants_singleton.write("const PLAYER_CONTROLS_DESCRIPTION : Array = [ ")
        description = ",".join(map(lambda s : "\"%s\"" % s.upper(), controls))
        global_constants_singleton.write(description)
        global_constants_singleton.write(" ]\n")
        global_constants_singleton.close()


## Main ##

def main():
    global_filepath = ""
    specific_filepaths = []
    generate_debug = False

    try:
        opts, args = getopt.getopt(sys.argv[1:],"dg:s:")
    except getopt.GetoptError:
        print("%s -d -g [path_to_global_conf.json] -s [path_to_first_specific.json] -s ..." % sys.argv[0])
        sys_exit(1)
    for opt, arg in opts:
        if opt == "-g":
            global_filepath = arg
        elif opt == "-s":
            specific_filepaths.append(arg)
        elif opt == "-d":
            generate_debug = True

    print("Global Filepath = '%s'" % global_filepath)
    print("Specific Filepaths = '%s'" % specific_filepaths)

    controls = []

    with open(global_filepath, "r") as config_file:
        configuration = json.load(config_file)
        config_file.close()
        controls = configuration["Controls"]
    
    generate_main_constants(controls)

    for filepath in specific_filepaths:
        print("Read '%s'" % filepath)
        generate_specific(filepath, controls, generate_debug)

if __name__ == "__main__":
    main()
