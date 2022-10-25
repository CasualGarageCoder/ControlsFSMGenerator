#!/bin/python3

import os
import sys
import json
import queue
import copy
from random import randint
from pprint import pprint
import getopt

type_to_class = { "bool" : bool, "Timer" : bool, "Control" : int }

def sort_counters_dict(dictionary):
    return { k : v for k, v in sorted(dictionary.items(), key = lambda a : a[1], reverse = True) }

# current_rules : Rules that are still to evaluate.
# attr : array with names of attribute to evaluate.
# return map from attribute name to number of possible values.
def compute_attributes_values(current_rules, attr):
    set_of_values = dict((k, []) for k in attr)
    for c in current_rules:
        for a in attr:
            if not current_rules[c][a] in set_of_values[a]:
                set_of_values[a].append(current_rules[c][a])
    return set_of_values

def compute_attributes_from_rules(current_rules):
    attributes = []
    for c in current_rules:
        for a in current_rules[c]:
            if current_rules[c][a] != None:
                attributes.append(a)
    return set(attributes)

# current_rules : Rules that are still to evaluate.
# possible_attr_values : map of attribute names to array of possible values
# return 
# {
#     "attribute1" : {
#     "value1" : [ "rule1, ..., rulek" ],
#     "valuen" : [ "rule2, ..., rulem" ]
#     },
#     "attribute2" : { ... }
# }
def compute_rules_sorted_by_attribute_values(current_rules, possible_attr_values):
    result = {}
    for attr in possible_attr_values:
        result[attr] = {}
        values = possible_attr_values[attr]
        for v in values:
            result[attr][v] = []
            for r in current_rules:
                rule = current_rules[r]
                if attr in rule and rule[attr] == v:
                    result[attr][v].append(r)
    return result

# Retrieve rules from attributes.
def retrieve_rules(current_rules, attributes_values):
    result = {}
    for rule in current_rules:
        condition = current_rules[rule]
        compatible = True
        for a in attributes_values:
            attribute_name = a["Attribute"]
            attribute_value = a["Value"]
            if not attribute_name in condition:
                compatible = False
                break
            stored_value = condition[attribute_name]
            if stored_value != attribute_value:
                compatible = False
                break
        if compatible:
            result[rule] = current_rules[rule]
    return result

# The input must be sorted.
def compute_highest(computed_values):
    candidates_attributes = []
    candidate_value = None
    for candidate in computed_values:
        if candidate_value == None:
            candidate_value = computed_values[candidate]
            candidates_attributes.append(candidate)
        elif candidate_value == computed_values[candidate]:
            candidates_attributes.append(candidate)
        else:
            break
    return candidates_attributes

def is_in_history(attr, history):
    for h in history:
        if h["Attribute"] == attr:
            return True
    return False

# Return the symbols and their values from the current ruleset.
def retrieve_symbols(current_rules, history):
    symbols = {}
    for c in current_rules:
        for a in current_rules[c]:
            if is_in_history(a, history):
                continue
            if not a in symbols:
                symbols[a] = []
                symbols[a].append(None)
            if not current_rules[c][a] in symbols[a]:
                symbols[a].append(current_rules[c][a])
    return symbols

