#!/bin/python3

import sys
import json
import queue
import copy
from random import randint
from pprint import pprint
import getopt

type_to_class = { "bool" : bool, "Timer" : bool, "Control" : int }

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

# current_rules : Rules that left.
# attr : Attributes to inspect.
# return a map from attributes name to the attribute effectiveness score.
def compute_attributes_effectiveness(current_rules, attr):
    # For the sake of simplicity : number of rules = number of class (as in classification)
    # Warning ! It may not be the case in further developments.
    ae = dict((k, 0) for k in attr)
    for r in current_rules:
        for a in attr:
            if current_rules[r][a] == None:
                ae[a] += 1
    m = len(current_rules)
    for a in ae:
        ae[a] = (m - ae[a]) / float(m)
    sorted_ae = { k : v for k, v in sorted(ae.items(), key = lambda a : a[1], reverse = True) }
#    non_null_ae = { k : v for k, v in sorted_ae.items() if v > 0 }
    return sorted_ae

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

# current_rules : Rules that are still to evaluate.
# attr : Attributes that must be evaluated.
# return the score for each selected attributes.
def compute_attribute_autonomy(current_rules, attr):
    possible_attr_values = compute_attributes_values(current_rules, attr)
    rules_attribute_values = compute_rules_sorted_by_attribute_values(current_rules, possible_attr_values)

    for a in possible_attr_values:
        possible_attr_values[a] = set(possible_attr_values[a])

    ads_matrix = {}
    for value_rules in rules_attribute_values:
        # value_rules is an attribute name.
        ads_matrix[value_rules] = {}
        for values in rules_attribute_values[value_rules]:
            # values is an attribute value
            rules = rules_attribute_values[value_rules][values]
            # Rules is a set/list of rules.
            # Compute MaxADS for it, max value from the ADS_list, list of ADS for each attribute != value_rules
            ads_list = []
            for a in attr:
                if a == value_rules:
                    continue
                for first_rule in rules:
                    for second_rule in rules:
                        if first_rule == second_rule:
                            continue
                        # In our case, it is simple. Attribute values set card is 1. So ADS is either 0 or 3.
                        ads_list.append(0 if current_rules[first_rule][a] == current_rules[second_rule][a] else 3)
            ads_matrix[value_rules][values] = { "ads" : sum(ads_list), "list" : ads_list, "maxads" : (3 * len(rules) * (len(rules) - 1)) }

    aa = {}
    for a in attr:
        aa_for_attrib = 0
        for values in rules_attribute_values[a]: # Should work.
            rav = ads_matrix[a][values]
            found = False
            if rav["maxads"] == 0:
                found = True
                aa_for_attrib += 0 # yeah, it's dumb, but i stick to the algorithm.
            elif rav["maxads"] != 0:
                if len(attr) == 2:
                    for i in rav["list"]:
                        if i == rav["maxads"]:
                            found = True
                            break
                    if found:
                        aa_for_attrib += 1
            if not found: 
                aa_for_attrib = 1 + ( ((len(attr) - 1) * rav["maxads"]) - rav["ads"] )
        aa[a] = 0 if aa_for_attrib == 0 else (1.0 / float(aa_for_attrib))
    sorted_aa = { k : v for k, v in sorted(aa.items(), key = lambda a : a[1], reverse = True) }
    return sorted_aa

# current_rules : Rules that are still to evaluate.
# attr_to_compare : array with names of attributes for compare.
# return the name of the selected attribute.
def compute_minimum_value_distribution(current_rules, attr_to_compare):
    set_of_values = compute_attributes_values(current_rules, attr_to_compare)
    number_of_values = dict((k, len(v)) for (k, v) in set_of_values.items())
    # Find the attribute with the least values.
    sorted_set_of_values = { k : v for k, v in sorted(number_of_values.items(), key = lambda a : a[1]) }
    value = None
    selected_attributes = []
    for v in sorted_set_of_values:
        if value == None:
            value = sorted_set_of_values[v]
            selected_attributes.append(v)
        elif value != sorted_set_of_values[v]:
            break
        else:
            selected_attributes.append(v)
    if len(selected_attributes) > 1:
        print("??? Randomness induced in the distribution key due to concurrence between %s. You'd be advised to check your rules. ???" % selected_attributes)
    return selected_attributes[randint(0, len(selected_attributes) - 1)] # Yikes, I don't like random.

