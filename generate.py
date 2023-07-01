#!/bin/python3

import os
import sys
import json
import queue
import copy
from random import randint
from pprint import pprint
import getopt

verbose_mode = False

type_to_class = { "bool" : bool, "Timer" : bool, "Control" : int }

def log_verbose(message):
    if verbose_mode:
        print(message)

def sort_counters_dict(dictionary):
    return { k : v for k, v in sorted(dictionary.items(), key = lambda a : a[1], reverse = True) }

def find_symbol(t, symb):
    for s in symb:
        if t == s["Name"]:
            return True
    return False

def evaluate_symbols(prefix, symbols, temp_name, specific_script, symbols_class, symbols_types, print_invoke = True, evaluate_prefix = ""):
    for s in symbols:
        if symbols_types[s] == "Timer":
            specific_script.write("%sinvoke = invoke || %sevaluate_%s()\n" % (prefix, evaluate_prefix, s))
        else:
            specific_script.write("%svar %s_%s : %s = %sevaluate_%s()\n" % (prefix, temp_name, s, symbols_class[s].__name__, evaluate_prefix, s))
            specific_script.write("%sinvoke = invoke || (%s_v != %s_%s)\n" % (prefix, s, temp_name, s))
            specific_script.write("%s%s_v = %s_%s\n" % (prefix, s, temp_name, s))
    if print_invoke:
        specific_script.write("%sif invoke:\n%s\t%sinvoke_decision_tree()\n\n" % (prefix, prefix, evaluate_prefix))

def trigger_signals(indent, signals, common_signals, control_id, file_d):
    for s in signals:
        signal_arguments = signals[s]
        # Retrieve arguments.
        arguments_declaration = list(common_signals[s].keys())
        arguments_list = [ "\"%s\"" % (s) ]
        for a in arguments_declaration:
            raw_value = signal_arguments[a]
            raw_type = common_signals[s][a]
            if raw_type == "*":
                arguments_list.append("%s()" % (raw_value))
            elif raw_type == "Control":
                arguments_list.append("%d" % (control_id[raw_value]))
            elif raw_type == "bool":
                arguments_list.append("true" if raw_value else "false")
            elif raw_type == "$":
                arguments_list.append("%s" % raw_value)
            else:
                arguments_list.append("\"%s\"" % raw_value)
        write_indent(file_d, indent, "emit_signal(%s)" % (", ".join(arguments_list)))

def trigger_timers(out_gd, level, triggers, prefix = ""):
    for t in triggers:
        trigger_name = "%s" % t.upper()
        if prefix == "":
            if "reset" == triggers[t]:
                write_indent(out_gd, level, "trigger_timer(TIMERS_IDENTIFIER[\"%s\"], true)" % (trigger_name))
            else:
                write_indent(out_gd, level, "trigger_timer(TIMERS_IDENTIFIER[\"%s\"])" % (trigger_name))
        else:
            if "reset" == triggers[t]:
                write_indent(out_gd, level, "%strigger_timer(\"%s\", true)" % (prefix, trigger_name))
            else:
                write_indent(out_gd, level, "%strigger_timer(\"%s\")" % (prefix, trigger_name))

# current_rules : Rules that are still to evaluate.
# attr : array with names of attribute to evaluate.
# return map from attribute name to number of possible values.
def compute_attributes_values(current_rules, attr):
    set_of_values = dict((k, []) for k in attr)
    for c in current_rules:
        for a in attr:
            if not current_rules[c]["Conditions"][a] in set_of_values[a]:
                set_of_values[a].append(current_rules[c]["Conditions"][a])
    return set_of_values

def compute_attributes_from_rules(current_rules):
    attributes = []
    for c in current_rules:
        for a in current_rules[c]["Conditions"]:
            if current_rules[c]["Conditions"][a] != None:
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
                if attr in rule["Conditions"] and rule["Conditions"][attr] == v:
                    result[attr][v].append(r)
    return result

# Retrieve rules from attributes.
def retrieve_rules(current_rules, attributes_values):
    result = {}
    for rule in current_rules:
        condition = current_rules[rule]["Conditions"]
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
        for a in current_rules[c]["Conditions"]:
            if is_in_history(a, history):
                continue
            if not a in symbols:
                symbols[a] = []
                symbols[a].append(None)
            if not current_rules[c]["Conditions"][a] in symbols[a]:
                symbols[a].append(current_rules[c]["Conditions"][a])
    return symbols

# Write in a file with identation.
def write_indent(fl, indent, text):
    for i in range(indent):
        fl.write("\t")
    fl.write(text)
    fl.write("\n")

# Transform stack to a more readable form
def produce_readable_stack(stack):
    result = []
    for s in stack:
        node = s["Node"]
        statement_id = s["Statement"]
        value_id = s["Value"]
        description = None
        if statement_id == len(node):
            description = "To Discard"
        else:
            statement = node[statement_id]
            if "Event" in statement:
                description = "Event = %s" % statement["Event"]
            else:
                if value_id >= len(statement["Values"]):
                    description = "To Discard"
                else:
                    value = list(statement["Values"].keys())[value_id]
                    description = "%s = %s" % (statement["Attributes"], value)
        final_description = "%s (s=%d, v=%d)" % (description, statement_id, value_id)
        result.append(final_description)
    return result