######################## CREATE DECISION TREE ################################
def create_decision_tree(total_rules, config_name, is_debug):
    print("## Rule set")
    pprint(total_rules)
    # rules = dictionary of rules
    # attributes = all the attributes in the rules with name and types.
    branches = queue.Queue()
    current_branch = None
    decision_tree = { "History" : [] }
    # Decision_tree structure with be:
    # {
    #    "Attribute" : "name_of_attribute",
    #    "History" : [ { "Attribute" : "name_of_attribute", "Value" : "value" },
    #                  { "Attribute" : "name_of_other_attribute", "Value" : "another_value" }, ... 
    #                ],
    #    "Values" : {
    #        "Val1" : { ... another branch ... },     <--- Empty at creation. Reference stored in branches
    #        "Val2" : { "Event" : "EventName" }
    #    }
    # }

    branches.put(decision_tree)
    prune_count = 0
    while not branches.empty():
        cursor = branches.get()
        history = cursor["History"]
        current_rules = retrieve_rules(total_rules, history)
        current_symbols_occurrence = retrieve_symbols(current_rules, history)
        print("# New Iteration %s" % history)
        print("## Constrained rule set")
        pprint(current_rules)
        print("## Constrained symbol set")
        pprint(current_symbols_occurrence)

        search_attribute = True
        if len(current_rules) == 1: # Leaf
            # Not so fast ! What about the attributes ?
            # Count meaningful attributes.
            meaningful_attributes = False
            for s in current_symbols_occurrence:
                if current_symbols_occurrence[s] != None:
                    meaningful_attributes = True
                    break
            if not meaningful_attributes:
                cursor["Event"] = list(current_rules.keys())[0]
                print("## Leaf to '%s'" % cursor["Event"])
                search_attribute = False
        elif len(current_rules) == 0: # Leaf to prune.
            cursor["Prune"] = True
            print("## Leaf to prune")
            prune_count += 1
            search_attribute = False
        if search_attribute:
            # Elect the symbols with most occurences.
            symbol_count = {}
            for c in current_rules:
                for a in current_rules[c]:
                    if is_in_history(a, cursor["History"]):
                        continue
                    if not a in symbol_count:
                        symbol_count[a] = 1
                    else:
                        symbol_count[a] += 1
            sorted_symbol_count = sort_counters_dict(symbol_count)
            # Get the first one (arbitrary)
            choosen_attribute = list(sorted_symbol_count.keys())[0] # Should not be empty.
            # Hence, the cursor is attributed to the choosen_attribute.
            cursor["Attributes"] = choosen_attribute
            print("## Selected symbol : %s" % choosen_attribute)
            # Now, branch.
            cursor["Values"] = {}
            for v in current_symbols_occurrence[choosen_attribute]:
                new_history = copy.deepcopy(cursor["History"])
                new_history.append({ "Attribute" : choosen_attribute, "Value" : v })
                new_cursor = { "History" : new_history }
                cursor["Values"][v] = new_cursor
                print("### Add branch for attribute '%s' and value '%s'" % (choosen_attribute, v))
                branches.put(new_cursor)
    if prune_count > 0:
        print("!!! %d branches to prune !!!" % prune_count)
        # Let's do this.
        prune = queue.Queue()
        prune.put(decision_tree)
        while not prune.empty():
            cursor = prune.get()
            to_remove = []
            if "Event" in cursor:
                continue
            for v in cursor["Values"]:
                if "Prune" in cursor["Values"][v]:
                    to_remove.append(v)
                else:
                    prune.put(cursor["Values"][v])
            for v in to_remove:
                cursor["Values"].pop(v)
            if len(cursor["Values"]) == 0:
                cursor["Prune"] = True
                # We'll have to reinspect.
                prune.put(decision_tree) # Not optimal at all.

    if is_debug: # Generate the verbose debug JSON
        with open("build/decision_tree_%s.json" % config_name, "w") as out_json:
            file_content = json.dumps(decision_tree, indent=4)
            out_json.write(file_content)
            out_json.write("\n")
            out_json.close()

    # And now decision tree compression. All those "None" value can be transformed in 'or' statement
    # fallthrough.
    ## First, remove history.
    print("### Remove History")
    branches.put(decision_tree)
    while not branches.empty():
        cursor = branches.get()
        if "History" in cursor:
            cursor.pop("History")
        if "Values" in cursor:
            for v in cursor["Values"]:
                branches.put(cursor["Values"][v])
    ## Second, shorten None branching.
    print("### Remove 'None' thread")
    branches.put(decision_tree)
    while not branches.empty():
        cursor = branches.get()
        if "Values" in cursor:
            print("### %s (%d) (%s)" % (cursor["Values"].keys(), len(cursor["Values"]), None in cursor["Values"]))
        while "Values" in cursor and len(cursor["Values"]) == 1 and None in cursor["Values"]:
            print("!! Thread removal")
            # We can get rid of the intermediate.
            next_entry = cursor["Values"][None]
            print(next_entry)
            if "Event" in next_entry:
                cursor.clear()
                cursor["Event"] = next_entry["Event"]
            else:
                cursor["Attributes"] = next_entry["Attributes"]
                cursor["Values"] = next_entry["Values"]
        if "Values" in cursor:
            for v in cursor["Values"]:
                print("#### Insert node %s" % v)
                branches.put(cursor["Values"][v])

    if is_debug: # Generate the dot.
        with open("build/decision_tree_%s.dot" % config_name, "w") as out_dot:
            out_dot.close()
    return decision_tree

######################## CREATE DECISION TREE ################################

