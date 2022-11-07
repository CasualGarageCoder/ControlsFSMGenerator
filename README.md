# Controls FSM Generator

Generates a JSON representing a Finite State Machine for player controls.

# How to use it

<code>$ ./generate.py <-d> -g [path_to_golbal_computation_rules] -l [path_to_specific_rules_1] ...</code>

The <code>-d</code> option activates the debug mode.

# Result

The result will be stored as follow:
- <code>build/debug/{name}_fsm.json</code> : Human readable graph for specific <code>name</code> configuration.
- <code>build/debug/{name}_debug.dot</code> : A dot file for graphviz representing the states and transition for configuration <code>name</code>.
- <code>build/debug/decision_tree_{name}.dot</code> : A dot file for graphviz representing the generated decision tree.
- <code>build/{name}_controller.gd</code> : A GDScript managing the evaluation of the several symbols and the decision tree.
- <code>build/{name}_fsm_pc.json</code> : Pre-computed graph with symbols replaced by their integer identifier counterpart.
- <code>build/global_controls.gd</code> : A Godot singleton containing the global constants related to the project.

The base script is named <code>control_fsm.gd</code> and is located at the project root.

# Roadmap

- Make a prototype using the tool.
- Make controls grouping so that you can make a sequence within a controls group without being interrupt by controls that are not part of it.
- For now, controls are "digital", meaning that they can only be pressed or released :
  - Consider analogic controls and add "quantity" to control input (pressed + value from deadzone to 1.0)
  - Create meta control : If an analogic control is above a certain threshold, it is considered as another control.

# Disclaimer

The current project is a work in progress, mainly oriented in generating GDScripts.
The main script refactoring is needed but it runs smoothly.
For now, all scripts are generated.

# Licensing

The whole project is under the Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) license.