######################## CREATE DECISION TREE ################################
def create_decision_tree(total_rules, symbols_types, symbols_declared_types, config_name, common_signals, control_id, is_debug, output_directory):
    if verbose_mode:
        print("## Symbols Types")
        pprint(symbols_types)
        print("## Rule set")
        pprint(total_rules)
    # rules = dictionary of rules
    # attributes = all the attributes in the rules with name and types.
    branches = queue.Queue()
    current_branch = None
    decision_tree = { "History" : [] }
    # Decision_tree structure will be:
    # {
    #    "Attributes" : "name_of_attribute",
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
    event_count = 0
    while not branches.empty():
        cursor = branches.get()
        history = cursor["History"]
        current_rules = retrieve_rules(total_rules, history)
        current_symbols_occurrence = retrieve_symbols(current_rules, history)
        if verbose_mode:
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
            name = None
            for s in current_symbols_occurrence:
                if len(current_symbols_occurrence[s]) > 1:
                    meaningful_attributes = True
                    name = s
                    break
            if not meaningful_attributes:
                cursor["Event"] = list(current_rules.keys())[0]
                log_verbose("## Leaf to '%s'" % cursor["Event"])
                event_count += 1
                search_attribute = False
            else:
                log_verbose("## Still meaningful attribute '%s'. No leaf." % name)
        elif len(current_rules) == 0: # Leaf to prune.
            cursor["Prune"] = True
            log_verbose("## Leaf to prune")
            prune_count += 1
            search_attribute = False
        if search_attribute:
            # Elect the symbols with most occurences.
            symbol_count = {}
            for c in current_rules:
                for a in current_rules[c]["Conditions"]:
                    if is_in_history(a, cursor["History"]) or current_rules[c]["Conditions"][a] == None:
                        continue
                    if not a in symbol_count:
                        symbol_count[a] = 1
                    else:
                        symbol_count[a] += 1
            if len(symbol_count) == 0:
                cursor["Prune"] = True
                prune_count += 1
                continue
            sorted_symbol_count = sort_counters_dict(symbol_count)
            candidates = compute_highest(sorted_symbol_count)
            if len(candidates) > 1:
                # Let's determine, for candidates, the number of different values.
                value_per_candidate = {}
                for candidate in candidates:
                    value_per_candidate[candidate] = set()
                for c in current_rules:
                    for a in current_rules[c]["Conditions"]:
                        if a in candidates and current_rules[c]["Conditions"][a] != None:
                            value_per_candidate[a].add(current_rules[c]["Conditions"][a])
                if verbose_mode:
                    pprint(value_per_candidate)
                card_per_candidate = dict({ (k, len(v)) for (k, v) in value_per_candidate.items() })
                sorted_card = sort_counters_dict(card_per_candidate)
                if verbose_mode:
                    print("## Cardinality per candidate")
                    print(sorted_card)
                choosen_attribute = list(sorted_card.keys())[len(sorted_card) - 1] # Should not be empty.
            else:
                # Get the first (and only) one
                choosen_attribute = list(sorted_symbol_count.keys())[0] # Should not be empty.
            # Hence, the cursor is attributed to the choosen_attribute.
            cursor["Attributes"] = choosen_attribute
            log_verbose("## Selected symbol : %s" % choosen_attribute)
            # Now, branch.
            cursor["Values"] = {}
            for v in current_symbols_occurrence[choosen_attribute]:
                new_history = copy.deepcopy(cursor["History"])
                new_history.append({ "Attribute" : choosen_attribute, "Value" : v })
                new_cursor = { "History" : new_history }
                cursor["Values"][v] = new_cursor
                log_verbose("### Add branch for attribute '%s' and value '%s'" % (choosen_attribute, v))
                branches.put(new_cursor)
    if event_count == 0:
        if verbose_mode:
            print("!!! Internal Error : No event matched !!!")
            pprint(decision_tree)
        sys.exit(1)
    if prune_count > 0:
        log_verbose("!!! %d branches to prune !!!" % prune_count)
        # Let's do this.
        if verbose_mode:
            pprint(decision_tree)
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
        with open("%s/debug/decision_tree_%s.json" % (output_directory, config_name), "w") as out_json:
            file_content = json.dumps(decision_tree, indent=4)
            out_json.write(file_content)
            out_json.write("\n")
            out_json.close()

    # And now decision tree compression. All those "None" value can be transformed in 'or' statement
    # fallthrough.
    ## First, remove history.
    log_verbose("### Remove History")
    branches.put(decision_tree)
    while not branches.empty():
        cursor = branches.get()
        if "History" in cursor:
            cursor.pop("History")
        if "Values" in cursor:
            for v in cursor["Values"]:
                branches.put(cursor["Values"][v])
    ## Second, shorten None branching.
    log_verbose("### Remove 'None' thread")
    branches.put(decision_tree)
    while not branches.empty():
        cursor = branches.get()
        if "Values" in cursor:
            log_verbose("### %s (%d) (%s)" % (cursor["Values"].keys(), len(cursor["Values"]), None in cursor["Values"]))
        while "Values" in cursor and len(cursor["Values"]) == 1 and None in cursor["Values"]:
            log_verbose("!! Thread removal")
            # We can get rid of the intermediate.
            next_entry = cursor["Values"][None]
            log_verbose(next_entry)
            if "Event" in next_entry:
                cursor.clear()
                cursor["Event"] = next_entry["Event"]
            else:
                cursor["Attributes"] = next_entry["Attributes"]
                cursor["Values"] = next_entry["Values"]
        if "Values" in cursor:
            for v in cursor["Values"]:
                log_verbose("#### Insert node %s" % v)
                branches.put(cursor["Values"][v])

    if is_debug: # Generate the dot.
        with open("%s/debug/decision_tree_%s.dot" % (output_directory, config_name), "w") as out_dot:
            # The decision tree has been cleared.
            node_id = 0
            out_dot.write("digraph G {\n")
            # First pass : Node attribution
            branches.put(decision_tree)
            while not branches.empty():
                cursor = branches.get()
                if "Attributes" in cursor:
                    out_dot.write("\tnode_%d [ label = \"%s\", shape = diamond ]\n" % (node_id, cursor["Attributes"]))
                    cursor["Node"] = "node_%d" % node_id
                    for v in cursor["Values"]:
                        branches.put(cursor["Values"][v])
                if "Event" in cursor:
                    out_dot.write("\tnode_%d [ label = \"%s\", shape = box ]\n" % (node_id, cursor["Event"]))
                    cursor["Node"] = "node_%d" % node_id
                node_id += 1
            # Second pass : Edge building
            branches.put(decision_tree)
            while not branches.empty():
                cursor = branches.get()
                if "Attributes" in cursor:
                    for v in cursor["Values"]:
                        out_dot.write("%s -> %s [ label = \"%s\"]\n" % (cursor["Node"], cursor["Values"][v]["Node"], v))
                        branches.put(cursor["Values"][v])
            out_dot.write("}\n")
            out_dot.close()

    # Transform the decision tree to flatten the statements.
    # Decision_tree structure will be transformed as follow:
    # [
    #   {
    #    "Attributes" : "name_of_attribute",
    #    "Values" : {
    #        "Val1" : [ { ... another branch ... }, { ... concurrent branch ... } ],
    #        "Val2" : [ { "Event" : "EventName" } ]
    #    }
    #  },
    #  { "Attributes" : "other" ... }
    # ]
    flat_tree = []
    decision_tree["Flat"] = flat_tree
    branches.put(decision_tree)
    while not branches.empty():
        cursor = branches.get()
        # New node from the old decision tree structure.
        ## First, replicate it.
        if "Event" in cursor:
            new_decision = { "Event" : cursor["Event"] }
            cursor["Flat"].append(new_decision)
        elif "Attributes" in cursor:
            new_decision = { "Attributes" : cursor["Attributes"], "Values" : {} }
            # Time to sort values in case of booleans. True first, then false.
            for v in cursor["Values"]:
                if v == None:
                    none_cursor = cursor["Values"][None]
                    branches.put(none_cursor)
                    none_cursor["Flat"] = cursor["Flat"]
                    continue
                new_decision["Values"][v] = []
                cursor["Values"][v]["Flat"] = new_decision["Values"][v]
                branches.put(cursor["Values"][v])
            if symbols_types[cursor["Attributes"]] == bool and len(new_decision["Values"]) == 2:
                if verbose_mode:
                    print("## Sorting boolean values.")
                    print("## %s" % new_decision["Values"].keys())
                falseValue = new_decision["Values"][False]
                new_decision["Values"].pop(False)
                new_decision["Values"][False] = falseValue
            cursor["Flat"].append(new_decision)
        else:
            print("!!! Internal error. Such a node should not exists !!!")
    if verbose_mode:
        print("## Flat Tree :")
        pprint(flat_tree)

    with open("%s/decision_tree_%s.gd" % (output_directory, config_name), "w") as out_gd:
        ## Try to generate code
        ## Inside the stack, we'll position a decision tree node and a counter.
        stack = []
        stack.append({ "Node" : flat_tree, "Statement" : 0, "Value" : 0 })
        specific_identifier = config_name.upper()
        while len(stack) > 0:
            if verbose_mode:
                print("## --------------------------")
                print(produce_readable_stack(stack))
                print("### -------------------------")
            cursor = stack.pop()
            node = cursor["Node"]
            statement_id = cursor["Statement"]
            value = cursor["Value"]
            if statement_id == len(node):
                if len(stack) == 0:
                    log_verbose("## Break because end of main statement list")
                    break
                log_verbose("## Discard because of end of statements reached")
                cursor = stack.pop()
                cursor["Value"] += 1
                stack.append(cursor)
                continue
            statement = node[statement_id]
            if "Event" in statement:
                event_name = statement["Event"]
                # Apply effects in any.
                if "Effects" in total_rules[event_name]:
                    effects = total_rules[event_name]["Effects"]
                    # Launch signal if any.
                    if "Signals" in effects and len(effects["Signals"]) > 0:
                        trigger_signals(len(stack), effects["Signals"], common_signals, control_id, out_gd)
                    # Launch timers if any.
                    if "Timers" in effects and len(effects["Timers"]) > 0:
                        timer_triggers = effects["Timers"]
                        if "Self" in timer_triggers:
                            self_triggers = timer_triggers["Self"]
                            trigger_timers(out_gd, len(stack), self_triggers)
                        if "Distribute" in timer_triggers:
                            distribute_triggers = timer_triggers["Distribute"]
                            for grp in distribute_triggers:
                                group_name = grp.lower()
                                write_indent(out_gd, len(stack), "for i in get_tree().get_nodes_in_group(\"%s\"):" % grp)
                                write_indent(out_gd, len(stack) + 1, "if i == controlled_node_%s:" % group_name)
                                write_indent(out_gd, len(stack) + 2, "continue")
                                trigger_timers(out_gd, len(stack) + 1, distribute_triggers[grp], "i.")
                    if "Self" in effects and len(effects["Self"]) > 0:
                        symbols_to_evaluate = effects["Self"]
                        write_indent(out_gd, len(stack), "var invoke : bool = false")
                        evaluate_symbols("\t"*len(stack), symbols_to_evaluate, "new", out_gd, symbols_types, symbols_declared_types)
                    if "Distribute" in effects:
                        for target in effects["Distribute"]:
                            symbols_to_evaluate = effects["Distribute"][target]
                            write_indent(out_gd, len(stack), "for i in get_tree().get_nodes_in_group(\"%s\"):" % target)
                            write_indent(out_gd, len(stack) + 1, "if i == controlled_node_%s:" % (target.lower()))
                            write_indent(out_gd, len(stack) + 2, "continue")
                            write_indent(out_gd, len(stack) + 1, "invoke = false")
                            evaluate_symbols("\t" * (len(stack)+1), symbols_to_evaluate, "new_dist", out_gd, symbols_types, symbols_declared_types, True, "i.")

                # Trigger event.
                identifier = "EVENT_%s" % event_name.upper()
                write_indent(out_gd, len(stack), "trigger(%s)" % identifier)
                cursor = stack.pop()
                cursor["Value"] += 1
                stack.append(cursor)
                # It should be the only statement in the node. Rewind.
            elif "Attributes" in statement:
                if value == len(statement["Values"]):
                    cursor["Value"] = 0
                    cursor["Statement"] += 1
                    stack.append(cursor)
                    log_verbose("### Discard because of end of values reached")
                    continue
                if value == 0:
                    # So, we begin with a new attributes.
                    if symbols_declared_types[statement["Attributes"]] == "bool": # Boolean
                        negate = "!" if list(statement["Values"].keys())[0] == False else ""
                        write_indent(out_gd, len(stack), "if %s%s_v:" % (negate, statement["Attributes"]))
                    elif symbols_declared_types[statement["Attributes"]] == "Timer":
                        negate = "!" if list(statement["Values"].keys())[0] == False else ""
                        write_indent(out_gd, len(stack), "if %s%s():" % (negate, statement["Attributes"]))
                    else:
                        value_name = list(statement["Values"].keys())[value]
                        write_indent(out_gd, len(stack), "if %s_v == %s:" % (statement["Attributes"], value_name))
                else:
                    if symbols_types[statement["Attributes"]] == bool: # Boolean
                        write_indent(out_gd, len(stack), "else:")
                    else:
                        value_name = list(statement["Values"].keys())[value]
                        # It can't be anything else that a control.
                        write_indent(out_gd, len(stack), "elif %s_v == %s:" % (statement["Attributes"], value_name))
                # We reinject the cursor as-is. It will be modified when going up.
                stack.append(cursor)
                # Don't forget to append the next statement/value
                next_statement = { "Node" : statement["Values"][list(statement["Values"].keys())[value]], "Statement" : 0, "Value" : 0 }
                stack.append(next_statement)

        out_gd.close()

    return decision_tree