def generate_specific(config_filepath, controls, common_symbols, generate_debug):
    control_id = {}
    for i in range(len(controls)):
        control_id[controls[i]] = i

        order_matters = []
        sequences = {}
        config_name = ""
        sequence_timeout = 0
        local_symbols = []
        events = {}
        # Command line arguments are controls.
        with open(config_filepath, "r") as config_file:
            configuration = json.load(config_file)
            config_file.close()
            order_matters = configuration["Rules"]["Order"]
            sequences = configuration["Rules"]["Sequences"]
            config_name = configuration["Name"]
            sequence_timeout = configuration["Rules"]["Sequences"]["Timeout"]
            local_symbols = configuration["Rules"]["Symbols"]
            events = configuration["Rules"]["Events"]

        # Determine events condition tree

        # Check that local symbols don't overshadow common symbols.
        for i in local_symbols:
            symbol_name = i["Name"]
        for j in common_symbols:
            if symbol_name == j["Name"]:
                print("!!! The symbol '%s' is declared both globally and locally !!!" % symbol_name)
                sys.exit(1)
    # Merge the symbols.
    symbols = common_symbols.copy()
    symbols += local_symbols
    symbols_types = {}
    for s in symbols:
        symbol_name = s["Name"]
        symbol_type = s["Type"]
        symbols_types[symbol_name] = symbol_type

    # Using the events, build the decision tree.
    ## First, verify that the symbols of the conditions exist.
    for event in events:
        event_conditions = events[event]
        for condition_symbol in event_conditions:
            # Existence check
            if not condition_symbol in symbols_types:
                print("!!! In event '%s', condition symbol '%s' is not defined !!!" % (event, condition_symbol))
                sys.exit(1)
            # Type check
            type_to_check = type(event_conditions[condition_symbol])
            declared_type = symbols_types[condition_symbol]
            if (((declared_type == "bool" or declared_type == "Timer") and (not type_to_check is bool)) or 
                    (declared_type == "Control" and (not (type_to_check is str and event_conditions[condition_symbol] in controls)))):
                print("!!! In event '%s', condition symbol '%s' type mismatch !!!" % (event, condition_symbol))
                sys.exit(1)

    ## Change the Control type to 'int'.
    for event in events:
        for attr in events[event]:
            if symbols_types[attr] == "Control" and events[event][attr] != None:
                events[event][attr] = control_id[events[event][attr]]
    ## Complete rules with "None".
    for event in events:
        for attr in symbols_types:
            if not attr in events[event]:
                events[event][attr] = None

    ## Create the symbol->type mapping
    symbols_class = dict((k, type_to_class[v]) for (k, v) in symbols_types.items())

    decision_tree = create_decision_tree(events, config_name, generate_debug)

    print("## Generated Decision Tree")
    pprint(decision_tree)
    # Find missing events.
    actual_events = list(events.keys())
    parkour = queue.Queue()
    parkour.put(decision_tree)
    while not parkour.empty():
        cursor = parkour.get()
        if "Event" in cursor:
            actual_events.remove(cursor["Event"])
        if "Values" in cursor:
            for v in cursor["Values"]:
                parkour.put(cursor["Values"][v])
    if len(actual_events) > 0:
        print("!!! Missing events in decision tree : %s !!!" % actual_events)
        sys.exit(1)
    else:
        print("## Decision tree manage all the events.")

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
        new_state.append({ "Name" : name })
        # No need to identify the state as the ID = index in the array
        for t in states[name]["Transitions"]:
            if "Description" in t:
                continue
            new_transition = {}
            if "Control" in t:
                new_transition["Control"] = control_id[t["Control"]]
                new_transition["Pressed"] = t["Pressed"]
            new_transition["Target"] = states_id[t["Target"]]
            new_transition["State"] = t["Target"]
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
            specific_constants_singleton.write("const SEQUENCE_%s_%s_DURATION_TIMER : int = %d\n" % (config_name.upper(), sequences_list[s]["Name"].upper(), (s * 2)))
            specific_constants_singleton.write("const SEQUENCE_%s_%s_COOLDOWN_TIMER : int = %d\n" % (config_name.upper(), sequences_list[s]["Name"].upper(), ((s * 2) + 1)))
        specific_constants_singleton.write("const SEQUENCE_%s_SEQUENCE_TIMER : int = %d\n" % (config_name.upper(), len(sequences_list) * 2))

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

def generate_main_constants(controls, common_symbols):
    with open("build/GlobalControls.gd", "w") as global_constants_singleton:
        global_constants_singleton.write("# Global constants for player controls identification\nextends Node\n\n")
        for c in range(len(controls)):
            global_constants_singleton.write("const PLAYER_CONTROL_%s : int = %d\n" % (controls[c], c))
        global_constants_singleton.write("const PLAYER_CONTROLS_DESCRIPTION : Array = [ ")
        description = ",".join(map(lambda s : "\"%s\"" % s.upper(), controls))
        global_constants_singleton.write(description)
        global_constants_singleton.write(" ]\n")
        global_constants_singleton.close()
        # TODO Integrate common symbols.


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
            try:
                os.mkdir("build")
            except OSError as error:
                pass
            generate_debug = True

    print("Global Filepath = '%s'" % global_filepath)
    print("Specific Filepaths = '%s'" % specific_filepaths)

    controls = []
    common_symbols = []

    with open(global_filepath, "r") as config_file:
        configuration = json.load(config_file)
        config_file.close()
        controls = configuration["Controls"]
        common_symbols = configuration["Symbols"]

    generate_main_constants(controls, common_symbols)

    for filepath in specific_filepaths:
        print("Read '%s'" % filepath)
        generate_specific(filepath, controls, common_symbols, generate_debug)

if __name__ == "__main__":
    main()