def retrieve_rules(current_rules, attributes_values):
    print("## Retrieve rules for attributes values %s" % attributes_values)
    result = {}
    for rule in current_rules:
        condition = current_rules[rule]
        compatible = True
        for a in attributes_values:
            attribute_name = a["Attribute"]
            attribute_value = a["Value"]
            stored_value = condition[attribute_name]
            if stored_value != attribute_value:
                compatible = False
                break
        if compatible:
            result[rule] = current_rules[rule]
    pprint(result)
    print("## --------------------------------")
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

def create_decision_tree(total_rules, symbols_value_occurrence, config_name, is_debug):
    print("## Symbols Value Occurrence")
    pprint(symbols_value_occurrence)
    # rules = dictionary of rules
    # attributes = all the attributes in the rules with name and types.
    branches = queue.Queue()
    current_branch = None
    decision_tree = {}
    # Decision_tree structure with be:
    # {
    #    "Attribute" : "name_of_attribute",
    #    "History" : [ { "Attribute" : "name_of_attribute", "Value" : "value" }, { "Attribute" : "name_of_other_attribute", "Value" : "another_value" }, ... ],
    #    "Values" : {
    #        "Val1" : { ... another branch ... },     <--- Empty at creation. Reference stored in branches
    #        "Val2" : { "Event" : "EventName" }
    #    }
    # }
    cursor = decision_tree

    current_rules = copy.deepcopy(total_rules)
    current_attributes = compute_attributes_from_rules(current_rules)

    event_treated = []

    while (not cursor == None):
        print("## Computed attributes are %s" % current_attributes)
        if len(current_rules) == 1:
            for s in current_rules:
                cursor["Event"] = s
                event_treated.append(s)
            print("## Only one rule : Leaf %s" % cursor["Event"])
        elif len(current_attributes) == 0:
            # no more attributes.
            print("## No more attributes")
            print("## History is %s" % cursor["History"])
            # Retrieve the event/rule/class. Normally, there should only be one.
            if len(current_rules) != 1:
                print("!!! Error while building decision tree : More or less than 1 final rule left !!!")
                pprint(current_rules)
                print("# --------------------------------")
                pprint(decision_tree)
                sys.exit(1)
            else:
                print("## Leaf : %s" % current_rules[0])
                cursor["Event"] = current_rules[0]
                event_treated.append(current_rules[0])
        else: # This is where the fun begins ...
            ae = compute_attributes_effectiveness(current_rules, current_attributes)
            # Determine if there's more than one attribute.
            candidates_attributes = compute_highest(ae)
            print("## Attribute Effectiveness is %s" % ae)
            print("## Candidates are %s" % candidates_attributes)
            selected_attribute = None
            singleton = True # Not a big fan of this, but let's trust the algorithm from the academic paper.
            if len(candidates_attributes) > 1:
                # Do all the stuff with AA and MVD
                print("## Attribute Effectiveness is equals for attributes %s" % candidates_attributes)
                print("## Let's compute Attribute Autonomy for each")
                aa = compute_attribute_autonomy(current_rules, candidates_attributes)
                print("## Attribute Autonomy is %s" % aa)
                # Compute the number of candidates.
                candidates_attributes = compute_highest(aa)
                print("## Candidate attributes %s" % candidates_attributes)
                if len(candidates_attributes) > 1:
                    print("## Compute Minimum Value Distribution")
                    selected_attribute = compute_minimum_value_distribution(current_rules, candidates_attributes)
                    print("## Selected attribute : %s" % selected_attribute)
                    # Create a node
                    cursor["Attribute"] = selected_attribute
                    cursor["Values"] = {}
                    cursor["Remaining"] = list(current_attributes.copy())
                    if not "History" in cursor:
                        cursor["History"] = []
                    singleton = False
                else:
                    selected_attribute = candidates_attributes[0]
                    print("## Selected attribute is '%s'" % selected_attribute)
            elif len(candidates_attributes) == 1:
                selected_attribute = candidates_attributes[0]
            else:
                # Should never happen !
                print("!!! Error while computing decision tree !!!")
                print("!!! Here is the result so far !!!")
                pprint(decision_tree)
                sys.exit(1)
            if singleton:
                print("## Time to deal with attribute %s" % selected_attribute)
                # So, 'cursor' point to where whe sould put the attribute. However, the cursor might not be empty.
                # History should be there to except at the begining.
                print("## Remove attribute %s" % selected_attribute)
                if not selected_attribute in current_attributes:
                    print("!!! Internal Error. '%s' is not part of existing attributes !!!" % selected_attribute)
                    pprint(decision_tree)
                    sys.exit(1)
                current_attributes.remove(selected_attribute)
                cursor["Attribute"] = selected_attribute
                cursor["Values"] = {}
                if not "History" in cursor:
                    cursor["History"] = []
            # So, cursor should be filled with "Attribute" and "History".
            # Now, we'll extends all of this using "possible" value of the attribute at this stage, replicate
            # the history and add the attribute=value pair
            for s in symbols_value_occurrence[selected_attribute]:
#                if s == None:
#                    continue
                new_history = cursor["History"].copy()
                new_history.append({ "Attribute" : selected_attribute, "Value" : s })
                new_node = { "History" : new_history, "Remaining" : list(current_attributes.copy()) }
                cursor["Values"][s] = new_node
                branches.put(new_node)
        if not branches.empty():
            current_rules = {}
            while(len(current_rules) == 0) and not branches.empty():
                cursor = branches.get()
                if cursor == None:
                    print("!!! Internal error : not null cursor should be stored in branches !!!")
                    pprint(decision_tree)
                    sys_exit()
                # We must select rules with the good history.
                current_rules = retrieve_rules(total_rules, cursor["History"])
                current_attributes = set(cursor["Remaining"])
                if len(current_rules) == 0:
                    print("## DEAD END - Prune this branch")
                    cursor["Prune"] = True
            if branches.empty():
                print("## NO MORE BRANCH")
                cursor = None
        else:
            cursor = None


    if is_debug:
        with open("build/decision_tree_%s.json" % config_name, "w") as out_json:
            file_content = json.dumps(decision_tree, indent=4)
            out_json.write(file_content)
            out_json.write("\n")
            out_json.close()
        ## Verify in all events have been treated
        not_in_tree = []
        for e in total_rules:
            if not e in event_treated:
                not_in_tree.append(e)
        if len(not_in_tree):
            print("!!! Event not treated : %s !!!" % not_in_tree)
        node = queue.Queue()
        node.put(decision_tree)
        while not node.empty():
            current = node.get()
            if "Event" in current:
                print("### Event %s : %s" % (current["Event"], current["History"]))
            if "Values" in current:
                for n in current["Values"]:
                    node.put(current["Values"][n])
            elif not "Prune" in current:
                pprint(current)

        with open("build/decision_tree_%s.dot" % config_name, "w") as out_dot:
            out_dot.write("digraph debug_fsm {\n")
            out_dot.write("\tedge [arrowhead=normal, fontsize=6];\n")
            out_dot.write("\tnode [shape=box, fontsize=8];\n")
            out_dot.write("}\n")
            out_dot.close()

    return decision_tree


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

    ## Everything is ok. Now, check if we can build a decision tree.
    ### Complete the rules and the number of possible values for each attributes.
    symbols_value_occurrence = dict((k["Name"], [ None ]) for k in symbols)
    for event in events:
        for s in symbols_types:
            if not s in events[event]:
                events[event][s] = None
            if not events[event][s] in symbols_value_occurrence[s]:
                symbols_value_occurrence[s].append(events[event][s])

    ## Change the Control type to 'int'.
    for event in events:
        for attr in events[event]:
            if symbols_types[attr] == "Control" and events[event][attr] != None:
                events[event][attr] = control_id[events[event][attr]]
    ## Do the same in symbols_value_occurrence
    for s in symbols_value_occurrence:
        if symbols_types[s] == "Control":
            new_values = []
            for v in symbols_value_occurrence[s]:
                if v == None:
                    new_values.append(None)
                else:
                    new_values.append(control_id[v])
            symbols_value_occurrence[s] = new_values
    new_symbols = {}
    for s in symbols_value_occurrence:
        if len(symbols_value_occurrence[s]) > 1:
            new_symbols[s] = symbols_value_occurrence[s]
    symbols_value_occurrence = new_symbols
    ## Remove symbols the doesn't appears in the list from the rules.
    for event in events:
        new_conditions = {}
        for c in events[event]:
            if c in symbols_value_occurrence:
                new_conditions[c] = events[event][c]
        events[event] = new_conditions

    ## Create the symbol->type mapping
    symbols_class = dict((k, type_to_class[v]) for (k, v) in symbols_types.items())

    decision_tree = create_decision_tree(events, symbols_value_occurrence, config_name, generate_debug)

    pprint(decision_tree)

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