######################## END OF CREATE DECISION TREE ############################

def generate_specific(config_filepath, controls, common_symbols, common_signals, common_groups, common_defaults, common_variables, generate_debug, output_directory):
    control_id = {}
    for i in range(len(controls)):
        control_id[controls[i]] = i+1

        order_matters = []
        sequences = {}
        config_name = ""
        sequence_timeout = 0
        local_symbols = []
        events = {}
        control_triggered_symbols = {}
        process_triggered_symbols = []
        can_move_conditions = {}
        default_evaluations = common_defaults.copy()
        local_variables = common_variables.copy()
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
            process_triggered_symbols = configuration["Rules"]["Frame"]
            control_triggered_symbols = configuration["Rules"]["Trigger"]
            can_move_conditions = configuration["Rules"]["Controlable"]
            if "Defaults" in configuration:
                default_evaluations.update(configuration["Defaults"])
            if "Variables" in configuration:
                local_variables.update(configuration["Variables"])

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
        event_conditions = events[event]["Conditions"]
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
                print("!!! In event '%s', condition symbol '%s' type mismatch !!! (should be %s but is %s)" % (event, condition_symbol, declared_type, type_to_check))
                sys.exit(1)

    ## TODO Verify "Effects" validity too.

    ## Change the Control type to 'int'.
    for event in events:
        for attr in events[event]["Conditions"]:
            if symbols_types[attr] == "Control" and events[event]["Conditions"][attr] != None:
                events[event]["Conditions"][attr] = control_id[events[event]["Conditions"][attr]]
    ## Complete rules with "None".
    for event in events:
        for attr in symbols_types:
            if not attr in events[event]["Conditions"]:
                events[event]["Conditions"][attr] = None

    ## Create the symbol->type mapping
    symbols_class = dict((k, type_to_class[v]) for (k, v) in symbols_types.items())

    ## Finite State Machine

    # Sequences define a tree. Each leaf is a special movement.
    sequences_tree = {}

    for s in sequences["List"]:
        cursor_node = sequences_tree
        controls_sequence = s["Sequence"]
        if "Freeze" in s:
            freeze = s["Freeze"]
        else:
            freeze = False
        for key in controls_sequence:
            if not key in controls:
                print("!!! The sequence control '%s' is not a declared control !!!" % key)
                sys.exit(-1)
            if not key in cursor_node:
                cursor_node[key] = { "Freeze" : freeze }
            elif "Name" in cursor_node[key]:
                print("!!! The sequence '%s' collides with sequence '%s'!!!" % (s["Name"], cursor_node[key]["Name"]))
                sys.exit(-1)
            cursor_node = cursor_node[key]
        # At the end, the cursor node will contain informations about special move.
        if len(cursor_node) > 1 : # The node will always have one node.
            print("!!! The sequence '%s' is a prefix of another one ! ABORT !!! (%s)" % (s["Name"], cursor_node))
            sys.exit(-1)
        else:
            cursor_node["Name"] = s["Name"]
            cursor_node["Duration"] = s["Duration"]
            cursor_node["Cooldown"] = s["Cooldown"]

    if verbose_mode:
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
            "Sequence" : sequences_tree,         # Current sequence tree node.
            "Progress" : [],                     # Current sequence progression.
            "Freeze" : False                     # Freeze
            }

    states["Idle"] = idle_state

    # Until there's no state left to expand.

    state_seeds = queue.Queue()
    state_seeds.put("Idle")

    while not state_seeds.empty():
        current_state = state_seeds.get()
        if verbose_mode:
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
                        "Progress" : [],
                        "Freeze" : False
                        }
                state_seeds.put(target_name)

        ## Controls management.
        log_verbose("-? Controls order : %s" % states[current_state]["Pressed"])
        current_state_controls = states[current_state]["Controls"]
        # We can change only one control at a time
        for c in controls:
            trigger = {}
            trigger["Control"] = c
            new_controls = current_state_controls.copy()
            new_controls[c] = not current_state_controls[c]
            log_verbose("- Control %s=%s" % (c, new_controls[c]))
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
                        if "Infer" in seq_finish:
                            trigger["Infer"] = seq_finish["Infer"]
                        new_sequence = sequences_tree
                        new_progress = []
                        trigger["Freeze"] = True
                    else:
                        trigger["Timer"] = "SequenceTimer"
                        new_sequence = new_sequence[c]
                        new_progress.append(c)
                        trigger["Freeze"] = new_sequence["Freeze"]
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
            log_verbose("-- New controls : %s" % new_controls)
            for k in states[current_state]["Pressed"]:
                if k in order_matters and current_state_controls[k] and new_controls[k]:
                    log_verbose("-- Add %s" % k)
                    name_controls.append(k)
                    toinsert_controls.pop(k)
            for k in toinsert_controls:
                if new_controls[k]:
                    log_verbose("-+ Add %s" % k)
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
                        "Progress" : new_progress,
                        }
                log_verbose("--+ Add '%s' state" % new_name)
                log_verbose("--+ With control order %s" % control_order)
                state_seeds.put(new_name)
            else:
                log_verbose("--! Existing state or start state '%s'" % new_name)

            found = False
            for i in states[current_state]["Transitions"]:
                found |= i["Target"] == new_name
            if not found:
                states[current_state]["Transitions"].append(trigger)

    if verbose_mode:
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

    for i in range(len(sequences_list)):
        if "Infer" in sequences_list[i]:
            # Compute new inference sequence id.
            infer_id = list(map(lambda inf : sequences_id[inf], sequences_list[i]["Infer"]))
            pre_computed_sequences[i]["Infer"] = infer_id
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

    if generate_debug:
        save_target = "%s/debug/%s_fsm.json" % (output_directory, config_name)
        with open(save_target, "w") as generated_file:
            generated_file.write(file_content)
            generated_file.close()
            print("Debug Result stored in %s" % save_target)

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
            if "Freeze" in t:
                new_transition["Freeze"] = t["Freeze"]
            new_state.append(new_transition)
        pre_computed_transitions.append(new_state)
    pre_computed["Transitions"] = pre_computed_transitions

    file_content = json.dumps(pre_computed, indent=4)

    save_target = "%s/%s_fsm_pc.json" % (output_directory, config_name.lower())
    with open(save_target, "w") as generated_file:
        generated_file.write(file_content)
        generated_file.close()
        print("Precomputed result stored in %s" % save_target)

    with open("%s/%s_controller.gd" % (output_directory, config_name.lower()), "w") as specific_constants:
        name_tokens = config_name.split('_')
        specific_script_class_name = ''.join(e.title() for e in name_tokens)
        specific_constants.write("class_name %sCharacterController\n" % specific_script_class_name)
        specific_constants.write("extends BaseCharacterController\n\n")
        timers_identifier = {}
        sequences_list = sequences["List"]
        for s in range(len(sequences_list)):
            useq_name = sequences_list[s]["Name"].upper()
            specific_constants.write("const SEQUENCE_%s : int = %d\n" % (useq_name, s))
            specific_constants.write("const SEQUENCE_%s_DURATION_TIMER : int = %d\n" % (useq_name, (s * 2)))
            timers_identifier["SEQUENCE_%s_DURATION" % (useq_name)] = s * 2
            specific_constants.write("const SEQUENCE_%s_COOLDOWN_TIMER : int = %d\n" % (useq_name, ((s * 2) + 1)))
            timers_identifier["SEQUENCE_%s_COOLDOWN" % (useq_name)] = (s * 2) + 1
        specific_constants.write("const SEQUENCE_TIMER : int = %d\n" % (len(sequences_list) * 2))
        timers_identifier["SEQUENCE"] = len(sequences_list) * 2
        count = len(sequences_list) * 2 + 1
        ## Add timer symbols
        for s in symbols:
            if s["Type"] == "Timer":
                specific_constants.write("const %s_TIMER : int = %d\n" % (s["Name"].upper(), count))
                timers_identifier[s["Name"].upper()] = count
                count += 1
        ## And timer name to identifier dictionary
        specific_constants.write("const TIMERS_IDENTIFIER : Dictionary = %s\n" % (timers_identifier))
        # Add events
        count = 0
        event_descriptor = []
        for e in events:
            event_name = e.upper()
            identifier = "EVENT_%s" % event_name
            event_descriptor.append(e)
            specific_constants.write("const %s : int = %d\n" % (identifier, count))
            count += 1
        specific_constants.write("const EVENT_DESCRIPTOR : Array = %s" % (event_descriptor))


    if generate_debug:
        with open("%s/debug/%s_debug.dot" % (output_directory, config_name), "w") as debug_file:
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

    # And finally, generate decision tree to generate the specific script.
    # We got all we need. The symbols, the triggers, the timers.
    decision_tree = create_decision_tree(events, symbols_class, symbols_types, config_name, common_signals, control_id, generate_debug, output_directory)
    print("## Generated Decision Tree")

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

    # And now, we are ready to generate the specific script, the last thing we'll do here.
    script_path = "%s/%s_controller.gd" % (output_directory, config_name.lower())
    print("## Print specific controller script in : %s" % script_path)
    uconf_name = config_name.upper()
    with open(script_path, "a") as specific_script:
        specific_script.write("\n\n")
        # All signals
        for s in common_signals:
            attributes = ", ".join(list(common_signals[s].keys()))
            specific_script.write("signal %s(%s)\n" % (s, attributes))
        specific_script.write("\n")
        # All exported nodepath
        for g in common_groups:
            specific_script.write("export (NodePath) var controlled_nodepath_%s : NodePath\n" % (g.lower()))
        specific_script.write("\n")
        for g in common_groups:
            specific_script.write("onready var controlled_node_%s\n" % (g.lower()))
        specific_script.write("\n")
        # All local variables
        specific_script.write("# Local Variables\n")
        for s in local_variables:
            if "onready" in local_variables[s] and local_variables[s]["onready"]:
                specific_script.write("onready ");
            specific_script.write("var %s" % (s))
            if "type" in local_variables[s]:
                specific_script.write(" : %s" % (local_variables[s]["type"]))
            if "value" in local_variables[s]:
                specific_script.write(" = %s" % (local_variables[s]["value"]))
            specific_script.write("\n")
        specific_script.write("\n")
        # All symbols
        specific_script.write("# Decision tree symbols\n")
        for s in symbols:
            if not s["Type"] == "Timer":
                # Compute default value.
                default_value = None
                if s["Type"] == "Control":
                    default_value = control_id[s["Default"]]
                else:
                    default_value = s["Default"]
                specific_script.write("var %s_v : %s = %s\n" % (s["Name"], symbols_class[s["Name"]].__name__, default_value))
        specific_script.write("\nfunc _ready():\n")
        # Add controlled nodes
        for g in common_groups:
            group_name = g.lower()
            specific_script.write("\tif controlled_nodepath_%s != null:\n" % (group_name))
            specific_script.write("\t\tcontrolled_node_%s = get_node(controlled_nodepath_%s)\n" % (group_name, group_name))
            specific_script.write("\telse:\n\t\tcontrolled_node_%s = null\n" % (group_name))
        specific_script.write("\n")
        # Add local timers
        for s in symbols:
            if s["Type"] == "Timer":
                timer_name = "%s_TIMER" % s["Name"].upper()
                specific_script.write("\ttimer_expire[%s] = -1\n\ttimer_timeout[%s] = %d\n" % (timer_name, timer_name, s["Default"]))
        specific_script.write("\n")
        # Symbol accessors
        for s in symbols:
            if s["Type"] == "Timer":
                specific_script.write("func %s() -> bool:\n" % s["Name"])
                specific_script.write("\tvar identifier : int = TIMERS_IDENTIFIER[\"%s\"]\n" % (s["Name"].upper()))
                specific_script.write("\tif identifier >= timer_expire.size():\n\t\treturn false\n")
                specific_script.write("\treturn timer_expire[identifier] > 0 && current_time < timer_expire[identifier]\n\n")
            else:
                specific_script.write("func %s() -> %s:\n\treturn %s_v\n\n" % (s["Name"], symbols_class[s["Name"]].__name__, s["Name"]))
        # Decision tree !
        specific_script.write("func invoke_decision_tree() -> void:\n")
        decision_tree_path = "%s/decision_tree_%s.gd" % (output_directory, config_name)
        with open(decision_tree_path, "r") as generated_dt:
            lines = generated_dt.readlines()
            for line in lines:
                specific_script.write("\t%s" % line)
            generated_dt.close()
        os.remove(decision_tree_path)
        # Delegate process : Manage per-frame trigger
        specific_script.write("\nfunc delegate_process() -> void:\n\tvar invoke : bool = false\n")
        evaluate_symbols("\t", process_triggered_symbols, "new", specific_script, symbols_class, symbols_types)
        # Delegate process : Manage on control trigger.
        specific_script.write("func process_move(control : int, pressed : bool) -> void:\n\tvar invoke : bool = false\n")
        # Disable move control using conditions in Rules/Controlable.
        for t in control_triggered_symbols["Controls"]:
            specific_script.write("\tif control == GlobalControls.PLAYER_CONTROL_%s:\n" % t.upper())
            press_list = control_triggered_symbols["Controls"][t]["onPress"] if "onPress" in control_triggered_symbols["Controls"][t] else []
            if len(press_list) > 0:
                specific_script.write("\t\tif pressed:\n")
                evaluate_symbols("\t\t\t", press_list, "temp", specific_script, symbols_class, symbols_types, False)
            unpressed_list = control_triggered_symbols["Controls"][t]["onRelease"] if "onRelease" in control_triggered_symbols["Controls"][t] else []
            if len(unpressed_list) > 0:
                if len(press_list) > 0:
                    specific_script.write("\t\telse:\n")
                else:
                    specific_script.write("\t\tif not pressed:\n")
                evaluate_symbols("\t\t\t", unpressed_list, "temp", specific_script, symbols_class, symbols_types, False)
        specific_script.write("\n\n\tif invoke:\n\t\tinvoke_decision_tree()\n\n")
        # Triggering on sequence activation
        specific_script.write("func activate_sequence(sequence_id : int, duration : int, cooldown : int) -> bool:\n")
        specific_script.write("\tvar invoke : bool = false\n")
        first_seq = True
        for seq in sequences["List"]:
            if "Self" in seq or "Distribute" in seq or "Timers" in seq or "Signals" in seq:
                sequence_name = "SEQUENCE_%s" % seq["Name"].upper()
                if first_seq:
                    specific_script.write("\tif sequence_id == %s:\n" % sequence_name)
                    first_seq = False
                else:
                    specific_script.write("\telif sequence_id == %s:\n" % sequence_name)
            if "Timers" in seq:
                if "Self" in seq["Timers"]:
                    trigger_timers(specific_script, 2, seq["Timers"]["Self"])
                if "Distribute" in seq["Timers"]:
                    distribute_triggers = seq["Timers"]["Distribute"]
                    for grp in distribute_triggers:
                        group_name = grp.lower()
                        write_indent(specific_script, 2, "for i in get_tree().get_nodes_in_group(\"%s\"):" % grp)
                        write_indent(specific_script, 3, "if i == controlled_node_%s:" % group_name)
                        write_indent(specific_script, 4, "continue")
                        trigger_timers(specific_script, 3, distribute_triggers[grp], "i.")
                specific_script.write("\n")
            if "Signals" in seq and len(seq["Signals"]) > 0:
                trigger_signals(2, seq["Signals"], common_signals, control_id, specific_script)
                specific_script.write("\n")
            if "Self" in seq:
                symbols_to_evaluate = seq["Self"]
                specific_script.write("\t\tinvoke = false\n")
                evaluate_symbols("\t\t", symbols_to_evaluate, "new", specific_script, symbols_class, symbols_types)
            if "Distribute" in seq:
                for target in seq["Distribute"]:
                    symbols_to_evaluate = seq["Distribute"][target]
                    specific_script.write("\t\tfor i in get_tree().get_nodes_in_group(\"%s\"):\n" % target)
                    specific_script.write("\t\t\tif i == controlled_node_%s:\n\t\t\t\tcontinue\n\t\t\tinvoke = false\n" % (target.lower()))
                    evaluate_symbols("\t\t\t", symbols_to_evaluate, "new_dist", specific_script, symbols_class, symbols_types, True, "i.")
        specific_script.write("\treturn delegate_sequence_activation(sequence_id, duration, cooldown)\n\n")
        # Override "reset" function to set the symbols/variable in their "default" values.
        specific_script.write("func reset() -> void:\n")
        for s in symbols:
            if not s["Type"] == "Timer":
                # Compute default value.
                default_value = None
                if s["Type"] == "Control":
                    default_value = control_id[s["Default"]]
                else:
                    default_value = s["Default"]
                specific_script.write("\t%s_v = %s\n" % (s["Name"], default_value))
        specific_script.write("\t.reset()\n\n")
        # Print debug function. Print values of all symbols and state of all timers.
        specific_script.write("func print_symbols() -> void:\n")
        for s in symbols:
            if s["Type"] == "Timer":
                timer_name = "TIMERS_IDENTIFIER[\"%s\"]" % s["Name"].upper()
                specific_script.write("\tprint(\"Timer : %s is %%s\" %% (\"active\" if timer_expire[%s] > 0 else \"inactive\"))\n" % (s["Name"].upper(), timer_name))
            elif s["Type"] == "Control":
                specific_script.write("\tprint(\"%s = %%s\" %% (GlobalControls.PLAYER_CONTROLS_DESCRIPTION[%s_v - 1] if %s_v > 0 else \"None\"))\n" % (s["Name"], s["Name"], s["Name"]))
            else:
                specific_script.write("\tprint(\"%s = %%s\" %% (%s_v))\n" % (s["Name"], s["Name"]))
        specific_script.write("\n")
        # Compute 'can_move' based on "Rules/Controlable".
        specific_script.write("func can_move() -> bool:\n")
        if len(can_move_conditions) == 0:
            specific_script.write("\treturn true\n\n")
        else:
            # TODO Convert the value using the type and replacing the possible literals.
            condition_tokens = [ "%s() == %s" % (k, str(v).lower()) for (k, v) in can_move_conditions.items() ]
            condition_string = " && ".join(condition_tokens)
            specific_script.write("\treturn %s\n\n" % condition_string)
        # Timer expiration
        specific_script.write("func on_timer_expire(timer : int) -> void:\n\tvar invoke : bool = false\n")
        if "Timers" in control_triggered_symbols:
            timer_expirations = control_triggered_symbols["Timers"]
            for timer in timer_expirations:
                evaluation_group = timer_expirations[timer]
                specific_script.write("\tif timer == TIMERS_IDENTIFIER[\"%s\"]:\n" % timer.upper())
                if len(evaluation_group) == 0:
                    specific_script.write("\t\tinvoke = true\n\n")
                else:
                    evaluate_symbols("\t\t", evaluation_group, "temp", specific_script, symbols_class, symbols_types, False)
            specific_script.write("\n\tif invoke:\n\t\tinvoke_decision_tree()\n\n")
        specific_script.write("\ton_timer_delegate(timer)\n\n")
        # Finish with filled-by-user functions.
        specific_script.write("func on_timer_delegate(timer : int) -> void:\n\tpass\n\n")
        specific_script.write("func delegate_sequence_activation(sequence_id : int, duration : int, cooldown : int) -> bool:\n")
        specific_script.write("\treturn false\n\n")
        specific_script.write("func trigger(event : int) -> void:\n\tpass\n\n")
        # All the evaluation and setting functions.
        for s in symbols:
            specific_script.write("func evaluate_%s() -> %s:\n" % (s["Name"], symbols_class[s["Name"]].__name__))
            if s["Name"] in default_evaluations:
                specific_script.write(default_evaluations[s["Name"]])
                specific_script.write("\n\n")
            else:
                if symbols_class[s["Name"]] == bool:
                    specific_script.write("\treturn false\n\n")
                else:
                    specific_script.write("\treturn 0\n\n")

            if symbols_types[s["Name"]] != "Timer":
                specific_script.write("func set_%s(var arg : %s) -> void:\n" % (s["Name"], symbols_class[s["Name"]].__name__))
                specific_script.write("\tif arg != %s_v:\n\t\t%s_v = arg\n\t\tinvoke_decision_tree()\n\n" % (s["Name"], s["Name"]))
        specific_script.close()


