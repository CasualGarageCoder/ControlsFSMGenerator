[1mdiff --git a/control_fsm.gd b/control_fsm.gd[m
[1mindex f1c59d4..7e87587 100644[m
[1m--- a/control_fsm.gd[m
[1m+++ b/control_fsm.gd[m
[36m@@ -76,8 +76,12 @@[m [monready var dampened : bool = false[m
 # If true, the action is freezed.[m
 onready var freezed : bool = false[m
 [m
[32m+[m[32m# Event start date (in ms).[m
 onready var start_date : int = -1[m
 [m
[32m+[m[32m# Sequence active.[m
[32m+[m[32monready var sequence_active : bool = true # TODO Turn this to false and implement beacons.[m
[32m+[m
 ## Initialisation. Read the JSON, collect and compute useful data.[m
 func _ready():[m
 	set_process(false)[m
[36m@@ -198,7 +202,7 @@[m [mfunc set_move(control : int, pressed : bool) -> void:[m
 			timer_expire[timer] = current_time + timer_timeout[timer][m
 		var seq_id : int = states[current_state].fire[filtered_control][m
 		var override_sequence : bool = true[m
[31m-		if pressed and seq_id >= 0 and (not dampened) and start_date < 0:[m
[32m+[m		[32mif pressed and seq_id >= 0 and (not dampened) and start_date < 0 and sequence_active:[m
 			timer_expire[sequence.size() * 2] = -1[m
 			if timer_expire[(seq_id * 2) + 1] < 0: # If the timer is a cooldown, we don't activate special move.[m
 				if sequence[seq_id].duration > 0:[m
[36m@@ -206,6 +210,7 @@[m [mfunc set_move(control : int, pressed : bool) -> void:[m
 				timer_expire[(seq_id * 2) + 1] = current_time + sequence[seq_id].cooldown[m
 				freezed = true[m
 				override_sequence = activate_sequence(seq_id, sequence[seq_id].duration, sequence[seq_id].cooldown)[m
[32m+[m				[32memit_signal("sequence_readiness", seq_id, 1.0)[m
 				# Other cooldown inference[m
 				for i in sequence[seq_id].infer:[m
 					var id : int = int((i * 2) + 1)[m
[36m@@ -218,7 +223,7 @@[m [mfunc set_move(control : int, pressed : bool) -> void:[m
 		if pressed:[m
 			freezed = states[current_state].freeze[filtered_control][m
 		if (override_sequence or (not in_sequence)) and (not freezed):[m
[31m-			invoke_decision_tree()[m
[32m+[m[32m#			invoke_decision_tree()[m
 			process_move(filtered_control, pressed)[m
 			emit_signal("process_event", filtered_control, pressed)[m
 		# Switch to next state.[m
[1mdiff --git a/generate.py b/generate.py[m
[1mindex f0c6430..0cef71b 100755[m
[1m--- a/generate.py[m
[1m+++ b/generate.py[m
[36m@@ -1182,9 +1182,10 @@[m [mdef generate_specific(config_filepath, controls, common_symbols, common_signals,[m
                     specific_script.write("\treturn false\n\n")[m
                 else:[m
                     specific_script.write("\treturn 0\n\n")[m
[31m-                if symbols_types[s["Name"]] != "Timer":[m
[31m-                    specific_script.write("func set_%s(var arg : %s) -> void:\n" % (s["Name"], symbols_class[s["Name"]].__name__))[m
[31m-                    specific_script.write("\tif arg != %s_v:\n\t\t%s_v = arg\n\t\tinvoke_decision_tree()\n\n" % (s["Name"], s["Name"]))[m
[32m+[m
[32m+[m[32m            if symbols_types[s["Name"]] != "Timer":[m
[32m+[m[32m                specific_script.write("func set_%s(var arg : %s) -> void:\n" % (s["Name"], symbols_class[s["Name"]].__name__))[m
[32m+[m[32m                specific_script.write("\tif arg != %s_v:\n\t\t%s_v = arg\n\t\tinvoke_decision_tree()\n\n" % (s["Name"], s["Name"]))[m
         specific_script.close()[m
 [m
 [m
