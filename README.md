# Controls FSM Generator

Generates a JSON representing a Finite State Machine for player controls.

# How to use it

<code>$ ./generate_fsm.py <-d> -g [path_to_golbal_computation_rules] -l [path_to_specific_rules_1] ...</code>

The <code>-d</code> option activates the debug mode.

# Result

The result will be stored as follow:
- <code>build/{name}_fsm.json</code> : Human readable graph for specific <code>name</code> configuration.
- <code>build/{name}_fsm_pc.json</code> : Pre-computed graph with symbols replaced by their integer identifier counterpart.
- <code>build/{name}_debug.dot</code> : A dot file for graphviz representing the states and transition for configuraton <code>name</code>.
- <code>build/{name}Contols.gd</code> : A Godot singleton containing symbols for the specific <code>name</code> configuration.
- <code>build/GlobalControls.gd</code> : A Godot singleton containing the global constants related to the project.

# Roadmap

- Make controls grouping so that you can make a sequence within a controls group without being interrupt by controls that are not part of it.
- For now, controls are "digital", meaning that they can only be pressed or released :
  - Consider analogic controls and add "quantity" to control input (pressed + value from deadzone to 1.0)
  - Create meta control : If an analogic control is above a certain threshold, it is considered as another control.