def generate_main_constants(controls, common_symbols, output_directory):
    with open("%s/global_controls.gd" % output_directory, "w") as global_constants_singleton:
        global_constants_singleton.write("# Global constants for player controls identification\nextends Node\n\n")
        for c in range(len(controls)):
            global_constants_singleton.write("const PLAYER_CONTROL_%s : int = %d\n" % (controls[c].upper(), c+1))
        global_constants_singleton.write("const PLAYER_CONTROLS_DESCRIPTION : Array = [ ")
        description = ",".join(map(lambda s : "\"%s\"" % s.upper(), controls))
        global_constants_singleton.write(description)
        global_constants_singleton.write(" ]\n")
        global_constants_singleton.close()


## Main ##

def main():
    global verbose_mode
    global_filepath = ""
    specific_filepaths = []
    generate_debug = False
    output_directory = "build"

    try:
        opts, args = getopt.getopt(sys.argv[1:],"vdg:s:P:o:")
    except getopt.GetoptError:
        print("%s -d -g [path_to_global_conf.json] -s [path_to_first_specific.json] -s ... -P [path_to_project_directory] -o [output_directory]" % sys.argv[0])
        sys_exit(1)
    for opt, arg in opts:
        if opt == "-g":
            global_filepath = arg
        elif opt == "-s":
            specific_filepaths.append(arg)
        elif opt == "-P":
            specific_filepaths = [os.path.join(arg, fl) for fl in filter(lambda x : x.endswith(".json"), os.listdir(arg))]
        elif opt == "-v":
            print("## Activate Verbose Mode")
            verbose_mode = True
        elif opt == "-o":
            output_directory = arg
        elif opt == "-d":
            generate_debug = True

    try:
        os.mkdir(output_directory)
    except OSError as error:
        if error.errno != 17:
            print("!!! Can't create build folder !!!")
            print(error)
            sys.exit(1)

    if generate_debug:
        try:
            os.mkdir("%s/debug" % (output_directory))
        except OSError as error:
            if error.errno != 17:
                print("!!! Can't create debug folder !!!")
                print(error)
                sys.exit(1)


    if global_filepath in specific_filepaths:
        specific_filepaths.remove(global_filepath)
    print("Global Filepath = '%s'" % global_filepath)
    print("Specific Filepaths = '%s'" % specific_filepaths)
    print("Output directory : %s" % output_directory)

    controls = []
    common_symbols = []
    common_signals = {}
    common_groups = []
    common_defaults = {}
    common_variables = {}

    with open(global_filepath, "r") as config_file:
        configuration = json.load(config_file)
        config_file.close()
        controls = configuration["Controls"]
        common_symbols = configuration["Symbols"]
        common_signals = configuration["Signals"]
        common_groups = configuration["Groups"]
        if "Variables" in configuration:
            common_variables = configuration["Variables"]
        if "Defaults" in configuration:
            common_defaults = configuration["Defaults"]

    generate_main_constants(controls, common_symbols, output_directory)

    for filepath in specific_filepaths:
        print("Read '%s'" % filepath)
        generate_specific(filepath, controls, common_symbols, common_signals, common_groups, common_defaults, common_variables, generate_debug, output_directory)

if __name__ == "__main__":
    main()
